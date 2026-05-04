import { useEffect, useMemo, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts'
import { useDarkMode } from '../lib/useDarkMode.jsx'
import { getTheme, getTooltipStyle } from '../lib/chartTheme.js'

const PANEL_KEYS = [
  'yields', 'breakevens', 'fx', 'equities', 'volatility', 'policy_rates', 'commodities_uncertainty',
]

const PANEL_LABELS = {
  yields:                  'Sovereign yields',
  breakevens:              'Breakeven inflation',
  fx:                      'FX (vs USD)',
  equities:                'Equity indices',
  volatility:              'Volatility indices',
  policy_rates:            'Policy rates',
  commodities_uncertainty: 'Commodities & uncertainty',
}

const COUNTRY_LABELS = {
  US: 'United States', JP: 'Japan',     DE: 'Germany',  FR: 'France',
  IT: 'Italy',         UK: 'United Kingdom', CA: 'Canada',  EA: 'Euro Area',
  CH: 'Switzerland',   KR: 'Korea',     AU: 'Australia', CN: 'China',
}

const COUNTRY_ORDER = ['US', 'JP', 'DE', 'FR', 'IT', 'UK', 'CA', 'EA', 'CH', 'KR', 'AU', 'CN']

const PALETTE = [
  '#6366f1', '#0891b2', '#10b981', '#f59e0b', '#ef4444',
  '#8b5cf6', '#ec4899', '#14b8a6', '#84cc16', '#f97316', '#06b6d4',
]

const TENOR_ORDER = ['3M', '1Y', '2Y', '5Y', '10Y', '20Y', '30Y']

const RANGE_PRESETS = [
  { id: '1M',  label: '1M',  days: 30 },
  { id: '3M',  label: '3M',  days: 91 },
  { id: '6M',  label: '6M',  days: 182 },
  { id: 'YTD', label: 'YTD', days: null },
  { id: '1Y',  label: '1Y',  days: 365 },
  { id: '2Y',  label: '2Y',  days: 730 },
  { id: '5Y',  label: '5Y',  days: 1825 },
  { id: 'MAX', label: 'MAX', days: null },
]

const SPREAD_FAMILIES = {
  curve_slope: {
    label: 'Curve slope (10Y − 2Y)',
    yLabel: 'pp',
    countries: ['US', 'JP', 'DE', 'FR', 'IT', 'UK', 'CA', 'KR', 'AU', 'CN'],
    build: (panels, c) => makeSpread(
      findYield(panels, c, '10Y'),
      findYield(panels, c, '2Y'),
    ),
  },
  vs_us: {
    label: 'Sovereign 10Y vs US (XX − US)',
    yLabel: 'pp',
    countries: ['JP', 'DE', 'FR', 'IT', 'UK', 'CA', 'KR', 'AU', 'CN'],
    build: (panels, c) => makeSpread(
      findYield(panels, c, '10Y'),
      findYield(panels, 'US', '10Y'),
    ),
  },
  real_rate: {
    label: 'Ex-ante 10Y real rate (nominal − BEI)',
    yLabel: '% p.a.',
    countries: ['US', 'JP', 'DE', 'FR', 'CA', 'KR', 'AU'],
    build: (panels, c) => makeSpread(
      findYield(panels, c, '10Y'),
      findBEI(panels, c),
    ),
  },
  yield_curve: {
    label: 'Yield curves (snapshot)',
    yLabel: '% p.a.',
    isYieldCurve: true,
    countries: ['US', 'JP', 'DE', 'FR', 'IT', 'UK', 'CA', 'KR', 'AU', 'CN'],
  },
}

// Tenor → years (for x-axis spacing on the yield curve chart)
const MATURITY_YEARS = { '3M': 0.25, '1Y': 1, '2Y': 2, '5Y': 5, '10Y': 10, '20Y': 20, '30Y': 30 }

// Last value at-or-before a given date, or last value overall if dateStr is null.
function valueAtOrBefore(history, dateStr) {
  if (!history?.length) return null
  if (!dateStr) return history[history.length - 1][1]
  let last = null
  for (const [d, v] of history) {
    if (d <= dateStr) last = v
    else break
  }
  return last
}

// The most recent date the series has any observation for.
function lastDateOf(history) {
  return history?.length ? history[history.length - 1][0] : null
}

function findYield(panels, country, tenor) {
  return panels.yields?.rows.find(r => r.country === country && r.label === tenor)?.history ?? null
}

function findBEI(panels, country) {
  return panels.breakevens?.rows.find(r => r.country === country)?.history ?? null
}

// Date-aligned a − b on intersection of dates
function makeSpread(a, b) {
  if (!a || !b) return null
  const m = new Map()
  for (const [d, v] of b) m.set(d, v)
  const out = []
  for (const [d, v] of a) {
    const bv = m.get(d)
    if (Number.isFinite(v) && Number.isFinite(bv)) out.push([d, v - bv])
  }
  return out
}

function fetchPanel(key, base) {
  return fetch(`${base}data/${key}.json`).then(r => {
    if (!r.ok) throw new Error(`Failed to load ${key}.json`)
    return r.json()
  })
}

function cutoffFor(rangeId, lastDateStr) {
  if (!lastDateStr || rangeId === 'MAX') return null
  if (rangeId === 'YTD') return `${lastDateStr.slice(0, 4)}-01-01`
  const preset = RANGE_PRESETS.find(p => p.id === rangeId)
  if (!preset?.days) return null
  const d = new Date(lastDateStr)
  d.setDate(d.getDate() - preset.days)
  return d.toISOString().slice(0, 10)
}

// ----------------------------------------------------------------------------

export default function ChartsPanel() {
  const [panels, setPanels]         = useState({})
  const [loading, setLoading]       = useState(true)
  const [mode, setMode]             = useState('country') // 'country' | 'theme' | 'spreads'
  const [country, setCountry]       = useState('JP')
  const [theme, setTheme]           = useState('yields')
  const [yieldTenor, setYieldTenor] = useState('10Y')
  const [spreadFamily, setSpreadFamily] = useState('curve_slope')
  const [range, setRange]           = useState('5Y')
  // Per-theme series selection. Key = theme name, value = Set<seriesCode>.
  // Absent key (or null) means "all series visible".
  const [selectedByTheme, setSelectedByTheme] = useState({})

  useEffect(() => {
    const base = import.meta.env.BASE_URL
    Promise.all(PANEL_KEYS.map(k => fetchPanel(k, base)))
      .then(results => {
        const obj = {}
        PANEL_KEYS.forEach((k, i) => { obj[k] = results[i] })
        setPanels(obj)
        setLoading(false)
      })
      .catch(err => { console.error(err); setLoading(false) })
  }, [])

  // Most recent date observed across all loaded panels — anchors the date range cutoff.
  // Must run unconditionally before the loading early-return to keep hook order stable.
  const latestDate = useMemo(() => {
    let max = null
    for (const k of PANEL_KEYS) {
      for (const r of panels[k]?.rows ?? []) {
        if (r.latest_date && (!max || r.latest_date > max)) max = r.latest_date
      }
    }
    return max
  }, [panels])

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-500 text-sm">Loading…</div>

  const availableCountries = COUNTRY_ORDER.filter(c =>
    PANEL_KEYS.some(k => panels[k]?.rows.some(r => r.country === c))
  )

  const cutoff = cutoffFor(range, latestDate)

  return (
    <div className="py-4 space-y-4">

      <div className="flex flex-wrap items-end gap-3 px-1">
        <ModeToggle mode={mode} onChange={setMode} />

        {mode === 'country' && (
          <Selector label="Country" value={country} onChange={setCountry}
            options={availableCountries.map(c => [c, COUNTRY_LABELS[c] ?? c])} />
        )}

        {mode === 'theme' && (
          <>
            <Selector label="Theme" value={theme} onChange={setTheme}
              options={PANEL_KEYS.map(k => [k, PANEL_LABELS[k]])} />
            {theme === 'yields' && (
              <Selector label="Tenor" value={yieldTenor} onChange={setYieldTenor}
                options={TENOR_ORDER.map(t => [t, t])} />
            )}
          </>
        )}

        {mode === 'spreads' && (
          <Selector label="Spread" value={spreadFamily} onChange={setSpreadFamily}
            options={Object.entries(SPREAD_FAMILIES).map(([k, v]) => [k, v.label])} />
        )}

        <RangePicker value={range} onChange={setRange} />
      </div>

      {mode === 'country' && <ByCountryView panels={panels} country={country} cutoff={cutoff} range={range} />}
      {mode === 'theme'   && (
        <ByThemeView
          panels={panels}
          theme={theme}
          yieldTenor={yieldTenor}
          cutoff={cutoff}
          range={range}
          selectedSet={selectedByTheme[theme] ?? null}
          onToggleSeries={(code, allCodes) => {
            setSelectedByTheme(prev => {
              const cur = prev[theme] ?? new Set(allCodes)
              const next = new Set(cur)
              if (next.has(code)) next.delete(code); else next.add(code)
              return { ...prev, [theme]: next }
            })
          }}
          onSelectAll={(allCodes) => setSelectedByTheme(prev => ({ ...prev, [theme]: new Set(allCodes) }))}
          onClearAll={() => setSelectedByTheme(prev => ({ ...prev, [theme]: new Set() }))}
        />
      )}
      {mode === 'spreads' && <SpreadsView   panels={panels} family={spreadFamily} cutoff={cutoff} range={range} />}
    </div>
  )
}

// ----------------------------------------------------------------------------

function ModeToggle({ mode, onChange }) {
  const opts = [
    ['country', 'By country'],
    ['theme',   'By theme'],
    ['spreads', 'Spreads'],
  ]
  return (
    <div className="flex items-center gap-1 rounded-lg bg-slate-100 dark:bg-slate-800 p-1">
      {opts.map(([id, lbl]) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
            mode === id ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white' : 'text-slate-600 dark:text-slate-400'
          }`}
        >{lbl}</button>
      ))}
    </div>
  )
}

function Selector({ label, value, onChange, options }) {
  return (
    <label className="flex items-center gap-2 text-xs text-slate-500">
      {label}
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="text-xs rounded px-2 py-1 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 outline-none cursor-pointer"
      >
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  )
}

function RangePicker({ value, onChange }) {
  return (
    <div className="flex items-center gap-1 ml-auto">
      <span className="text-xs text-slate-500 mr-1">Range</span>
      <div className="flex items-center rounded-lg bg-slate-100 dark:bg-slate-800 p-0.5">
        {RANGE_PRESETS.map(p => (
          <button
            key={p.id}
            onClick={() => onChange(p.id)}
            className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${
              value === p.id ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white' : 'text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >{p.label}</button>
        ))}
      </div>
    </div>
  )
}

// ----------------------------------------------------------------------------

function ByCountryView({ panels, country, cutoff, range }) {
  const blocks = []
  const hasYields = !!panels.yields?.rows.some(r => r.country === country)

  const yieldRows = panels.yields?.rows.filter(r => r.country === country) ?? []
  if (yieldRows.length) {
    const sorted = [...yieldRows].sort(
      (a, b) => TENOR_ORDER.indexOf(a.label) - TENOR_ORDER.indexOf(b.label)
    )
    blocks.push({
      key: 'yields',
      title: `${COUNTRY_LABELS[country] ?? country} — Sovereign yields`,
      yLabel: '% p.a.',
      series: sorted.map((r, i) => ({
        key: r.label,
        history: r.history,
        color: PALETTE[i % PALETTE.length],
      })),
    })
  }

  const singleLinePanels = [
    ['breakevens',   '10Y BEI',          '% p.a.'],
    ['fx',           'FX (vs USD)',      ''],
    ['equities',     'Equity index',     'level'],
    ['volatility',   'Volatility index', 'index'],
    ['policy_rates', 'Policy rate',      '% p.a.'],
  ]

  for (const [key, title, yLabel] of singleLinePanels) {
    const row = panels[key]?.rows.find(r => r.country === country)
    if (row && row.history?.length) {
      blocks.push({
        key,
        title: `${COUNTRY_LABELS[country] ?? country} — ${title} (${row.label})`,
        yLabel,
        series: [{ key: row.label, history: row.history, color: PALETTE[0] }],
      })
    }
  }

  if (!blocks.length) return (
    <div className="panel p-6 text-sm text-slate-500">No series available for {country}.</div>
  )

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {hasYields && (
        <YieldCurveChart
          panels={panels}
          countries={[country]}
          title={`${COUNTRY_LABELS[country] ?? country} — Yield curve`}
          yLabel="% p.a."
          comparisonCutoff={cutoff}
          rangeLabel={range}
          height={240}
        />
      )}
      {blocks.map(b => <ChartCard key={b.key} {...b} cutoff={cutoff} />)}
    </div>
  )
}

// ----------------------------------------------------------------------------

function ByThemeView({ panels, theme, yieldTenor, cutoff, range, selectedSet, onToggleSeries, onSelectAll, onClearAll }) {
  const panel = panels[theme]
  if (!panel) return <div className="panel p-6 text-sm text-slate-500">No data for {theme}.</div>

  let rows = panel.rows
  if (theme === 'yields') {
    rows = rows.filter(r => r.label === yieldTenor)
  }
  rows = rows.filter(r => r.history?.length)

  if (!rows.length) return <div className="panel p-6 text-sm text-slate-500">No matching series.</div>

  // Stable per-row identity = the underlying Haver code (unique within the panel)
  const allCodes = rows.map(r => r.series)
  const isSelected = (code) => selectedSet === null ? true : selectedSet.has(code)

  // Each row gets a fixed color based on its position, regardless of selection state,
  // so toggling a series off doesn't recolor the others.
  const decorated = rows.map((r, i) => ({
    ...r,
    color: PALETTE[i % PALETTE.length],
    selected: isSelected(r.series),
  }))

  const visible = decorated.filter(r => r.selected)

  const series = visible.map(r => ({
    key: `${r.country} ${r.label}`,
    history: r.history,
    color: r.color,
  }))

  const title = theme === 'yields'
    ? `${PANEL_LABELS[theme]} — ${yieldTenor} across countries`
    : `${PANEL_LABELS[theme]} — across countries`

  const yLabelMap = {
    yields: '% p.a.', breakevens: '% p.a.', policy_rates: '% p.a.',
    fx: '', equities: 'level', volatility: 'index', commodities_uncertainty: 'level',
  }

  const picker = (
    <SeriesPicker
      rows={decorated}
      onToggle={(code) => onToggleSeries(code, allCodes)}
      onAll={() => onSelectAll(allCodes)}
      onClear={onClearAll}
    />
  )

  if (theme === 'yields') {
    const curveCountries = visible.map(r => r.country)
    return (
      <div className="space-y-4">
        {picker}
        {series.length
          ? <ChartCard title={title} yLabel={yLabelMap[theme]} series={series} cutoff={cutoff} tall />
          : <div className="panel p-6 text-sm text-slate-500">No series selected.</div>}
        {curveCountries.length > 0 && (
          <YieldCurveChart
            panels={panels}
            countries={curveCountries}
            title="Sovereign yields — curves across countries"
            yLabel="% p.a."
            comparisonCutoff={cutoff}
            rangeLabel={range}
          />
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {picker}
      {series.length
        ? <ChartCard title={title} yLabel={yLabelMap[theme]} series={series} cutoff={cutoff} tall />
        : <div className="panel p-6 text-sm text-slate-500">No series selected.</div>}
    </div>
  )
}

// Strip of toggle chips — one per row, color-coded to match its line.
function SeriesPicker({ rows, onToggle, onAll, onClear }) {
  return (
    <div className="panel p-3 flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-slate-500 mr-1">Series</span>
      {rows.map(r => (
        <button
          key={r.series}
          onClick={() => onToggle(r.series)}
          className={`text-xs px-2 py-0.5 rounded border transition-colors flex items-center gap-1.5 ${
            r.selected
              ? 'bg-white text-slate-800 border-slate-300 shadow-sm dark:bg-slate-800 dark:text-slate-100 dark:border-slate-600'
              : 'bg-transparent text-slate-400 border-slate-200 dark:text-slate-600 dark:border-slate-700 hover:text-slate-600 dark:hover:text-slate-300'
          }`}
          title={`${r.country} · ${r.label}${r.selected ? '' : ' (hidden)'}`}
        >
          <span
            className="inline-block w-2 h-2 rounded-full shrink-0"
            style={{ background: r.selected ? r.color : 'transparent', border: `1.5px solid ${r.color}` }}
          />
          <span className="font-medium">{r.country}</span>
          <span className="text-slate-400 dark:text-slate-500">{r.label}</span>
        </button>
      ))}
      <span className="ml-auto flex gap-1">
        <button onClick={onAll} className="text-xs px-2 py-0.5 rounded text-slate-500 hover:text-slate-800 dark:hover:text-slate-200">All</button>
        <button onClick={onClear} className="text-xs px-2 py-0.5 rounded text-slate-500 hover:text-slate-800 dark:hover:text-slate-200">Clear</button>
      </span>
    </div>
  )
}

// ----------------------------------------------------------------------------

function SpreadsView({ panels, family, cutoff, range }) {
  const cfg = SPREAD_FAMILIES[family]

  if (cfg.isYieldCurve) {
    return (
      <YieldCurveChart
        panels={panels}
        countries={cfg.countries}
        title={cfg.label}
        yLabel={cfg.yLabel}
        comparisonCutoff={cutoff}
        rangeLabel={range}
      />
    )
  }

  const series = cfg.countries
    .map(c => ({ country: c, history: cfg.build(panels, c) }))
    .filter(s => s.history && s.history.length)
    .map((s, i) => ({
      key: s.country,
      history: s.history,
      color: PALETTE[i % PALETTE.length],
    }))

  if (!series.length) return <div className="panel p-6 text-sm text-slate-500">No series available for this spread.</div>

  return (
    <ChartCard
      title={cfg.label}
      yLabel={cfg.yLabel}
      series={series}
      cutoff={cutoff}
      tall
      zeroLine
    />
  )
}

// ----------------------------------------------------------------------------
// Yield curve snapshot: x-axis = maturity in years, y-axis = yield.
// One line per country (current). Optionally a dashed comparison line per
// country when the range picker is set to anything other than MAX.

function YieldCurveChart({
  panels,
  countries,
  title = 'Yield curves (snapshot)',
  yLabel = '% p.a.',
  comparisonCutoff,
  rangeLabel,
  height = 460,
}) {
  const { isDark } = useDarkMode()
  const t = getTheme(isDark)

  const { plotData, countriesPresent, latestDate, comparisonDate } = useMemo(() => {
    if (!panels.yields) return { plotData: [], countriesPresent: [], latestDate: null, comparisonDate: null }

    const present = []
    let latestSeen = null
    let comparisonSeen = null

    const rows = TENOR_ORDER.map(tenor => {
      const point = { maturity: MATURITY_YEARS[tenor], tenor }
      for (const c of countries) {
        const series = panels.yields.rows.find(r => r.country === c && r.label === tenor)
        if (!series?.history?.length) continue

        const lastDate = lastDateOf(series.history)
        const lastV    = valueAtOrBefore(series.history, null)
        const prevV    = comparisonCutoff ? valueAtOrBefore(series.history, comparisonCutoff) : null

        if (Number.isFinite(lastV)) {
          point[c] = lastV
          if (!present.includes(c)) present.push(c)
          if (!latestSeen || lastDate > latestSeen) latestSeen = lastDate
        }
        if (Number.isFinite(prevV)) {
          point[`${c}_prev`] = prevV
          if (!comparisonSeen) comparisonSeen = comparisonCutoff
        }
      }
      return point
    })

    return {
      plotData: rows,
      countriesPresent: present,
      latestDate: latestSeen,
      comparisonDate: comparisonSeen,
    }
  }, [panels, comparisonCutoff, countries])

  const showComparison = comparisonCutoff != null && rangeLabel !== 'MAX'

  return (
    <div className="panel p-4 flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <span className="text-sm font-medium text-slate-800 dark:text-slate-100">
          {title}
          <span className="ml-2 text-xs text-slate-500 dark:text-slate-400 font-normal">
            solid = {latestDate ?? 'latest'}
            {showComparison && <> · dashed = {comparisonDate ?? rangeLabel}</>}
          </span>
        </span>
        <span className="text-xs text-slate-400 dark:text-slate-500">{yLabel}</span>
      </div>
      <div style={{ width: '100%', height }}>
        <ResponsiveContainer>
          <LineChart data={plotData} margin={{ top: 5, right: 15, bottom: 5, left: 0 }}>
            <CartesianGrid stroke={t.ui.grid} strokeDasharray="3 3" vertical={false} />
            <XAxis
              type="number"
              dataKey="maturity"
              domain={[0, 30]}
              ticks={[0.25, 1, 2, 5, 10, 20, 30]}
              tickFormatter={v => {
                const tenor = Object.entries(MATURITY_YEARS).find(([, m]) => m === v)
                return tenor ? tenor[0] : v
              }}
              tick={{ fill: t.ui.tickLabel, fontSize: t.ui.tickFontSize }}
              axisLine={{ stroke: t.ui.axis }}
              tickLine={false}
              label={{ value: 'Maturity', position: 'insideBottom', offset: -2, fill: t.ui.tickLabel, fontSize: 11 }}
            />
            <YAxis
              tick={{ fill: t.ui.tickLabel, fontSize: t.ui.tickFontSize }}
              axisLine={{ stroke: t.ui.axis }}
              tickLine={false}
              width={45}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={getTooltipStyle(isDark)}
              labelStyle={{ color: t.ui.tickLabel, fontSize: 11 }}
              itemStyle={{ fontSize: 11 }}
              formatter={(v) => Number.isFinite(v) ? `${v.toFixed(3)}%` : '—'}
              labelFormatter={(v) => {
                const tenor = Object.entries(MATURITY_YEARS).find(([, m]) => m === v)
                return tenor ? `${tenor[0]} (${v}y)` : `${v}y`
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
              iconType="line"
              payload={countriesPresent.map((c, i) => ({
                value: c,
                type: 'line',
                color: PALETTE[i % PALETTE.length],
              }))}
            />
            {countriesPresent.map((c, i) => (
              <Line
                key={c}
                type="monotone"
                dataKey={c}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={1.6}
                dot={{ r: 3 }}
                isAnimationActive={false}
                connectNulls
                legendType="line"
              />
            ))}
            {showComparison && countriesPresent.map((c, i) => (
              <Line
                key={`${c}_prev`}
                type="monotone"
                dataKey={`${c}_prev`}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={1}
                strokeDasharray="3 3"
                strokeOpacity={0.55}
                dot={{ r: 2 }}
                isAnimationActive={false}
                connectNulls
                legendType="none"
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ----------------------------------------------------------------------------

function ChartCard({ title, yLabel, series, cutoff = null, tall = false, zeroLine = false }) {
  const { isDark } = useDarkMode()
  const t = getTheme(isDark)

  const merged = useMemo(() => {
    const byDate = new Map()
    for (const s of series) {
      for (const [d, v] of s.history) {
        if (cutoff && d < cutoff) continue
        if (!byDate.has(d)) byDate.set(d, { date: d })
        byDate.get(d)[s.key] = v
      }
    }
    return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
  }, [series, cutoff])

  return (
    <div className="panel p-4 flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium text-slate-800 dark:text-slate-100">{title}</span>
        {yLabel && <span className="text-xs text-slate-400 dark:text-slate-500">{yLabel}</span>}
      </div>
      <div style={{ width: '100%', height: tall ? 380 : 240 }}>
        <ResponsiveContainer>
          <LineChart data={merged} margin={{ top: 5, right: 10, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={t.ui.grid} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: t.ui.tickLabel, fontSize: t.ui.tickFontSize }}
              axisLine={{ stroke: t.ui.axis }}
              tickLine={false}
              tickFormatter={d => d.slice(0, 7)}
              minTickGap={50}
            />
            <YAxis
              tick={{ fill: t.ui.tickLabel, fontSize: t.ui.tickFontSize }}
              axisLine={{ stroke: t.ui.axis }}
              tickLine={false}
              width={45}
              domain={['auto', 'auto']}
            />
            {zeroLine && (
              <ReferenceLine y={0} stroke={t.ui.axis} strokeDasharray="3 3" />
            )}
            <Tooltip
              contentStyle={getTooltipStyle(isDark)}
              labelStyle={{ color: t.ui.tickLabel, fontSize: 11 }}
              itemStyle={{ fontSize: 11 }}
              formatter={(v) => Number.isFinite(v) ? v.toFixed(3) : '—'}
            />
            <Legend wrapperStyle={{ fontSize: 11, paddingTop: 4 }} iconType="line" />
            {series.map(s => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                stroke={s.color}
                strokeWidth={1.4}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
