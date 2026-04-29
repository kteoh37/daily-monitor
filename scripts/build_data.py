"""
Build per-panel JSON snapshots for the Daily Market Monitor dashboard.

Reads daily series from a local clone of the haver-data repo and writes one
JSON file per panel into public/data/. Each row carries the latest level, 1d /
5d / 21d change, 5y rolling z-score, and the trailing-5y daily history for a
sparkline.

Usage:
    python scripts/build_data.py --haver-data ../haver-data
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


# Panel configs. `change_type` controls how chg_* fields are computed:
#   'pp'  -> simple difference (rates, yields, BEI in % p.a.)
#   'pct' -> percentage change (FX, equities, commodity indices, levels)
PANELS = {
    'yields': {
        'change_type': 'pp',
        'rows': [
            # (country, tenor_label, code)
            ('US', '3M',  'r111m3m@intdaily'),
            ('US', '1Y',  'r111m1y@intdaily'),
            ('US', '2Y',  'r111m2y@intdaily'),
            ('US', '5Y',  'r111m5y@intdaily'),
            ('US', '10Y', 'fcm10@daily'),
            ('US', '20Y', 'fcm20@daily'),
            ('US', '30Y', 'fcm30@daily'),
            ('JP', '3M',  'r158m3m@intdaily'),
            ('JP', '1Y',  'r158m1y@intdaily'),
            ('JP', '2Y',  'r158m2y@intdaily'),
            ('JP', '5Y',  'r158m5y@intdaily'),
            ('JP', '10Y', 'r158ga@intdaily'),
            ('JP', '20Y', 'r158gk@intdaily'),
            ('JP', '30Y', 'r158gt@intdaily'),
            ('DE', '3M',  'r134e3m@intdaily'),
            ('DE', '1Y',  'r134m1y@intdaily'),
            ('DE', '2Y',  'r134m2y@intdaily'),
            ('DE', '5Y',  'r134m5y@intdaily'),
            ('DE', '10Y', 'r134ma@intdaily'),
            ('DE', '20Y', 'r134mk@intdaily'),
            ('DE', '30Y', 'r134mt@intdaily'),
            ('FR', '3M',  'r132m3m@intdaily'),
            ('FR', '1Y',  'r132m1y@intdaily'),
            ('FR', '2Y',  'r132m2y@intdaily'),
            ('FR', '5Y',  'r132m5y@intdaily'),
            ('FR', '10Y', 'r132ma@intdaily'),
            ('FR', '20Y', 'r132mk@intdaily'),
            ('FR', '30Y', 'r132mt@intdaily'),
            ('IT', '3M',  'r136m3m@intdaily'),
            ('IT', '1Y',  'r136m1y@intdaily'),
            ('IT', '2Y',  'r136m2y@intdaily'),
            ('IT', '5Y',  'r136m5y@intdaily'),
            ('IT', '10Y', 'r136ma@intdaily'),
            ('IT', '20Y', 'r136mk@intdaily'),
            ('IT', '30Y', 'r136mt@intdaily'),
            ('UK', '3M',  't112d3m@intdaily'),
            ('UK', '1Y',  'r112m1y@intdaily'),
            ('UK', '2Y',  'r112m2y@intdaily'),
            ('UK', '5Y',  'r112m5y@intdaily'),
            ('UK', '10Y', 'r112ma@intdaily'),
            ('UK', '20Y', 'r112mk@intdaily'),
            ('UK', '30Y', 'r112mt@intdaily'),
            ('CA', '3M',  'r156m3m@intdaily'),
            ('CA', '1Y',  'r156m1y@intdaily'),
            ('CA', '2Y',  'r156m2y@intdaily'),
            ('CA', '5Y',  'r156m5y@intdaily'),
            ('CA', '10Y', 'r156ma@intdaily'),
            ('CA', '20Y', 'r156mk@intdaily'),
            ('CA', '30Y', 'r156mt@intdaily'),
            ('KR', '3M',  'r542s3m@intdaily'),
            ('KR', '1Y',  'r542m1y@intdaily'),
            ('KR', '2Y',  'r542m2y@intdaily'),
            ('KR', '5Y',  'r542m5y@intdaily'),
            ('KR', '10Y', 'r542ma@intdaily'),
            ('KR', '20Y', 'r542mk@intdaily'),
            ('KR', '30Y', 'r542mt@intdaily'),
            ('AU', '3M',  'r193g3m@intdaily'),
            ('AU', '1Y',  'r193m1y@intdaily'),
            ('AU', '2Y',  'r193m2y@intdaily'),
            ('AU', '5Y',  'r193m5y@intdaily'),
            ('AU', '10Y', 'r193ma@intdaily'),
            ('AU', '20Y', 'r193mk@intdaily'),
            ('AU', '30Y', 'r193mt@intdaily'),
        ],
    },
    'breakevens': {
        'change_type': 'pp',
        'rows': [
            ('US', '10Y BEI',         'fin10@daily'),
            ('JP', '10Y BEI',         'r158fbv@intdaily'),
            ('DE', '10Y BEI',         'r134fbv@intdaily'),
            ('FR', '10Y BEI',         'r132fbv@intdaily'),
            ('UK', '10Y fwd infl*',   'r112yaa@intdaily'),  # proxy, not true BEI
            ('CA', '10Y BEI',         'r156fbv@intdaily'),
            ('AU', '10Y BEI',         'r193fbv@intdaily'),
            ('KR', '10Y BEI',         'r542fbv@intdaily'),
        ],
    },
    'fx': {
        'change_type': 'pct',
        'rows': [
            ('JP', 'JPY/USD',    'x111jpj@intdaily'),
            ('UK', 'GBP/USD',    'x111ukj@intdaily'),
            ('EA', 'EUR/USD',    'x111euj@intdaily'),
            ('CH', 'CHF/USD',    'x111chj@intdaily'),
            ('CA', 'CAD/USD',    'x111caj@intdaily'),
            ('AU', 'AUD/USD',    'x111auj@intdaily'),
            ('KR', 'KRW/USD',    'x111krj@intdaily'),
            ('US', 'WSJ Dollar', 'fxwsj@daily'),
        ],
    },
    'equities': {
        'change_type': 'pct',
        'rows': [
            ('US', 'S&P 500',         's111sp5@intdaily'),
            ('JP', 'Nikkei 225',      's158nka@intdaily'),
            ('DE', 'DAX',             's134dax@intdaily'),
            ('UK', 'FTSE All-Share',  's112fta@intdaily'),
            ('IT', 'FTSE MIB',        's136mbi@intdaily'),
            ('FR', 'CAC 40',          's132cac@intdaily'),
            ('CA', 'S&P/TSX',         's156toi@intdaily'),
            ('CH', 'SMI',             's146smi@intdaily'),
            ('AU', 'All Ordinaries',  's193aor@intdaily'),
            ('KR', 'KOSPI',           's542cex@intdaily'),
        ],
    },
    'volatility': {
        'change_type': 'pct',
        'rows': [
            ('US', 'VIX',           's111vix@intdaily'),
            ('DE', 'VDAX-NEW',      's134vdx@intdaily'),
            ('JP', 'Nikkei VI',     's158nkx@intdaily'),
            ('CH', 'VSMI',          's146vmi@intdaily'),
            ('CA', 'TSX 60 VIX',    's156sxc@intdaily'),
            ('KR', 'KOSPI 200 VI',  's542v2x@intdaily'),
        ],
    },
    'policy_rates': {
        'change_type': 'pp',
        'rows': [
            ('US', 'Fed funds tgt', 'r111rdt@intdaily'),
            ('JP', 'BoJ rate',      'r158tar@intdaily'),
            ('UK', 'BoE Bank Rate', 'r112rd@intdaily'),
            ('CH', 'SNB rate',      'r146l3t@intdaily'),
            ('CA', 'BoC tgt',       'r156dtr@intdaily'),
            ('AU', 'RBA cash',      'r193rtr@intdaily'),
            ('KR', 'BoK base',      'r542rd@intdaily'),
            ('EA', 'ECB MRO',       'r023rm@intdaily'),
        ],
    },
    'overnight_rates': {
        'change_type': 'pp',
        'rows': [
            ('US', 'OBFR',  'r111obr@intdaily'),
            ('JP', 'TONAR', 'r158rdu@intdaily'),
            ('UK', 'SONIA', 'r112los@intdaily'),
            ('CH', 'SARON', 'r146son@intdaily'),
            ('CA', 'CORRA', 'r156rr@intdaily'),
            ('KR', 'KOFR',  'r542ko@intdaily'),
        ],
    },
    'commodities_uncertainty': {
        'change_type': 'pct',
        'rows': [
            ('--', 'GSCI Crude Oil', 'gscl@daily'),
            ('--', 'GSCI Gold',      'gsgc@daily'),
            ('US', 'EPU index',      'sepuin@daily'),
            ('US', 'TPU index',      'stpui@daily'),
        ],
    },
}

# History window written into each row (for sparklines and re-computation client-side)
HISTORY_YEARS = 5

# Z-score window — trailing 5y daily observations (~252 * 5 = 1260)
ZSCORE_OBS = 252 * 5


def load_long_data(parquet_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(parquet_path)
    df = df[df['frequency'] == 'D'].copy()
    df['date'] = pd.to_datetime(df['date'])
    return df


def build_row(s: pd.Series, country: str, label: str, code: str, change_type: str) -> dict:
    """Compute summary stats and history window for a single series."""
    s = s.dropna().sort_index()
    if s.empty:
        return {
            'country': country, 'label': label, 'series': code,
            'latest_date': None, 'latest': None,
            'chg_1d': None, 'chg_5d': None, 'chg_21d': None,
            'z_5y': None, 'history': [],
        }

    last_date = s.index[-1]
    last_val = float(s.iloc[-1])

    def chg(window):
        if len(s) <= window:
            return None
        prev = s.iloc[-1 - window]
        if change_type == 'pp':
            return float(last_val - prev)
        # pct
        if prev == 0 or not np.isfinite(prev):
            return None
        return float((last_val / prev - 1) * 100)

    # 5y z-score
    tail = s.tail(ZSCORE_OBS)
    if len(tail) >= 60 and tail.std(ddof=0) > 0:
        z = float((last_val - tail.mean()) / tail.std(ddof=0))
        if not np.isfinite(z):
            z = None
    else:
        z = None

    # History — trailing HISTORY_YEARS of daily obs as [date_iso, value]
    cutoff = last_date - pd.DateOffset(years=HISTORY_YEARS)
    hist = s[s.index >= cutoff]
    history = [
        [d.strftime('%Y-%m-%d'), round(float(v), 6)]
        for d, v in hist.items()
        if np.isfinite(v)
    ]

    return {
        'country': country,
        'label': label,
        'series': code,
        'latest_date': last_date.strftime('%Y-%m-%d'),
        'latest': round(last_val, 6),
        'chg_1d': None if chg(1) is None else round(chg(1), 6),
        'chg_5d': None if chg(5) is None else round(chg(5), 6),
        'chg_21d': None if chg(21) is None else round(chg(21), 6),
        'z_5y': None if z is None else round(z, 4),
        'history': history,
    }


def build_panel(df: pd.DataFrame, panel_name: str, panel_cfg: dict) -> dict:
    rows = []
    for country, label, code in panel_cfg['rows']:
        sub = df[df['code'] == code]
        s = sub.set_index('date')['value'] if not sub.empty else pd.Series(dtype=float)
        rows.append(build_row(s, country, label, code, panel_cfg['change_type']))

    latest_dates = [r['latest_date'] for r in rows if r['latest_date']]
    vintage = max(latest_dates) if latest_dates else None

    return {
        'panel': panel_name,
        'change_type': panel_cfg['change_type'],
        'vintage': vintage,
        'rows': rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--haver-data', required=True, help='Path to local haver-data clone')
    parser.add_argument('--out-dir', default='public/data', help='Output directory for JSON panels')
    args = parser.parse_args()

    parquet_path = Path(args.haver_data) / 'data' / 'data.parquet'
    if not parquet_path.exists():
        raise FileNotFoundError(f'Parquet not found: {parquet_path}')

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f'Loading {parquet_path} ...')
    df = load_long_data(parquet_path)
    print(f'  {len(df):,} daily obs across {df["code"].nunique()} series')

    manifest = {'panels': [], 'vintage': None}

    for name, cfg in PANELS.items():
        panel = build_panel(df, name, cfg)
        out_path = out_dir / f'{name}.json'
        with open(out_path, 'w') as f:
            json.dump(panel, f, separators=(',', ':'))
        n_rows = len(panel['rows'])
        n_filled = sum(1 for r in panel['rows'] if r['latest'] is not None)
        size_kb = out_path.stat().st_size / 1024
        print(f'  {name:25s} {n_filled}/{n_rows} rows  vintage {panel["vintage"]}  ({size_kb:,.1f} KB)')
        manifest['panels'].append({
            'name': name,
            'vintage': panel['vintage'],
            'n_rows': n_rows,
            'n_filled': n_filled,
        })

    panel_vintages = [p['vintage'] for p in manifest['panels'] if p['vintage']]
    manifest['vintage'] = max(panel_vintages) if panel_vintages else None
    with open(out_dir / 'manifest.json', 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f'\nWrote {len(PANELS)} panels + manifest to {out_dir}')
    print(f'Overall vintage: {manifest["vintage"]}')


if __name__ == '__main__':
    main()
