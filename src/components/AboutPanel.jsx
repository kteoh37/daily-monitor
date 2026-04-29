export default function AboutPanel() {
  return (
    <div className="max-w-3xl mx-auto py-6 space-y-6">

      <div className="panel p-6 space-y-3">
        <div className="label">Daily Market Monitor</div>
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white leading-snug">
          Japan &amp; G7 — daily indicators across rates, FX, equities, and policy
        </h2>
        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
          Country scope: United States, Japan, Germany, France, Italy, United Kingdom, Canada,
          Euro Area aggregate, Korea, Australia.
        </p>
      </div>

      <div className="panel p-6 space-y-3">
        <div className="label">Data source</div>
        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
          All series are pulled from Haver Analytics via the
          {' '}<a href="https://github.com/jasonzhixinglu/haver-data" className="text-indigo-600 dark:text-indigo-400 hover:underline">haver-data</a>{' '}
          pipeline, refreshed daily. The build script reads the parquet snapshot, applies
          standard transforms (level, daily change, rolling z-score), and emits JSON files
          consumed by this dashboard.
        </p>
      </div>

    </div>
  )
}
