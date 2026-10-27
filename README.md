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

Pushes to `main` automatically build and deploy via [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml). The same workflow runs on a `schedule` cron (13:00 and 22:00 UTC daily), so the live site refreshes every day after the upstream haver-data parquet updates.

### Authenticating to the private haver-data repo

The `jasonzhixinglu/haver-data` repo is private. CI checks it out using a Personal Access Token stored as the **`HAVER_DATA_TOKEN`** secret on this repo. To rotate it:

1. On a GitHub account with read access to `jasonzhixinglu/haver-data`, create a **fine-grained PAT** (Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token):
   - Resource owner: `jasonzhixinglu`
   - Repository access: only `jasonzhixinglu/haver-data`
   - Permissions → Repository → **Contents: Read**
   - Expiration: as long as you're comfortable with (90 days / 1 year)
2. On `kteoh37/daily-monitor` → Settings → Secrets and variables → Actions → New repository secret:
   - Name: `HAVER_DATA_TOKEN`
   - Value: the PAT from step 1
3. Re-run any failed workflow run.

If the token expires, scheduled and push-triggered deploys will fail at the haver-data checkout step.
