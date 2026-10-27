"""Live MOF + pinned JSDA refresh. Publish ONLY PNGs, prose and compact display state."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import shutil
import tempfile

import pandas as pd
import portfolio_mof as mof
import portfolio_jsda as jsda

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'public/reports/japan-portfolio'
FILES = {'MOF': ['portfolio_flows.png', 'portfolio_flows_recent.png'], 'JSDA': ['jsda/rolling_jgb_purchases.png']}


def digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def compare_periods(periods, previous):
    """A compact prior-prefix digest detects revisions without persisting raw history."""
    dates = sorted(periods)
    if not dates:
        raise ValueError('No observations')
    latest = dates[-1]
    if previous.get('latest') and latest < previous['latest']:
        raise ValueError('Source coverage regressed')
    prior_date = previous.get('latest')
    fingerprint = digest([(d, periods[d]) for d in dates])
    if prior_date and previous.get('fingerprint'):
        prefix = digest([(d, periods[d]) for d in dates if d <= prior_date])
        revised = prefix != previous['fingerprint']
        added = sum(d > prior_date for d in dates)
        status = 'revised' if revised else ('new' if added else 'unchanged')
    else:
        revised, added, status = False, None, 'initialized'
    return dict(latest=latest, fingerprint=fingerprint, status=status,
                new_periods=added, prior_history_revised=revised)


def mof_component(stage, previous):
    raw = mof.fetch()  # genuine official HTTP download; no fixture fallback
    rows, final_update = mof.parse_csv(raw)
    periods = {r['week_end']: [r[k] for k in mof.COLUMNS] for r in rows}
    state = compare_periods(periods, previous)
    if date.fromisoformat(state['latest']) > date.today():
        raise ValueError('Future MOF observation')
    cards = []
    for baseline, filename, title in [(date(2022,1,1),'portfolio_flows.png','Cross-border portfolio flows since 2022'),
                                       (date(2026,1,1),'portfolio_flows_recent.png','Cross-border portfolio flows rebased to 2026')]:
        cumulative = mof.cumulative(rows, baseline)
        (stage / filename).write_bytes(mof.chart(cumulative, baseline, stage))
        row = cumulative[-1]
        amount = lambda k: f'{row[k]:+.2f}'
        cards.append(dict(file=filename, title=title, description=(
            f'Cumulative net purchases from January {baseline.year}, yen trillion. Residents: foreign equities {amount("resident_equity")}, '
            f'foreign long-term debt {amount("resident_long_term_debt")}, foreign short-term debt {amount("resident_short_term_debt")}. '
            f'Nonresidents: Japanese equities {amount("nonresident_equity")}, Japanese long-term debt {amount("nonresident_long_term_debt")}, '
            f'Japanese short-term debt {amount("nonresident_short_term_debt")}. Positive values mean net purchases; negative values mean net sales.')))
    state.update(cards=cards, source='MOF weekly securities transactions', source_url=mof.SOURCE,
                 source_final_update=final_update, stale=(date.today()-date.fromisoformat(state['latest'])).days>21)
    return state


def jsda_component(stage, previous, folder, commit):
    if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('Full pinned Haver commit required')
    frame = jsda.calculate((folder/'haver_output_monthly.parquet').read_bytes(),
                           (folder/'haver_metadata_monthly.parquet').read_bytes(), 5)
    visible, png = jsda.outputs(frame, date(2022,1,1), 5, stage)
    # Fingerprints use transaction levels, not rolling sums; revisions remain detectable.
    periods = {str(month.date()): group.sort_values(['sector','maturity'])[['sector','maturity','purchases_100million_yen','sales_100million_yen']].to_json(orient='values',double_precision=10)
               for month,group in frame.groupby('month')}
    definition = 'five-sectors-plus-jsda-others-v1'
    changed_definition = previous.get('definition') != definition
    state = compare_periods(periods, {} if changed_definition else previous)
    if changed_definition:
        state['status'] = 'definition updated / comparison baseline reset'
    state['definition'] = definition
    (stage/'jsda').mkdir(exist_ok=True)
    (stage/'jsda/rolling_jgb_purchases.png').write_bytes(png)
    latest = visible.month.max()
    totals=visible[(visible.month==latest)&visible.maturity.eq('All coupon-bearing JGBs')&visible.sector.isin(jsda.DISPLAY_SECTORS)]
    if len(totals)!=6 or totals.rolling_net_trillion_yen.isna().any():
        raise ValueError('Incomplete latest JSDA sector totals')
    values='; '.join(f'{r.sector}: {r.rolling_net_trillion_yen:+.2f}' for r in totals.itertuples())
    card=dict(file='jsda/rolling_jgb_purchases.png',title='Who is buying coupon-bearing JGBs?',description=(
        'Rolling five calendar month net purchases, yen trillion; displayed since 2022. Latest all coupon-bearing totals — '+values+
        '. Super-long-, long- and medium-term maturity groups are shown separately. Nominal/face value; excludes Treasury bills and discount bonds. Others (JSDA category) uses the six directly reported Others purchase/sale series, not overall minus the displayed sectors. This mixed category includes government auction allocations, BoJ operations and other institutions. It is not pure BoJ activity or aggregate private investor demand. Net purchases are purchases minus sales from the investor/counterparty perspective.'))
    snapshot=json.loads((folder/'snapshot_manifest.json').read_text())
    state.update(cards=[card],source='JSDA via Haver Analytics',source_commit=commit,snapshot_utc=snapshot['snapshot_utc'],
                 stale=(date.today()-latest.date()).days>75)
    return state


def render(state):
    esc=lambda v:html.escape(str(v))
    cards=[]
    for name,item in state['components'].items():
        for c in item.get('cards',[]):
            vintage=f' · Haver snapshot: {esc(item["snapshot_utc"])} · Source commit: {esc(item["source_commit"])}' if name=='JSDA' else f' · {esc(item.get("source_final_update",""))}'
            cards.append(f'<section class="card"><h2>{esc(c["title"])}</h2><p>{esc(c["description"])}</p>'
                f'<p class="source">{esc(item["source"])} · Latest observation: {esc(item["latest"])} · Status: {esc(item["status"])}'
                f' · New periods: {esc(item.get("new_periods") if item.get("new_periods") is not None else "baseline established")} · Prior history revised: {esc(item.get("prior_history_revised","unknown"))}'
                f' · Last successful check: {esc(item.get("last_success","historical seed"))}{vintage}</p>'
                f'<p>{"Stale or retained input: check the observation date and last successful check. " if item.get("stale") else ""}'
                f'{"Refresh failed; previous complete chart retained. " if item.get("failed") else ""}</p>'
                f'<a href="{esc(c["file"])}"><img src="{esc(c["file"])}" alt="{esc(c["title"])}" loading="lazy"></a></section>')
    template=(ROOT/'scripts/portfolio-report-template.html').read_text()
    return template.replace('<!--STATUS-->',esc(state['status'])).replace('<!--CHECKED-->',esc(state['attempted_at_utc'])).replace('<!--CHARTS-->',''.join(cards))


def refresh(folder, commit, destination=DEST):
    destination=Path(destination)
    old=json.loads((destination/'manifest.json').read_text()) if (destination/'manifest.json').exists() else {'components':{}}
    stamp=datetime.now(timezone.utc).isoformat()
    state=dict(schema_version=1,mode='live-source-check',attempted_at_utc=stamp,components={})
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix='.portfolio-') as tmp:
        tmp=Path(tmp);candidate=tmp/'candidate';candidate.mkdir()
        for name,files in FILES.items():
            previous=old.get('components',{}).get(name,{})
            component=tmp/name;component.mkdir()
            try:
                item=mof_component(component,previous) if name=='MOF' else jsda_component(component,previous,folder,commit)
                for file in files:
                    if not (component/file).is_file():raise ValueError('Incomplete staged component')
                item.update(last_success=stamp,failed=False)
                source=component
            except Exception as exc:
                # No raw rows, paths, HTTP payloads or credential-bearing exception text in logs.
                if not previous.get('cards') or any(not (destination/f).is_file() for f in files):
                    raise RuntimeError(f'{name} failed without last-good charts ({type(exc).__name__})') from None
                item=dict(previous,failed=True,stale=True,status='failed / retained',error_type=type(exc).__name__)
                source=destination
            state['components'][name]=item
            for file in files:
                target=candidate/file;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/file,target)
        failed=sum(i['failed'] for i in state['components'].values())
        state['status']='failed / last-good charts retained' if failed==2 else ('partial / failed component retained' if failed else 'complete / live sources checked')
        (candidate/'manifest.json').write_text(json.dumps(state,indent=2,allow_nan=False)+'\n')
        (candidate/'index.html').write_text(render(state))
        backup=tmp/'backup'
        if destination.exists():destination.rename(backup)
        try:candidate.rename(destination)
        except BaseException:
            if backup.exists():backup.rename(destination)
            raise
    print(json.dumps({'status':state['status'],'components':{k:{x:v.get(x) for x in ['status','latest','new_periods','prior_history_revised','failed']} for k,v in state['components'].items()}}))
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--haver-data',type=Path,required=True);p.add_argument('--source-commit',required=True)
    p.add_argument('--output',type=Path,default=DEST)
    a=p.parse_args();state=refresh(a.haver_data,a.source_commit,a.output)
    # Partial outputs still deploy with visible warnings; the workflow separately flags them.
    raise SystemExit(0 if all(not c['failed'] for c in state['components'].values()) else 2)
