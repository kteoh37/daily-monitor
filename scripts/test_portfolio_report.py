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
 def test_calendar_window_and_separate_overall_total(self):
  import io
  import pandas as pd
  import portfolio_jsda as jsda
  months=pd.date_range('2021-01-31',periods=8,freq=pd.offsets.MonthEnd())
  columns={};metadata=[]
  for sector in jsda.SECTORS:
   for maturity in jsda.MATURITIES:
    for action,value,word in [('P',2.,'purchases'),('S',1.,'sales')]:
     code=f'GB{maturity}{sector}{action}@JAPAN';columns[code]=[value if sector else value*6]*8
     metadata.append({'Series Code':code,'Series Name':f'{word} (100 Mil.Yen)','shortsource':'JSDA','frequency':'M'})
  data=pd.DataFrame(columns,index=months);meta=pd.DataFrame(metadata)
  def encode(frame):
   out=io.BytesIO();frame.to_parquet(out);return out.getvalue()
  with self.assertRaisesRegex(ValueError,'Missing required series'):
   jsda.calculate(encode(data.drop(columns=[data.columns[0]])),encode(meta),5)
  badmeta=meta.copy();badmeta.loc[0,'frequency']='Q'
  with self.assertRaisesRegex(ValueError,'Unexpected source/frequency/units'):
   jsda.calculate(encode(data),encode(badmeta),5)
  frame=jsda.calculate(encode(data),encode(meta),5)
  totals=frame[(frame.month==months[-1])&frame.maturity.eq('All coupon-bearing JGBs')]
  self.assertEqual(len(totals),7)
  shown=totals[totals.sector.isin(jsda.DISPLAY_SECTORS)]
  self.assertEqual(len(shown),6)
  self.assertTrue((shown.rolling_net_trillion_yen==.0015).all())
  fields=['purchases_100million_yen','sales_100million_yen','net_100million_yen','rolling_net_trillion_yen']
  for (month,maturity),group in frame.groupby(['month','maturity']):
   overall=group[group.sector.eq(jsda.OVERALL_LABEL)].iloc[0]
   displayed=group[group.sector.isin(jsda.DISPLAY_SECTORS)]
   for field in fields:
    expected=overall[field]
    if pd.notna(expected):self.assertAlmostEqual(displayed[field].sum(min_count=6),expected)
  missing=data.copy();missing.iloc[4,1]=float('nan')
  incomplete=jsda.calculate(encode(missing),encode(meta),5)
  residual=incomplete[incomplete.sector.eq(jsda.RESIDUAL_LABEL)&incomplete.month.eq(months[4])]
  self.assertTrue(residual.rolling_net_trillion_yen.isna().any())
  # A missing calendar month must invalidate windows, never collapse to five observations.
  gap=jsda.calculate(encode(data.drop(months[4])),encode(meta),5)
  self.assertTrue(gap[gap.month==months[-1]].rolling_net_trillion_yen.isna().all())
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
