#!/usr/bin/env python3
"""Build a reproducible, redacted E2E artifact.

The command is deliberately a packaging gate, not a career-flow bypass.  It refuses a dirty
repository by default, records the exact Git tree and runtime versions, requires explicit skill
execution classifications, and fails before creating a ZIP when local paths survive redaction.

Example::

    python scripts/e2e_artifact.py check --repo . --expected-commit <sha>
    python scripts/e2e_artifact.py package --repo <clean-worktree> \
        --artifact-root <e2e-output> --output <downloads>/e2e.zip \
        --skill-status-json <e2e-output>/skill-status.json \
        --fixture-status-json <e2e-output>/fixture-status.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ARTIFACT_SCHEMA = "japan-recruit-ai-agent.e2e-artifact.v2"
ALLOWED_SKILL_STATUSES = frozenset(
    {"runtime_e2e_pass", "contract_audit_pass", "not_executable"}
)
FIXTURE_STATUSES = frozenset(
    {"PASS", "PASS_AFTER_FIXTURE_CORRECTION", "PASS_AFTER_RETRY", "FAIL"}
)
_LOCAL_PATH_PATTERNS = (
    re.compile(r"(?i)(?<![A-Za-z0-9_])[A-Z]:[\\/]+Users[\\/][^\r\n\"']+"),
    re.compile(r"(?i)(?<![A-Za-z0-9_])(?:[A-Z]:[\\/]+(?:tmp|temp)[\\/]|/tmp/|/var/tmp/|/Users/|/home/)[^\r\n\"']+"),
)


class ArtifactError(RuntimeError):
    """Raised when an artifact is not safe or reproducible enough to package."""


def _run_text(argv: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _git(repo_root: Path, *args: str, required: bool = True) -> str:
    result = _run_text(["git", *args], cwd=repo_root)
    if required and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ArtifactError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _untracked_digest(repo_root: Path) -> bytes:
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ArtifactError(f"git ls-files failed: {detail}")

    output = bytearray()
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = os.fsdecode(raw_path)
        path = repo_root / relative
        if path.is_file():
            output.extend(raw_path)
            output.extend(b"\0")
            output.extend(path.read_bytes())
            output.extend(b"\0")
    return bytes(output)


def repository_identity(repo_root: Path) -> dict[str, Any]:
    """Return a path-free identity for the repository tree used by an E2E run."""

    repo_root = repo_root.expanduser().resolve()
    head = _git(repo_root, "rev-parse", "HEAD")
    branch = _git(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD", required=False)
    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    diff = subprocess.run(
        ["git", "diff", "--no-ext-diff", "--binary", "HEAD", "--"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if diff.returncode:
        detail = diff.stderr.decode("utf-8", errors="replace").strip()
        raise ArtifactError(f"git diff failed: {detail}")
    dirty_material = status.encode("utf-8") + b"\0" + diff.stdout + _untracked_digest(repo_root)
    return {
        "repository_commit": head,
        "repository_branch": branch or "(detached)",
        "git_status_clean": not bool(status),
        "git_status_porcelain": status.splitlines(),
        "dirty_diff_sha256": hashlib.sha256(dirty_material).hexdigest(),
        "repository_root": "<REPOSITORY>",
    }


def prepare_detached_worktree(
    *,
    repo_root: Path,
    worktree: Path,
    expected_commit: str,
) -> dict[str, Any]:
    """Create a clean detached worktree at an explicitly requested commit."""

    repo_root = repo_root.expanduser().resolve()
    worktree = worktree.expanduser().resolve()
    if worktree.exists():
        raise ArtifactError(f"worktree target already exists; refusing to overwrite: {worktree}")
    source_commit = _git(repo_root, "rev-parse", "HEAD")
    if source_commit != expected_commit:
        raise ArtifactError(
            f"source repository commit mismatch: expected {expected_commit}, got {source_commit}"
        )
    worktree.parent.mkdir(parents=True, exist_ok=True)
    result = _run_text(
        ["git", "worktree", "add", "--detach", str(worktree), expected_commit],
        cwd=repo_root,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ArtifactError(f"git worktree add failed: {detail}")
    identity = repository_identity(worktree)
    if identity["repository_commit"] != expected_commit or not identity["git_status_clean"]:
        raise ArtifactError("created worktree did not satisfy the clean expected-commit gate")
    return {
        "worktree": str(worktree),
        "expected_commit": expected_commit,
        "repository": identity,
    }


def _tool_version(argv: Sequence[str]) -> str | None:
    try:
        result = _run_text(argv, cwd=Path.cwd())
    except OSError:
        return None
    if result.returncode:
        return None
    first_line = result.stdout.strip().splitlines()
    return first_line[0] if first_line else None


def runtime_identity() -> dict[str, str | None]:
    """Return reproducibility-relevant runtime versions without executable paths."""

    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "node_version": _tool_version(["node", "--version"]),
    }


def validate_skill_statuses(statuses: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Validate explicit runtime/contract/non-executable skill classifications.

    A generic ``PASS`` is intentionally rejected.  The evidence field required for each status
    makes it difficult for a contract scan to be mistaken for a runtime E2E result.
    """

    if not isinstance(statuses, Mapping) or not statuses:
        raise ArtifactError("skill statuses must be a non-empty mapping")
    validated: dict[str, dict[str, Any]] = {}
    for name, raw in statuses.items():
        if not isinstance(name, str) or not name.strip():
            raise ArtifactError("skill status names must be non-empty strings")
        if not isinstance(raw, Mapping):
            raise ArtifactError(f"skill status {name!r} must be an object")
        status = raw.get("status")
        if status not in ALLOWED_SKILL_STATUSES:
            allowed = ", ".join(sorted(ALLOWED_SKILL_STATUSES))
            raise ArtifactError(f"{name}: status must be one of {allowed}; got {status!r}")
        item = dict(raw)
        if status == "runtime_e2e_pass":
            commands = item.get("runtime_commands")
            if not isinstance(commands, list) or not commands or not all(isinstance(command, str) for command in commands):
                raise ArtifactError(f"{name}: runtime_e2e_pass requires runtime_commands")
        elif status == "contract_audit_pass":
            checks = item.get("contract_checks")
            if not isinstance(checks, list) or not checks or not all(isinstance(check, str) for check in checks):
                raise ArtifactError(f"{name}: contract_audit_pass requires contract_checks")
        else:
            reason = item.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise ArtifactError(f"{name}: not_executable requires a reason")
        validated[name] = item
    return validated


def fixture_result_status(
    *,
    initial_failed_commands: Sequence[str],
    correction_kind: str,
    correction_reason: str | None,
    final_passed: bool,
) -> dict[str, Any]:
    """Classify the final fixture result without hiding an initial failed run."""

    failed = [str(command) for command in initial_failed_commands]
    if correction_kind not in {"none", "fixture", "environment", "unknown"}:
        raise ArtifactError(f"unsupported correction_kind: {correction_kind!r}")
    if failed and correction_kind == "unknown":
        raise ArtifactError("initial failures require a correction_kind classification")
    if correction_kind != "none" and not correction_reason:
        raise ArtifactError("a correction_kind requires correction_reason")

    if not final_passed:
        status = "FAIL"
    elif correction_kind == "fixture" and failed:
        status = "PASS_AFTER_FIXTURE_CORRECTION"
    elif correction_kind == "environment" and failed:
        status = "PASS_AFTER_RETRY"
    elif failed:
        raise ArtifactError("initial failures cannot be summarized as a generic PASS")
    else:
        status = "PASS"
    return {
        "status": status,
        "initial_failed_commands": failed,
        "correction_kind": correction_kind,
        "correction_reason": correction_reason,
        "final_passed": bool(final_passed),
    }


def _path_variants(path: Path) -> set[str]:
    value = str(path.expanduser().resolve())
    windows = value.replace("/", "\\")
    variants = {
        value,
        value.replace("\\", "/"),
        windows,
        windows.replace("\\", "\\\\"),
    }
    # JSON command logs may escape both backslashes and non-ASCII user-directory characters.
    variants.update(json.dumps(item, ensure_ascii=True)[1:-1] for item in tuple(variants))
    return variants


def _redaction_roots(repo_root: Path, source_root: Path, stage_root: Path) -> list[tuple[str, str]]:
    named = (
        (Path.home(), "<HOME>"),
        (Path(tempfile.gettempdir()), "<TEMP>"),
        (repo_root, "<REPOSITORY>"),
        (source_root, "<ARTIFACT_ROOT>"),
        (stage_root, "<ARTIFACT_ROOT>"),
    )
    pairs = [(variant, token) for path, token in named for variant in _path_variants(path)]
    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def redact_text(text: str, pairs: Iterable[tuple[str, str]]) -> str:
    result = text
    for source, token in pairs:
        result = re.sub(re.escape(source), token, result, flags=re.IGNORECASE if os.name == "nt" else 0)
    return result


def _decode_text(payload: bytes) -> tuple[str, str] | None:
    if b"\0" in payload[:4096] and not payload.startswith((b"\xff\xfe", b"\xfe\xff")):
        return None
    if payload.startswith(b"\xef\xbb\xbf"):
        try:
            return payload.decode("utf-8-sig"), "utf-8-sig"
        except UnicodeDecodeError:
            return None
    try:
        return payload.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    for encoding in ("utf-16",):
        try:
            return payload.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return None


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ArtifactError(f"symlinks are not allowed in artifacts: {path.relative_to(root)}")
        if path.is_file():
            yield path


def _copy_redacted_tree(source_root: Path, stage_root: Path, pairs: list[tuple[str, str]]) -> int:
    count = 0
    for source in _iter_files(source_root):
        relative = source.relative_to(source_root)
        destination = stage_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = source.read_bytes()
        decoded = _decode_text(payload)
        if decoded is None:
            destination.write_bytes(payload)
        else:
            text, encoding = decoded
            destination.write_text(redact_text(text, pairs), encoding=encoding, newline="")
        shutil.copystat(source, destination, follow_symlinks=False)
        count += 1
    return count


def scan_text_artifacts(root: Path, pairs: Iterable[tuple[str, str]]) -> list[dict[str, Any]]:
    """Find known local roots or common local absolute-path forms in text artifacts."""

    pair_values = [(source.casefold(), token) for source, token in pairs]
    findings: list[dict[str, Any]] = []
    for path in _iter_files(root):
        decoded = _decode_text(path.read_bytes())
        if decoded is None:
            continue
        text = decoded[0]
        relative = path.relative_to(root).as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            lowered = line.casefold()
            for source, token in pair_values:
                if source and source in lowered:
                    findings.append({"path": relative, "line": line_number, "token": token})
            for pattern in _LOCAL_PATH_PATTERNS:
                if pattern.search(line):
                    findings.append({"path": relative, "line": line_number, "token": "local_absolute_path"})
    unique = {(item["path"], item["line"], item["token"]): item for item in findings}
    return [unique[key] for key in sorted(unique)]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _file_manifest(root: Path) -> list[dict[str, Any]]:
    files = []
    for path in _iter_files(root):
        relative = path.relative_to(root).as_posix()
        if relative == "artifact-manifest.json":
            continue
        files.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return files


def _command_log_failures(artifact_root: Path) -> list[str]:
    log_path = artifact_root / "outputs" / "commands.jsonl"
    if not log_path.is_file():
        return []
    failures: list[str] = []
    for index, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ArtifactError(f"commands.jsonl line {index} is invalid JSON: {exc}") from exc
        if row.get("exit_code") not in (0, None):
            argv = row.get("argv") or [f"line-{index}"]
            failures.append(str(argv[0]) if isinstance(argv, list) else f"line-{index}")
    return failures


def package_artifact(
    *,
    artifact_root: Path,
    output_zip: Path,
    repo_root: Path,
    skill_statuses: Mapping[str, Any],
    fixture_status: Mapping[str, Any] | None = None,
    expected_commit: str | None = None,
    allow_dirty: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Sanitize, verify, manifest, and ZIP an E2E artifact."""

    artifact_root = artifact_root.expanduser().resolve()
    repo_root = repo_root.expanduser().resolve()
    if not artifact_root.is_dir():
        raise ArtifactError(f"artifact root is not a directory: {artifact_root}")
    identity = repository_identity(repo_root)
    if expected_commit and identity["repository_commit"] != expected_commit:
        raise ArtifactError(
            f"repository commit mismatch: expected {expected_commit}, got {identity['repository_commit']}"
        )
    if not identity["git_status_clean"] and not allow_dirty:
        raise ArtifactError(
            "repository working tree is dirty; run the E2E from a clean detached worktree or pass "
            "--allow-dirty for a non-reproducible diagnostic artifact"
        )

    validated_skills = validate_skill_statuses(skill_statuses)
    if fixture_status is None:
        initial_failures = _command_log_failures(artifact_root)
        fixture = fixture_result_status(
            initial_failed_commands=initial_failures,
            correction_kind="none" if not initial_failures else "unknown",
            correction_reason=None,
            final_passed=not initial_failures,
        )
    else:
        fixture = dict(fixture_status)
        expected_keys = {"status", "initial_failed_commands", "correction_kind", "correction_reason", "final_passed"}
        if not expected_keys <= set(fixture):
            raise ArtifactError(f"fixture status missing keys: {sorted(expected_keys - set(fixture))}")
        expected_status = fixture_result_status(
            initial_failed_commands=fixture["initial_failed_commands"],
            correction_kind=fixture["correction_kind"],
            correction_reason=fixture["correction_reason"],
            final_passed=fixture["final_passed"],
        )
        if fixture.get("status") != expected_status["status"]:
            raise ArtifactError(
                f"fixture status mismatch: declared {fixture.get('status')!r}, "
                f"derived {expected_status['status']!r}"
            )
        fixture = expected_status

    output_zip = output_zip.expanduser().resolve()
    if output_zip.exists() and not force:
        raise ArtifactError(f"output already exists; refusing to overwrite: {output_zip}")

    with tempfile.TemporaryDirectory(prefix="japan-recruit-e2e-stage-") as temporary:
        stage_root = Path(temporary) / artifact_root.name
        stage_root.mkdir(parents=True)
        pairs = _redaction_roots(repo_root, artifact_root, stage_root)
        scanned_files = _copy_redacted_tree(artifact_root, stage_root, pairs)
        findings = scan_text_artifacts(stage_root, pairs)
        redaction = {
            "status": "PASS" if not findings else "FAIL",
            "scanned_text_artifacts": scanned_files,
            "findings": findings,
            "tokens": sorted({token for _, token in pairs}),
        }
        _write_json(stage_root / "redaction-report.json", redaction)
        if findings:
            raise ArtifactError(f"redaction gate failed with {len(findings)} finding(s); ZIP was not created")

        manifest = {
            "schema": ARTIFACT_SCHEMA,
            "repository": identity,
            "reproducibility_status": "CLEAN_TREE" if identity["git_status_clean"] else "DIRTY_TREE_ALLOWED",
            "runtime": runtime_identity(),
            "fixture": fixture,
            "skill_statuses": validated_skills,
            "redaction": redaction,
            "manifest_self_hash": "excluded; hash artifact-manifest.json separately if needed",
            "files": _file_manifest(stage_root),
        }
        manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        (stage_root / "artifact-manifest.json").write_text(
            redact_text(manifest_text, pairs), encoding="utf-8", newline="\n"
        )
        manifest = json.loads((stage_root / "artifact-manifest.json").read_text(encoding="utf-8"))
        final_findings = scan_text_artifacts(stage_root, pairs)
        if final_findings:
            redaction["status"] = "FAIL"
            redaction["findings"] = final_findings
            _write_json(stage_root / "redaction-report.json", redaction)
            raise ArtifactError(
                f"redaction gate failed with {len(final_findings)} finding(s) in final artifact; ZIP was not created"
            )
        output_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in _iter_files(stage_root):
                archive.write(path, arcname=Path(artifact_root.name) / path.relative_to(stage_root))
        with zipfile.ZipFile(output_zip) as archive:
            corrupt = archive.testzip()
            if corrupt is not None:
                output_zip.unlink(missing_ok=True)
                raise ArtifactError(f"ZIP integrity check failed at {corrupt}")

    return {
        "output": str(output_zip),
        "bytes": output_zip.stat().st_size,
        "entries": len(manifest["files"]) + 1,
        "manifest": manifest,
    }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"cannot load JSON {path}: {exc}") from exc


def _check_command(args: argparse.Namespace) -> int:
    identity = repository_identity(args.repo)
    commit_matches = not args.expected_commit or identity["repository_commit"] == args.expected_commit
    clean = bool(identity["git_status_clean"])
    print(json.dumps({"repository": identity, "commit_matches": commit_matches}, ensure_ascii=False, indent=2))
    if not commit_matches:
        return 1
    if not clean and not args.allow_dirty:
        return 1
    return 0


def _prepare_worktree_command(args: argparse.Namespace) -> int:
    result = prepare_detached_worktree(
        repo_root=args.repo,
        worktree=args.worktree,
        expected_commit=args.commit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _package_command(args: argparse.Namespace) -> int:
    skill_statuses = _load_json(args.skill_status_json)
    fixture_status = _load_json(args.fixture_status_json) if args.fixture_status_json else None
    result = package_artifact(
        artifact_root=args.artifact_root,
        output_zip=args.output,
        repo_root=args.repo,
        skill_statuses=skill_statuses,
        fixture_status=fixture_status,
        expected_commit=args.expected_commit,
        allow_dirty=args.allow_dirty,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="verify the repository identity and clean-tree gate")
    check.add_argument("--repo", type=Path, required=True)
    check.add_argument("--expected-commit")
    check.add_argument("--allow-dirty", action="store_true")
    check.set_defaults(handler=_check_command)

    prepare = subparsers.add_parser(
        "prepare-worktree", help="create a clean detached worktree at an exact commit"
    )
    prepare.add_argument("--repo", type=Path, required=True)
    prepare.add_argument("--commit", required=True)
    prepare.add_argument("--worktree", type=Path, required=True)
    prepare.set_defaults(handler=_prepare_worktree_command)

    package = subparsers.add_parser("package", help="redact, verify, manifest, and ZIP an E2E artifact")
    package.add_argument("--repo", type=Path, required=True)
    package.add_argument("--artifact-root", type=Path, required=True)
    package.add_argument("--output", type=Path, required=True)
    package.add_argument("--skill-status-json", type=Path, required=True)
    package.add_argument("--fixture-status-json", type=Path)
    package.add_argument("--expected-commit")
    package.add_argument("--allow-dirty", action="store_true")
    package.add_argument("--force", action="store_true")
    package.set_defaults(handler=_package_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.handler(args)
    except ArtifactError as exc:
        print(f"e2e artifact error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
