#!/usr/bin/env python3
"""Exercise promotion, freshness, selection and Skill-integration boundaries."""
import copy
import datetime as dt
from pathlib import Path
import tempfile
import unittest

import yaml

from query_career_knowledge import CLAIMS, REGISTRY, ROOT, blockers, fingerprint, load_registry, query

TODAY = dt.date(2026, 9, 11)

# Every active registry item must have an explicit runtime representation for every declared
# Skill scope. The value is scope -> tuples of (owner path, required invariant fragments).
# This is intentionally exhaustive: adding/removing an active knowledge item or scope without
# updating its shipped lazy-reference representation must fail CI.
RUNTIME_BINDINGS = {
    'progressive_readability': {
        'humanize-japanese-career': (
            ('skills/humanize-japanese-career/SKILL.md',
             ('support rapid comprehension', 'survives detailed review',
              'optimize around a universal `30-second` reading claim')),
        ),
    },
    'shibo_doki_consistency': {
        'job-seeker-agent': (
            ('skills/job-seeker-agent/references/shibo-doki.md',
             ('Why leave -> Why this role -> Why this company -> Contribution',
              'Do not assign fixed weights')),
        ),
    },
    'weakness_mitigation': {
        'mock-interviewer': (
            ('skills/mock-interviewer/references/japan-market-probes.md',
             ('weakness -> observed downside -> mitigation behavior -> evidence of improvement',
              'Mitigation does not erase it')),
        ),
    },
    'short_tenure_context': {
        'mock-interviewer': (
            ('skills/mock-interviewer/references/japan-market-probes.md',
             ('there is no universal three-year minimum',
              'Do not convert the 9.5-month survey average into a cutoff')),
        ),
        'tenshoku-strategy': (
            ('skills/tenshoku-strategy/references/transition-risk.md',
             ('Do not require three years', 'or apply a fixed multiplier')),
        ),
    },
    'gap_activity_separation': {
        'mock-interviewer': (
            ('skills/mock-interviewer/references/japan-market-probes.md',
             ('does not erase the gap', 'Do not assign a fixed penalty')),
        ),
        'tenshoku-strategy': (
            ('skills/tenshoku-strategy/references/transition-risk.md',
             ('it does not turn the period into employment or erase the gap',
              'Do not assign a universal penalty')),
        ),
    },
    'salary_anchor_not_rule': {
        'tenshoku-strategy': (
            ('skills/tenshoku-strategy/references/nenshu-koushou.md',
             ('Current compensation is one process input',
              'Never use `current salary + 10%`')),
        ),
    },
    'evidence_safe_story_lens': {
        'career-tanaoroshi': (
            ('skills/career-tanaoroshi/references/evidence-elicitation.md',
             ('not treated as a Japanese hiring standard',
              'never create an estimate, range, rounded KPI')),
        ),
    },
    'career_values_legitimate': {
        'tenshoku-strategy': (
            ('skills/tenshoku-strategy/references/transition-risk.md',
             ('independent career values',
              'Do not rank salary or benefits as lower-quality motives')),
        ),
    },
    'career_relevant_self_intro': {
        'job-seeker-agent': (
            ('skills/job-seeker-agent/references/mensetsu-rounds.md',
             ('career-relevant hook grounded in confirmed evidence',
              'Do not insert a hobby, novelty fact, or personal anecdote solely as bait')),
        ),
        'mock-interviewer': (
            ('skills/mock-interviewer/references/japan-market-probes.md',
             ('concise career-relevant hook from confirmed experience',
              'A novelty hobby is not required as bait')),
        ),
    },
    'ai_draft_defensibility': {
        'job-seeker-agent': (
            ('skills/job-seeker-agent/references/shibo-doki.md',
             ('AI-written text is draft material, not evidence',
              'Do not infer deception from AI use')),
        ),
        'mock-interviewer': (
            ('skills/mock-interviewer/references/japan-market-probes.md',
             ('AI use is not proof of deception', 'Test defendability instead')),
        ),
    },
    'resume_role_distinction': {
        'job-seeker-agent': (
            ('skills/job-seeker-agent/references/shokumukeireki-saigensei.md',
             ('Treat the documents as overlapping but different surfaces',
              'Do not imply a single statutory template')),
        ),
    },
}


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'knowledge.yml'
        self.claims_path = Path(self.tmp.name) / 'claims.yml'
        self.items, self.claims = load_registry(REGISTRY, CLAIMS)
        self.items = copy.deepcopy(self.items)
        self.item = self.items[0]
        # Lifecycle unit tests always begin from a synthetic candidate regardless of the
        # repository registry's current promotion state.
        self.item['status'] = 'candidate'
        self.item['promotion'] = None
        self.topic = self.item['topics'][0]

    def save(self):
        self.path.write_text(yaml.safe_dump({'schema_version': '1.0', 'knowledge': self.items}))
        self.claims_path.write_text(yaml.safe_dump({'claims': list(self.claims.values())}))

    def run_query(self, topics=None, **kw):
        self.save()
        scope = kw.pop('scope', self.item['scope'][0])
        return query(topics or [self.topic], scope=scope, path=self.path,
                     claims_path=self.claims_path,
                     as_of=kw.pop('as_of', TODAY), **kw)

    def promote(self):
        self.item['status'] = 'active'
        self.item['promotion'] = dict(evidence_sha256=fingerprint(self.item, self.claims),
                                     reviewer='synthetic-test-reviewer', evaluated_at='2026-09-11',
                                     evaluation_ref='synthetic://test-run',
                                     results={s: 'pass' for s in self.item['required_scenarios']})

    def test_candidates_excluded_and_research_explicit(self):
        self.assertEqual(self.run_query()['items'], [])
        result = self.run_query(research=True)
        self.assertEqual(result['mode'], 'research_only')
        self.assertFalse(result['items'][0]['eligible'])
        self.assertEqual(len(result['items']), 1)

    def test_promotion_requires_receipt(self):
        self.item['status'] = 'active'
        self.assertEqual(self.run_query()['items'], [])
        self.promote()
        self.assertEqual(len(self.run_query()['items']), 1)

    def test_modified_behavior_or_claim_invalidates_promotion(self):
        self.promote()
        self.item['allowed_behavior'].append('Changed behavior')
        self.assertEqual(self.run_query()['items'], [])
        self.promote()
        self.claims[self.item['supporting_claim_ids'][0]]['claim'] += ' Changed evidence'
        self.assertEqual(self.run_query()['items'], [])

    def test_failed_or_missing_evaluation(self):
        for result in ('fail', None, True):
            self.promote()
            self.item['promotion']['results'][self.item['required_scenarios'][0]] = result
            self.assertEqual(self.run_query()['items'], [])
        self.promote()
        self.item['promotion']['results'] = {}
        self.assertEqual(self.run_query()['items'], [])

    def test_expiry_boundary_and_future_review(self):
        self.promote()
        self.assertEqual(len(self.run_query(as_of=dt.date(2026, 12, 11))['items']), 1)
        self.assertEqual(self.run_query(as_of=dt.date(2026, 12, 12))['items'], [])
        self.assertEqual(self.run_query(as_of=dt.date(2026, 9, 10))['items'], [])

    def test_stale_support_fails_even_with_fresh_knowledge(self):
        self.claims[self.item['supporting_claim_ids'][0]]['expires_on'] = '2026-09-10'
        self.promote()
        self.assertEqual(self.run_query()['items'], [])

    def test_community_only_support_is_not_promotable(self):
        self.claims[self.item['supporting_claim_ids'][0]]['claim_type'] = 'third_party'
        self.promote()
        self.assertEqual(self.run_query()['items'], [])

    def test_retired_excluded_even_with_valid_receipt(self):
        self.promote()
        self.item['status'] = 'retired'
        with self.assertRaisesRegex(ValueError, 'must clear promotion'):
            self.run_query()

    def test_reactivation_requires_new_lifecycle_evaluation(self):
        self.promote()
        old_promotion = copy.deepcopy(self.item['promotion'])
        self.item['status'] = 'retired'
        self.item['promotion'] = None
        self.run_query(research=True)
        self.item['status'] = 'active'
        self.item['lifecycle_revision'] += 1
        self.item['promotion'] = old_promotion
        self.assertEqual(self.run_query()['items'], [])
        self.promote()
        self.assertEqual(len(self.run_query()['items']), 1)

    def test_scope_prevents_cross_skill_leakage_for_same_topic(self):
        self.promote()
        other = copy.deepcopy(self.item)
        other['id'] = 'same_topic_other_skill'
        other['scope'] = ['other-skill']
        other['promotion'] = None
        self.items.append(other)
        self.item = other
        self.promote()
        result = self.run_query(scope='other-skill')
        self.assertEqual([row['knowledge']['id'] for row in result['items']],
                         ['same_topic_other_skill'])
        self.assertEqual(result['excluded'],
                         [{'id': 'progressive_readability', 'reasons': ['scope_mismatch']}])

    def test_scope_is_required_and_mismatch_is_excluded(self):
        self.promote()
        self.save()
        with self.assertRaisesRegex(ValueError, 'scope'):
            query([self.topic], scope='', path=self.path, claims_path=self.claims_path)
        result = self.run_query(scope='other-skill')
        self.assertEqual(result['items'], [])
        self.assertEqual(result['excluded'][0]['reasons'], ['scope_mismatch'])

    def test_unknown_topic_and_no_topic_fail(self):
        with self.assertRaises(ValueError):
            self.run_query(['not-a-topic'])
        with self.assertRaises(ValueError):
            query([], scope=self.item['scope'][0], path=self.path,
                  claims_path=self.claims_path)

    def test_duplicate_ids_missing_claim_and_bad_shape(self):
        original = copy.deepcopy(self.items)
        for mutation in ('duplicate', 'claim', 'shape', 'date', 'revision', 'extra'):
            self.items = copy.deepcopy(original)
            if mutation == 'duplicate':
                self.items.append(copy.deepcopy(self.items[0]))
            elif mutation == 'claim':
                self.items[0]['supporting_claim_ids'] = ['missing']
            elif mutation == 'shape':
                self.items[0]['topics'] = 'string-not-list'
            elif mutation == 'date':
                self.items[0]['expires_on'] = 'bad'
            elif mutation == 'revision':
                self.items[0]['lifecycle_revision'] = True
            else:
                self.items[0]['score'] = 0.5
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.run_query()

    def test_duplicate_claim_ids(self):
        self.save()
        self.claims_path.write_text(yaml.safe_dump({'claims': [next(iter(self.claims.values()))] * 2}))
        with self.assertRaises(ValueError):
            load_registry(self.path, self.claims_path)

    def test_source_updated_at_is_validated_and_bound_to_promotion(self):
        self.promote()
        claim = self.claims[self.item['supporting_claim_ids'][0]]
        claim['source_updated_at'] = 'not-a-date'
        with self.assertRaisesRegex(ValueError, 'source_updated_at'):
            self.run_query()
        claim['source_updated_at'] = '2025-12-12'
        self.assertEqual(self.run_query()['items'], [])

    def test_selection_is_deterministic_and_deduplicated(self):
        self.promote()
        first = self.run_query([self.topic, self.topic])
        self.items.reverse()
        self.assertEqual(first, self.run_query([self.topic]))
        self.assertEqual(len(first['items']), 1)

    def test_repository_active_knowledge_has_valid_receipts(self):
        items, claims = load_registry(REGISTRY, CLAIMS)
        active = [item for item in items if item['status'] == 'active']
        self.assertGreaterEqual(len(active), 11)
        errors = {item['id']: blockers(item, claims, TODAY) for item in active}
        self.assertEqual({key: value for key, value in errors.items() if value}, {})

    def test_every_active_knowledge_item_is_bound_to_every_runtime_scope(self):
        items, _ = load_registry(REGISTRY, CLAIMS)
        active = {item['id']: item for item in items if item['status'] == 'active'}

        # The mapping is the explicit registry -> shipped-runtime contract. Neither side may grow
        # or shrink independently without this test forcing a reviewed integration update.
        self.assertEqual(set(active), set(RUNTIME_BINDINGS))

        cache = {}
        for knowledge_id, item in active.items():
            bindings = RUNTIME_BINDINGS[knowledge_id]
            self.assertEqual(set(item['scope']), set(bindings), knowledge_id)
            for scope, owners in bindings.items():
                self.assertTrue(owners, f'{knowledge_id}:{scope} has no runtime owner')
                for path, required_fragments in owners:
                    target = ROOT / path
                    self.assertTrue(target.is_file(), f'{knowledge_id}:{scope} missing {path}')
                    text = cache.setdefault(path, target.read_text(encoding='utf-8'))
                    for fragment in required_fragments:
                        self.assertIn(fragment, text,
                                      f'{knowledge_id}:{scope} missing runtime invariant in {path}')

    def test_skill_references_keep_non_registry_invariants(self):
        self_analysis = (ROOT / 'skills/jiko-bunseki/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('MBTI may be used only as reflection vocabulary', self_analysis)
        self.assertIn('not candidate skill evidence', self_analysis)

        strategy = (ROOT / 'skills/tenshoku-strategy/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('never impose a fixed application mix such as `3:2:5`', strategy)


if __name__ == '__main__':
    unittest.main()
