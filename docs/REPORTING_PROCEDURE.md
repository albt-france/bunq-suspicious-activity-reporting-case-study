# Suspicious-activity reporting procedure — France desk (illustrative)

> **Status: illustrative procedure written for an independent case study.** It describes a *simulated* desk, not bunq's
> real process. Legal points are limited to what the sources below say; everything else is marked
> **to be confirmed with Compliance / Legal**. This is not legal advice.

Sources read (18 Nov 2026):
- Tracfin, *Quand et comment déclarer un soupçon ?* and *La confidentialité de la déclaration de soupçon* (economie.gouv.fr).
- Regulation (EU) 2024/1624 (AMLR), EUR-Lex, articles 69, 71, 73 and 77; applies from 10 July 2027.

## 1. Scope and roles
Roles only, never names.

| Role | Responsibility |
|---|---|
| **Triage analyst** | Reviews alerts, closes false positives with a reason, escalates the rest to a case. |
| **Investigator (preparer)** | Investigates the case, decides *report / no report*, writes the analysis. |
| **Reviewer (four eyes)** | Checks the draft against the 10-point QA list, returns or approves. |
| **Reporting agent / compliance officer function** | Submits the report to the FIU, records the submission, handles FIU requests. |
| **Reporting analyst (data)** | Owns the KPIs, the data-quality checks and the CAP tracker. |

## 2. From alert to submission

```
Alert ──► Triage ──► Case opened ──► Investigation ──► Decision ──► Draft (pre-filled) ──► QA (4 eyes) ──► Submission ──► Record & archive
 (rule,     (close or     │              │              │  no report: record the        │ blocked if a       │ returned:      │ ERMES (FR)
 referral,   escalate)    │              │              │  assessment and the reason    │ required field     │ back to         │
 request)                 │              │              │                                │ is missing         │ preparer        │
```

1. **Alert intake.** Every alert has a source: monitoring rule, internal referral (support, onboarding, fraud), or external request. Timestamp stored in UTC.
2. **Triage.** Close with a coded reason, or escalate. A closed alert keeps its reason (auditability).
3. **Case opening.** One case per subject and pattern; link all related alerts to the case.
4. **Investigation.** Review the customer file (CDD; EDD where the risk is high), the transactions, counterparties and the links between transactions. AMLR art. 69(2) lists what a suspicion is based on: the characteristics of the customer and counterparts, size and nature of the transaction, methods and patterns, links between transactions, origin, destination or use of funds.
5. **Decision.** *Report* or *no report*. Both are recorded with the analysis: AMLR art. 77(1)(b) requires keeping a record of the assessment **whether or not** it results in a report.
6. **Draft.** Pre-filled by `src/prefill_report.py`; the analysis is written by the investigator. A draft with a missing required field is **blocked** (section 3).
7. **QA (four eyes).** The reviewer applies the 10-point list (section 4). Returned drafts go back with a coded reason.
8. **Submission.** In France, through **ERMES**, Tracfin's online platform (Tracfin: the professional must use ERMES as a priority and be registered as a *déclarant*).
9. **Timing.** Tracfin: the report is made **before the transaction is executed**, so that Tracfin can use its right of opposition; the professional must refrain from executing a transaction it suspects. Three exceptions allow reporting after execution (impossible to postpone; postponing could hinder investigations; suspicion arose after execution) — then Tracfin must be informed **without delay**. AMLR art. 71 sets a similar rule from 2027 (refrain until reported; may proceed after assessing the risk if no instruction within 3 working days). The internal 14-day target in this case study applies to post-execution alerts only and is **not** a legal deadline — *to be confirmed with Compliance / Legal*.
10. **New information.** Tracfin: any new element that weakens, supports or changes a report must be sent **without delay**.
11. **FIU requests.** AMLR art. 69(1): reply to FIU information requests within **5 working days** (the FIU may shorten it, including to less than 24 hours, or extend it). Track each request as a dated item.
12. **Record and archive.** Keep the case file, the assessment, the report and supporting evidence (AMLR art. 77). Retention period in France: *to be confirmed with Compliance / Legal*.

## 3. Required fields (blocking)
`subject_id`, `account_id`, `amount_eur`, `transaction_dates`, `counterparty_country`, `counterparty_iban`, `typology`,
narrative ≥ 30 words, `alert_source`, `alert_ts_utc`.
Tracfin: by law a report contains the identification of the reporting entity, the identification and knowledge of the
customer or beneficial owner, and the analysis that motivates the suspicion. There is **no threshold** for reporting.

## 4. QA checklist (10 points)
1. All required fields present (the tool blocks otherwise).
2. Subject and accounts match the case file (IDs, not copied text).
3. Amounts and dates reconcile with the transaction extract.
4. Counterparties identified (country, IBAN) or the gap is explained.
5. The narrative explains *why* it is suspicious (facts, pattern, links), not only *what* happened.
6. Typology chosen from the controlled list.
7. CDD / EDD status stated; EDD documents attached when required.
8. Timing checked in **Paris local time**; post-execution reports explain why (Tracfin's three cases).
9. No duplicate: one report per case unless it is a documented follow-up.
10. Confidentiality: no customer contact planned that could reveal the report.

## 5. Confidentiality (tipping-off)
- Tracfin: the report is confidential (art. L. 561-18 CMF, *as cited by Tracfin*). This covers its existence, its content and what follows. The reporting entity must **not inform the customer** that a report was made, nor discuss its existence or content with a third party. Breaches are criminal offences (art. L. 574-1 CMF, *as cited by Tracfin*). Limited exceptions exist (supervisory authority; for financial-sector entities, revealing the existence — not the content — to judicial authorities).
- AMLR art. 73 (from 2027): no disclosure to the customer or third parties that transactions are being assessed, that information is or will be transmitted, or that an analysis may be carried out; listed exceptions (competent authorities, same group, etc.).
- In practice: support scripts never mention reports; case notes are restricted; data exports for KPIs carry IDs only, never narratives.

## 6. Controls on the data (owned by the reporting analyst)
| Control | Why | Where |
|---|---|---|
| Count reports by `report_id`, not by submission row | retry bugs duplicate rows | `sql/04_quality.sql` |
| Time to file starts at the **alert** | a later clock start flatters the KPI | `docs/KPI_DEFINITIONS.md` |
| Deadlines checked on **Paris** dates | UTC dates misclassify after-midnight submissions | `src/prefill_report.py`, tests |
| Field completeness at draft and at submission | schema changes silently drop fields | `sql/04_quality.sql` |
| CAP item closed only with evidence | closure without proof is not closure | `sql/05_cap_tracking.sql` |
