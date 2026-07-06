#!/usr/bin/env python3
"""Deterministic scoring for matching-simulator.

Replaces LLM mental arithmetic for the three formulas in _shared/frameworks.md §6.
Input: JSON on stdin (or a file path as argv[1]). Output: JSON on stdout.

Input schema (any subset of the three blocks may be present):
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
  },
  "culture": {
    "candidate": {"autonomy": 5, "social_contribution": 3, "management_quality": 4, "mutual_respect": 4},
    "company":   {"autonomy": 4, "social_contribution": 2, "management_quality": 4, "mutual_respect": 5}
  }
}

Run self-test (frameworks.md §6 worked example, expects recruit=65):
  python3 scoring.py --self-test
"""
import json
import math
import sys


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
    return {
        "skill_term": round(skill_term, 1),
        "raw": round(raw, 1),
        "total": round(total, 1),
        "grade": grade(total),
        "weight_sum_warning": None if abs(weight_sum - 1.0) < 1e-9
        else f"skill weights sum to {weight_sum}, expected 1.0",
    }


def persol_style(v_candidate, v_job, bonus=0):
    if len(v_candidate) != len(v_job):
        raise ValueError("vector length mismatch")
    dot = sum(a * b for a, b in zip(v_candidate, v_job))
    na = math.sqrt(sum(a * a for a in v_candidate))
    nb = math.sqrt(sum(b * b for b in v_job))
    cos = dot / (na * nb) if na and nb else 0.0
    bonus = max(0, min(20, bonus))
    total = min(100.0, cos * 100 + bonus)
    return {
        "cosine": round(cos, 3),
        "bonus": bonus,
        "total": round(total, 1),
        "grade": grade(total),
    }


def culture_fit(candidate, company):
    keys = ["autonomy", "social_contribution", "management_quality", "mutual_respect"]
    diffs = {k: abs(candidate[k] - company[k]) for k in keys if candidate.get(k) is not None and company.get(k) is not None}
    if len(diffs) < len(keys):
        missing = [k for k in keys if k not in diffs]
    else:
        missing = []
    diff_sum = sum(diffs.values())
    total = max(0, 100 - diff_sum * 10)
    fit = "High Fit" if diff_sum <= 4 else "Medium Fit" if diff_sum <= 8 else "Low Fit"
    return {"diff_sum": diff_sum, "total": total, "fit": fit,
            "missing_factors": missing or None}


def self_test():
    # frameworks.md §6 worked example: DE candidate vs DE role JD
    r = recruit_style(
        skills=[{"name": "Python", "s": 70, "w": 0.5},
                {"name": "SQL", "s": 80, "w": 0.3},
                {"name": "Docker/K8s", "s": 20, "w": 0.2}],
        p_fit=75, b_behavioral=60)
    assert r["raw"] == 97.5, r
    assert r["total"] == 65.0, r
    assert r["grade"] == "C", r
    p = persol_style([1, 1, 0], [1, 1, 0], bonus=5)
    assert p["cosine"] == 1.0 and p["total"] == 100.0, p
    c = culture_fit({"autonomy": 5, "social_contribution": 3, "management_quality": 4, "mutual_respect": 4},
                    {"autonomy": 4, "social_contribution": 2, "management_quality": 4, "mutual_respect": 5})
    assert c["diff_sum"] == 3 and c["total"] == 70 and c["fit"] == "High Fit", c
    print("self-test OK: recruit=65.0/C, persol=100.0, culture=70/High Fit")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            payload = json.load(f)
    else:
        payload = json.load(sys.stdin)
    out = {}
    if "recruit" in payload:
        r = payload["recruit"]
        out["recruit"] = recruit_style(r["skills"], r["p_fit"], r["b_behavioral"],
                                       r.get("alpha", 0.3), r.get("beta", 0.2))
    if "persol" in payload:
        p = payload["persol"]
        out["persol"] = persol_style(p["v_candidate"], p["v_job"], p.get("bonus", 0))
    if "culture" in payload:
        c = payload["culture"]
        out["culture"] = culture_fit(c["candidate"], c["company"])
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
