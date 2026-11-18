# Sources and licences

All sources read or retrieved on **18 Nov 2026**. Raw files stay in `data/raw/` (not published); only extracts and aggregates are in `data/processed/`.

| Source | What is used | Access | Licence / terms | File |
|---|---|---|---|---|
| bunq annual report 2025 — https://static.bunq.com/website/documents/bunq-report-annual-2025-en.pdf | Users (p. 6, 25, 55), staff by function (p. 79), fee income by geography (p. 78), AML/AI statement (p. 21), supervisor (p. 52) — **as stated by bunq** | Saved once from a browser (robots.txt of static.bunq.com disallows scripts), read locally | © bunq; short factual quotes | `processed/bunq_facts.csv`, `processed/bunq_fee_income_geography.csv` |
| bunq job posting "Reporting Agent (France)" — https://careers.bunq.com/o/reporting-agent-france-3 (published 10 Nov 2026) | Role description | One request (robots.txt allows) | © bunq | — |
| Tracfin, activity and impact report 2025 — https://www.economie.gouv.fr/tracfin/tracfin-publie-son-rapport-dactivite-et-dimpact-2025 (published 27 Aug 2026) | Report volumes, sector shares, growth, quality message | Read in a browser (scripted requests get 403) | Public information | `processed/tracfin_2025.csv` |
| Tracfin, "Quand et comment déclarer un soupçon ?" and "La confidentialité de la déclaration de soupçon" (economie.gouv.fr) | When/how to report (ERMES, before execution), confidentiality (L. 561-18 CMF as cited by Tracfin) | Read in a browser | Public information | `docs/REPORTING_PROCEDURE.md`, `docs/GAP_ANALYSIS.md` |
| ECB Data Portal, PAY dataset — `https://data-api.ecb.europa.eu/service/data/PAY/H.FR+NL.W0.CT0+CP0+DD+EMP0.1.F+_Z.N.EUR+PN` | Payment fraud (FRD_TYP = F) and all transactions (_Z), FR and NL, semi-annual; UNIT_MULT = 6 (millions) | API | ECB statistics re-use terms (source acknowledged) | `processed/ecb_payment_fraud.csv` |
| Regulation (EU) 2024/1624 (AMLR) — https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32024R1624 | Articles 69, 70, 71, 73, 77; application date 10 July 2027 | One request | © European Union, re-use authorised | `docs/GAP_ANALYSIS.md` |
| IBM "AML" HI-Small (AMLSim, **synthetic**) — Hugging Face mirror `OsamaMIT/IBM-AML-HI-Small` | 5,078,345 transactions with laundering labels; 370 laundering attempts by typology | Download (`src/download_ibm.py`) | **CDLA-Sharing-1.0** | aggregates only: `processed/ibm_*.parquet` |

Not used: Himalayas job page (behind Cloudflare, not bypassed), Légifrance (403 to scripts; French code articles cited as stated by Tracfin), any sanctions or asset-freeze list.
