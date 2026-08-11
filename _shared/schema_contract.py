"""Executable validation for the shared YAML contract catalog.

Two validators, one catalog. `validate_document` reads: it accepts properties the catalog does not
name, because a record written by an older version of this suite has to stay readable and there is
no migration that can reach a file on someone else's disk. `validate_new_write` writes: it rejects
them, because an unrecognized key on the way in is a typo or a producer that has drifted, and both
are cheaper to catch here than to discover later in a consumer that silently read nothing.

The strict schema is derived from the tolerant one rather than written out beside it. A second copy
in the YAML would be a second thing to update, and the two would eventually disagree about which
field belongs to which object -- which is the exact failure this is meant to prevent.
"""

from __future__ import annotations

import copy
from functools import lru_cache
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


def _closed(schema: Any) -> Any:
    """Close every object in a schema so an unnamed property is rejected.

    `additionalProperties: true` does not merely permit unknown keys, it *evaluates* them, which is
    why `unevaluatedProperties` would be a no-op here and the permissive setting has to be replaced
    rather than supplemented. None of the six definitions compose with `allOf`/`anyOf`/`$ref`, so
    the plain keyword is exact and there is nothing subtler to reach for.
    """
    if isinstance(schema, list):
        return [_closed(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    closed = {key: _closed(value) for key, value in schema.items()}
    if "properties" in closed or closed.get("type") == "object":
        closed["additionalProperties"] = False
    return closed


@lru_cache(maxsize=None)
def _validators(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog = load_catalog(path)
    tolerant = {
        name: jsonschema.Draft202012Validator(
            {"$schema": catalog["$schema"], "$ref": f"#/$defs/{name}", "$defs": catalog["$defs"]}
        )
        for name in catalog["$defs"]
    }
    strict_defs = _closed(copy.deepcopy(catalog["$defs"]))
    strict = {
        name: jsonschema.Draft202012Validator(
            {"$schema": catalog["$schema"], "$ref": f"#/$defs/{name}", "$defs": strict_defs}
        )
        for name in strict_defs
    }
    return tolerant, strict


def _validator(
    name: str, path: Path = SCHEMA_PATH, *, strict: bool = False
) -> jsonschema.Draft202012Validator:
    tolerant, closed = _validators(path)
    validators = closed if strict else tolerant
    if name not in validators:
        raise SchemaContractError(f"unknown canonical schema: {name}")
    return validators[name]


def _check(name: str, value: Any, validator: jsonschema.Draft202012Validator) -> Any:
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = "".join(f"[{part!r}]" for part in first.path)
        raise SchemaContractError(f"{name}{location}: {first.message}")
    return value


def validate_document(name: str, value: Any, *, path: Path = SCHEMA_PATH) -> Any:
    """The tolerant read path: shape is checked, unknown properties are kept."""
    return _check(name, value, _validator(name, path))


@lru_cache(maxsize=None)
def _legacy_fields(path: Path) -> frozenset[str]:
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    policy = catalog.get("legacy_field_policy", {}) if isinstance(catalog, dict) else {}
    return frozenset(str(field) for field in policy.get("fields", []))


def _frozen_in(value: Any, legacy: frozenset[str]) -> list[str]:
    """Frozen field names anywhere in the document, not only at its top level.

    MATCH_HISTORY is an array and a pipeline's legacy numbers live one level down in a company
    entry, so a top-level-only check would let both write a retired score while reporting success.
    The frozen names are specific enough -- `overall_grade`, `top_performer_spi3` -- that a nested
    occurrence is the same field, not a coincidence.
    """
    if isinstance(value, dict):
        found = sorted(set(value) & legacy)
        for nested in value.values():
            found += _frozen_in(nested, legacy)
        return found
    if isinstance(value, list):
        return [name for item in value for name in _frozen_in(item, legacy)]
    return []


def validate_new_write(name: str, value: Any, *, path: Path = SCHEMA_PATH) -> Any:
    """Validate a new document strictly and reject frozen legacy fields at any depth."""
    _check(name, value, _validator(name, path, strict=True))
    forbidden = sorted(set(_frozen_in(value, _legacy_fields(path))))
    if forbidden:
        raise SchemaContractError(f"{name} cannot write legacy fields: {', '.join(forbidden)}")
    return value
