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
  CH: 'Switzerland',   KR: 'Korea',     AU: 'Australia',
}

const COUNTRY_ORDER = ['US', 'JP', 'DE', 'FR', 'IT', 'UK', 'CA', 'EA', 'CH', 'KR', 'AU']

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
    countries: ['US', 'JP', 'DE', 'FR', 'IT', 'UK', 'CA', 'KR', 'AU'],
    build: (panels, c) => makeSpread(
      findYield(panels, c, '10Y'),
      findYield(panels, c, '2Y'),
    ),
  },
  vs_bund: {
    label: 'Sovereign 10Y vs Bund (XX − DE)',
    yLabel: 'pp',
    countries: ['US', 'JP', 'FR', 'IT', 'UK', 'CA', 'KR', 'AU'],
    build: (panels, c) => makeSpread(
      findYield(panels, c, '10Y'),
      findYield(panels, 'DE', '10Y'),
    ),
  },
  real_rate: {
    label: 'Ex-ante 10Y real rate (nominal − BEI)',
    yLabel: '% p.a.',
    countries: ['US', 'JP', 'DE', 'FR', 'UK', 'CA', 'KR', 'AU'],
    build: (panels, c) => makeSpread(
      findYield(panels, c, '10Y'),
      findBEI(panels, c),
    ),
  },
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

      {mode === 'country' && <ByCountryView panels={panels} country={country} cutoff={cutoff} />}
      {mode === 'theme'   && <ByThemeView   panels={panels} theme={theme} yieldTenor={yieldTenor} cutoff={cutoff} />}
      {mode === 'spreads' && <SpreadsView   panels={panels} family={spreadFamily} cutoff={cutoff} />}
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

function ByCountryView({ panels, country, cutoff }) {
  const blocks = []

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
      {blocks.map(b => <ChartCard key={b.key} {...b} cutoff={cutoff} />)}
    </div>
  )
}

// ----------------------------------------------------------------------------

function ByThemeView({ panels, theme, yieldTenor, cutoff }) {
  const panel = panels[theme]
  if (!panel) return <div className="panel p-6 text-sm text-slate-500">No data for {theme}.</div>

  let rows = panel.rows
  if (theme === 'yields') {
    rows = rows.filter(r => r.label === yieldTenor)
  }
  rows = rows.filter(r => r.history?.length)

  if (!rows.length) return <div className="panel p-6 text-sm text-slate-500">No matching series.</div>

  const series = rows.map((r, i) => ({
    key: `${r.country} ${r.label}`,
    history: r.history,
    color: PALETTE[i % PALETTE.length],
  }))

  const title = theme === 'yields'
    ? `${PANEL_LABELS[theme]} — ${yieldTenor} across countries`
    : `${PANEL_LABELS[theme]} — across countries`

  const yLabelMap = {
    yields: '% p.a.', breakevens: '% p.a.', policy_rates: '% p.a.',
    fx: '', equities: 'level', volatility: 'index', commodities_uncertainty: 'level',
  }

  return <ChartCard title={title} yLabel={yLabelMap[theme]} series={series} cutoff={cutoff} tall />
}

// ----------------------------------------------------------------------------

function SpreadsView({ panels, family, cutoff }) {
  const cfg = SPREAD_FAMILIES[family]
  const series = useMemo(() => (
    cfg.countries
      .map((c, i) => ({
        country: c,
        history: cfg.build(panels, c),
      }))
      .filter(s => s.history && s.history.length)
      .map((s, i) => ({
        key: s.country,
        history: s.history,
        color: PALETTE[i % PALETTE.length],
      }))
  ), [panels, family])

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
