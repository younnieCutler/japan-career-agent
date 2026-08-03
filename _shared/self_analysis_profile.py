"""Strict validation for reviewed SELF_ANALYSIS_PROFILE v2 objects."""

from __future__ import annotations

from typing import Any


LANGUAGES = {"ko", "ja", "en"}
TRACKS = {"shinsotsu", "chuto"}
CONFIDENCE = {"high", "medium", "low", "unknown"}
BEHAVIOR_IDS = {
    "initiative", "execution", "discipline", "ownership", "analysis", "learning",
    "strategy", "empathy", "harmony", "communication", "support", "confidence",
}
ACTIVITY_IDS = {
    "hands_on_systems", "investigate_causes", "create_expressions",
    "help_explain", "persuade_lead", "organize_processes",
}
ENVIRONMENT_IDS = {
    "autonomy", "competence", "relatedness", "structure_preference", "speed_preference",
    "change_tolerance", "collaboration_preference", "feedback_frequency",
}
REQUIRED_FIELDS = {
    "self_analysis_version", "candidate_name", "language_preference", "track",
    "interest_hypotheses", "behavior_tendencies", "evidence_episodes", "career_self_efficacy",
    "perceived_barriers", "perceived_supports", "environment_preferences", "value_candidates",
    "avoid_candidates",
}
OPTIONAL_FIELDS = {
    "preferred_environment_hypothesis", "verification_questions", "recommended_role_clusters",
    "self_pr_seeds", "career_anchors", "derailers", "energy_map", "career_theme",
    "career_values", "career_context_confirmed", "notes",
}
RAW_ONLY_FIELDS = {
    "jiko_bunseki_submission", "submission_version", "name", "language", "interest_activities",
    "episodes", "unanswered_fields", "explicit_unknown_fields",
}


class ProfileValidationError(ValueError):
    """Raised when a value cannot be treated as a canonical v2 profile."""


def _string(value: Any, label: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ProfileValidationError(f"{label} must be a non-empty string")


def _scale(value: Any, label: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise ProfileValidationError(f"{label} must be an integer from 1 to 5, or null")


def _list(value: Any, label: str, *, nullable: bool = False) -> list[Any] | None:
    if nullable and value is None:
        return None
    if not isinstance(value, list):
        raise ProfileValidationError(f"{label} must be a list or null")
    return value


def _strings(value: Any, label: str, *, nullable: bool = False) -> None:
    values = _list(value, label, nullable=nullable)
    if values is None:
        return
    for index, item in enumerate(values):
        _string(item, f"{label}[{index}]")


def _confidence(value: Any, label: str) -> None:
    if not isinstance(value, str) or value not in CONFIDENCE:
        raise ProfileValidationError(f"{label} must be one of {sorted(CONFIDENCE)}")


def _validate_interest(value: Any) -> None:
    values = _list(value, "interest_hypotheses", nullable=True)
    if values is None:
        return
    for index, item in enumerate(values):
        if not isinstance(item, dict):
            raise ProfileValidationError(f"interest_hypotheses[{index}] must be an object")
        activity = item.get("activity")
        if not isinstance(activity, str) or activity not in ACTIVITY_IDS:
            raise ProfileValidationError(
                f"interest_hypotheses[{index}].activity must be a known checklist activity id; "
                f"allowed: {sorted(ACTIVITY_IDS)}"
            )
        _string(item.get("response_basis"), f"interest_hypotheses[{index}].response_basis")
        _confidence(item.get("confidence"), f"interest_hypotheses[{index}].confidence")


def _validate_behavior(value: Any, episode_ids: set[str]) -> None:
    values = _list(value, "behavior_tendencies", nullable=True)
    if values is None:
        return
    seen: set[str] = set()
    for index, item in enumerate(values):
        label = f"behavior_tendencies[{index}]"
        if not isinstance(item, dict):
            raise ProfileValidationError(f"{label} must be an object")
        name = item.get("name")
        if not isinstance(name, str) or name not in BEHAVIOR_IDS or name in seen:
            raise ProfileValidationError(
                f"{label}.name must be a unique known tendency id; allowed: {sorted(BEHAVIOR_IDS)}"
            )
        seen.add(name)
        _scale(item.get("self_report"), f"{label}.self_report")
        _string(item.get("response_basis"), f"{label}.response_basis")
        refs = _list(item.get("evidence_episode_refs"), f"{label}.evidence_episode_refs")
        assert refs is not None
        for ref_index, ref in enumerate(refs):
            _string(ref, f"{label}.evidence_episode_refs[{ref_index}]")
            if ref not in episode_ids:
                raise ProfileValidationError(
                    f"{label}.evidence_episode_refs[{ref_index}] references unknown episode {ref!r}"
                )
        _confidence(item.get("confidence"), f"{label}.confidence")


def _validate_episodes(value: Any) -> set[str]:
    values = _list(value, "evidence_episodes", nullable=True)
    if values is None:
        return set()
    required = ("id", "experience_type", "situation", "action", "energy_effect", "source_type", "confidence")
    episode_ids: set[str] = set()
    for index, item in enumerate(values):
        label = f"evidence_episodes[{index}]"
        if not isinstance(item, dict):
            raise ProfileValidationError(f"{label} must be an object")
        for field in required:
            _string(item.get(field), f"{label}.{field}")
        episode_id = item["id"]
        if episode_id in episode_ids:
            raise ProfileValidationError(f"{label}.id must be unique within evidence_episodes")
        episode_ids.add(episode_id)
        if not isinstance(item["energy_effect"], str) or item["energy_effect"] not in {
            "energizing", "draining", "mixed", "unknown"
        }:
            raise ProfileValidationError(f"{label}.energy_effect is invalid")
        _string(item.get("energy_reason"), f"{label}.energy_reason", nullable=True)
        if item["source_type"] != "user":
            raise ProfileValidationError(f"{label}.source_type must be user")
        _confidence(item["confidence"], f"{label}.confidence")
    return episode_ids


def _validate_efficacy(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"learning_confidence", "outcome_expectation", "goal"}:
        raise ProfileValidationError(
            "career_self_efficacy must contain learning_confidence, outcome_expectation, and goal"
        )
    _scale(value["learning_confidence"], "career_self_efficacy.learning_confidence")
    _string(value["outcome_expectation"], "career_self_efficacy.outcome_expectation", nullable=True)
    _string(value["goal"], "career_self_efficacy.goal", nullable=True)


def _validate_environment(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != ENVIRONMENT_IDS:
        raise ProfileValidationError("environment_preferences must contain exactly the eight preference ids")
    for field in ENVIRONMENT_IDS:
        _scale(value[field], f"environment_preferences.{field}")


def _validate_anchors(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"primary", "secondary", "will_not_give_up"}:
        raise ProfileValidationError("career_anchors has an invalid shape")
    _string(value["primary"], "career_anchors.primary")
    _strings(value["secondary"], "career_anchors.secondary")
    _string(value["will_not_give_up"], "career_anchors.will_not_give_up")


def _validate_energy_map(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"energizes", "drains", "misfit_flag"}:
        raise ProfileValidationError("energy_map has an invalid shape")
    _strings(value["energizes"], "energy_map.energizes")
    _strings(value["drains"], "energy_map.drains")
    _string(value["misfit_flag"], "energy_map.misfit_flag", nullable=True)


def _validate_values(value: Any, label: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"must_have", "avoid"}:
        raise ProfileValidationError(f"{label} has an invalid shape")
    _strings(value["must_have"], f"{label}.must_have")
    _strings(value["avoid"], f"{label}.avoid")


def _validate_derailers(value: Any) -> None:
    values = _list(value, "derailers", nullable=True)
    if values is None:
        return
    required = {"strength", "overuse_risk", "watch_signal"}
    for index, item in enumerate(values):
        label = f"derailers[{index}]"
        if not isinstance(item, dict) or set(item) != required:
            raise ProfileValidationError(f"{label} must contain strength, overuse_risk, and watch_signal")
        if item["strength"] not in BEHAVIOR_IDS:
            raise ProfileValidationError(
                f"{label}.strength must be a known tendency id; allowed: {sorted(BEHAVIOR_IDS)}"
            )
        _string(item["overuse_risk"], f"{label}.overuse_risk")
        _string(item["watch_signal"], f"{label}.watch_signal")


def _validate_preferred_environment_hypothesis(value: Any) -> None:
    values = _list(value, "preferred_environment_hypothesis", nullable=True)
    if values is None:
        return
    required = {"preference", "hypothesis", "verification_question", "confidence"}
    for index, item in enumerate(values):
        label = f"preferred_environment_hypothesis[{index}]"
        if not isinstance(item, dict) or set(item) != required:
            raise ProfileValidationError(
                f"{label} must contain preference, hypothesis, verification_question, and confidence"
            )
        if item["preference"] not in ENVIRONMENT_IDS:
            raise ProfileValidationError(
                f"{label}.preference must be a known environment preference id; "
                f"allowed: {sorted(ENVIRONMENT_IDS)}"
            )
        _string(item["hypothesis"], f"{label}.hypothesis")
        _string(item["verification_question"], f"{label}.verification_question")
        _confidence(item["confidence"], f"{label}.confidence")


def _validate_self_pr_seeds(value: Any, episode_ids: set[str]) -> None:
    values = _list(value, "self_pr_seeds", nullable=True)
    if values is None:
        return
    required = {"episode_ref", "seed"}
    for index, item in enumerate(values):
        label = f"self_pr_seeds[{index}]"
        if not isinstance(item, dict) or set(item) != required:
            raise ProfileValidationError(f"{label} must contain episode_ref and seed")
        _string(item["episode_ref"], f"{label}.episode_ref")
        if item["episode_ref"] not in episode_ids:
            raise ProfileValidationError(
                f"{label}.episode_ref references unknown episode {item['episode_ref']!r}"
            )
        _string(item["seed"], f"{label}.seed")


def validate_self_analysis_profile(value: Any) -> dict[str, Any]:
    """Validate without normalizing or migrating any field."""
    if not isinstance(value, dict):
        raise ProfileValidationError("SELF_ANALYSIS_PROFILE must be an object")
    raw_fields = sorted(RAW_ONLY_FIELDS.intersection(value))
    if raw_fields:
        raise ProfileValidationError(f"raw checklist fields cannot be canonical: {', '.join(raw_fields)}")
    missing = sorted(REQUIRED_FIELDS.difference(value))
    if missing:
        raise ProfileValidationError(f"SELF_ANALYSIS_PROFILE missing required fields: {', '.join(missing)}")
    unknown = sorted(set(value).difference(REQUIRED_FIELDS | OPTIONAL_FIELDS))
    if unknown:
        raise ProfileValidationError(f"SELF_ANALYSIS_PROFILE has unknown fields: {', '.join(unknown)}")
    if value["self_analysis_version"] != 2 or isinstance(value["self_analysis_version"], bool):
        raise ProfileValidationError("self_analysis_version must be integer 2")
    _string(value["candidate_name"], "candidate_name")
    if not isinstance(value["language_preference"], str) or value["language_preference"] not in LANGUAGES:
        raise ProfileValidationError(f"language_preference must be one of {sorted(LANGUAGES)}")
    if not isinstance(value["track"], str) or value["track"] not in TRACKS:
        raise ProfileValidationError(f"track must be one of {sorted(TRACKS)}")

    _validate_interest(value["interest_hypotheses"])
    episode_ids = _validate_episodes(value["evidence_episodes"])
    _validate_behavior(value["behavior_tendencies"], episode_ids)
    _validate_efficacy(value["career_self_efficacy"])
    _strings(value["perceived_barriers"], "perceived_barriers", nullable=True)
    _strings(value["perceived_supports"], "perceived_supports", nullable=True)
    _validate_environment(value["environment_preferences"])
    _strings(value["value_candidates"], "value_candidates", nullable=True)
    _strings(value["avoid_candidates"], "avoid_candidates", nullable=True)

    if "preferred_environment_hypothesis" in value:
        _validate_preferred_environment_hypothesis(value["preferred_environment_hypothesis"])
    if "verification_questions" in value:
        _strings(value["verification_questions"], "verification_questions", nullable=True)
    if "recommended_role_clusters" in value:
        _strings(value["recommended_role_clusters"], "recommended_role_clusters", nullable=True)
    if "self_pr_seeds" in value:
        _validate_self_pr_seeds(value["self_pr_seeds"], episode_ids)
    if "career_anchors" in value:
        _validate_anchors(value["career_anchors"])
    if "derailers" in value:
        _validate_derailers(value["derailers"])
    if "energy_map" in value:
        _validate_energy_map(value["energy_map"])
    if "career_theme" in value:
        _string(value["career_theme"], "career_theme", nullable=True)
    if "career_values" in value:
        _validate_values(value["career_values"], "career_values")
    if "career_context_confirmed" in value and not isinstance(value["career_context_confirmed"], bool):
        raise ProfileValidationError("career_context_confirmed must be boolean")
    if value.get("career_values") is not None and value.get("career_context_confirmed") is not True:
        raise ProfileValidationError("career_values requires career_context_confirmed=true")
    if "notes" in value:
        _strings(value["notes"], "notes", nullable=True)
    return value
