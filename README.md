# Daily Market Monitor — Japan & G7

**Live dashboard:** https://kteoh37.github.io/daily-monitor/

Interactive dashboard for daily monitoring of key market indicators across **G7 + Euro Area + Korea + Australia + China** (11 jurisdictions).

Sourced from Haver Analytics via the [haver-data](https://github.com/jasonzhixinglu/haver-data) pipeline (refreshed daily).

## Stack

Vite + React 18 + Tailwind + Recharts. Static JSON snapshots in `public/data/`. Deploys to GitHub Pages.

## Data flow

```
haver-data/data.parquet  ->  scripts/build_data.py  ->  public/data/*.json  ->  React UI
```

The build script reads the local `haver-data` clone, applies standard transforms (level, daily change, rolling z-score), and writes one JSON per panel.

## Country scope

US | JP | DE | FR | IT | UK | CA | EA | KR | AU | CN

## Local development

```bash
npm install
npm run dev
```

Refresh data:

```bash
python scripts/build_data.py --haver-data ../haver-data
```

## Deployment

Pushes to `main` automatically build and deploy via [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml). The same workflow also runs daily on a `cron: '0 13 * * *'` schedule, so the live site refreshes every day after the upstream haver-data parquet updates.
