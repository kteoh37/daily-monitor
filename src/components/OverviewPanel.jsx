export default function OverviewPanel() {
  return (
    <div className="py-6">
      <div className="panel p-6">
        <div className="label mb-2">Overview</div>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Heatmap of latest values vs trailing window</h2>
        <p className="text-sm text-slate-500 mt-2">
          Placeholder. Will render a sortable grid of every monitored indicator across G7 + EA + KR + AU,
          with latest value, daily / weekly / 1-month change, and a z-score against trailing 5y.
        </p>
      </div>
    </div>
  )
}
