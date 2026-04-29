# Daily Market Monitor — Japan & G7

Interactive dashboard for daily monitoring of key market indicators across **G7 + Euro Area + Korea + Australia** (10 jurisdictions).

Sourced from Haver Analytics via the [haver-data](https://github.com/jasonzhixinglu/haver-data) pipeline (refreshed daily).

## Stack

Vite + React 18 + Tailwind + Recharts. Static JSON snapshots in `public/data/`. Deploys to GitHub Pages.

## Data flow

```
haver-data/data.parquet  ->  scripts/build_data.py  ->  public/data/*.json  ->  React UI
```

The build script reads the local `haver-data` clone, applies standard transforms (level, daily change, rolling z-score), and writes one JSON per panel.

## Country scope

US | JP | DE | FR | IT | UK | CA | EA | KR | AU

## Local development

```bash
npm install
npm run dev
```

Refresh data:

```bash
python scripts/build_data.py --haver-data ../haver-data
```

## Project status

Scaffold only. Indicator spec in [`docs/indicator_spec.md`](docs/indicator_spec.md). Build script and panels are next.
