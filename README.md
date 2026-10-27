# Daily Market Monitor — Japan & G7

**Live dashboard:** https://kteoh37.github.io/daily-monitor/

Interactive dashboard for daily monitoring of key market indicators across **G7 + Euro Area + Korea + Australia + China** (11 jurisdictions).

**Japan policy report:** https://kteoh37.github.io/daily-monitor/reports/japan-policy-events.html

Standalone interactive JGB yield and yen charts from January 2022 through October 26, 2026,
with color-coded policy events, sourced descriptions, and selection/methodology notes.
Every deployment refreshes both report series from `kteoh37/haver-dataset`, preserving
the curated event dates, descriptions, classifications, colors and FXI verification notes.
The report displays each series' latest observation and its source revision. Event research
remains dated through October 26, 2026; new announcements require an editorial update.
The existing twice-daily deployment schedule (13:00 and 22:00 UTC) refreshes this report too.
The `HAVER_DATA_TOKEN` secret must have Contents: Read access to both Haver source repos.

Refresh the report locally:

```bash
python scripts/refresh_policy_report.py --haver-data ../haver-dataset --source-commit <revision>
```

The committed report HTML is the editorial source. The workflow changes chart values,
marker heights and data-availability labels only in the deployment build, without committing
generated data. Missing exact series, lost annotated dates, non-finite values or a source
ending before the report's existing observations fail the build rather than publish a shorter history.

Sourced from Haver Analytics via the [haver-data](https://github.com/jasonzhixinglu/haver-data) pipeline (refreshed daily).

## Stack

Vite + React 18 + Tailwind + Recharts. Static JSON snapshots in `public/data/`. Deploys to GitHub Pages.

## Data flow

One commit-pinned `kteoh37/haver-dataset` checkout supplies wide daily data and native-frequency metadata to `scripts/build_data.py`, plus the Japan policy report and monthly JSDA portfolio chart. The strict dashboard loader requires all 122 exact daily codes and finite observations; no series substitutions or raw snapshot files are published. The sanitized dashboard manifest records source SHA and snapshot vintage.

Portfolio reports publish only three PNGs, HTML descriptions and a compact manifest of dates/status/fingerprints. Raw Haver data, metadata, CSVs and tracker state histories stay in temporary build inputs. A full-history prefix digest detects revisions without storing transaction history in public state. See `docs/portfolio-integration.md`.

## Country scope

US | JP | DE | FR | IT | UK | CA | EA | KR | AU | CN

## Local development

```bash
npm install
npm run dev
```

Refresh data from a clean pinned snapshot:

```bash
SOURCE_REVISION=$(git -C ../haver-dataset rev-parse HEAD)
python scripts/build_data.py --haver-dataset ../haver-dataset --source-commit "$SOURCE_REVISION"
```

## Deployment and automatic updates

The existing workflow rebuilds at 13:00 and 22:00 UTC and on main pushes. All dashboard indicators use the exact new-repository codes, preserving units, transformations and charts. The curated policy report refreshes price series in the same build; its researched event annotations remain separately dated.

Portfolio charts refresh Thursdays at 10:00 America/New_York with a daylight-saving-aware UTC gate (GitHub cron may run late). The live cloud integration was verified successfully in run 40525581304 before enabling this schedule.

Manual `workflow_dispatch` with `refresh_portfolio=true` fetches official live MOF CSV and calculates JSDA rolling five-calendar-month purchases from the same commit-pinned Haver checkout. It commits only the approved five-file export and deploys it. On component failure the last complete chart/prose remains with a visible warning; the site still deploys the warning and a follow-up workflow job marks the run failed. Haver observations remain as current as the upstream snapshot; a successful fetch does not imply a new vendor observation.

The existing named secret `HAVER_DATA_TOKEN` already provides workflow access to `kteoh37/haver-dataset` and is reused without inspecting, copying or changing its value or grants. No client-side GitHub authentication is introduced. No private tracker access is needed: reviewed calculation code runs inside daily-monitor. The private tracker schedule and ChatGPT task remain unchanged.
