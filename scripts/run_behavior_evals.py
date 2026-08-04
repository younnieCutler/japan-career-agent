#!/usr/bin/env python3
"""Run the repository's registered, replayable behavior-evaluation scenarios.

The repository deliberately keeps static contract checks and executable behavior checks separate.
This runner is the bridge for the latter: YAML declares scenario identity and assertions, while
Python owns the finite adapter registry. A scenario can never smuggle an arbitrary command into CI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _shared import behavior_replay  # noqa: E402


SCHEMA_VERSION = 1
RUNNER_VERSION = "1"
ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]+$")
RISK_CLASSES = frozenset({"critical", "high", "medium", "low"})
EXECUTION_MODES = frozenset({"contract_audit", "behavior_replay", "runtime_e2e", "live_canary"})
CLASSIFICATIONS = frozenset(
    {
        "contract_audit_pass",
        "contract_audit_fail",
        "behavior_replay_pass",
        "behavior_replay_fail",
        "runtime_e2e_pass",
        "runtime_e2e_fail",
        "not_executable",
    }
)
ASSERTION_TYPES = frozenset(
    {
        "exit_code",
        "stdout_contains",
        "stdout_not_contains",
        "stderr_contains",
        "stderr_not_contains",
        "stdout_json_path_equals",
    }
)


class BehaviorEvalError(ValueError):
    """Raised when the behavior-evaluation contract is malformed or unsafe."""


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    skill: str
    adapter: str
    execution_mode: str
    classification: str
    risk_class: str
    inputs: tuple[Path, ...]
    assertions: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Execution:
    status: str
    returncode: int | None
    stdout: str
    stderr: str
    duration_ms: int
    failure_class: str | None = None


@dataclass(frozen=True)
class AdapterContext:
    root: Path
    scenario: Scenario


Adapter = Callable[[AdapterContext], Execution]


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BehaviorEvalError(f"{label} must be a mapping")
    return value


def _require_keys(value: Mapping[str, Any], required: set[str], optional: set[str], label: str) -> None:
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - optional)
    if missing:
        raise BehaviorEvalError(f"{label} is missing required keys: {', '.join(missing)}")
    if unknown:
        raise BehaviorEvalError(f"{label} contains unsupported keys: {', '.join(unknown)}")


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BehaviorEvalError(f"{label} must be a non-empty string")
    return value


def _confined_input(raw: Any, label: str) -> Path:
    value = _require_string(raw, label)
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise BehaviorEvalError(f"{label} must be repository-relative: {value!r}")
    if ".." in posix.parts or ".." in windows.parts:
        raise BehaviorEvalError(f"{label} cannot escape the repository: {value!r}")

    candidate = (ROOT / Path(value)).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise BehaviorEvalError(f"{label} must stay under the repository: {value!r}") from exc
    if not candidate.is_file():
        raise BehaviorEvalError(f"{label} does not name an existing file: {value!r}")
    return candidate


def _validate_assertion(value: Any, label: str) -> dict[str, Any]:
    mapping = _require_mapping(value, label)
    _require_keys(mapping, {"id", "type"}, {"expected", "value", "path"}, label)
    _require_string(mapping["id"], f"{label}.id")
    assertion_type = _require_string(mapping["type"], f"{label}.type")
    if assertion_type not in ASSERTION_TYPES:
        raise BehaviorEvalError(f"{label}.type is not registered: {assertion_type!r}")
    if assertion_type == "exit_code":
        expected = mapping.get("expected")
        if isinstance(expected, bool) or not isinstance(expected, int):
            raise BehaviorEvalError(f"{label}.expected must be an integer for exit_code")
    elif assertion_type == "stdout_json_path_equals":
        if not isinstance(mapping.get("path"), str) or not mapping["path"].strip():
            raise BehaviorEvalError(f"{label}.path is required for stdout_json_path_equals")
        if "expected" not in mapping:
            raise BehaviorEvalError(f"{label}.expected is required for stdout_json_path_equals")
    elif not isinstance(mapping.get("value"), str):
        raise BehaviorEvalError(f"{label}.value must be a string for {assertion_type}")
    return dict(mapping)


def load_scenarios(schema_path: Path) -> tuple[Scenario, ...]:
    try:
        document = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise BehaviorEvalError(f"could not read behavior schema {schema_path}: {exc}") from exc

    root = _require_mapping(document, "schema")
    _require_keys(root, {"schema_version", "contract", "scenarios"}, {"description"}, "schema")
    if root["schema_version"] != SCHEMA_VERSION or isinstance(root["schema_version"], bool):
        raise BehaviorEvalError(f"schema_version must be integer {SCHEMA_VERSION}")

    contract = _require_mapping(root["contract"], "schema.contract")
    _require_keys(
        contract,
        {"execution_modes", "classifications", "risk_classes", "assertion_types"},
        set(),
        "schema.contract",
    )
    for key, allowed in (
        ("execution_modes", EXECUTION_MODES),
        ("classifications", CLASSIFICATIONS),
        ("risk_classes", RISK_CLASSES),
        ("assertion_types", ASSERTION_TYPES),
    ):
        values = contract[key]
        if not isinstance(values, list) or set(values) != set(allowed):
            raise BehaviorEvalError(f"schema.contract.{key} must enumerate the registered values")

    raw_scenarios = root["scenarios"]
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise BehaviorEvalError("schema.scenarios must be a non-empty list")

    scenarios: list[Scenario] = []
    seen: set[str] = set()
    for index, raw_scenario in enumerate(raw_scenarios):
        label = f"schema.scenarios[{index}]"
        mapping = _require_mapping(raw_scenario, label)
        _require_keys(
            mapping,
            {"id", "skill", "adapter", "execution_mode", "classification", "risk_class", "assertions"},
            {"inputs"},
            label,
        )
        scenario_id = _require_string(mapping["id"], f"{label}.id")
        if not ID_PATTERN.fullmatch(scenario_id):
            raise BehaviorEvalError(f"{label}.id must use stable uppercase identifier syntax")
        if scenario_id in seen:
            raise BehaviorEvalError(f"duplicate scenario id: {scenario_id}")
        seen.add(scenario_id)

        skill = _require_string(mapping["skill"], f"{label}.skill")
        adapter = _require_string(mapping["adapter"], f"{label}.adapter")
        if adapter not in ADAPTERS:
            raise BehaviorEvalError(f"{label}.adapter is not registered: {adapter!r}")
        execution_mode = _require_string(mapping["execution_mode"], f"{label}.execution_mode")
        classification = _require_string(mapping["classification"], f"{label}.classification")
        risk_class = _require_string(mapping["risk_class"], f"{label}.risk_class")
        if execution_mode not in EXECUTION_MODES:
            raise BehaviorEvalError(f"{label}.execution_mode is not registered: {execution_mode!r}")
        if classification not in CLASSIFICATIONS:
            raise BehaviorEvalError(f"{label}.classification is not registered: {classification!r}")
        if risk_class not in RISK_CLASSES:
            raise BehaviorEvalError(f"{label}.risk_class is not registered: {risk_class!r}")

        raw_inputs = mapping.get("inputs", [])
        if not isinstance(raw_inputs, list):
            raise BehaviorEvalError(f"{label}.inputs must be a list")
        inputs = tuple(
            _confined_input(raw, f"{label}.inputs[{input_index}]")
            for input_index, raw in enumerate(raw_inputs)
        )

        raw_assertions = mapping["assertions"]
        if not isinstance(raw_assertions, list) or not raw_assertions:
            raise BehaviorEvalError(f"{label}.assertions must be a non-empty list")
        assertions = tuple(
            _validate_assertion(raw, f"{label}.assertions[{assertion_index}]")
            for assertion_index, raw in enumerate(raw_assertions)
        )
        scenarios.append(
            Scenario(
                scenario_id=scenario_id,
                skill=skill,
                adapter=adapter,
                execution_mode=execution_mode,
                classification=classification,
                risk_class=risk_class,
                inputs=inputs,
                assertions=assertions,
            )
        )
    return tuple(scenarios)


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _duration_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def _run_registered_script(relative_script: str) -> Execution:
    script = ROOT / relative_script
    if not script.is_file():
        return Execution("NOT_EXECUTABLE", None, "", "", 0, "registered_script_missing")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            capture_output=True,
            check=False,
            timeout=120,
        )
    except FileNotFoundError:
        return Execution("NOT_EXECUTABLE", None, "", "", _duration_ms(started), "python_unavailable")
    except subprocess.TimeoutExpired as exc:
        return Execution(
            "FAIL",
            None,
            _decode(exc.stdout or b"") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            _decode(exc.stderr or b"") if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
            _duration_ms(started),
            "timeout",
        )
    except OSError:
        return Execution("HOST_UNAVAILABLE", None, "", "", _duration_ms(started), "host_os_error")
    return Execution(
        "PASS" if completed.returncode == 0 else "FAIL",
        completed.returncode,
        _decode(completed.stdout),
        _decode(completed.stderr),
        _duration_ms(started),
        None if completed.returncode == 0 else "exit_code",
    )


def _mock_interviewer_contract(_: AdapterContext) -> Execution:
    return _run_registered_script("skills/mock-interviewer/tests/test_contract.py")


def _matching_v3_contract(_: AdapterContext) -> Execution:
    return _run_registered_script("_shared/test_matching_v3.py")


def _career_agent_boundary_contract(_: AdapterContext) -> Execution:
    return _run_registered_script("scripts/test_career_agent_boundaries.py")


def _run_replay(kind: str, context: AdapterContext) -> Execution:
    started = time.perf_counter()
    try:
        result = behavior_replay.run(kind, context.scenario.inputs)
        stdout = json.dumps(result, ensure_ascii=False, sort_keys=True)
    except behavior_replay.ReplayError as exc:
        return Execution("FAIL", 1, "", f"replay error: {exc}", _duration_ms(started), "replay_contract")
    except (OSError, TypeError, ValueError) as exc:
        return Execution("FAIL", 1, "", f"replay error: {exc}", _duration_ms(started), "replay_adapter")
    return Execution("PASS", 0, stdout, "", _duration_ms(started))


def _mock_interviewer_contract_replay(context: AdapterContext) -> Execution:
    return _run_replay("mock_interviewer_contract", context)


def _matching_v3_replay(context: AdapterContext) -> Execution:
    return _run_replay("matching_v3", context)


def _career_agent_replay(context: AdapterContext) -> Execution:
    return _run_replay("career_agent", context)


ADAPTERS: dict[str, Adapter] = {
    "mock_interviewer_contract": _mock_interviewer_contract,
    "matching_v3_contract": _matching_v3_contract,
    "career_agent_boundary_contract": _career_agent_boundary_contract,
    "mock_interviewer_contract_replay": _mock_interviewer_contract_replay,
    "matching_v3_replay": _matching_v3_replay,
    "career_agent_replay": _career_agent_replay,
}


def _sha256_inputs(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix()):
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _sha256_output(execution: Execution) -> str:
    digest = hashlib.sha256()
    digest.update(b"stdout\0")
    digest.update(execution.stdout.encode("utf-8"))
    digest.update(b"\0stderr\0")
    digest.update(execution.stderr.encode("utf-8"))
    return digest.hexdigest()


def _runtime_identity() -> dict[str, Any]:
    commit = "unknown"
    clean = False
    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True, check=False
        )
        if commit_result.returncode == 0:
            commit = commit_result.stdout.strip()
        status_result = subprocess.run(
            ["git", "status", "--porcelain"], cwd=str(ROOT), capture_output=True, text=True, check=False
        )
        clean = status_result.returncode == 0 and not status_result.stdout.strip()
    except OSError:
        pass
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "repository_commit": commit,
        "git_status_clean": clean,
    }


def _json_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if not part:
            raise KeyError(path)
        if isinstance(current, Mapping):
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            raise KeyError(path)
    return current


def _evaluate_assertion(assertion: Mapping[str, Any], execution: Execution) -> dict[str, Any]:
    assertion_type = assertion["type"]
    passed = False
    actual: Any
    expected: Any
    if assertion_type == "exit_code":
        actual = execution.returncode
        expected = assertion["expected"]
        passed = actual == expected
    elif assertion_type in {"stdout_contains", "stdout_not_contains"}:
        actual = assertion["value"] in execution.stdout
        expected = True if assertion_type == "stdout_contains" else False
        passed = actual == expected
    elif assertion_type in {"stderr_contains", "stderr_not_contains"}:
        actual = assertion["value"] in execution.stderr
        expected = True if assertion_type == "stderr_contains" else False
        passed = actual == expected
    else:
        try:
            parsed = json.loads(execution.stdout)
            actual = _json_path(parsed, assertion["path"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            actual = "<unreadable>"
        expected = assertion["expected"]
        passed = actual == expected
    return {
        "id": assertion["id"],
        "type": assertion_type,
        "passed": passed,
        "expected": expected,
        "actual": actual,
    }


def _failure_class(scenario: Scenario, execution: Execution, assertions: list[dict[str, Any]]) -> str | None:
    if execution.failure_class:
        return execution.failure_class
    if not all(item["passed"] for item in assertions):
        return "assertion"
    if scenario.classification == "not_executable":
        return "scenario_declared_not_executable"
    return None


def evaluate_scenario(scenario: Scenario, runtime_identity: dict[str, Any]) -> dict[str, Any]:
    adapter = ADAPTERS.get(scenario.adapter)
    if adapter is None:
        execution = Execution("NOT_EXECUTABLE", None, "", "", 0, "unregistered_adapter")
    else:
        execution = adapter(AdapterContext(ROOT, scenario))
    assertions = [_evaluate_assertion(assertion, execution) for assertion in scenario.assertions]
    assertions_passed = all(item["passed"] for item in assertions)
    if execution.status == "NOT_EXECUTABLE":
        status = "NOT_EXECUTABLE"
        classification = "not_executable"
    elif execution.status == "HOST_UNAVAILABLE":
        status = "HOST_UNAVAILABLE"
        classification = "not_executable"
    elif execution.status != "PASS" or not assertions_passed:
        status = "FAIL"
        classification = {
            "runtime_e2e": "runtime_e2e_fail",
            "behavior_replay": "behavior_replay_fail",
        }.get(scenario.execution_mode, "contract_audit_fail")
    else:
        status = "PASS"
        classification = scenario.classification
    return {
        "scenario_id": scenario.scenario_id,
        "skill": scenario.skill,
        "adapter": scenario.adapter,
        "risk_class": scenario.risk_class,
        "execution_mode": scenario.execution_mode,
        "expected_classification": scenario.classification,
        "classification": classification,
        "status": status,
        "passed": status == "PASS",
        "assertions": assertions,
        "exit_code": execution.returncode,
        "input_sha256": _sha256_inputs(scenario.inputs),
        "output_sha256": _sha256_output(execution),
        "runtime_identity": runtime_identity,
        "model_identity": None,
        "duration_ms": execution.duration_ms,
        "failure_class": _failure_class(scenario, execution, assertions),
    }


def run(schema_path: Path, selected_ids: set[str] | None = None) -> dict[str, Any]:
    scenarios = load_scenarios(schema_path)
    if selected_ids is not None:
        known = {scenario.scenario_id for scenario in scenarios}
        missing = sorted(selected_ids - known)
        if missing:
            raise BehaviorEvalError(f"unknown scenario id(s): {', '.join(missing)}")
        scenarios = tuple(scenario for scenario in scenarios if scenario.scenario_id in selected_ids)
    identity = _runtime_identity()
    results = [evaluate_scenario(scenario, identity) for scenario in scenarios]
    summary = {
        "total": len(results),
        "passed": sum(result["status"] == "PASS" for result in results),
        "failed": sum(result["status"] == "FAIL" for result in results),
        "host_unavailable": sum(result["status"] == "HOST_UNAVAILABLE" for result in results),
        "not_executable": sum(result["status"] == "NOT_EXECUTABLE" for result in results),
    }
    return {
        "result_schema_version": SCHEMA_VERSION,
        "runner_version": RUNNER_VERSION,
        "runtime_identity": identity,
        "model_identity": None,
        "scenarios": results,
        "summary": summary,
    }


def _write_json(path: Path, document: Mapping[str, Any]) -> None:
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", default="_shared/behavior_eval_schema.yml")
    parser.add_argument("--output", help="optional JSON result manifest path")
    parser.add_argument("--scenario", action="append", dest="scenario_ids")
    parser.add_argument("--list", action="store_true", help="list registered scenarios without executing")
    args = parser.parse_args(argv)
    schema_path = Path(args.schema)
    if not schema_path.is_absolute():
        schema_path = ROOT / schema_path
    try:
        scenarios = load_scenarios(schema_path.resolve())
        if args.list:
            for scenario in scenarios:
                print(f"{scenario.scenario_id}\t{scenario.execution_mode}\t{scenario.classification}")
            return 0
        selected = set(args.scenario_ids) if args.scenario_ids else None
        document = run(schema_path.resolve(), selected)
        if args.output:
            output_path = Path(args.output)
            if not output_path.is_absolute():
                output_path = ROOT / output_path
            _write_json(output_path.resolve(), document)
        print(json.dumps(document["summary"], sort_keys=True))
        return 0 if document["summary"]["failed"] == 0 and document["summary"]["not_executable"] == 0 else 1
    except (BehaviorEvalError, OSError) as exc:
        print(f"behavior eval error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
