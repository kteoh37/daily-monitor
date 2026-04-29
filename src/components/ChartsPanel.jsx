import { useEffect, useMemo, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
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

function fetchPanel(key, base) {
  return fetch(`${base}data/${key}.json`).then(r => {
    if (!r.ok) throw new Error(`Failed to load ${key}.json`)
    return r.json()
  })
}

// ----------------------------------------------------------------------------

export default function ChartsPanel() {
  const [panels, setPanels]   = useState({})
  const [loading, setLoading] = useState(true)
  const [mode, setMode]       = useState('country') // 'country' | 'theme'
  const [country, setCountry] = useState('JP')
  const [theme, setTheme]     = useState('yields')
  const [yieldTenor, setYieldTenor] = useState('10Y')

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

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-500 text-sm">Loading…</div>

  const availableCountries = COUNTRY_ORDER.filter(c =>
    PANEL_KEYS.some(k => panels[k]?.rows.some(r => r.country === c))
  )

  return (
    <div className="py-4 space-y-4">

      <div className="flex flex-wrap items-end gap-3 px-1">
        <div className="flex items-center gap-1 rounded-lg bg-slate-100 dark:bg-slate-800 p-1">
          <button
            onClick={() => setMode('country')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              mode === 'country' ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white' : 'text-slate-600 dark:text-slate-400'
            }`}
          >By country</button>
          <button
            onClick={() => setMode('theme')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              mode === 'theme' ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white' : 'text-slate-600 dark:text-slate-400'
            }`}
          >By theme</button>
        </div>

        {mode === 'country' && (
          <label className="flex items-center gap-2 text-xs text-slate-500">
            Country
            <select
              value={country}
              onChange={e => setCountry(e.target.value)}
              className="text-xs rounded px-2 py-1 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 outline-none cursor-pointer"
            >
              {availableCountries.map(c => (
                <option key={c} value={c}>{COUNTRY_LABELS[c] ?? c}</option>
              ))}
            </select>
          </label>
        )}

        {mode === 'theme' && (
          <>
            <label className="flex items-center gap-2 text-xs text-slate-500">
              Theme
              <select
                value={theme}
                onChange={e => setTheme(e.target.value)}
                className="text-xs rounded px-2 py-1 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 outline-none cursor-pointer"
              >
                {PANEL_KEYS.map(k => (
                  <option key={k} value={k}>{PANEL_LABELS[k]}</option>
                ))}
              </select>
            </label>
            {theme === 'yields' && (
              <label className="flex items-center gap-2 text-xs text-slate-500">
                Tenor
                <select
                  value={yieldTenor}
                  onChange={e => setYieldTenor(e.target.value)}
                  className="text-xs rounded px-2 py-1 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 outline-none cursor-pointer"
                >
                  {TENOR_ORDER.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>
            )}
          </>
        )}
      </div>

      {mode === 'country'
        ? <ByCountryView panels={panels} country={country} />
        : <ByThemeView panels={panels} theme={theme} yieldTenor={yieldTenor} />}
    </div>
  )
}

// ----------------------------------------------------------------------------

function ByCountryView({ panels, country }) {
  const blocks = []

  // Yield curve — multi-line
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

  // Single-line panels
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
      {blocks.map(b => <ChartCard key={b.key} {...b} />)}
    </div>
  )
}

// ----------------------------------------------------------------------------

function ByThemeView({ panels, theme, yieldTenor }) {
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

  return (
    <ChartCard title={title} yLabel={yLabelMap[theme]} series={series} tall />
  )
}

// ----------------------------------------------------------------------------

function ChartCard({ title, yLabel, series, tall = false }) {
  const { isDark } = useDarkMode()
  const t = getTheme(isDark)

  // Merge series histories on date key for Recharts
  const merged = useMemo(() => {
    const byDate = new Map()
    for (const s of series) {
      for (const [d, v] of s.history) {
        if (!byDate.has(d)) byDate.set(d, { date: d })
        byDate.get(d)[s.key] = v
      }
    }
    return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
  }, [series])

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
            <Tooltip
              contentStyle={getTooltipStyle(isDark)}
              labelStyle={{ color: t.ui.tickLabel, fontSize: 11 }}
              itemStyle={{ fontSize: 11 }}
              formatter={(v) => Number.isFinite(v) ? v.toFixed(3) : '—'}
            />
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 4 }}
              iconType="line"
            />
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
