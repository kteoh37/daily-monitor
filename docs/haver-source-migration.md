# Haver source migration — local draft

Not deployed. Live dashboard retains its existing source until exact coverage is resolved.

Validated snapshot: `kteoh37/haver-dataset@8f6e2d9fcdcccc296a5bb46dff00fd4185677ede`; snapshot vintage `2026-10-26T21:59:54+00:00`. Downloaded through existing authenticated gh and verified blob sizes/hashes, Parquet signatures, schemas and date indexes. No credential changes.

| Panel | Exact daily series | Missing |
|---|---:|---:|
| yields | 61 | 9 |
| breakevens | 7 | 0 |
| fx | 9 | 0 |
| equities | 9 | 2 |
| volatility | 6 | 0 |
| policy_rates | 9 | 0 |
| overnight_rates | 6 | 0 |
| commodities_uncertainty | 4 | 0 |

111/122 exact series; all 111 retain native D frequency. No ambiguous matches or frequency substitutions. The daily storage bucket also contains native weekly series; these are excluded by metadata, not storage filename.

## Missing exact series

| Panel | Dashboard definition | Required code |
|---|---|---|
| yields | US 10Y | `fcm10@daily` |
| yields | US 20Y | `fcm20@daily` |
| yields | US 30Y | `fcm30@daily` |
| yields | JP 10Y | `r158ga@intdaily` |
| yields | JP 20Y | `r158gk@intdaily` |
| yields | JP 30Y | `r158gt@intdaily` |
| yields | UK 3M | `t112d3m@intdaily` |
| yields | KR 3M | `r542s3m@intdaily` |
| yields | CN 3M | `f924m3m@intdaily` |
| equities | IT FTSE MIB | `s136mbi@intdaily` |
| equities | CN CSI 300 | `s924sh3@intdaily` |

No nearby benchmark, tenor or equity index is substituted. For example, Japan `R158MA@INTDAILY` exists but is a different code from existing `R158GA@INTDAILY`; matching the label “10Y” is insufficient to establish identical definition/history. Preserve original country/label/code configs, rates in percent with pp changes, index/FX levels with pct changes, 1/5/21-observation horizons, trailing five-year histories and 1260-observation population-standard-deviation z scores. Exact-code identity plus metadata descriptors confirm units for available matches; no conversion is introduced. Existing AU three-month bank-accepted-bill definition and FX quotation directions are retained.

## Draft implementation and activation gates

`scripts/build_data.py` accepts either legacy `--haver-data` (unchanged workflow) or new `--haver-dataset PATH --source-commit SHA`. New loader validates provenance, metadata/data code identity, case ambiguity, native frequency, date order and finite observations. Full dashboard coverage is required before writing any panels. `--coverage-report` is a LOCAL diagnostic containing selected descriptors; do not put it in public/dist or commit source metadata.

The real pinned snapshot deliberately fails validation with the 11 missing series and writes no panel output. Seven synthetic tests cover transformation parity, case mapping, native weekly rejection, missing exact codes, ambiguous casing, bad provenance, duplicate dates and nonfinite input. A direct real-data check verifies all 111 available series produce identical summaries/history to the same original build_row calculations.

Before activation, add these exact series to the upstream snapshot (separately authorized work), or obtain explicit approval for definition changes/removed rows. After coverage passes, reuse one clean pinned dataset checkout for both panels and the policy report, remove the legacy checkout, run loader/tests, update displayed attribution and README, and keep raw snapshots outside public/dist. Resolve source revision once per build and record the SHA and snapshot vintage in the sanitized panel manifest.

Current workflow already checks out kteoh37/haver-dataset for the policy report using the existing named secret HAVER_DATA_TOKEN; that checkout succeeded in deployment 40521553361. This is empirical access evidence, not a token-scope claim. No new credential should be requested or existing token read/reconfigured without parent review. Minimal requirement is server-side Contents:Read to kteoh37/haver-dataset for the existing GitHub Actions checkout; no browser token or client-side private GitHub fetch.

Live workflow and source labels intentionally unchanged while coverage remains blocked.
