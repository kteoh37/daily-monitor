"""Fail closed if the public portfolio directory exceeds its five-file contract."""
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parents[1]/'public/reports/japan-portfolio'
EXPECTED={'index.html','manifest.json','portfolio_flows.png','portfolio_flows_recent.png','jsda/rolling_jgb_purchases.png'}
files={str(p.relative_to(FOLDER)) for p in FOLDER.rglob('*') if p.is_file()}
if files!=EXPECTED:raise ValueError('Public portfolio export differs from approved five-file allowlist')
state=json.loads((FOLDER/'manifest.json').read_text())
allowed={'cards','source','source_url','source_final_update','snapshot_utc','source_commit','latest','fingerprint','status','new_periods','prior_history_revised','last_success','failed','stale','error_type','definition'}
if set(state)-{'schema_version','mode','attempted_at_utc','components','status'}:raise ValueError('Unexpected public manifest fields')
for component in state['components'].values():
 if set(component)-allowed:raise ValueError('Unexpected component fields')
 for card in component['cards']:
  if set(card)!={'file','title','description'} or card['file'] not in EXPECTED:raise ValueError('Unexpected card contract')
if '<script' in (FOLDER/'index.html').read_text().lower():raise ValueError('Portfolio HTML must contain prose and images only')

jsda=state['components']['JSDA']
if jsda.get('definition') != 'five-sectors-plus-jsda-others-v1':raise ValueError('JSDA report must use the formal JSDA Others definition')
if 'Others (JSDA category)' not in jsda['cards'][0]['description'] or 'All other categories (residual)' in jsda['cards'][0]['description'] or 'Overall total (all investor categories):' in jsda['cards'][0]['description']:raise ValueError('JSDA description does not match formal JSDA Others chart')

print('Approved export: three PNGs, HTML descriptions, compact display manifest; no raw snapshot or state history.')
