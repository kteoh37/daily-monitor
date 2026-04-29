import { useEffect, useMemo, useState } from 'react'
import { fmtLevel, fmtChange, fmtZ, zBgClass, changeColorClass } from '../lib/format.js'

const PANELS = [
  { key: 'yields',                  label: 'Sovereign yields',         layout: 'matrix' },
  { key: 'breakevens',              label: 'Breakeven inflation',      layout: 'flat'   },
  { key: 'fx',                      label: 'FX (vs USD)',              layout: 'flat'   },
  { key: 'equities',                label: 'Equity indices',           layout: 'flat'   },
  { key: 'volatility',              label: 'Volatility indices',       layout: 'flat'   },
  { key: 'policy_rates',            label: 'Policy rates',             layout: 'flat'   },
  { key: 'overnight_rates',         label: 'Overnight rates',          layout: 'flat'   },
  { key: 'commodities_uncertainty', label: 'Commodities & uncertainty',layout: 'flat'   },
]

const TENOR_ORDER = ['3M', '1Y', '2Y', '5Y', '10Y', '20Y', '30Y']
const COUNTRY_ORDER = ['US', 'JP', 'DE', 'FR', 'IT', 'UK', 'CA', 'EA', 'CH', 'KR', 'AU', '--']

function fetchPanel(key, base) {
  return fetch(`${base}data/${key}.json`).then(r => {
    if (!r.ok) throw new Error(`Failed to load ${key}.json`)
    return r.json()
  })
}

export default function OverviewPanel() {
  const [panels, setPanels]       = useState({})
  const [manifest, setManifest]   = useState(null)
  const [loading, setLoading]     = useState(true)
  const [colorBy, setColorBy]     = useState('z_5y') // z_5y | chg_1d | chg_5d | chg_21d

  useEffect(() => {
    const base = import.meta.env.BASE_URL
    Promise.all([
      fetchPanel('manifest', base).catch(() => null),
      ...PANELS.map(p => fetchPanel(p.key, base)),
    ]).then(([mani, ...results]) => {
      const obj = {}
      PANELS.forEach((p, i) => { obj[p.key] = results[i] })
      setPanels(obj)
      setManifest(mani)
      setLoading(false)
    }).catch(err => {
      console.error(err)
      setLoading(false)
    })
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-500 text-sm">Loading…</div>
  )

  return (
    <div className="py-4 space-y-5">

      <div className="flex flex-wrap items-end justify-between gap-3 px-1">
        <div>
          <div className="label">Daily snapshot</div>
          <div className="text-sm text-slate-700 dark:text-slate-300">
            Vintage <span className="font-medium text-indigo-600 dark:text-indigo-300">{manifest?.vintage ?? '—'}</span>
            <span className="text-slate-400 dark:text-slate-600"> · color by</span>
            {' '}
            <ColorByToggle value={colorBy} onChange={setColorBy} />
          </div>
        </div>
        <Legend colorBy={colorBy} />
      </div>

      {PANELS.map(p => (
        <PanelBlock
          key={p.key}
          panel={panels[p.key]}
          title={p.label}
          layout={p.layout}
          colorBy={colorBy}
        />
      ))}
    </div>
  )
}

function ColorByToggle({ value, onChange }) {
  const opts = [
    ['z_5y',   'z-score (5y)'],
    ['chg_1d', '1d chg'],
    ['chg_5d', '5d chg'],
    ['chg_21d','21d chg'],
  ]
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="text-xs rounded px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 outline-none cursor-pointer"
    >
      {opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  )
}

function Legend({ colorBy }) {
  const swatches = [
    { cls: 'bg-sky-300 dark:bg-sky-800/70',     label: '< -2' },
    { cls: 'bg-sky-200 dark:bg-sky-900/50',     label: '-2..-1' },
    { cls: 'bg-sky-100 dark:bg-sky-950/40',     label: '-1..-0.5' },
    { cls: 'bg-slate-100 dark:bg-slate-800/60', label: '~0' },
    { cls: 'bg-amber-100 dark:bg-amber-950/40', label: '0.5..1' },
    { cls: 'bg-amber-200 dark:bg-amber-900/50', label: '1..2' },
    { cls: 'bg-amber-300 dark:bg-amber-800/70', label: '> 2' },
  ]
  const unit = colorBy === 'z_5y' ? 'σ' : (colorBy.startsWith('chg') ? 'std-norm' : '')
  return (
    <div className="flex items-center gap-1.5 text-xs text-slate-500">
      <span className="hidden sm:inline">cool ←</span>
      {swatches.map((s, i) => (
        <span key={i} className={`inline-block w-5 h-3 rounded-sm border border-slate-300/40 dark:border-slate-700/40 ${s.cls}`} title={s.label} />
      ))}
      <span className="hidden sm:inline">→ hot</span>
      <span className="ml-1 hidden md:inline text-slate-400 dark:text-slate-600">({unit})</span>
    </div>
  )
}

function PanelBlock({ panel, title, layout, colorBy }) {
  if (!panel) return (
    <div className="panel p-4 text-xs text-slate-500">No data loaded for {title}.</div>
  )
  return (
    <div className="panel p-4">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">{title}</h3>
        <span className="label">{panel.vintage} · {panel.rows.filter(r => r.latest != null).length}/{panel.rows.length}</span>
      </div>
      {layout === 'matrix'
        ? <YieldMatrix rows={panel.rows} changeType={panel.change_type} colorBy={colorBy} />
        : <FlatTable rows={panel.rows} changeType={panel.change_type} colorBy={colorBy} />}
    </div>
  )
}

// ---------- Flat table ----------

function FlatTable({ rows, changeType, colorBy }) {
  return (
    <div className="overflow-x-auto -mx-2 px-2">
      <table className="w-full text-xs tabular-nums">
        <thead>
          <tr className="text-left text-slate-500">
            <th className="font-normal px-2 py-1.5">Country</th>
            <th className="font-normal px-2 py-1.5">Series</th>
            <th className="font-normal px-2 py-1.5 text-right">Latest</th>
            <th className="font-normal px-2 py-1.5 text-right">1d</th>
            <th className="font-normal px-2 py-1.5 text-right">5d</th>
            <th className="font-normal px-2 py-1.5 text-right">21d</th>
            <th className="font-normal px-2 py-1.5 text-right">z (5y)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const colorVal = r[colorBy]
            return (
              <tr key={r.series} className="border-t border-slate-200/60 dark:border-slate-800/60">
                <td className="px-2 py-1.5">
                  <span className="inline-block min-w-[1.75rem] text-center text-[10px] font-semibold tracking-wide rounded px-1 py-0.5 bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">{r.country}</span>
                </td>
                <td className="px-2 py-1.5 text-slate-700 dark:text-slate-200">{r.label}</td>
                <td className={`px-2 py-1.5 text-right font-mono font-medium text-slate-800 dark:text-slate-100 ${zBgClass(colorVal)}`}>
                  {fmtLevel(r.latest)}
                </td>
                <td className={`px-2 py-1.5 text-right font-mono ${changeColorClass(r.chg_1d)}`}>{fmtChange(r.chg_1d, changeType)}</td>
                <td className={`px-2 py-1.5 text-right font-mono ${changeColorClass(r.chg_5d)}`}>{fmtChange(r.chg_5d, changeType)}</td>
                <td className={`px-2 py-1.5 text-right font-mono ${changeColorClass(r.chg_21d)}`}>{fmtChange(r.chg_21d, changeType)}</td>
                <td className="px-2 py-1.5 text-right font-mono text-slate-600 dark:text-slate-400">{fmtZ(r.z_5y)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ---------- Yield matrix: rows = countries, cols = tenors ----------

function YieldMatrix({ rows, changeType, colorBy }) {
  const { byCountry, countries } = useMemo(() => {
    const byCountry = {}
    rows.forEach(r => {
      if (!byCountry[r.country]) byCountry[r.country] = {}
      byCountry[r.country][r.label] = r
    })
    const countries = COUNTRY_ORDER.filter(c => byCountry[c])
    return { byCountry, countries }
  }, [rows])

  return (
    <div className="overflow-x-auto -mx-2 px-2">
      <table className="w-full text-xs tabular-nums">
        <thead>
          <tr className="text-slate-500">
            <th className="font-normal px-2 py-1.5 text-left">Country</th>
            {TENOR_ORDER.map(t => (
              <th key={t} className="font-normal px-2 py-1.5 text-right">{t}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {countries.map(c => (
            <tr key={c} className="border-t border-slate-200/60 dark:border-slate-800/60">
              <td className="px-2 py-1.5">
                <span className="inline-block min-w-[1.75rem] text-center text-[10px] font-semibold tracking-wide rounded px-1 py-0.5 bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">{c}</span>
              </td>
              {TENOR_ORDER.map(t => {
                const r = byCountry[c][t]
                if (!r) return <td key={t} className="px-2 py-1.5 text-right text-slate-300 dark:text-slate-700">—</td>
                const colorVal = r[colorBy]
                return (
                  <td
                    key={t}
                    className={`px-2 py-1.5 text-right font-mono font-medium text-slate-800 dark:text-slate-100 ${zBgClass(colorVal)}`}
                    title={`${c} ${t}\nlatest ${r.latest_date}: ${fmtLevel(r.latest)}\n1d ${fmtChange(r.chg_1d, changeType)}  5d ${fmtChange(r.chg_5d, changeType)}  21d ${fmtChange(r.chg_21d, changeType)}\nz(5y) ${fmtZ(r.z_5y)}`}
                  >
                    {fmtLevel(r.latest)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
