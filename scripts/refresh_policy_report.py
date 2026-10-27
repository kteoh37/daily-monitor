"""Refresh chart values in the curated Japan report; retain its policy chronology.

The committed HTML is the editorial source. CI regenerates only its data and data
availability labels before Vite copies it to dist; no generated commits are needed.
"""
import argparse
import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'public/reports/japan-policy-events.html'
CODES = {'jgb': 'R158MA@INTDAILY', 'yen': 'X111JPJ@INTDAILY'}
PAYLOAD = re.compile(r'(const data=)(.*?)(;\nfunction drawRange)', re.S)


def load_series(folder):
    path = Path(folder) / 'haver_output_daily.parquet'
    frame = pd.read_parquet(path)
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError('Haver snapshot must have a date index')
    if not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        raise ValueError('Duplicate or unordered Haver dates')
    columns = {str(c).upper(): c for c in frame.columns}
    result = {}
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    for key, code in CODES.items():
        if code not in columns:
            raise ValueError(f'Required exact Haver series missing: {code}')
        s = frame[columns[code]].loc['2022-01-01':today]
        s = pd.to_numeric(s, errors='raise').dropna()
        s = s[s.index.dayofweek < 5]
        if s.empty or s.index[0] > pd.Timestamp('2022-01-10'):
            raise ValueError(f'Insufficient history for {code}')
        if not np.isfinite(s.to_numpy()).all():
            raise ValueError(f'Non-finite values in {code}')
        result[key] = s
    return result


def refresh(document, series, source_commit='unknown'):
    match = PAYLOAD.search(document)
    if not match:
        raise ValueError('Report chart payload not found')
    payload = json.loads(match[2])
    original_events = {k: copy.deepcopy((p['fiscal'], p['context'])) for k,p in payload.items()}
    latest = {}
    for key, code in CODES.items():
        s = series[key]
        p = payload[key]
        if s.index[-1].date().isoformat() < p['dates'][-1]:
            raise ValueError(f'Refusing stale source that would shorten {code}')
        p['dates'] = [t.date().isoformat() for t in s.index]
        p['values'] = [float(v) for v in s]
        p['figure']['data'][0]['x'] = p['dates']
        p['figure']['data'][0]['y'] = p['values']
        for family in ['fiscal', 'context']:
            for event in p[family]:
                date = pd.Timestamp(event['date'])
                if date not in s.index:
                    raise ValueError(f'Missing annotated date {date.date()} for {code}')
                event['value'] = float(s.at[date])
        groups = [p['fiscal'], [e for e in p['context'] if e['category']=='BoJ'],
                  [e for e in p['context'] if e['category']=='FX intervention']]
        for trace, events in zip(p['figure']['data'][1:], groups):
            trace['x'] = [e['date'] for e in events]
            trace['y'] = [e['value'] for e in events]
        # Dates, descriptions, classifications, colors and verification status are editorial.
        for before, after in zip(original_events[key], [p['fiscal'],p['context']]):
            clean = lambda es: [{k:v for k,v in e.items() if k!='value'} for e in es]
            if clean(before) != clean(after):
                raise AssertionError('Event annotations changed during data refresh')
        latest[key] = p['dates'][-1]
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False).replace('</','<\\/')
    document = document[:match.start(2)] + encoded + document[match.end(2):]
    # Turn the original fixed-year controls into data-driven controls.
    document = document.replace("b='2026-10-30';", "b=p.dates[p.dates.length-1];")
    document = document.replace("period==='2026'?'2026-10-30':period+'-12-31'", "period===p.dates[p.dates.length-1].slice(0,4)?p.dates[p.dates.length-1]:period+'-12-31'")
    document = document.replace("drawRange(key,'2026');", "drawRange(key,p.dates[p.dates.length-1].slice(0,4));")
    document = document.replace("e.target.value?null:'2026'", "e.target.value?null:p.dates[p.dates.length-1].slice(0,4)")
    insertion = " const p=data[key];await Plotly.newPlot"
    replacement = """ const p=data[key];
 const yearBox=document.querySelector(`[data-for="${key}"] .years`);
 yearBox.replaceChildren();
 for(const year of ['All',...Array.from({length:Number(p.dates[p.dates.length-1].slice(0,4))-2022+1},(_,i)=>String(2022+i))]){
  const button=document.createElement('button');button.dataset.period=year;button.textContent=year;yearBox.append(button);
 }
 await Plotly.newPlot"""
    document = document.replace(insertion, replacement)
    document = document.replace('January 2022 – 26 October 2026.', 'January 2022 onward.')
    document = document.replace('The charts initially show 2026.', 'Each chart initially shows its latest available year.')
    old_start = 'Both series use the same Haver snapshot through October 26, 2026:'
    document = document.replace(old_start, 'Both series refresh from the Haver dataset during each daily-monitor deployment:')
    document = re.sub(r'The snapshot is pinned to commit [0-9a-f]{40}\.',
                      'The source revision and each series’ latest available date are displayed above the charts.', document)
    document = document.replace('The review does not presume later disclosures',
                                'Event research is retained through October 26, 2026; refreshing prices does not add later policy announcements or presume later disclosures')
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    status = (f'<p class="intro" id="data-refresh-status">Data refreshed {stamp}. '
              f'Latest observations: JGB {latest["jgb"]}; yen {latest["yen"]}. '
              f'Haver source revision: {source_commit}. '
              'Event annotations retained through October 26, 2026.</p>')
    document = re.sub(r'<p class="intro" id="data-refresh-status">.*?</p>', '', document)
    document = document.replace('<h1>Japan: JGB yields and the yen</h1>',
                                '<h1>Japan: JGB yields and the yen</h1>'+status, 1)
    return document, latest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--haver-data', required=True, help='kteoh37/haver-dataset checkout')
    parser.add_argument('--report', type=Path, default=REPORT)
    parser.add_argument('--source-commit', default='unknown')
    args = parser.parse_args()
    text, latest = refresh(args.report.read_text(), load_series(args.haver_data), args.source_commit)
    temporary = args.report.with_suffix('.html.tmp')
    temporary.write_text(text)
    temporary.replace(args.report)
    print(f'Policy report refreshed: {latest}; annotations retained')


if __name__ == '__main__':
    main()
