# Gap analysis — France desk vs Tracfin requirements and the EU AMLR (from 10 July 2027)

> Illustrative. "Current process" is the **SIMULATED** desk of this case study, not bunq's process.
> Requirements are quoted only from sources read on 18 Nov 2026: Tracfin pages (economie.gouv.fr) and the text of
> Regulation (EU) 2024/1624 on EUR-Lex (article numbers checked in the text). French code articles are cited *as stated by
> Tracfin* (Légifrance not read). **Every line: to be confirmed with Compliance / Legal. Not legal advice.**

Priority score = impact (1–3) × likelihood (1–3); 6–9 = high, 3–4 = medium, 1–2 = low (same formula in the workbook).

| # | Requirement | France (Tracfin) | EU AMLR from 10 July 2027 | Current process (SIMULATED) | Gap | Action | Impact | Likelihood | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | When to report | Before executing the transaction (right of opposition); after execution only in 3 cases, then "without delay" | Art. 71: refrain from executing until reported; may proceed after risk assessment if no FIU instruction within 3 working days | Timeliness measured only alert → submission against a 14-day internal target | Pre-execution cases are not flagged or measured separately | Add a `pre_execution` flag and a same-day KPI for held transactions | 3 | 2 | 6 high | Open |
| 2 | Reporting channel | ERMES, as a priority; registration as *déclarant* | Art. 69(3): AMLA draft ITS on the report format by 10 July 2026 | ERMES submission; fields from our own schema | Our field list may not map 1:1 to the future EU format | Keep a field-mapping table; review it when the ITS is adopted | 2 | 2 | 4 medium | Watch |
| 3 | Content | Identification of the reporting entity, of the customer/beneficial owner, and the analysis motivating the suspicion; no threshold | Art. 69(2): suspicion based on customer and counterparts, size/nature, methods and patterns, links, origin/destination of funds | 14% of FR drafts lost counterparty country and IBAN (May–Jul schema change) | Required fields were not enforced by the tool | Blocking completeness check (`src/prefill_report.py`) + monitoring of completeness at draft | 3 | 3 | 9 high | Done (tool) / monitor |
| 4 | Follow-up information | New elements that confirm, weaken or change a report: send without delay | Art. 69(1)(a): respond to FIU requests for additional information | No link between follow-ups and the original report | Follow-ups may be filed as new reports (duplicate counts) | `follow_up_of` field; count follow-ups apart | 2 | 2 | 4 medium | Open |
| 5 | FIU information requests | — (not covered by the pages read) | Art. 69(1): reply within 5 working days; FIU may shorten (incl. < 24 h) or extend | Requests are alerts with source `external_request`; no SLA clock | No 5-working-day tracker | Add a request register with a business-day clock (FR calendar) | 3 | 2 | 6 high | Open |
| 6 | Confidentiality | L. 561-18 CMF (as cited by Tracfin): existence, content and follow-up are confidential; no informing the customer; sanction L. 574-1 | Art. 73: prohibition of disclosure, with listed exceptions | Narratives in some exports used for KPIs | KPI datasets should carry IDs only | Strip narratives from analytics extracts; access review | 3 | 1 | 3 medium | Open |
| 7 | Record keeping | — (retention period to be confirmed) | Art. 77(1)(b): keep a record of the assessment whether or not a report is made, and a copy of the report | "No report" decisions stored without a structured reason | Weak audit trail for no-report decisions | Mandatory reason code + analysis for every no-report | 2 | 2 | 4 medium | Open |
| 8 | Duplicate submissions | — | — (data-quality control) | Retry bug duplicated 3% of submissions in Jun–Jul | Counts inflated; FIU may receive the same report twice | Idempotent submission key = `report_id`; daily duplicate check | 2 | 2 | 4 medium | Fixed / monitor |
| 9 | Time accuracy | — | — (data-quality control) | Deadline check on UTC dates | ~2% of reports misclassified on time vs late | All deadline logic on Europe/Paris dates (tested) | 2 | 3 | 6 high | Fixed (tests) |
| 10 | Indicators of suspicion | — | Art. 69(5): AMLA guidelines on indicators by 10 July 2027 | Typology list maintained locally | Typology list may diverge from AMLA indicators | Map typologies to AMLA indicators when published | 2 | 2 | 4 medium | Watch |
| 11 | Corrective actions (CAP) | — | — (governance) | 2 overdue CAP items (team T3); 1 closed without evidence | Closure without proof; slippage concentrated in one team | Evidence required to close; weekly CAP review | 2 | 3 | 6 high | Open |

## Reading the table
- **France today** is the reference until the AMLR applies; the AMLR column shows what to prepare for, not what applies now.
- High-priority items (1, 3, 5, 9, 11) are all **measurable**: each has a KPI in `docs/KPI_DEFINITIONS.md` or the workbook.
- Items marked *Watch* depend on texts not yet adopted or published (AMLA standards and guidelines).
