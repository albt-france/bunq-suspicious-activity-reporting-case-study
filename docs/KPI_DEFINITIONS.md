# KPI definitions (SIMULATED reporting desk)

All timestamps are stored in **UTC**. Calendar logic (months, deadlines) uses **Europe/Paris** local dates.
A report is counted **once per `report_id`** (its first submission). SQL: `sql/03_reporting_funnel.sql`, `sql/04_quality.sql`, `sql/05_cap_tracking.sql`.

| KPI | Formula | Clock start → stop | Time zone | Exclusions / notes |
|---|---|---|---|---|
| Alerts | count of alerts | — | month of alert, Paris | split by source: rule, internal referral, external request |
| Alert-to-case rate | escalated alerts / alerts | — | Paris month | closed alerts keep a reason code |
| Reports filed | count distinct `report_id` with a submission | — | month of first submission, Paris | duplicate submission rows excluded |
| **Time to file (median, p90)** | first submission − **alert** timestamp, in days | **alert → first submission** | durations are time-zone free | never use the tool's own field (see the trap below) |
| On-time rate | share of reports with Paris date of submission ≤ Paris date of alert + 14 | alert → submission | **Paris dates** | 14 days = internal target of the simulated desk, not a legal deadline |
| Triage backlog by age | escalated alerts not yet opened as a case at month end, by days since alert | alert → snapshot | snapshot at 23:59 UTC month end | buckets 0–6, 7–13, 14–29, 30+ days |
| Completeness at draft | drafts with all required fields / drafts | — | — | required list: `docs/REPORTING_PROCEDURE.md` §3 |
| Completeness at submission | submitted reports with all required fields / reports | — | — | target 100%: the pre-fill tool blocks incomplete drafts |
| QA return rate | reports returned at least once / reports | — | — | reason codes in `quality_returns` |
| Duplicate rate | (submission rows − distinct reports) / distinct reports | — | — | should be 0 |
| Analyst effort per case | hours logged on the case (geometric mean) | pickup → decision | — | outcome of the pre-fill evaluation |
| CAP items overdue | open items with due date < as-of date | — | — | by owner team code |
| CAP closed without evidence | closed items with `evidence_attached = false` | — | — | counted as **not done** |

## The trap: a 40% "improvement" that is a definition change (event 4)

In September 2026 the reporting tool's own field `tool_time_to_file_days` falls from **11.0 to 6.7 days (−40%)**.
Nothing improved: the tool started its clock at **case opening** instead of the **alert** (`tool_clock_start` changes from
`alert_ts` to `case_opened_ts`). Recomputed from the raw timestamps, the true median is flat (**11.05 → 11.00 days**).

How to catch it:
1. Recompute the KPI from raw timestamps instead of reading a pre-computed field.
2. Check the definition metadata (`tool_clock_start`) month by month.
3. Ask *what changed in the process* before crediting a big step change: a real gain comes with a cause (here, none in September; the real gain — the pre-fill — came in August and was −23% on effort, not −40% on time to file).

Rule: **the clock starts at the first signal (the alert)**. A clock that starts later hides the triage queue, which is exactly where delays built up in April–May.
