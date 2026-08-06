#!/usr/bin/env python3
"""Check direct dependency constraints against the repository's pinned hash locks."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.-]*)\s*"
    r"((?:==|>=|<=|~=|>|<)\s*[0-9]+(?:\.[0-9]+)*"
    r"(?:\s*,\s*(?:==|>=|<=|~=|>|<)\s*[0-9]+(?:\.[0-9]+)*)*)$"
)
SPECIFIER_RE = re.compile(r"(==|>=|<=|~=|>|<)\s*([0-9]+(?:\.[0-9]+)*)")
PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\s\\]+)")
HASH_RE = re.compile(r"--hash=sha256:([0-9a-fA-F]{64})")


@dataclass(frozen=True)
class LockedPackage:
    name: str
    version: str
    hashes: tuple[str, ...]


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def direct_dependencies(path: Path) -> dict[str, str]:
    dependencies: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "--")):
            continue
        match = PACKAGE_RE.match(line)
        if not match:
            raise ValueError(f"unsupported dependency declaration: {raw!r}")
        name = _normalize(match.group(1))
        dependencies[name] = match.group(2)
    return dependencies


def _version_parts(value: str) -> tuple[int, ...]:
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", value):
        raise ValueError(f"unsupported version for constraint evaluation: {value!r}")
    return tuple(int(part) for part in value.split("."))


def _compare_versions(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    width = max(len(left), len(right))
    padded_left = left + (0,) * (width - len(left))
    padded_right = right + (0,) * (width - len(right))
    return (padded_left > padded_right) - (padded_left < padded_right)


def version_satisfies(version: str, specifier: str) -> bool:
    actual = _version_parts(version)
    for operator, expected_text in SPECIFIER_RE.findall(specifier):
        expected = _version_parts(expected_text)
        comparison = _compare_versions(actual, expected)
        if operator == "~=" and len(expected) >= 2:
            index = 0 if len(expected) == 2 else len(expected) - 2
            upper = (*expected[:index], expected[index] + 1, *((0,) * (len(expected) - index - 1)))
            matches = comparison >= 0 and _compare_versions(actual, upper) < 0
        else:
            matches = {
                "==": comparison == 0,
                ">=": comparison >= 0,
                "<=": comparison <= 0,
                ">": comparison > 0,
                "<": comparison < 0,
            }.get(operator, False)
        if not matches:
            return False
    return True


def parse_lock(path: Path, _seen: set[Path] | None = None) -> dict[str, LockedPackage]:
    seen = set() if _seen is None else set(_seen)
    path = path.resolve()
    if path in seen:
        raise ValueError(f"recursive lock include: {path}")
    seen.add(path)
    packages: dict[str, LockedPackage] = {}
    current_name: str | None = None
    current_version: str | None = None
    current_hashes: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line == "--require-hashes":
            continue
        if line.startswith("-r "):
            included = (path.parent / line[3:].strip()).resolve()
            packages.update(parse_lock(included, seen))
            continue
        match = PIN_RE.match(line)
        if match:
            if current_name is not None and current_version is not None:
                packages[current_name] = LockedPackage(
                    current_name, current_version, tuple(sorted(set(current_hashes)))
                )
            current_name = _normalize(match.group(1))
            current_version = match.group(2)
            current_hashes = []
        if current_name is not None:
            current_hashes.extend(HASH_RE.findall(line))
    if current_name is not None and current_version is not None:
        packages[current_name] = LockedPackage(current_name, current_version, tuple(sorted(set(current_hashes))))
    if not packages:
        raise ValueError(f"lock contains no pinned packages: {path}")
    for package in packages.values():
        if not package.hashes:
            raise ValueError(f"{package.name} has no SHA-256 hash in {path.name}")
    return packages


def validate(runtime: Path, development: Path, requirements: Path) -> list[str]:
    errors: list[str] = []
    direct = direct_dependencies(requirements)
    runtime_packages = parse_lock(runtime)
    development_packages = parse_lock(development)
    missing_direct = sorted(set(direct) - set(runtime_packages))
    if missing_direct:
        errors.append(f"runtime lock is missing direct packages {missing_direct}")
    # Transitive runtime dependencies are intentionally pinned in the lock even though they do
    # not belong in the small direct requirements.txt contract.
    for name in sorted(direct):
        package = runtime_packages.get(name)
        if package is None:
            continue
        if not version_satisfies(package.version, direct[name]):
            errors.append(
                f"runtime lock pin {name}=={package.version} does not satisfy requirements constraint {direct[name]}"
            )
        if name not in development_packages:
            errors.append(f"development lock is missing runtime package {name}")
        elif development_packages[name] != package:
            errors.append(f"development lock disagrees with runtime package {name}")
    for name, package in development_packages.items():
        if not package.version or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+(?:[-+][0-9A-Za-z.-]+)?", package.version):
            errors.append(f"invalid pinned version for {name}: {package.version!r}")
    if "ruff" not in development_packages:
        errors.append("development lock must pin ruff")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", default="requirements.txt")
    parser.add_argument("--runtime-lock", default="requirements.lock")
    parser.add_argument("--development-lock", default="requirements-dev.lock")
    args = parser.parse_args()
    paths = [Path(args.requirements), Path(args.runtime_lock), Path(args.development_lock)]
    paths = [path if path.is_absolute() else ROOT / path for path in paths]
    try:
        errors = validate(paths[1], paths[2], paths[0])
    except (OSError, ValueError) as exc:
        print(f"dependency lock check: FAIL ({exc})")
        return 1
    if errors:
        for error in errors:
            print(f"dependency lock check: {error}")
        return 1
    print("dependency lock check: PASS (direct constraints, pins, and hashes are aligned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
