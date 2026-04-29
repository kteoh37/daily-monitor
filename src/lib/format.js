// Number formatting helpers for the dashboard.

export function fmtLevel(v) {
  if (v == null || !Number.isFinite(v)) return '—'
  const abs = Math.abs(v)
  if (abs >= 1000) return v.toLocaleString('en-US', { maximumFractionDigits: 0 })
  if (abs >= 100)  return v.toFixed(1)
  if (abs >= 10)   return v.toFixed(2)
  return v.toFixed(3)
}

export function fmtChange(v, type) {
  if (v == null || !Number.isFinite(v)) return '—'
  if (type === 'pp') {
    if (Math.abs(v) < 1) {
      const bp = Math.round(v * 100)
      if (bp === 0) return '0bp'
      return `${bp > 0 ? '+' : ''}${bp}bp`
    }
    return `${v > 0 ? '+' : ''}${v.toFixed(2)}pp`
  }
  const rounded = Number(v.toFixed(2))
  if (rounded === 0) return '0.00%'
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
}

export function fmtZ(z) {
  if (z == null || !Number.isFinite(z)) return '—'
  const sign = z > 0 ? '+' : ''
  return `${sign}${z.toFixed(2)}`
}

// Map z-score to a Tailwind background color class for a heatmap cell.
// Positive z -> amber/red, negative z -> indigo/sky, near-zero -> neutral.
export function zBgClass(z) {
  if (z == null || !Number.isFinite(z)) return ''
  const a = Math.abs(z)
  if (a < 0.5) return 'bg-slate-100 dark:bg-slate-800/60'
  if (z > 0) {
    if (a < 1)   return 'bg-amber-100 dark:bg-amber-950/40'
    if (a < 2)   return 'bg-amber-200 dark:bg-amber-900/50'
    return 'bg-amber-300 dark:bg-amber-800/70'
  }
  if (a < 1)   return 'bg-sky-100 dark:bg-sky-950/40'
  if (a < 2)   return 'bg-sky-200 dark:bg-sky-900/50'
  return 'bg-sky-300 dark:bg-sky-800/70'
}

export function changeColorClass(v) {
  if (v == null || !Number.isFinite(v)) return 'text-slate-400 dark:text-slate-600'
  // matches fmtChange's rounding precision: < 0.005 rounds to "0"
  if (Math.abs(v) < 0.005) return 'text-slate-400 dark:text-slate-500'
  if (v > 0) return 'text-amber-600 dark:text-amber-400'
  return 'text-sky-600 dark:text-sky-400'
}
