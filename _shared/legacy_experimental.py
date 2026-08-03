#!/usr/bin/env python3
"""legacy_experimental namespace — model_version: legacy_v1. NOT the default path.

Was `_shared/scoring.py`, the default matching engine. It is no longer: the evidence-based
v3 diagnosis in `_shared/matching_v3.py` replaced it. These heuristics stay reachable only so
that scores already written to `data/match_history.md` and `data/pipeline.yml` remain
reproducible and readable — not so that new ones get produced casually.

    Experimental heuristic. Not an official Recruit/Persol model,
    not calibrated, and not a hiring-probability estimate.

Every result carries that warning and `model_version: legacy_v1`. Two rules hold everywhere
these numbers appear:

  - a legacy score and a v3 result never share a table, a ranking, or a sort key. They
    measure different things and one of them was never validated against anything.
  - `culture_fit()` is discontinued outright, not merely deprecated. `100 - Σdiff × 10`
    turned four ordinal preference ratings into a percentage with an invented multiplier.
    Historical values stay on disk; no new one is computed. Calling it raises.

CLI requires the opt-in flag, so nothing runs this by accident:
    python3 _shared/legacy_experimental.py --legacy-experimental < payload.json
    python3 _shared/legacy_experimental.py --self-test

Input schema (either block may be present):
{
  "recruit": {
    "skills": [{"name": "Python", "s": 70, "w": 0.5}, ...],   # s: 0-100, w: sum should be 1.0
    "p_fit": 75,            # SPI3 personality fit 0-100
    "b_behavioral": 60,     # behavioral signal approximation (CTR/CF proxy) 0-100
    "alpha": 0.3,           # optional, default 0.3
    "beta": 0.2             # optional, default 0.2
  },
  "persol": {
    "v_candidate": [1, 0.5, 0, ...],   # capability vectors, same length
    "v_job":       [1, 1,   0, ...],
    "bonus": 10                        # transferable bonus 0-20
  }
}
"""
import json
import math
import sys

MODEL_VERSION = "legacy_v1"

LEGACY_WARNING = (
    "Experimental heuristic. Not an official Recruit/Persol model, "
    "not calibrated, and not a hiring-probability estimate."
)

OPT_IN_FLAG = "--legacy-experimental"

CULTURE_FIT_DISCONTINUED = (
    "culture_fit (100 - Σdiff × 10) is discontinued and produces no new scores. "
    "The multiplier had no validation behind it and the output read as a percentage. "
    "Existing values in data/match_history.md stay as legacy_v1 history. "
    "Use the Career Values & Conditions axis in _shared/matching_v3.py instead — it "
    "reports aligned / tradeoff / conflict / unknown per item and never totals them."
)


class DiscontinuedError(RuntimeError):
    """A legacy calculation retained in history but no longer produced."""


def _stamp(result: dict) -> dict:
    """Every legacy result is self-identifying. A number that escapes this module without
    its version and its warning is exactly the failure v3 exists to stop."""
    return {**result, "model_version": MODEL_VERSION, "warning": LEGACY_WARNING}


def grade(score):
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def recruit_style(skills, p_fit, b_behavioral, alpha=0.3, beta=0.2):
    weight_sum = sum(sk["w"] for sk in skills)
    skill_term = sum(sk["s"] * sk["w"] for sk in skills)
    raw = skill_term + alpha * p_fit + beta * b_behavioral
    total = raw / (1 + alpha + beta)
    return _stamp({
        "skill_term": round(skill_term, 1),
        "raw": round(raw, 1),
        "total": round(total, 1),
        "grade": grade(total),
        "weight_sum_warning": None if abs(weight_sum - 1.0) < 1e-9
        else f"skill weights sum to {weight_sum}, expected 1.0",
    })


def persol_style(v_candidate, v_job, bonus=0):
    if len(v_candidate) != len(v_job):
        raise ValueError("vector length mismatch")
    dot = sum(a * b for a, b in zip(v_candidate, v_job))
    na = math.sqrt(sum(a * a for a in v_candidate))
    nb = math.sqrt(sum(b * b for b in v_job))
    cos = dot / (na * nb) if na and nb else 0.0
    bonus = max(0, min(20, bonus))
    total = min(100.0, cos * 100 + bonus)
    return _stamp({
        "cosine": round(cos, 3),
        "bonus": bonus,
        "total": round(total, 1),
        "grade": grade(total),
    })


def culture_fit(candidate=None, company=None):
    raise DiscontinuedError(CULTURE_FIT_DISCONTINUED)


def self_test():
    r = recruit_style(
        skills=[{"name": "Python", "s": 70, "w": 0.5},
                {"name": "SQL", "s": 80, "w": 0.3},
                {"name": "Docker/K8s", "s": 20, "w": 0.2}],
        p_fit=75, b_behavioral=60)
    assert r["raw"] == 97.5, r
    assert r["total"] == 65.0, r
    assert r["grade"] == "C", r
    assert r["model_version"] == MODEL_VERSION and r["warning"] == LEGACY_WARNING, r
    p = persol_style([1, 1, 0], [1, 1, 0], bonus=5)
    assert p["cosine"] == 1.0 and p["total"] == 100.0, p
    assert p["model_version"] == MODEL_VERSION, p
    try:
        culture_fit({"autonomy": 5}, {"autonomy": 5})
    except DiscontinuedError:
        pass
    else:
        raise AssertionError("culture_fit must refuse to produce a new score")
    assert main([]) == 2, "CLI must refuse to run without the opt-in flag"
    print(f"self-test OK: recruit=65.0/C, persol=100.0 [{MODEL_VERSION}], culture_fit discontinued")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        self_test()
        return 0
    if OPT_IN_FLAG not in argv:
        print(
            f"{LEGACY_WARNING}\n"
            f"Refusing to run: pass {OPT_IN_FLAG} to compute a legacy_v1 score anyway.\n"
            "The default diagnosis is _shared/matching_v3.py (model_version: evidence_based_v3).",
            file=sys.stderr,
        )
        return 2
    print(LEGACY_WARNING, file=sys.stderr)
    paths = [arg for arg in argv if not arg.startswith("--")]
    if paths:
        with open(paths[0], encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        payload = json.load(sys.stdin)
    out = {"model_version": MODEL_VERSION, "warning": LEGACY_WARNING}
    if "recruit" in payload:
        r = payload["recruit"]
        out["recruit"] = recruit_style(r["skills"], r["p_fit"], r["b_behavioral"],
                                       r.get("alpha", 0.3), r.get("beta", 0.2))
    if "persol" in payload:
        p = payload["persol"]
        out["persol"] = persol_style(p["v_candidate"], p["v_job"], p.get("bonus", 0))
    if "culture" in payload:
        out["culture"] = {"status": "discontinued", "reason": CULTURE_FIT_DISCONTINUED}
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
