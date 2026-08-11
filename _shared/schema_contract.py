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
    """Close an object exactly when the catalog declares what belongs in it.

    The rule is `properties` is declared, not "this looks like an object". Both other readings are
    wrong in a way that shows up as a wrong answer rather than as an error:

    - Closing on `type: object` alone closes the objects the catalog deliberately leaves shapeless.
      `work_style_reflection` is `{type: object}` with no properties and is *required* on every
      CANDIDATE_PROFILE, so closing it rejects every profile that has one filled in.
    - Closing on the declared type at all misses `type: [object, 'null']`, which is how every
      nullable object in this catalog is written.

    Keying on `properties` gets both: a field gains strictness the moment its shape is written
    down, in whichever way its type is spelled, and an intentionally opaque field stays open. The
    opaque ones are not unvalidated -- `portable_skill_allocation` is checked by
    `matching_v3.validate_allocation`, the v2 profile by `self_analysis_profile.py` -- they are
    validated by the code that knows their rules rather than by a shape the catalog does not state.

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
    if "properties" in closed:
        closed["additionalProperties"] = False
    return closed


def closed_object_paths(*, path: Path = SCHEMA_PATH) -> tuple[tuple[str, ...], ...]:
    """Every object the strict schema closes, as a JSON pointer path.

    Exposed so a test can pin the list. Which objects are strict is a contract, and a field that
    silently joined or left the set would change what a write is allowed to contain without anyone
    reading a diff of this file.
    """
    found: list[tuple[str, ...]] = []

    def walk(node: Any, pointer: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            if node.get("additionalProperties") is False:
                found.append(pointer)
            for key, value in node.items():
                walk(value, (*pointer, key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, (*pointer, str(index)))

    walk(_closed(load_catalog(path)["$defs"]), ())
    return tuple(found)


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
    # The derived schema is checked too. `_closed` walks a JSON Schema as plain nested data, so a
    # canonical object that ever declares a property named `properties` would have the transform
    # rewrite its property map instead of the object. No definition does today; this is what turns
    # that from a silent corruption into an error naming the file.
    try:
        jsonschema.Draft202012Validator.check_schema(
            {"$schema": catalog["$schema"], "$defs": strict_defs}
        )
    except jsonschema.exceptions.SchemaError as exc:
        raise SchemaContractError(f"strict schema derivation produced invalid JSON Schema: {exc.message}") from exc
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


def _without_required(schema: Any) -> Any:
    if isinstance(schema, list):
        return [_without_required(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    return {key: _without_required(value) for key, value in schema.items() if key != "required"}


@lru_cache(maxsize=None)
def _fragment_validator(name: str, pointer: tuple[str, ...], path: Path) -> jsonschema.Draft202012Validator:
    catalog = load_catalog(path)
    if name not in catalog["$defs"]:
        raise SchemaContractError(f"unknown canonical schema: {name}")
    node: Any = catalog["$defs"][name]
    for step in pointer:
        try:
            node = node[step]
        except (KeyError, TypeError) as exc:
            raise SchemaContractError(f"no such schema location: {name}/{'/'.join(pointer)}") from exc
    strict = _without_required(_closed(copy.deepcopy(node)))
    return jsonschema.Draft202012Validator({"$schema": catalog["$schema"], **strict})


def validate_new_fragment(
    name: str, value: Any, *, at: tuple[str, ...] = (), path: Path = SCHEMA_PATH
) -> Any:
    """Validate the part of a document a write is adding, strictly and at every depth.

    A writer that merges fields into an existing record cannot be checked by validating the merged
    result: the record may already hold keys from an older version, and rejecting those would make
    an existing file unwritable rather than upgradeable. So the *fragment* is what gets checked —
    what this write is introducing — while whatever was already on disk is left alone.

    `required` is dropped for the same reason: a partial update legitimately carries two fields out
    of thirty. Presence rules belong to the whole document; this answers the narrower question of
    whether every key being written is a key the catalog knows about.
    """
    _check(name, value, _fragment_validator(name, tuple(at), path))
    # A frozen field is refused here too. `pipeline_store` keeps its own check for the message it
    # writes, but a caller reaching this function directly must not get a weaker guarantee than
    # `validate_new_write` gives for the same document.
    forbidden = sorted(set(_frozen_in(value, _legacy_fields(name, path))))
    if forbidden:
        raise SchemaContractError(f"{name} cannot write legacy fields: {', '.join(forbidden)}")
    return value


@lru_cache(maxsize=None)
def _legacy_fields(name: str, path: Path) -> frozenset[str]:
    """The fields frozen *for this document*, which is not the same as frozen everywhere.

    A name can be retired in one schema and current in another. `wellbeing_priorities` is a v1
    self-analysis field no v2 producer recreates, and at the same time a live optional field of
    CANDIDATE_PROFILE — so a global list would refuse a legitimate candidate profile in order to
    protect a different document. The policy is recorded per schema for exactly that reason, and
    read per schema here.
    """
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    policy = catalog.get("legacy_field_policy", {}) if isinstance(catalog, dict) else {}
    by_schema = policy.get("by_schema") or {}
    return frozenset(str(field) for field in by_schema.get(name, ()))


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
    forbidden = sorted(set(_frozen_in(value, _legacy_fields(name, path))))
    if forbidden:
        raise SchemaContractError(f"{name} cannot write legacy fields: {', '.join(forbidden)}")
    return value
