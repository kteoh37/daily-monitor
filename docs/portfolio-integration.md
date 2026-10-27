# Japan portfolio snapshot

Public report: `public/reports/japan-portfolio/index.html`, linked from the dashboard as **Japan flows**. User approved public publication on October 27, 2026. This uses the existing standalone report pattern and does not change deployment, visibility, credentials, schedules or other dashboard sections.

The report contains only three PNGs and HTML descriptions derived from tracker CSV values. MOF latest week: October 17, 2026; JSDA latest month: September 2026. Historical checks: October 27 around 01:10 UTC. These are existing Mac seed results, not a fresh cloud refresh. Source tracker main: `9d6564d607d8edaa0c87b85596c31131490739b4`; results: `69ca2f4426a573f1862f13ef7a65e01a8aff7f02`.

No CSVs, raw Haver Parquets, full internal state or interactive JSDA HTML are published. JSDA sector totals and the separate overall total are not interchangeable. Domestic JGB purchases alongside foreign-security sales do not establish same-investor repatriation.

Portfolio auto-sync is not configured. The existing Pages workflow deploys this dated snapshot; it does not refresh the tracker. A future separately approved server-side integration should transfer only allowlisted rendered charts and sanitized display metadata after successful tracker results, preserving last-good charts with visible stale/partial warnings on failures. It must record source/results provenance and observation/check dates separately, and never put private repository tokens in browser code. The existing HAVER_DATA_TOKEN is for a different repository and must not be repurposed.
