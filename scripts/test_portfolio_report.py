import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import refresh_portfolio_report as report

class PortfolioTests(unittest.TestCase):
 def test_new_unchanged_revised(self):
  a=report.compare_periods({'2026-01-01':[1]},{});self.assertEqual(a['status'],'initialized')
  b=report.compare_periods({'2026-01-01':[1]},a);self.assertEqual(b['status'],'unchanged')
  c=report.compare_periods({'2026-01-01':[1],'2026-01-08':[2]},a);self.assertEqual(c['status'],'new');self.assertEqual(c['new_periods'],1)
  d=report.compare_periods({'2026-01-01':[3],'2026-01-08':[2]},a);self.assertEqual(d['status'],'revised');self.assertTrue(d['prior_history_revised'])
 def test_regression_rejected(self):
  with self.assertRaises(ValueError):report.compare_periods({'2025-01-01':[1]},{'latest':'2026-01-01'})
 def test_partial_failure_retains_complete_component(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'output';dest.mkdir();components={}
   for name,files in report.FILES.items():
    cards=[]
    for f in files:
     p=dest/f;p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(b'old');cards.append({'file':f,'title':name,'description':'old'})
    components[name]={'cards':cards,'source':name,'latest':'2026-09-30','status':'unchanged','failed':False,'last_success':'old'}
   components['JSDA'].update(snapshot_utc='old',source_commit='a'*40)
   (dest/'manifest.json').write_text(json.dumps({'components':components}))
   def success(stage,previous):
    for f in report.FILES['MOF']:(stage/f).write_bytes(b'new')
    return dict(previous,status='unchanged')
   with patch.object(report,'mof_component',side_effect=success),patch.object(report,'jsda_component',side_effect=ValueError('do not leak sensitive message')):
    state=report.refresh(Path(tmp),'a'*40,dest)
   self.assertIn('partial',state['status']);self.assertEqual((dest/'jsda/rolling_jgb_purchases.png').read_bytes(),b'old')
   self.assertEqual((dest/'portfolio_flows.png').read_bytes(),b'new')
   text=(dest/'index.html').read_text();self.assertIn('Refresh failed',text);self.assertNotIn('sensitive message',text)
 def test_initial_failure_has_no_fake_output(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'new'
   with patch.object(report,'mof_component',side_effect=ValueError):
    with self.assertRaises(RuntimeError):report.refresh(Path(tmp),'a'*40,dest)
   self.assertFalse(dest.exists())

if __name__=='__main__':unittest.main()
