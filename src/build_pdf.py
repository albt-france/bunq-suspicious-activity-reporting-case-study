"""Build the 8-page PDF: charts (src/charts.py) -> HTML pages (16:9) -> PDF with headless Edge/Chrome, empty metadata.

Every number is read from data/processed (findings.json and public extracts), so the report matches the code.
    python src/build_pdf.py
Outputs: report/report.html, report/bunq_suspicious_activity_reporting_case_study.pdf
"""
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pandas as pd
from pypdf import PdfReader, PdfWriter

import charts

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "report"
PROC = ROOT / "data" / "processed"
PDF_NAME = "bunq_suspicious_activity_reporting_case_study.pdf"
READ_ON = "18 Nov 2026"
DISCLAIMER = "Independent case study based on public data · not affiliated with or endorsed by bunq"
# The AI-use note is written once, in README.md (Methods), and reused here verbatim.
AI_NOTE = next(l[2:].strip() for l in (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
               if l.startswith("- AI-assisted workflow:"))
TITLE = "bunq: making suspicious-activity reporting to France's FIU fast, complete and measurable"


def pct(x, d=0, sign=False):
    return f"{x * 100:{'+' if sign else ''}.{d}f}%"


def page(n, title, subtitle, tags, body, sources):
    t = "".join(f'<div class="tag tag-{x.lower().split()[0]}">{x}</div>' for x in tags)
    return f"""
<section class="page">
  <header><div><h1>{title}</h1><p class="sub">{subtitle}</p></div><div class="tags">{t}</div></header>
  <main>{body}</main>
  <footer><span>{sources}</span><span>{DISCLAIMER}</span><span>{n + 1} / 8</span></footer>
</section>"""


def card(inner, cls="", tag=None):
    tg = f'<span class="ctag ctag-{tag.lower().split()[0]}">{tag}</span>' if tag else ""
    return f'<div class="card {cls}">{tg}{inner}</div>'


def img(src, tag, cap=""):
    return card(f'<figure><img src="{src}"/>{f"<figcaption>{cap}</figcaption>" if cap else ""}</figure>', "fig", tag)


def tile(label, value, text, tag):
    return card(f'<div class="label">{label}</div><div class="big">{value}</div><p>{text}</p>', "tile", tag)


# ------------------------------------------------------------------ pages
def p0(f, ch):
    s, d, i, t = f["sim"], f["did"], f["ibm"], f["tracfin"]
    qs = ["What does bunq publish about its size and its compliance workforce?",
          "How big and how fast-growing is suspicious-activity reporting in France?",
          "How well do simple monitoring rules separate laundering from normal activity?",
          "Which reporting KPIs can be trusted, and which ones lie?",
          "What should a France reporting desk fix first, before the EU AMLR applies on 10 July 2027?"]
    body = f"""<div class="grid4">
      {tile("TRACFIN 2025", f"{t['str_total_2025']:,.0f}", f"suspicious-activity reports received in France, {pct(t['str_growth_2025'], sign=True)} in a year; banks {pct(t['banks_growth'], sign=True)}", "PUBLIC DATA")}
      {tile("SIMPLE RULES (IBM AML)", pct(i['false_alerts_share']), f"of accounts flagged by 4 simple rules are not laundering; recall {pct(i['any_recall'])}", "PUBLIC DATA")}
      {tile("A METRIC THAT LIED", pct(s['tool_change_pct'], sign=True), f"time to file 'improved' in September; recomputed from the alert: {pct(s['true_change_pct'], 1, True)}", "SIMULATED")}
      {tile("PRE-FILL EFFECT", pct(d['did_pct'], sign=True), f"analyst effort per case, difference-in-differences, 95% CI {pct(d['ci_low_pct'])} to {pct(d['ci_high_pct'])}", "SIMULATED")}
    </div>
    <div class="grid3">
      {card('<h2>Five questions</h2><ol class="qs">' + ''.join(f'<li>{q}</li>' for q in qs) + '</ol>')}
      {card(f'''<h2>What the data shows</h2><ol class="reco">
        <li>bunq reports 280 FTE in onboarding, support and compliance (42% of staff) and fee income of €{f['bunq_fe25']:.2f}m from France/Belgium customers (as stated by bunq).</li>
        <li>Tracfin: 93% of French reports come from the financial sector, banks {pct(t['banks_growth'], sign=True)}; its stated challenge is quality.</li>
        <li>Four transparent rules reach {i['lift']:.1f}× the base rate on labelled synthetic data, but miss {pct(1 - i['any_recall'])} of laundering accounts.</li>
        <li>In the simulated desk, a new rule doubled time to file in spring; a schema change cut completeness at draft to {pct(s['complete_draft_jun'])}; a clock change faked a {pct(s['tool_change_pct'])} gain.</li>
        <li>The pre-fill cut analyst effort by {pct(-d['did_pct'])} (DiD; truth 25%).</li></ol>''', '', 'PUBLIC DATA + SIMULATED')}
      {card(f'''<h2>Recommendations for a France reporting desk</h2><ol class="reco">
        <li><b>Quality before volume</b> (Tracfin's own message for 2025): block drafts with missing required fields; track completeness at draft, not only at submission.</li>
        <li><b>One definition per KPI</b>: time to file starts at the alert; deadlines on Paris dates; reports counted once per report_id.</li>
        <li><b>Never credit a step change without a cause</b>: the September "{pct(s['tool_change_pct'])}" was a clock change; the real gain was the August pre-fill ({pct(d['did_pct'])} effort).</li>
        <li><b>Measure what the law cares about</b>: pre-execution reports, follow-ups and the 5-working-day FIU request clock of AMLR art. 69.</li>
        <li><b>Close CAP items with evidence</b>; review overdue items weekly by owner team.</li></ol>
        <p class="note">Methods: SQL (DuckDB), Python, a labelled public AML dataset (IBM, synthetic), a 12-month simulated desk with 8 hidden events,
        difference-in-differences with a week-cluster bootstrap. Simulated numbers show how the methods behave; they are not bunq's figures.</p>''')}
    </div>"""
    return page(0, TITLE, "How a France reporting team can track volume, timeliness and quality of its reports, fix its data problems and prepare for the AMLR 2027, from numbers it can trust.",
                ["OVERVIEW"], body, f"Sources: bunq annual report 2025, Tracfin, ECB, EUR-Lex, IBM AML (read {READ_ON})")


def p1(f, ch):
    b = pd.read_csv(PROC / "bunq_facts.csv").set_index("fact")
    osc, tot = b.loc["fte_onboarding_support_compliance"], b.loc["fte_total"]
    fe = b.loc["fee_income_france_belgium"]
    body = f"""<div class="grid4">
      {tile("USERS", "22 million", "\"serves 22 million users across Europe\" (p. 25), as stated by bunq", "PUBLIC DATA")}
      {tile("STAFF", f"{tot.value_2025:.0f} FTE", f"{osc.value_2025:.0f} in Onboarding, Support, Compliance ({osc.value_2025 / tot.value_2025:.0%}), up from {osc.value_2024:.0f} (p. 79)", "PUBLIC DATA")}
      {tile("FRANCE / BELGIUM", f"€{fe.value_2025 / 1000:.2f}m", f"fee income from customers with a France/Belgium address, vs €{fe.value_2024 / 1000:.2f}m in 2024 (p. 78)", "PUBLIC DATA")}
      {tile("AML AND AI", "AI screening", "\"one of the first banks to win the right to use AI and machine learning for anti-money laundering screening\" (p. 21)", "PUBLIC DATA")}
    </div>
    <div class="grid-1-1-1">
      {img(ch['bunq_fee'], 'PUBLIC DATA', 'bunq annual report 2025, note on fee income by geography (customer address), p. 78.')}
      {img(ch['bunq_staff'], 'PUBLIC DATA', 'bunq annual report 2025, staff table by function, p. 79.')}
      {card('''<h2>What the role does (job posting)</h2><ul class="facts">
        <li>Report suspicious activity to the competent <b>FIUs</b> and apply <b>country-specific</b> reporting requirements.</li>
        <li>Write <b>clear procedures</b>; improve the process through <b>gap analysis</b> and <b>automation</b>.</li>
        <li>Monitor reporting performance with <b>Retool, Looker and Google Sheets</b>; manage open <b>CAP items</b> within deadlines.</li>
        <li>Profile: AML, EDD and reporting requirements; investigation and critical thinking; data-driven; English and French.</li></ul>
        <p class="note">Source: careers.bunq.com, "Reporting Agent (France)", published 10 Nov 2026. bunq B.V. is supervised by De Nederlandsche Bank (annual report, p. 52).
        This study does not describe bunq's internal processes: everything about the desk on pages 4-6 is simulated.</p>''')}
    </div>"""
    return page(1, "bunq grew its onboarding, support and compliance staff to 280 FTE: reporting quality scales with people only if the data is right",
                "Facts as stated by bunq in its 2025 annual report; the France reporting role as described in the job posting.",
                ["PUBLIC DATA"], body, f"bunq annual report 2025 (static.bunq.com), careers.bunq.com · read {READ_ON}")


def p2(f, ch):
    t, e = f["tracfin"], f["ecb"]
    body = f"""<div class="grid-1-1-1 tall">
      {img(ch['tracfin'], 'PUBLIC DATA', 'Tracfin, activity and impact report 2025 (page published 27 Aug 2026).')}
      {card(f'''<h2>Tracfin's message: quality must grow as fast as volume</h2><ul class="facts">
        <li><b>{t['str_total_2025']:,.0f}</b> reports in 2025, <b>{pct(t['str_growth_2025'], sign=True)}</b> in one year, a flow multiplied by six since 2015.</li>
        <li>Financial sector: <b>{t['financial_sector_str']:,.0f}</b> reports, <b>{pct(t['financial_sector_share'])}</b> of the flow; banks and credit institutions <b>{pct(t['banks_growth'], sign=True)}</b>.</li>
        <li>Tracfin's stated challenge: improve the quality of the information sent as quickly as its volume, so that reports can be used directly in investigations.</li>
        <li>How to report (Tracfin): before executing the transaction, through ERMES; no threshold; any new element sent without delay.</li></ul>
        <p class="note">Read in a browser on {READ_ON} (the site refuses scripted requests).</p>''')}
      {card(f'''<h2>Why it matters for a France desk</h2>
        <p>More reports do not mean better reporting. A desk that files fast but incomplete reports adds work for the FIU.
        The KPIs on the next pages therefore weigh <b>completeness and correctness</b> as much as speed.</p>
        <p>France also has more payment fraud than the Netherlands, bunq's home market: card fraud of
        <b>{e['card_fraud_rate_bp_2025S2']['FR']:.1f}</b> vs <b>{e['card_fraud_rate_bp_2025S2']['NL']:.1f}</b> basis points of value in 2025-S2;
        French credit-transfer fraud reached <b>€{e['fr_ct_fraud_2025S2_m']:.0f}m</b> in 2025-S2, {pct(e['fr_ct_fraud_growth'], sign=True)} in a year.</p>
        <p class="note">ECB payment statistics: values in millions (UNIT_MULT = 6, checked). Fraud rate = fraudulent / all transactions, same series key.</p>''')}
    </div>
    <div class="grid1">{img(ch['ecb'], 'PUBLIC DATA', 'ECB Data Portal, PAY dataset, semi-annual, fraudulent transactions sent (FRD_TYP = F) and all transactions (_Z), retrieved ' + READ_ON + '.')}</div>"""
    return page(2, f"France's FIU received {t['str_total_2025']:,.0f} reports in 2025 and asks for quality to grow as fast as volume",
                "Tracfin 2025 figures and ECB payment-fraud statistics, France compared with the Netherlands.",
                ["PUBLIC DATA"], body, f"Tracfin (economie.gouv.fr), ECB Data Portal · read {READ_ON}")


def p3(f, ch):
    i = f["ibm"]
    body = f"""<div class="grid-2-1">
      {img(ch['ibm_rules'], 'PUBLIC DATA', f"IBM AML HI-Small (synthetic, AMLSim, CDLA-Sharing-1.0): {i['transactions']:,} transactions, {i['accounts']:,} accounts, {i['positive_accounts']:,} touched by laundering.")}
      {card(f'''<h2>What four simple rules do</h2><ul class="facts">
        <li>Together they flag <b>{i['any_flagged']:,}</b> accounts ({i['any_alerts_per_1000']:.0f} per 1,000).</li>
        <li><b>Precision {pct(i['any_precision'], 1)}</b>: {i['lift']:.1f}× the base rate of {pct(i['base_rate'], 1)}, but {pct(i['false_alerts_share'])} of alerts are false.</li>
        <li><b>Recall {pct(i['any_recall'])}</b>: most laundering accounts are never flagged.</li>
        <li>At 20 minutes per alert (assumption), <b>{i['analyst_hours_per_true_positive']:.1f} analyst hours</b> per true positive.</li></ul>
        <p class="note">Account-level evaluation; thresholds fixed before looking at the labels. Rules: fan-out and fan-in (8+ counterparties a week),
        structuring (3+ payments of USD 8.5-10k a week), rapid pass-through (80-100% sent on the same day).</p>''')}
    </div>
    <div class="grid-1-1-1">
      {img(ch['ibm_curve'], 'PUBLIC DATA', 'Lower thresholds catch more but bury analysts in false alerts.')}
      {img(ch['ibm_typ'], 'PUBLIC DATA', f"370 labelled attempts. Weakest: {i['weakest_typology']} ({pct(i['weakest_detection'])}).")}
      {card('''<h2>So what for reporting</h2><p>Rules are a <b>funnel input</b>, not the answer: the reporting desk inherits their noise.
        That is why triage capacity, alert-to-case rates and time to file must be read together, and why a new rule
        (page 4) shows up first as a backlog.</p><p>Reports to the FIU should carry the <b>pattern</b> (typology, links between
        transactions) because single-transaction views miss cycles and multi-hop schemes.</p>
        <p class="note">Synthetic data: no real customers, no names. Only aggregates are published.</p>''')}
    </div>"""
    return page(3, f"Simple rules flag laundering accounts at {i['lift']:.1f}× the base rate, yet {pct(i['false_alerts_share'])} of alerts are false",
                "From transactions to alerts: four transparent rules evaluated against labelled synthetic laundering (IBM AML).",
                ["PUBLIC DATA"], body, "IBM AML HI-Small via Hugging Face mirror (CDLA-Sharing-1.0) · sql/01-02")


def p4(f, ch):
    s = f["sim"]
    body = f"""<div class="grid2">
      {img(ch['sim_alerts'], 'SIMULATED', 'France desk. A new monitoring rule multiplies rule alerts by 1.8 from 2 March; year-end scam season in December is a real inflow.')}
      {img(ch['sim_clock'], 'SIMULATED', f"The tool's field starts its clock at case opening from 1 Sep: {s['tool_aug']:.1f} → {s['tool_sep']:.1f} days. From the alert: {s['true_aug']:.1f} → {s['true_sep']:.1f}.")}
    </div>
    <div class="grid-1-1-1">
      {img(ch['sim_backlog'], 'SIMULATED', f"Backlog peaks at {s['backlog_peak']} alerts ({s['backlog_peak_month']}) until triage capacity is reinforced on 20 Apr.")}
      {img(ch['sim_ontime'], 'SIMULATED', 'Internal 14-day target (not a legal deadline). The UTC check counts after-midnight submissions as on time.')}
      {card(f'''<h2>Reading the three stories</h2><ul class="facts">
        <li><b>New rule (March)</b>: real operational effect. Alerts {s['alerts_feb']:,} → {s['alerts_apr']:,} a month; median time to file {s['true_feb']:.0f} → {s['true_may']:.0f} days; on time {pct(s['ontime_feb'])} → {pct(s['ontime_may'])}.</li>
        <li><b>December</b>: a seasonal inflow of scam alerts, not a process failure. Plan capacity, do not open a CAP item.</li>
        <li><b>September</b>: a <b>definition artefact</b>. The {pct(s['tool_change_pct'])} is not credited. Always recompute from raw timestamps and check the clock start.</li></ul>''')}
    </div>"""
    return page(4, f"Volume, timeliness and a metric that lied: a {pct(-s['tool_change_pct'])} 'faster filing' was only a clock that started later",
                "Simulated France desk, Nov 2025 - Oct 2026. Three hidden events: a new rule, the year-end spike, a KPI definition change.",
                ["SIMULATED"], body, "src/simulate.py (seed 42) · sql/03_reporting_funnel.sql · docs/KPI_DEFINITIONS.md")


def p5(f, ch):
    s, d = f["sim"], f["did"]
    body = f"""<div class="grid2">
      {img(ch['sim_quality'], 'SIMULATED', f"Schema change (11 May - 14 Jul): counterparty country and IBAN lost in 14% of drafts; QA catches most, not all.")}
      {img(ch['sim_did'], 'SIMULATED', 'Weekly geometric mean of analyst hours per case. Grey band: pre period. Parallel before August, gap after.')}
    </div>
    <div class="grid4">
      {tile("COMPLETE AT DRAFT, JUNE", pct(s['complete_draft_jun']), f"QA return rate {pct(s['returns_jun'])} vs {pct(s['returns_apr'], 1)} in April; {pct(1 - s['complete_sub_jun'], 1)} of June reports still went out incomplete", "SIMULATED")}
      {tile("DUPLICATE SUBMISSIONS", f"{s['duplicate_rows']}", "extra submission rows from a retry bug (Jun-Jul, both desks): count reports by report_id, not by row", "SIMULATED")}
      {tile("UTC VS PARIS", f"{s['utc_misclassified']}", f"reports ({pct(s['utc_misclassified_share'], 1)}) change on-time status when the deadline is checked on Paris dates", "SIMULATED")}
      {tile("PRE-FILL, DiD", pct(d['did_pct'], sign=True), f"effort per case, 95% CI {pct(d['ci_low_pct'])} to {pct(d['ci_high_pct'])} (week-cluster bootstrap); true simulated effect −25%", "SIMULATED")}
    </div>"""
    return page(5, "Quality before volume: a broken schema, duplicates and UTC dates distort the numbers; the pre-fill cut effort by about a fifth",
                "Simulated France desk with a Benelux control desk. Data-quality events found from the data, then fixed in the pipeline.",
                ["SIMULATED"], body, "sql/04_quality.sql · sql/06_did_prefill.sql · src/findings.py · src/prefill_report.py (blocking check + tests)")


def p6(f, ch):
    c = f["cap"]
    steps = ["Alert", "Triage", "Case", "Investigation", "Decision", "Pre-filled draft", "QA (4 eyes)", "ERMES submission", "Record & archive"]
    flow = '<div class="flow">' + "".join(f'<div class="step">{x}</div>' for x in steps) + "</div>"
    gap = [("Content of the report", "Blocking completeness check", "High", "Done / monitor"),
           ("When to report (before execution)", "pre_execution flag + same-day KPI", "High", "Open"),
           ("FIU requests: 5 working days (AMLR art. 69)", "Request register + business-day clock", "High", "Open"),
           ("Deadline on Paris dates", "Paris-date logic + tests", "High", "Fixed"),
           ("CAP governance", "Evidence to close; weekly review", "High", "Open"),
           ("Confidentiality (art. 73; L. 561-18 CMF as cited by Tracfin)", "IDs only in KPI data", "Medium", "Open")]
    rows = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{p}</td><td>{s}</td></tr>" for a, b, p, s in gap)
    body = f"""{card('<h2>Procedure in one picture (illustrative)</h2>' + flow + '''<p class="small">Roles, not names: triage analyst → investigator → reviewer (four eyes) → reporting function.
        A draft with a missing required field is <b>blocked</b>. A "no report" decision is recorded with its reasons (AMLR art. 77(1)(b)).
        <b>Confidentiality</b>: never tell the customer, or a third party, that a report was made or is being prepared (Tracfin; AMLR art. 73).</p>''', "auto", "SIMULATED")}
    <div class="grid-1-1-1">
      {img(ch['sim_cap'], 'SIMULATED', f"{c['items']} items: {c['overdue']} overdue, both in team {', '.join(c['overdue_teams'])}; {c['no_evidence']} closed without evidence.")}
      {card(f'<h2>Gap analysis, top items</h2><table class="small"><tr><th>Requirement</th><th>Action</th><th>Priority</th><th>Status</th></tr>{rows}</table>'
            '<p class="note">Full table: docs/GAP_ANALYSIS.md and the workbook. Process column is simulated. To be confirmed with Compliance / Legal; not legal advice.</p>', "", "SIMULATED + PUBLIC DATA")}
      {card('''<h2>AMLR: what changes on 10 July 2027</h2><ul class="facts">
        <li>Art. 69: report suspicions to the FIU and reply to its requests within <b>5 working days</b> (may be shortened or extended).</li>
        <li>Art. 69(3): AMLA standards on the <b>report format</b> (draft due 10 July 2026); art. 69(5): guidelines on <b>indicators</b> by 10 July 2027.</li>
        <li>Art. 71: refrain from executing suspected transactions until reported.</li>
        <li>Art. 73: prohibition of disclosure. Art. 77: keep the assessment, reported or not.</li></ul>
        <p class="note">Regulation (EU) 2024/1624, EUR-Lex text, articles checked on ''' + READ_ON + '.</p>', "", "PUBLIC DATA")}
    </div>"""
    return page(6, "Procedures, CAP and AMLR 2027 readiness: the highest-priority gaps are all measurable",
                "An illustrative procedure, the corrective-action tracker and the gap analysis against Tracfin's requirements and the AMLR.",
                ["SIMULATED", "PUBLIC DATA"], body, "docs/REPORTING_PROCEDURE.md · docs/GAP_ANALYSIS.md · sql/05_cap_tracking.sql · EUR-Lex 32024R1624")


def p7(f, ch):
    body = f"""<div class="grid3">
      {card(f'''<h2>Sources (PUBLIC DATA)</h2><ul class="small">
        <li>bunq annual report 2025 (static.bunq.com), pages 6, 21, 25, 52, 55, 78, 79; job posting on careers.bunq.com. Saved once from a browser (static.bunq.com robots.txt disallows scripts).</li>
        <li>Tracfin: activity and impact report 2025 page; "Quand et comment déclarer un soupçon"; "La confidentialité de la déclaration de soupçon" (economie.gouv.fr), read in a browser.</li>
        <li>ECB Data Portal, PAY dataset (payment fraud), API, licence: ECB re-use terms.</li>
        <li>Regulation (EU) 2024/1624 (AMLR), EUR-Lex.</li>
        <li>IBM "AML" HI-Small, synthetic (AMLSim), Hugging Face mirror, licence <b>CDLA-Sharing-1.0</b>.</li></ul>
        <p class="note">All read or retrieved on {READ_ON}. Polite collection: robots.txt respected, ≥ 3 s between requests, no account, no form.</p>''')}
      {card('''<h2>Methods</h2><ul class="small">
        <li><b>SQL</b> (DuckDB; CTEs and window functions): IBM profile and rules; funnel, timeliness, backlog, quality, CAP, DiD cells.</li>
        <li><b>Rules</b> evaluated at account level: precision, recall, alerts per 1,000 accounts; threshold curve.</li>
        <li><b>Simulation</b>: 12 months, 2 desks, seed 42, 8 hidden events found without the answer key.</li>
        <li><b>Difference-in-differences</b> on log effort, France vs Benelux, 95% interval from a bootstrap over weeks.</li>
        <li><b>Automation</b>: pre-filled draft + blocking completeness check, with tests (missing field, duplicate, midnight, clock).</li></ul>''')}
      {card('''<h2>Assumptions (SIMULATED)</h2><ul class="small">
        <li>France desk 55 alerts a day, Benelux 40; 75% rules, 20% internal referrals, 5% external requests.</li>
        <li>28-90% of alerts become cases by source; 40% of cases become reports.</li>
        <li>Internal target 14 calendar days from alert to submission: a simulated rule, not a legal deadline.</li>
        <li>20 minutes to review an alert (cost per true positive).</li>
        <li>Volumes are plausible for an online bank; they are <b>not</b> bunq's.</li></ul>''')}
    </div>
    <div class="grid3">
      {card('''<h2>Limits</h2><ul class="small">
        <li>No real bunq data: pages 4-6 show how the methods behave, not bunq's performance, processes or failures.</li>
        <li>IBM data is synthetic; real laundering is rarer, more varied and adaptive.</li>
        <li>Legal points only from the sources read; French code articles cited as stated by Tracfin. Not legal advice: to be confirmed with Compliance / Legal.</li>
        <li>Looker files are illustrative and not validated in a Looker instance.</li></ul>''')}
      {card('''<h2>How to re-run</h2><pre>pip install -r requirements.txt
python src/fetch_public.py
python src/download_ibm.py
python src/extract_ibm_aml.py
python src/simulate.py
python src/run_sql.py
python src/findings.py
python src/prefill_report.py
pytest
python src/build_excel.py
python src/build_dashboard.py
python src/build_pdf.py</pre>''')}
      {card(f'''<h2>Deliverables</h2><ul class="small"><li>This PDF and an interactive HTML dashboard (4 tabs).</li>
        <li>Workbook: weekly KPIs, CAP tracker, SLA calculator, gap analysis (Excel / Google Sheets formulas).</li>
        <li>Procedure, KPI definitions, gap analysis, data-issues log, glossary; LookML view; one notebook.</li></ul>
        <h2>AI note</h2><p class="small">{AI_NOTE}</p>''')}
    </div>"""
    return page(7, "Methods, limits and AI note", "What is public, what is simulated, how each number is produced, and what it cannot tell.",
                ["OVERVIEW"], body, "data/SOURCES.md · DATA_ISSUES_LOG.md")


CSS = """
@page { size: 1600px 900px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: 'Segoe UI', Arial, sans-serif; color: #0B0B0B; background: #F4F4F2; }
.page { width: 1600px; height: 900px; padding: 30px 44px 22px; display: flex; flex-direction: column; page-break-after: always; overflow: hidden; background: #F4F4F2; }
header { display: flex; justify-content: space-between; align-items: flex-start; gap: 30px; }
h1 { font-size: 27px; margin: 0 0 6px; font-weight: 700; line-height: 1.15; max-width: 1300px; }
.sub { margin: 0; color: #52514E; font-size: 15px; max-width: 1300px; }
.tags { display: flex; gap: 6px; }
.tag, .ctag { font-size: 12px; font-weight: 700; letter-spacing: .08em; padding: 5px 10px; border-radius: 4px; white-space: nowrap; color: #52514E; }
.ctag { position: absolute; top: 8px; right: 10px; font-size: 9.5px; padding: 2px 6px; }
.tag-public, .ctag-public { background: #E3EEFB; color: #1C5CAB; } .tag-simulated, .ctag-simulated { background: #FBE9E0; color: #9A3B12; } .tag-overview { color: #52514E; }
main { flex: 1; display: flex; flex-direction: column; gap: 12px; margin-top: 14px; min-height: 0; }
footer { display: flex; justify-content: space-between; gap: 20px; font-size: 11px; color: #898781; margin-top: 10px; }
.card { position: relative; background: #FCFCFB; border: 1px solid #E1E0D9; border-radius: 8px; padding: 12px 16px; min-height: 0; overflow: hidden; }
.card h2 { font-size: 16px; margin: 0 0 6px; padding-right: 90px; }
.card p, .card li { font-size: 13.5px; line-height: 1.4; margin: 3px 0; color: #2B2A27; }
.card ul, .card ol { padding-left: 18px; margin: 4px 0; }
.fig { padding: 10px 12px 8px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.grid1 { display: grid; grid-template-columns: 1fr; flex: 1; min-height: 0; }
.grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.g0 { display: grid; grid-template-columns: 1fr 1.25fr; gap: 12px; flex: 1; min-height: 0; }
.grid-2-1 { display: grid; grid-template-columns: 1.6fr 1fr; gap: 12px; flex: 1.1; min-height: 0; }
.grid-1-1-1 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
figure { margin: 0; height: 100%; display: flex; flex-direction: column; }
figure img { width: 100%; flex: 1; min-height: 0; object-fit: contain; }
figcaption { font-size: 11.5px; color: #52514E; margin-top: 3px; }
.tile .label { font-size: 12px; font-weight: 700; color: #52514E; letter-spacing: .04em; }
.tile .big { font-size: 40px; font-weight: 700; margin: 2px 0; color: #0B0B0B; }
.tile p { font-size: 13px; color: #52514E; }
.auto { flex: 0 0 auto !important; } .tall { flex: 1.2 !important; }
.qs li { font-size: 15px !important; margin: 8px 0; } .reco li { font-size: 14px !important; margin: 6px 0; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th { text-align: left; color: #52514E; font-weight: 600; border-bottom: 1px solid #E1E0D9; padding: 4px 6px; }
td { border-bottom: 1px solid #EFEEE9; padding: 4px 6px; vertical-align: top; }
table.small, .small, .small li { font-size: 12.5px !important; }
.note { font-size: 11.5px !important; color: #6B6A65 !important; }
.facts li { font-size: 13.5px !important; margin: 6px 0; }
pre { background: #F4F4F2; border-radius: 6px; padding: 8px 10px; font-size: 11.5px; margin: 4px 0; line-height: 1.3; }
.flow { display: flex; gap: 0; margin: 10px 0 8px; }
.step { flex: 1; background: #E3EEFB; color: #1C5CAB; font-weight: 600; font-size: 13px; text-align: center; padding: 12px 6px;
        clip-path: polygon(0 0, 90% 0, 100% 50%, 90% 100%, 0 100%, 10% 50%); margin-right: -8px; }
.step:first-child { clip-path: polygon(0 0, 90% 0, 100% 50%, 90% 100%, 0 100%); }
"""


def build_html() -> Path:
    ch = charts.build_all()
    f = json.loads((PROC / "findings.json").read_text(encoding="utf-8"))
    f["bunq_fe25"] = pd.read_csv(PROC / "bunq_facts.csv").set_index("fact").loc["fee_income_france_belgium", "value_2025"] / 1000
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>bunq suspicious-activity reporting case study</title><style>{CSS}</style></head><body>
{''.join(p(f, ch) for p in [p0, p1, p2, p3, p4, p5, p6, p7])}
</body></html>"""
    out = REP / "report.html"
    out.write_text(html, encoding="utf-8")
    return out


def find_browser() -> str:
    for c in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe", shutil.which("msedge") or "",
              shutil.which("google-chrome") or "", shutil.which("chromium") or ""]:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError("Edge or Chrome is needed to print the PDF")


def print_pdf(html: Path) -> Path:
    pdf, tmp = REP / PDF_NAME, REP / "_print.pdf"
    profile = tempfile.mkdtemp()
    subprocess.run([find_browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={profile}",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=5000",
                    f"--print-to-pdf={tmp}", html.as_uri()], check=True, timeout=180)
    last = -1
    for _ in range(120):
        time.sleep(1)
        size = tmp.stat().st_size if tmp.exists() else -1
        if size > 0 and size == last:
            break
        last = size
    shutil.rmtree(profile, ignore_errors=True)
    reader, writer = PdfReader(str(tmp)), PdfWriter()
    for pg in reader.pages:
        writer.add_page(pg)
    writer.add_metadata({"/Title": "bunq - suspicious-activity reporting case study", "/Author": "", "/Creator": "", "/Producer": ""})
    with open(pdf, "wb") as fh:
        writer.write(fh)
    tmp.unlink()
    return pdf


def main():
    html = build_html()
    pdf = print_pdf(html)
    print("written", pdf.relative_to(ROOT), len(PdfReader(str(pdf)).pages), "pages")


if __name__ == "__main__":
    main()
