"""Meaningful loader parity and rejection checks; uses synthetic local data only."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import build_data as builder

SHA = 'a' * 40
CONFIG = {'test': {'change_type': 'pp', 'rows': [('JP', 'Rate', 'r158ma@intdaily')]}}


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        (self.folder / 'snapshot_commit.json').write_text(json.dumps({'repository': 'kteoh37/haver-dataset', 'commit': SHA}))
        (self.folder / 'snapshot_manifest.json').write_text(json.dumps({'snapshot_utc': '2026-10-26T21:59:54Z'}))
        self.meta = pd.DataFrame({'Series Code': ['R158MA@INTDAILY'], 'frequency': ['D'],
                                  'descriptor': ['Japan: 10 Year Treasury Bond Mid Yield (% p.a.)'], 'database': ['intdaily']})
        self.wide = pd.DataFrame({'R158MA@INTDAILY': np.arange(100, dtype=float) / 100},
                                 index=pd.bdate_range('2026-01-01', periods=100, name='date'))

    def tearDown(self):
        self.temp.cleanup()

    def load(self):
        with patch.object(builder, 'PANELS', CONFIG), patch.object(builder.pd, 'read_parquet', side_effect=[self.meta, self.wide]):
            return builder.load_frequency_snapshot(self.folder, SHA)

    def test_case_normalization_and_transform_parity(self):
        frame, coverage, source = self.load()
        actual = builder.build_panel(frame, 'test', CONFIG['test'])
        expected = builder.build_row(self.wide.iloc[:, 0], 'JP', 'Rate', 'r158ma@intdaily', 'pp')
        self.assertEqual(actual['rows'], [expected])
        self.assertEqual(coverage[0]['status'], 'exact')
        self.assertEqual(source['commit'], SHA)

    def test_weekly_in_daily_bucket_is_unavailable(self):
        self.meta.loc[0, 'frequency'] = 'W'
        frame, coverage, _ = self.load()
        self.assertTrue(frame.empty)
        self.assertEqual(coverage[0]['status'], 'non_daily')

    def test_missing_exact_code_has_no_substitute(self):
        self.meta['Series Code'] = ['R158GA@INTDAILY']
        self.wide.columns = ['R158GA@INTDAILY']
        frame, coverage, _ = self.load()
        self.assertTrue(frame.empty)
        self.assertEqual(coverage[0]['status'], 'missing')

    def test_ambiguous_case_rejected(self):
        self.meta = pd.concat([self.meta, self.meta.assign(**{'Series Code': 'r158ma@intdaily'})])
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            self.load()

    def test_provenance_mismatch_rejected(self):
        (self.folder / 'snapshot_commit.json').write_text(json.dumps({'repository': 'kteoh37/haver-dataset', 'commit': 'b'*40}))
        with self.assertRaisesRegex(ValueError, 'provenance'):
            self.load()

    def test_duplicate_dates_rejected(self):
        self.wide.index = pd.DatetimeIndex([pd.Timestamp('2026-01-01')]*100)
        with self.assertRaisesRegex(ValueError, 'unique'):
            self.load()

    def test_nonfinite_rejected(self):
        self.wide.iloc[0, 0] = float('inf')
        with self.assertRaisesRegex(ValueError, 'Non-finite'):
            self.load()


if __name__ == '__main__':
    unittest.main()
