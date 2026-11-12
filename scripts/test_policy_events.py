import copy
from datetime import date
import json
from pathlib import Path
import unittest

import policy_events as m
import refresh_policy_report as r


class PolicyEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((Path(__file__).parent / 'fixtures/policy-events-mof-2026q3.json').read_text())
        cls.document = r.REPORT.read_text()
        cls.seed = json.loads(r.PAYLOAD.search(cls.document)[2])

    def test_current_registry_validates_and_renders(self):
        current = m.validate(json.loads(m.REGISTRY.read_text()))
        m.apply_registry(self.document, current)

    def test_checked_official_registry(self):
        self.assertEqual(m.validate(self.registry), self.registry)
        self.assertEqual(len(self.registry['events']), 3)

    def test_noop_upsert_is_idempotent(self):
        a = m.upsert({'schema_version': 1, 'events': []}, self.registry['events'])
        b = m.upsert(a, self.registry['events'])
        self.assertEqual(a, b)
        self.assertEqual(a, self.registry)
        self.assertEqual(m.upsert(a, []), a)

    def test_correction_keeps_id_and_other_records(self):
        update = copy.deepcopy(self.registry['events'][0]); update['caveat'] += ' Clarification.'
        result = m.upsert(self.registry, [update])
        self.assertEqual(result['events'][0], update)
        self.assertEqual(result['events'][1:], self.registry['events'][1:])
        update['event_date'] = '2026-07-29'
        with self.assertRaisesRegex(ValueError, 'identity'):
            m.upsert(self.registry, [update])

    def test_duplicate_identity_fails(self):
        event = copy.deepcopy(self.registry['events'][0]); event['id'] = 'DUPLICATE-ID'; event.pop('legacy_id')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            m.upsert(self.registry, [event])

    def test_nonofficial_sources_and_redirect_targets_fail(self):
        for url in ['https://www.mof.go.jp.evil.test/report', 'https://evil.test/report',
                    'http://www.mof.go.jp/report', 'https://www.mof.go.jp@evil.test/report',
                    'https://www.mof.go.jp/report?token=secret', 'https://www.mof.go.jp:8443/report',
                    'https://www.mof.go.jp/']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                m.official_url(url, 'MOF')
        with self.assertRaises(ValueError):
            m.official_url('https://www.boj.or.jp/en/report.html', 'MOF')

    def test_private_and_unexpected_data_rejected(self):
        for key, value in [('briefing', 'private prose'), ('confidence', 'probably'), ('raw_payload', {})]:
            bad = copy.deepcopy(self.registry); bad['events'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): m.validate(bad)
        for value in ['https://chatgpt.com/c/secret', '<script>alert(1)</script>', 'sandbox:/mnt/data/x', 'api_key=secret']:
            bad = copy.deepcopy(self.registry); bad['events'][0]['summary'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): m.validate(bad)
        bad = copy.deepcopy(self.registry); bad['private_briefing'] = 'secret'
        with self.assertRaises(ValueError): m.validate(bad)

    def test_dates_separate_and_future_events_rejected(self):
        for field, value in [('event_date', '2026-11-10'), ('verified_on', '2099-01-01'),
                             ('disclosure_date', '2026-07-29'), ('disclosure_date', '2026-11-08')]:
            bad = copy.deepcopy(self.registry); bad['events'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                m.validate(bad, today=date(2026, 11, 9))
        bad = copy.deepcopy(self.registry); bad['events'][0]['effective_date'] = '2027-01-01'
        m.validate(bad, today=date(2026, 11, 9))

    def test_evidence_requires_exact_public_quotes(self):
        calls = []
        evidence = {}
        for event in self.registry['events']:
            for source in event['sources']:
                evidence.setdefault(source['url'], []).extend(source['quotes'])
        def fetch(url, issuer):
            calls.append(url); return '\n\t'.join(evidence[url])
        self.assertEqual(m.verify_sources(self.registry, fetch), 2)
        self.assertEqual(len(calls), 2)
        with self.assertRaisesRegex(ValueError, 'no longer matches'):
            m.verify_sources(self.registry, lambda *args: 'unrelated page')
        with self.assertRaises(OSError):
            m.verify_sources(self.registry, lambda *args: (_ for _ in ()).throw(OSError('outage')))

    def test_replaces_two_markers_adds_one_preserves_all_other_events(self):
        result = m.apply_registry(self.document, self.registry)
        updated = json.loads(r.PAYLOAD.search(result)[2])
        for key, p in updated.items():
            self.assertEqual(p['dates'], self.seed[key]['dates'])
            self.assertEqual(p['values'], self.seed[key]['values'])
            self.assertEqual(p['figure']['data'][0], self.seed[key]['figure']['data'][0])
            self.assertEqual(p['fiscal'], self.seed[key]['fiscal'])
            old = [e for e in self.seed[key]['context'] if e.get('id') not in ('FX26-4R', 'FX26-5')]
            kept = [e for e in p['context'] if not e.get('policy_event_id')]
            self.assertEqual(old, kept)
            self.assertEqual(len(p['context']), len(self.seed[key]['context']) + 1)
            markers = [e for e in p['context'] if e.get('policy_event_id')]
            self.assertEqual([e['date'] for e in markers], ['2026-07-30', '2026-07-31', '2026-08-03'])
            self.assertTrue(all(e['disclosure_date'] == '2026-11-09' for e in markers))
            for trace in p['figure']['data'][1:]:
                self.assertEqual(len(trace['x']), len(trace['y']))
                self.assertEqual(len(trace['x']), len(trace['customdata']))
                self.assertEqual(len(trace['x']), len(trace['marker']['color']))
                if 'symbol' in trace['marker']: self.assertEqual(len(trace['x']), len(trace['marker']['symbol']))
            fx = p['figure']['data'][3]
            self.assertEqual(fx['marker']['symbol'][fx['x'].index('2026-07-30')], 'square-open')
        self.assertNotIn('July 30 remains separately marked as reported', result)
        self.assertEqual(result.count('data-policy-id='), 3)
        self.assertEqual(result.count('class="event-description"'), 52)
        self.assertIn('MOF-FXI-2026-08-03', result)
        self.assertEqual(m.apply_registry(result, self.registry), result)

    def test_empty_registry_is_exact_noop(self):
        self.assertEqual(m.apply_registry(self.document, {'schema_version': 1, 'events': []}), self.document)

    def test_missing_price_is_pending_not_invented(self):
        event = copy.deepcopy(self.registry['events'][-1])
        event.update(id='MOF-FXI-2026-11-09', event_date='2026-11-09')
        reg = {'schema_version': 1, 'events': [event]}
        result = m.apply_registry(self.document, reg)
        p = json.loads(r.PAYLOAD.search(result)[2])
        self.assertIn('No matching market observation yet for: jgb, yen', result)
        self.assertFalse(any(e.get('policy_event_id') == event['id'] for e in p['jgb']['context']))
        self.assertEqual(p['jgb']['values'], self.seed['jgb']['values'])

    def test_price_refresh_then_overlay_preserves_new_records(self):
        import pandas as pd
        dates = pd.bdate_range('2022-01-03', '2027-01-05')
        series = {'jgb': pd.Series(2.5, index=dates), 'yen': pd.Series(155., index=dates)}
        refreshed, latest = r.refresh(self.document, series, 'test-revision')
        rendered = m.apply_registry(refreshed, self.registry)
        rerun, _ = r.refresh(rendered, series, 'test-revision')
        rerun = m.apply_registry(rerun, self.registry)
        self.assertEqual(json.loads(r.PAYLOAD.search(rendered)[2]), json.loads(r.PAYLOAD.search(rerun)[2]))
        self.assertIn('verified updates checked through 2026-11-09', rendered)
        self.assertIn('JGB 2027-01-05; yen 2027-01-05', rendered)

    def test_transition_rejects_deleted_history_and_stale_verification(self):
        changed = copy.deepcopy(self.registry); changed['events'].pop()
        with self.assertRaisesRegex(ValueError, 'Deleting reviewed'):
            m.validate_transition(self.registry, changed)
        self.assertEqual(m.validate_transition(self.registry, self.registry), self.registry)
        base = copy.deepcopy(self.registry)
        candidate = copy.deepcopy(base['events'][0])
        candidate.update(verified_on='2026-11-08', disclosure_date='2026-11-08')
        candidate['sources'][0]['published_date'] = '2026-11-08'
        with self.assertRaisesRegex(ValueError, 'Stale verification'):
            m.upsert(base, [candidate])

    def test_legacy_mapping_and_effective_marker_ids_are_stable(self):
        changed = copy.deepcopy(self.registry['events'][0]); changed.pop('legacy_id')
        with self.assertRaisesRegex(ValueError, 'legacy mapping'):
            m.upsert(self.registry, [changed])
        changed = copy.deepcopy(self.registry); changed['events'][-1]['id'] = 'FX26-4R'
        with self.assertRaisesRegex(ValueError, 'marker ID'):
            m.validate(changed)

    def test_existing_marker_missing_price_fails_without_mutation(self):
        payload = copy.deepcopy(self.seed)
        for p in payload.values():
            index = p['dates'].index('2026-07-30')
            p['dates'].pop(index); p['values'].pop(index)
        match = r.PAYLOAD.search(self.document)
        doc = self.document[:match.start(2)] + json.dumps(payload) + self.document[match.end(2):]
        with self.assertRaisesRegex(ValueError, 'lost its market observation'):
            m.apply_registry(doc, self.registry)
        self.assertIn('FX26-4R', doc)

    def test_provenance_anchor_required(self):
        doc = self.document.replace('<section class="report-section methodology">', '')
        with self.assertRaisesRegex(ValueError, 'methodology anchor'):
            m.apply_registry(doc, self.registry)

    def test_unknown_legacy_marker_fails_closed(self):
        bad = copy.deepcopy(self.registry); bad['events'][0]['legacy_id'] = 'FX-UNKNOWN'
        with self.assertRaisesRegex(ValueError, 'target is missing'):
            m.apply_registry(self.document, bad)


    def test_us_global_events_have_distinct_sources_and_tokyo_session_dates(self):
        fed = copy.deepcopy(self.registry['events'][0])
        fed.update(id='FED-FOMC-2026-10-28', issuer='FED', category='Fed',
                   stage='decision', event_date='2026-10-28',
                   disclosure_date='2026-10-28', verified_on='2026-11-12',
                   plot_date='2026-10-29', direction='neutral')
        fed.pop('legacy_id', None)
        fed['sources'] = [{'url': 'https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm',
                           'title': 'Fed decision', 'published_date': '2026-10-28',
                           'quotes': ['October 28, 2026']}]
        cpi = copy.deepcopy(fed)
        cpi.update(id='BLS-CPI-2026-11-10', issuer='BLS', category='U.S. CPI',
                   stage='disclosure', event_date='2026-11-10', plot_date='2026-11-11',
                   disclosure_date='2026-11-10')
        cpi['sources'] = [{'url': 'https://www.bls.gov/news.release/archives/cpi_11102026.htm',
                           'title': 'BLS CPI', 'published_date': '2026-11-10',
                           'quotes': ['CONSUMER PRICE INDEX - OCTOBER 2026']}]
        registry = m.upsert({'schema_version': 1, 'events': []}, [fed, cpi],
                            today=date(2026, 11, 12))
        self.assertEqual(len(registry['events']), 2)
        self.assertEqual(m.upsert(registry, [], today=date(2026, 11, 12)), registry)
        for bad in [dict(fed, plot_date='2026-10-28'),
                    dict(fed, plot_date='2026-11-06'),
                    dict(cpi, issuer='MOF')]:
            with self.assertRaises(ValueError):
                m.validate({'schema_version': 1, 'events': [bad]}, today=date(2026, 11, 12))
        with self.assertRaises(ValueError):
            m.official_url('https://www.bls.gov.evil.test/notice', 'BLS')
        with self.assertRaises(ValueError):
            m.official_url('https://www.federalreserve.gov/private?token=abc', 'FED')
        import pandas as pd
        dates = pd.bdate_range('2022-01-03', '2026-11-12')
        series = {'jgb': pd.Series(2.5, index=dates),
                  'yen': pd.Series(156.0, index=dates)}
        refreshed, _ = r.refresh(self.document, series, 'test-revision')
        rendered = m.apply_registry(refreshed, registry)
        payload = json.loads(r.PAYLOAD.search(rendered)[2])
        for key, p in payload.items():
            self.assertEqual(len(p['figure']['data']), 5)
            self.assertEqual(p['figure']['data'][4]['x'], ['2026-10-29', '2026-11-11'])
            self.assertEqual(p['figure']['data'][4]['marker']['symbol'],
                             ['star-open', 'circle-open'])
            self.assertEqual(len([e for e in p['context'] if e.get('source_event_date')]), 2)
        self.assertIn('First Tokyo-session chart marker 2026-11-11', rendered)
        rerun, _ = r.refresh(rendered, series, 'test-revision')
        rerendered = m.apply_registry(rerun, registry)
        self.assertEqual(json.loads(r.PAYLOAD.search(rendered)[2]),
                         json.loads(r.PAYLOAD.search(rerendered)[2]))


if __name__ == '__main__':
    unittest.main()
