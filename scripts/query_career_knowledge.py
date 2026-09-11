#!/usr/bin/env python3
"""Read only requested career knowledge; candidates never enter operational output."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys

import yaml

from check_claim_freshness import CLAIMS, load_claims

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / '_shared' / 'career_knowledge.yml'
FIELDS = {'id', 'status', 'topics', 'scope', 'supporting_claim_ids', 'counterevidence',
          'allowed_behavior', 'forbidden_behavior', 'reviewed_at', 'expires_on',
          'required_scenarios', 'promotion'}


def date(value: object) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f'invalid ISO date: {value!r}') from exc


def strings(value: object, label: str, *, empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not empty):
        raise ValueError(f'{label} must be a list of nonempty strings')
    if any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError(f'{label} must contain nonempty strings')
    if len(set(value)) != len(value):
        raise ValueError(f'{label} contains duplicates')
    return value


def fingerprint(item: dict, claims: dict) -> str:
    """Bind review to behavior and all supporting evidence, excluding lifecycle status."""
    payload = {'knowledge': {k: v for k, v in item.items() if k not in {'status', 'promotion'}},
               'claims': [claims[k] for k in sorted(item['supporting_claim_ids'])]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     default=str).encode('utf-8')).hexdigest()


def load_registry(path: Path, claims_path: Path) -> tuple[list[dict], dict]:
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != '1.0':
        raise ValueError('knowledge schema_version must be 1.0')
    if not isinstance(data.get('knowledge'), list):
        raise ValueError('knowledge must be a list')
    claims = {}
    for claim in load_claims(claims_path):
        key = claim['id']
        if not isinstance(key, str) or not key.strip() or key in claims:
            raise ValueError('claim IDs must be nonempty and unique')
        claims[key] = claim
    seen = set()
    for item in data['knowledge']:
        if not isinstance(item, dict) or set(item) != FIELDS:
            raise ValueError('knowledge item has missing or unsupported fields')
        key = item['id']
        if not isinstance(key, str) or not key.strip() or key in seen:
            raise ValueError('knowledge IDs must be nonempty and unique')
        seen.add(key)
        if item['status'] not in ('candidate', 'active', 'retired'):
            raise ValueError(f'{key}: invalid status')
        for field in ('topics', 'scope', 'supporting_claim_ids', 'allowed_behavior',
                      'forbidden_behavior', 'required_scenarios', 'counterevidence'):
            strings(item[field], f'{key}.{field}', empty=field == 'counterevidence')
        if date(item['reviewed_at']) > date(item['expires_on']):
            raise ValueError(f'{key}: expiry precedes review')
        for claim_id in item['supporting_claim_ids']:
            if claim_id not in claims:
                raise ValueError(f'{key}: unknown claim {claim_id}')
        if item['promotion'] is not None and not isinstance(item['promotion'], dict):
            raise ValueError(f'{key}: promotion must be an object or null')
    return data['knowledge'], claims


def blockers(item: dict, claims: dict, today: dt.date) -> list[str]:
    reasons = []
    if date(item['reviewed_at']) > today:
        reasons.append('review_in_future')
    if date(item['expires_on']) < today:
        reasons.append('knowledge_expired')
    for key in item['supporting_claim_ids']:
        claim = claims[key]
        if date(claim['observed_at']) > today:
            reasons.append(f'claim_not_yet_observed:{key}')
        if date(claim['expires_on']) < today:
            reasons.append(f'claim_expired:{key}')
        if date(claim['observed_at']) > date(claim['expires_on']):
            reasons.append(f'claim_invalid_interval:{key}')
    # Community observations alone may never authorize operational behavior.
    if not any(claims[k]['claim_type'] in ('official', 'survey')
               for k in item['supporting_claim_ids']):
        reasons.append('no_primary_support')
    promotion = item['promotion']
    if not promotion:
        reasons.append('promotion_missing')
        return reasons
    required = {'evidence_sha256', 'reviewer', 'evaluated_at', 'evaluation_ref', 'results'}
    if set(promotion) != required:
        reasons.append('promotion_invalid')
        return reasons
    for field in ('reviewer', 'evaluation_ref'):
        if not isinstance(promotion[field], str) or not promotion[field].strip():
            reasons.append(f'promotion_invalid:{field}')
    if date(promotion['evaluated_at']) > today:
        reasons.append('evaluation_in_future')
    if date(promotion['evaluated_at']) < date(item['reviewed_at']):
        reasons.append('evaluation_predates_review')
    if promotion['evidence_sha256'] != fingerprint(item, claims):
        reasons.append('promotion_evidence_changed')
    results = promotion['results']
    if not isinstance(results, dict) or set(results) != set(item['required_scenarios']):
        reasons.append('evaluation_incomplete')
    elif any(result != 'pass' for result in results.values()):
        reasons.append('evaluation_failed')
    return reasons


def query(topics: list[str], *, path: Path = REGISTRY, claims_path: Path = CLAIMS,
          as_of: dt.date | None = None, research: bool = False) -> dict:
    if not topics:
        raise ValueError('at least one explicit topic is required')
    items, claims = load_registry(path, claims_path)
    today = as_of or dt.date.today()
    known = {topic for item in items for topic in item['topics']}
    unknown = sorted(set(topics) - known)
    if unknown:
        raise ValueError(f'unknown topics: {", ".join(unknown)}')
    selected, excluded = [], []
    for item in sorted(items, key=lambda x: x['id']):
        if not set(topics).intersection(item['topics']):
            continue
        reasons = blockers(item, claims, today)
        if item['status'] != 'active':
            reasons.insert(0, f'status:{item["status"]}')
        if reasons and not research:
            excluded.append({'id': item['id'], 'reasons': reasons})
            continue
        selected.append({'knowledge': item, 'claims': [claims[k] for k in item['supporting_claim_ids']],
                         'eligible': not reasons, 'blockers': reasons,
                         'evidence_sha256': fingerprint(item, claims)})
    return {'mode': 'research_only' if research else 'operational', 'as_of': today.isoformat(),
            'items': selected, 'excluded': excluded}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('topics', nargs='*')
    parser.add_argument('--research', action='store_true', help='explicit non-operational preview')
    parser.add_argument('--check', action='store_true', help='validate all active promotion records')
    parser.add_argument('--as-of', type=dt.date.fromisoformat)
    args = parser.parse_args()
    try:
        if args.check:
            if args.topics or args.research:
                raise ValueError('--check cannot be combined with topics or --research')
            items, claims = load_registry(REGISTRY, CLAIMS)
            errors = {i['id']: blockers(i, claims, args.as_of or dt.date.today())
                      for i in items if i['status'] == 'active'}
            errors = {k: v for k, v in errors.items() if v}
            print(json.dumps({'active_errors': errors}, ensure_ascii=False))
            return 1 if errors else 0
        result = query(args.topics, as_of=args.as_of, research=args.research)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except (ValueError, OSError, yaml.YAMLError) as exc:
        print(f'career knowledge error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
