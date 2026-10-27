#!/usr/bin/env python3
"""Download official Japan MOF weekly ITS data and refresh cumulative charts."""
import argparse
import csv
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SOURCE = 'https://www.mof.go.jp/policy/international_policy/reference/itn_transactions_in_securities/week.csv'
INDEX = 'https://www.mof.go.jp/english/policy/international_policy/reference/itn_transactions_in_securities/index.htm'
# Zero-based columns in the verified 23-column MOF historical weekly CSV.
COLUMNS = {'resident_equity': 3, 'resident_long_term_debt': 6,
           'resident_short_term_debt': 10, 'nonresident_equity': 14,
           'nonresident_long_term_debt': 17, 'nonresident_short_term_debt': 21}
PERIOD = re.compile(r'^(\d{4})\.(\d{1,2})\.(\d{1,2})[~〜～](?:(\d{4})\.)?(\d{1,2})\.(\d{1,2})$')


def parse_csv(raw):
    """Fail closed on layout changes, missing values, duplicates, or weekly gaps."""
    for encoding in ('utf-8-sig', 'cp932'):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            pass
    else:
        raise ValueError('CSV is neither UTF-8 nor CP932')
    rows = list(csv.reader(io.StringIO(text)))
    if 'Unit: 100 million Yen' not in text or 'Portfolio Investment Assets' not in text or 'Portfolio Investment Liabilities' not in text:
        raise ValueError('MOF units or portfolio headers changed; review source')
    header = next((r for r in rows if len(r) == 23 and r[1].strip() == 'Acquisition'), None)
    category = next((r for r in rows if len(r) == 23 and r[1].strip() == 'Equity and investment fund shares'), None)
    if not header or not category:
        raise ValueError('Expected 23-column English header absent')
    for offset in (0, 11):
        for col, label in ((1, 'Equity and investment fund shares'), (4, 'Long-term debt securities'), (8, 'Short-term debt securities')):
            if category[col + offset].strip() != label or header[col + offset:col + offset + 3] != ['Acquisition', 'Disposition', 'Net']:
                raise ValueError('MOF column layout changed')
    observations = []
    for row in rows:
        if not row:
            continue
        period = re.sub(r'\s+', '', unicodedata.normalize('NFKC', row[0]))
        if not re.match(r'^\d{4}\.', period):
            continue
        match = PERIOD.fullmatch(period)
        if not match or len(row) != 23:
            raise ValueError('Unexpected data row: ' + repr(row[0]))
        y, m, d, ey, em, ed = match.groups()
        start = date(int(y), int(m), int(d))
        end = date(int(ey or y), int(em), int(ed))
        if not ey and end < start:
            end = end.replace(year=end.year + 1)
        if (end - start).days != 6:
            raise ValueError('Unexpected weekly interval: ' + period)
        item = {'week_start': start.isoformat(), 'week_end': end.isoformat()}
        for key, col in COLUMNS.items():
            value = unicodedata.normalize('NFKC', row[col]).strip().replace(',', '')
            if not re.fullmatch(r'[+-]?\d+', value):
                raise ValueError(f'Missing/noninteger {key} for {end}: {value!r}')
            item[key] = int(value)
            # MOF rounds acquisition, disposition, and net separately.
            acquisition = int(row[col - 2].replace(',', '').strip())
            disposition = int(row[col - 1].replace(',', '').strip())
            if abs(acquisition - disposition - item[key]) > 1:
                raise ValueError(f'Net flow arithmetic mismatch for {key} at {end}')
        observations.append(item)
    if not observations:
        raise ValueError('No weekly observations found')
    observations.sort(key=lambda x: x['week_end'])
    for previous, current in zip(observations, observations[1:]):
        if (date.fromisoformat(current['week_end']) - date.fromisoformat(previous['week_end'])).days != 7:
            raise ValueError('Duplicate or missing weekly observation')
    update = re.search(r'Final Update[^\r\n]*', text)
    return observations, update.group(0).strip().rstrip(',"') if update else 'Not supplied'


def fetch(attempts=4):
    for attempt in range(attempts):
        try:
            request = Request(SOURCE, headers={'User-Agent': 'JapanMOFPortfolioChart/1.0', 'Cache-Control': 'no-cache'})
            with urlopen(request, timeout=60) as response:
                if not response.url.startswith('https://www.mof.go.jp/'):
                    raise ValueError('Unexpected redirect away from official MOF host')
                raw = response.read(5_000_001)
                if len(raw) > 5_000_000:
                    raise ValueError('Download exceeds 5 MB safety limit')
                return raw
        except HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
        except (URLError, TimeoutError, OSError):
            if attempt == attempts - 1:
                raise
        logging.warning('Download failed; retrying in %s seconds', 2 ** attempt)
        time.sleep(2 ** attempt)


def atomic_write(path, data):
    """Write beside destination and atomically replace; never truncate old output."""
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def compare(old, new):
    before = {r['week_end']: r for r in old}
    after = {r['week_end']: r for r in new}
    missing = sorted(set(before) - set(after))
    if missing:
        raise ValueError('Download dropped previously observed weeks: ' + ', '.join(missing[:3]))
    return sorted(set(after) - set(before)), sorted(k for k in before if before[k] != after[k])


def cumulative(rows, baseline):
    if baseline < date(2014, 1, 1):
        raise ValueError('Baseline must be 2014 or later (classification break)')
    selected = [r for r in rows if date.fromisoformat(r['week_end']) >= baseline]
    if not selected or date.fromisoformat(selected[0]['week_start']) > baseline + timedelta(days=6):
        raise ValueError('Source does not cover requested baseline')
    if not any(date.fromisoformat(r['week_end']) < baseline for r in rows):
        raise ValueError('Need observations before baseline to establish coverage')
    totals = dict.fromkeys(COLUMNS, 0)
    result = [{'week_end': (baseline - timedelta(days=1)).isoformat(), **totals}]
    for row in selected:
        for key in totals:
            totals[key] += row[key]
        result.append({'week_end': row['week_end'], **{k: v / 10000 for k, v in totals.items()}})
    return result


def csv_bytes(rows, fields):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def chart(series, baseline, destination):
    os.environ.setdefault('MPLCONFIGDIR', str(destination / '.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.7), sharex=True)
    dates = [date.fromisoformat(r['week_end']) for r in series]
    colors = ['#0062AF', '#D24A43', '#29916D']
    for ax, prefix, title in zip(axes, ('resident', 'nonresident'),
                               ('Japanese residents: foreign securities', 'Nonresidents: Japanese securities')):
        for asset, label, color in zip(('long_term_debt', 'short_term_debt', 'equity'),
                                      ('Long-term debt', 'Short-term debt', 'Equity and investment fund shares'), colors):
            ax.plot(dates, [r[prefix + '_' + asset] for r in series], label=label, color=color, linewidth=2)
        ax.axhline(0, color='#555555', linewidth=.7)
        ax.set_title(title, loc='left', fontsize=12, pad=15)
        ax.set_ylabel('Cumulative net purchases (¥ trillion)')
        ax.grid(axis='y', color='#e5e5e5')
        ax.spines[['top', 'right']].set_visible(False)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6 if (dates[-1] - dates[0]).days > 1096 else 3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.tick_params(axis='x', rotation=25)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.5, .13), ncol=3, frameon=False)
    fig.suptitle('Japan: cumulative portfolio flows', x=.065, ha='left', fontsize=17, fontweight='bold')
    fig.text(.065, .88, f'From {baseline:%d %B %Y}; latest week ending {dates[-1]:%d %B %Y}', fontsize=10)
    fig.text(.065, .075, 'Source: Ministry of Finance, Japan, International Transactions in Securities (weekly); calculations from official data.', fontsize=8)
    fig.text(.065, .044, 'Designated major investors. Positive = net purchases; negative = net sales. Full weeks allocated by week-end date.', fontsize=8)
    fig.subplots_adjust(left=.065, right=.985, top=.80, bottom=.29, wspace=.23)
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=180, facecolor='white')
    plt.close(fig)
    return buffer.getvalue()

