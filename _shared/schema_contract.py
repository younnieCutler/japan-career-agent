"""Executable validation for the shared YAML contract catalog."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "_shared" / "schemas.yml"
SCHEMA_NAMES = (
    "SELF_ANALYSIS_PROFILE",
    "CANDIDATE_PROFILE",
    "COMPANY_PROFILE",
    "MATCH_HISTORY",
    "PIPELINE",
    "RULES",
)


class SchemaContractError(ValueError):
    """Raised when a serialized canonical document violates its machine contract."""


def load_catalog(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SchemaContractError(f"cannot load schema catalog: {path}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("$defs"), dict):
        raise SchemaContractError("schemas.yml must contain a Draft 2020-12 $defs catalog")
    schema = {
        "$schema": document.get("$schema"),
        "$id": document.get("$id"),
        "$defs": document["$defs"],
    }
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.exceptions.SchemaError as exc:
        raise SchemaContractError(f"invalid shared JSON Schema: {exc.message}") from exc
    missing = [name for name in SCHEMA_NAMES if name not in schema["$defs"]]
    if missing:
        raise SchemaContractError(f"schema catalog is missing definitions: {', '.join(missing)}")
    return schema


def _validator(name: str, path: Path = SCHEMA_PATH) -> jsonschema.Draft202012Validator:
    catalog = load_catalog(path)
    if name not in catalog["$defs"]:
        raise SchemaContractError(f"unknown canonical schema: {name}")
    return jsonschema.Draft202012Validator(
        {"$schema": catalog["$schema"], "$ref": f"#/$defs/{name}", "$defs": catalog["$defs"]}
    )


def validate_document(name: str, value: Any, *, path: Path = SCHEMA_PATH) -> Any:
    errors = sorted(_validator(name, path).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = "".join(f"[{part!r}]" for part in first.path)
        raise SchemaContractError(f"{name}{location}: {first.message}")
    return value


def validate_new_write(name: str, value: Any, *, path: Path = SCHEMA_PATH) -> Any:
    """Validate a new document and reject frozen legacy top-level fields."""
    validate_document(name, value, path=path)
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    legacy = catalog.get("legacy_field_policy", {}).get("fields", []) if isinstance(catalog, dict) else []
    if isinstance(value, dict):
        forbidden = sorted(set(value).intersection(str(field) for field in legacy))
        if forbidden:
            raise SchemaContractError(f"{name} cannot write legacy fields: {', '.join(forbidden)}")
    return value
