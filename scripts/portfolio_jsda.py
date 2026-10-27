"""Validated JSDA calculations adapted from the portfolio tracker; no network/export state."""
import io
import json
import logging
import os
from pathlib import Path
SECTORS = {'CLB': 'City banks & long-term credit banks', 'RB': 'Regional banks', 'TB': 'Trust banks', 'LI': 'Life & non-life insurers', 'F': 'Foreign investors', '': 'Overall total (all investor categories)'}
MATURITIES = {'S': 'Super-long-term', 'L': 'Long-term', 'M': 'Medium-term'}

def calculate(raw_data, raw_metadata, window=5):
    import pandas as pd
    import numpy as np
    if not 1 <= window <= 60:
        raise ValueError('Rolling window must be between 1 and 60 months')
    data = pd.read_parquet(io.BytesIO(raw_data))
    metadata = pd.read_parquet(io.BytesIO(raw_metadata))
    if not isinstance(data.index, pd.DatetimeIndex) or data.index.has_duplicates or not data.index.is_monotonic_increasing:
        raise ValueError('Monthly observations must have a unique, ascending DatetimeIndex')
    if data.index.tz is not None or not data.index.is_month_end.all():
        raise ValueError('Expected timezone-free month-end observation dates')
    data.columns = data.columns.str.upper()
    if data.columns.has_duplicates:
        raise ValueError('Duplicate series codes after case normalization')
    metadata = metadata.copy()
    metadata['Series Code'] = metadata['Series Code'].str.upper()
    if metadata['Series Code'].duplicated().any():
        raise ValueError('Duplicate metadata series codes')
    metadata = metadata.set_index('Series Code')
    # Reindex to calendar months BEFORE rolling: a missing month must not shorten the window.
    index = pd.date_range(data.index.min(), data.index.max(), freq=pd.offsets.MonthEnd())
    data = data.reindex(index)
    parts = []
    for sector, label in SECTORS.items():
        for maturity, maturity_label in MATURITIES.items():
            purchase = f'GB{maturity}{sector}P@JAPAN'
            sale = f'GB{maturity}{sector}S@JAPAN'
            for code, action in ((purchase, 'purchas'), (sale, 'sales')):
                if code not in data or code not in metadata.index:
                    raise ValueError('Missing required series: ' + code)
                row = metadata.loc[code]
                description = str(row['Series Name']).lower()
                if (str(row['shortsource']).upper() != 'JSDA' or str(row['frequency']).upper() != 'M'
                        or '100 mil.yen' not in description or action not in description):
                    raise ValueError('Unexpected source/frequency/units/transaction metadata for ' + code)
            gross = data[[purchase, sale]].astype(float)
            if (gross < 0).any().any() or np.isinf(gross.to_numpy()).any():
                raise ValueError('Negative or infinite gross transaction amount')
            parts.append(pd.DataFrame({'month': index, 'sector': label, 'maturity': maturity_label,
                'purchases_100million_yen': gross[purchase].to_numpy(),
                'sales_100million_yen': gross[sale].to_numpy(),
                'net_100million_yen': (gross[purchase] - gross[sale]).to_numpy()}))
    monthly = pd.concat(parts, ignore_index=True)
    # Sum the three coupon-bearing maturity classes, requiring all three observations.
    total = monthly.groupby(['month', 'sector'])[['purchases_100million_yen', 'sales_100million_yen', 'net_100million_yen']].sum(min_count=3).reset_index()
    total['maturity'] = 'All coupon-bearing JGBs'
    monthly = pd.concat([monthly, total], ignore_index=True).sort_values(['sector', 'maturity', 'month'])
    monthly['rolling_net_trillion_yen'] = monthly.groupby(['sector', 'maturity'])['net_100million_yen'].transform(
        lambda s: s.rolling(window, min_periods=window).sum() / 10000)
    monthly['window_months'] = window
    # Remove leading/trailing padded rows shared by every source series, retaining internal gaps.
    valid = monthly.loc[monthly.net_100million_yen.notna(), 'month']
    if valid.empty:
        raise ValueError('No JSDA observations found')
    return monthly[monthly.month.between(valid.min(), valid.max())].reset_index(drop=True)


def outputs(frame, start, window, output):
    import pandas as pd
    os.environ.setdefault('MPLCONFIGDIR', str(output / '.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    start = pd.Timestamp(start)
    visible = frame[frame.month >= start].copy()
    if visible.empty:
        raise ValueError('Display start is after the latest JSDA month')
    # Refuse incomplete displayed windows rather than silently plotting shorter sums.
    if visible['rolling_net_trillion_yen'].isna().any():
        raise ValueError('Missing data in a displayed rolling window. Supply complete history or choose a later --baseline.')
    latest = visible.month.max()
    if latest > pd.Timestamp.now().normalize():
        raise ValueError('JSDA source has a future observation')
    if (pd.Timestamp.now().normalize() - latest).days > 75:
        logging.warning('JSDA latest month is more than 75 days old; refresh the repository snapshot')
    fig, axes = plt.subplots(3, 2, figsize=(13, 10), sharex=True)
    labels = list(SECTORS.values())
    series = [('All coupon-bearing JGBs', '#1f4e79', 2.5),
              ('Super-long-term', '#c00000', 1.3), ('Long-term', '#548235', 1.3),
              ('Medium-term', '#7030a0', 1.3)]
    for i, (ax, sector) in enumerate(zip(axes.flat, labels)):
        group = visible[visible.sector.eq(sector)]
        for maturity, color, width in series:
            sub = group[group.maturity.eq(maturity)].sort_values('month')
            ax.plot(sub.month, sub.rolling_net_trillion_yen, color=color, lw=width, label=maturity)
        ax.set_title(sector, loc='left', fontsize=11)
        ax.axhline(0, color='#666666', lw=.6)
        ax.grid(axis='y', color='#e5e5e5')
        ax.spines[['top', 'right']].set_visible(False)
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.tick_params(axis='x', labelrotation=25)
        ax.set_ylabel('¥ trillion')
    title = f'Japan: rolling {window}-month net purchases of coupon-bearing JGBs'
    subtitle = f'Purchases minus sales; window includes the indicated month and preceding {window - 1} months. Latest: {latest:%B %Y}.'
    source = 'Source: Japan Securities Dealers Association (JSDA), via Haver Analytics and kteoh37/haver-dataset; calculations.'
    fig.suptitle(title, x=.07, ha='left', fontsize=16, fontweight='bold')
    fig.text(.07, .94, subtitle, fontsize=9)
    handles, legends = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, legends, loc='lower center', bbox_to_anchor=(.5, .055), ncol=4, frameon=False)
    fig.text(.07, .035, source, fontsize=8)
    fig.text(.07, .017, 'Nominal/face value. Excludes Treasury bills and discount bonds. Overall total includes categories outside the five sectors shown.', fontsize=8)
    fig.subplots_adjust(top=.89, bottom=.15, left=.07, right=.98, hspace=.32, wspace=.20)
    png = io.BytesIO()
    fig.savefig(png, format='png', dpi=180)
    plt.close(fig)
    return visible, png.getvalue()
