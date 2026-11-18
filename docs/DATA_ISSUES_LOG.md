# Data issues log

Public-data issues are real (found while building this case). Desk issues are **SIMULATED** and were planted, then found
from the data without using the answer key.

| # | Data | Issue | Evidence | Impact | Fix | Status |
|---|---|---|---|---|---|---|
| 1 | IBM AML (public, synthetic) | My own load joined a currency-rate table where US Dollar appeared twice | Row count 6,973,505 after the join vs 5,078,345 in the file (+37%); laundering rows 7,089 vs 5,177 documented | Every count and rate would have been wrong | Rate table built without US Dollar duplicates; `assert` that the join adds no row | Fixed |
| 2 | IBM AML (public, synthetic) | 9 rows repeated exactly (all 11 columns) | `SELECT DISTINCT` count = 5,078,336 | Negligible | Exact duplicates removed | Fixed |
| 3 | IBM AML (public) | Two columns named `Account` | CSV header | Ambiguous sender / receiver | Renamed `from_account`, `to_account`; key = bank \| account | Fixed |
| 4 | IBM AML (public) | Mixed currencies | 15 payment currencies | Thresholds in one currency are meaningless | Converted to USD with rates implied by the data | Fixed |
| 5 | ECB payment statistics (public) | Values are in **millions** (`UNIT_MULT = 6`), counts too | API attribute | Factor 10⁶ errors | Unit read from the attribute, not assumed | Fixed |
| 6 | ECB (public) | NL total credit-transfer value missing in 2025-S2 | Empty cell | No NL credit-transfer fraud rate | Compare card fraud rates instead | Documented |
| 7 | Desk (SIMULATED) | Schema change: counterparty country and IBAN missing in 14% of FR drafts (May–Jul) | Completeness at draft 83% in June; QA returns 17% (vs 2% in April) | Rework, and ~4% of June reports submitted incomplete | Blocking completeness check; schema test | Fixed |
| 8 | Desk (SIMULATED) | Retry bug: duplicate submission rows (Jun–Jul) | Same `report_id`, new `submission_id`, 2–15 min later | Report counts inflated | Count distinct `report_id`; idempotent submission | Fixed |
| 9 | Desk (SIMULATED) | Tool KPI clock moved from alert to case opening (Sep) | `tool_clock_start` changes; tool median −40%, true median flat | A false 40% "improvement" | KPI recomputed from raw timestamps | Fixed |
| 10 | Desk (SIMULATED) | Deadline check on UTC dates | ~2.2% of reports change on-time status in Paris time | On-time rate overstated | Paris-date logic + tests | Fixed |
| 11 | Desk (SIMULATED) | CAP item closed without evidence | `evidence_attached = false` on a closed item | Closure cannot be shown to an auditor | Closed only with evidence | Open |
