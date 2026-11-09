# Japan policy events: draft-review workflow

## Review boundary

Every proposed policy event update must be a **draft pull request**. Nothing in this
pipeline merges a PR, enables auto-merge, pushes to `main`, or publishes a new event.
Only a human-approved merge makes reviewed registry records available to the normal
Pages deployment. Existing twice-daily price refresh and the separate approved
portfolio refresh remain unchanged.

The first setup PR also requires review/merge. Until then its registry and renderer
are not live. Subsequent proposals should not duplicate that pending setup work.

## Daily handoff

The existing daily macro briefing is the research trigger, not a public data feed.
Its original coverage and schedule remain intact. After preparing each briefing,
the scheduled assistant checks relevant Japanese fiscal, BOJ and intervention leads
against official sources and follows this procedure:

1. Read current `main`, open policy draft PRs, and their branch heads. If setup is
   still pending, report that blocker privately rather than creating a second setup.
2. Read the actual official announcement, decision, legislation, operation table or
   transcript. A search snippet, news article, or earlier briefing is insufficient.
   Independently verify every date, amount, decision and claimed policy stage.
3. Distinguish the economic event date from disclosure/publication, effective date
   and timezone. Later intervention allocations revise the original operations;
   minutes do not create a new rate decision. Future speeches remain a private
   watchlist unless an official completed communication warrants an event.
4. Preserve the economic event ID on corrections. Compare both merged records and
   open proposals. Same issuer/category/date/stage collisions require editorial
   resolution, not an invented ID. Never delete old records or infer the direction
   of a policy change from its market reaction.
5. Build only the strict public schema in `data/policy-events.json`: official facts,
   cautious classifications/caveats, source URLs, publication dates and short exact
   public excerpts. Never copy private briefing prose, conversation links, user
   information, raw research, credentials or private attachments into GitHub,
   comments, logs, commit messages or CI artifacts. Unknown fields are rejected;
   schema and leak-pattern checks are defense in depth, not a substitute for review.
6. Run the upsert, schema/evidence checks, tests and preview below. A primary source
   outage, changed quotation, ambiguous timezone/date, unclear classification,
   absent source or conflicting facts means hold the candidate privately and tell
   the user the actionable blocker. Do not label it verified or publish guesses.
7. If there are substantive changes, create a new dated `policy-events/YYYY-MM-DD`
   branch from current `main`, or update that day's existing **draft** PR only after
   rereading its head and checking that it remains draft. Use optimistic concurrency
   (expected head SHA); never force over other edits. Never modify a ready-for-review
   PR silently. Recheck `main` before writing. If it moved, rebuild and retest.
8. Change only `data/policy-events.json` for normal event proposals. PR descriptions
   contain a concise public-source summary, event/disclosure dates, official links,
   validation results and relevant limits. Keep the draft flag true; do not merge,
   mark ready, approve, enable auto-merge, deploy, or write to `main`.
9. Verify the PR URL, exact head, draft status and CI results. Privately notify the
   user when a draft is ready or a blocker requires attention. An unchanged run
   creates no PR and no extra event-update notification. Do not rewrite verification
   dates solely to generate daily churn.

If a scheduled environment cannot read/write GitHub or execute checks, it must
report the specific unavailable action. Successful schedule configuration is not
proof of a successful future run. Do not claim end-to-end unattended operation
until an actual scheduled run has created a verified draft PR successfully.

## Registry and renderer

The committed HTML remains the historical baseline. The registry is a separately
reviewable overlay outside `public/`; raw evidence excerpts are not shipped to the
site. During deployment `refresh_policy_report.py` first refreshes Haver prices as
before, then applies reviewed registry records to both charts, hover data, selectors
and sourced descriptions. Unrelated baseline events and price arrays are retained.

New events with no exact Haver observation appear in the written update with a
visible pending-price note, without an interpolated or borrowed price. They enter
the charts on the next data refresh that supplies that exact date. Weekend dates
remain unplotted while weekday-only market series omit them. This is intentional.

The schema requires completed event dates no later than disclosure/verification,
a known policy stage/direction, exact official source hosts, dated excerpts and
stable IDs. A future effective date may be recorded separately. Official URL checks
include redirects and refuse query strings, userinfo, unexpected ports and unofficial
hosts. Live quote matching confirms the page still contains the cited evidence;
it does **not** prove that a summary is semantically correct or exhaustive. The
researcher and human reviewer still check meaning and classification.

Ordinary CI is read-only and has no secrets or publishing step. Source checks fail
closed in draft review. Regular deployed price refresh does not depend on a new
external source fetch, so an official-site outage cannot silently erase reviewed
history or stop the existing market-data refresh.

## Local checks

```sh
pip install -r scripts/requirements.txt
# pdftotext (Poppler) is required only for PDF source evidence.
python -m unittest discover -s scripts -p 'test_*.py'
python scripts/policy_events.py --verify-sources \
  --report public/reports/japan-policy-events.html --output /tmp/policy-preview.html
npm ci
npm run build
```

Prepare a public-only candidates file with the same registry schema, then merge it
locally without overwriting the reviewed source:

```sh
python scripts/policy_events.py --candidates /tmp/public-candidates.json \
  --verify-sources --output /tmp/proposed-policy-events.json
```

Inspect the diff and preserve every existing record before using the proposed file
in a draft branch. Run the checks again on the exact final branch. No private
briefing is accepted as an input by any repository script.

## Initial verified example

MOF's November 9, 2026 Q3 release reports JPY7,975.6bn on July 30,
JPY5,552.3bn on July 31, and JPY1,871.4bn on August 3. These are operation dates,
not November interventions. Two old markers are revised and one is added; the
separate August 3 statement confirms July 31 US Eastern Time coordination.
The total is JPY15,399.3bn. No US amount, intraday timing, causal price effect or
record-size comparison is inferred.
