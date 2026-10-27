import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

spec = importlib.util.spec_from_file_location('refresh_report', Path(__file__).with_name('refresh_policy_report.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RefreshReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = m.REPORT.read_text()
        cls.seed = json.loads(m.PAYLOAD.search(cls.document)[2])

    def series(self, end='2027-01-05'):
        dates = pd.bdate_range('2022-01-03', end)
        return {'jgb': pd.Series(2.5, index=dates), 'yen': pd.Series(155., index=dates)}

    def test_advances_prices_preserves_every_annotation_and_description(self):
        result, latest = m.refresh(self.document, self.series(), 'test-revision')
        updated = json.loads(m.PAYLOAD.search(result)[2])
        self.assertEqual(latest, {'jgb':'2027-01-05','yen':'2027-01-05'})
        for key in updated:
            for family in ['fiscal','context']:
                strip = lambda events: [{k:v for k,v in e.items() if k!='value'} for e in events]
                self.assertEqual(strip(self.seed[key][family]), strip(updated[key][family]))
            self.assertEqual(updated[key]['figure']['data'][0]['x'][-1], '2027-01-05')
            self.assertEqual(updated[key]['figure']['data'][1]['y'], [e['value'] for e in updated[key]['fiscal']])
        self.assertEqual(result.count('class="event-description"'),51)
        self.assertIn('test-revision', result)
        self.assertIn("Number(p.dates[p.dates.length-1].slice(0,4))",result)
        self.assertNotIn("b='2026-10-30'",result)

    def test_rejects_truncated_snapshot(self):
        with self.assertRaisesRegex(ValueError,'stale source'):
            m.refresh(self.document,self.series('2026-10-01'))

    def test_rejects_lost_annotated_date(self):
        series=self.series()
        series['jgb']=series['jgb'].drop(pd.Timestamp('2026-07-31'))
        with self.assertRaisesRegex(ValueError,'Missing annotated date'):
            m.refresh(self.document,series)

    def test_no_silent_substitution_of_different_bond_series(self):
        with tempfile.TemporaryDirectory() as folder:
            pd.DataFrame({'R158GA@INTDAILY':[1.], 'X111JPJ@INTDAILY':[150.]},index=pd.to_datetime(['2022-01-03'])).to_parquet(Path(folder)/'haver_output_daily.parquet')
            with self.assertRaisesRegex(ValueError,'Required exact Haver series missing'):
                m.load_series(folder)


if __name__=='__main__':
    unittest.main()
