"""Build excel/reporting_ops_tracker.xlsx: real formulas, compatible with Excel and Google Sheets, empty metadata.

Tabs: README · Weekly KPIs · CAP tracker · SLA calculator · Gap analysis.
Functions used: IF, AND, OR, INT, COUNTIF, COUNTIFS, AVERAGE, WORKDAY, MAX, ROUND (all exist in both tools).
Data rows are SIMULATED (src/simulate.py). After writing, expected formula results are recomputed in Python
(check_expected) so the workbook can be verified without opening it.
    python src/build_excel.py
"""
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "data" / "simulated"
OUT = ROOT / "excel" / "reporting_ops_tracker.xlsx"
AS_OF = datetime(2026, 10, 31)
HEAD = PatternFill("solid", fgColor="E3EEFB")
INPUT = PatternFill("solid", fgColor="FFF4D6")
RED = PatternFill("solid", fgColor="FBE0E0")
BOLD = Font(bold=True)
FR_HOLIDAYS = ["2026-01-01", "2026-04-06", "2026-05-01", "2026-05-08", "2026-05-14", "2026-05-25", "2026-07-14",
               "2026-08-15", "2026-11-01", "2026-11-11", "2026-12-25", "2027-01-01", "2027-03-29", "2027-05-01",
               "2027-05-06", "2027-05-08", "2027-05-17", "2027-07-14", "2027-08-15", "2027-11-01", "2027-11-11",
               "2027-12-25"]
GAP = [  # requirement, France, AMLR, gap, action, impact, likelihood, status
    ("When to report", "Before execution; after only in 3 cases, then without delay (Tracfin)", "Art. 71: refrain until reported; 3 working days",
     "Pre-execution cases not measured", "pre_execution flag + same-day KPI", 3, 2, "Open"),
    ("Reporting channel / format", "ERMES (Tracfin)", "Art. 69(3): AMLA ITS on format", "Field mapping to future EU format",
     "Field-mapping table", 2, 2, "Watch"),
    ("Content of the report", "Entity, customer/BO, analysis; no threshold (Tracfin)", "Art. 69(2): basis of suspicion",
     "Required fields not enforced (schema change)", "Blocking completeness check", 3, 3, "Done / monitor"),
    ("Follow-up information", "New elements without delay (Tracfin)", "Art. 69(1)(a)", "Follow-ups not linked",
     "follow_up_of field", 2, 2, "Open"),
    ("FIU information requests", "-", "Art. 69(1): 5 working days", "No business-day clock", "Request register + WORKDAY clock", 3, 2, "Open"),
    ("Confidentiality", "L. 561-18 CMF as cited by Tracfin", "Art. 73", "Narratives in analytics extracts",
     "IDs only in KPI data", 3, 1, "Open"),
    ("Record of assessment", "Retention: to be confirmed", "Art. 77(1)(b)", "No-report reasons unstructured",
     "Mandatory reason code", 2, 2, "Open"),
    ("Duplicate submissions", "-", "-", "Retry bug 3% Jun-Jul", "Idempotent key = report_id", 2, 2, "Fixed / monitor"),
    ("Time accuracy", "-", "-", "UTC dates in deadline check", "Paris-date logic + tests", 2, 3, "Fixed"),
    ("Indicators of suspicion", "-", "Art. 69(5): AMLA guidelines by 10 Jul 2027", "Local typology list",
     "Map to AMLA indicators", 2, 2, "Watch"),
    ("CAP governance", "-", "-", "2 overdue (T3), 1 closed w/o evidence", "Evidence to close; weekly review", 2, 3, "Open"),
]


def weekly_kpis():
    a = pd.read_parquet(SIM / "alerts.parquet")
    c = pd.read_parquet(SIM / "cases.parquet")
    r = pd.read_parquet(SIM / "reports.parquet")
    r1 = r.sort_values("submitted_ts_utc").drop_duplicates("report_id")
    r1 = r1.merge(a[["case_id", "alert_ts_utc"]].dropna(), on="case_id")
    paris = lambda s: s.dt.tz_localize("UTC").dt.tz_convert("Europe/Paris").dt.tz_localize(None)
    r1["days"] = (r1.submitted_ts_utc - r1.alert_ts_utc).dt.total_seconds() / 86400
    r1["on_time"] = paris(r1.submitted_ts_utc).dt.normalize() <= paris(r1.alert_ts_utc).dt.normalize() + pd.Timedelta(days=14)
    req = ["counterparty_country", "counterparty_iban", "subject_id", "account_id", "transaction_dates"]
    r1["complete"] = r1[req].notna().all(axis=1) & (r1.narrative_words >= 30)
    ret = pd.read_parquet(SIM / "quality_returns.parquet").report_id.unique()
    r1["returned"] = r1.report_id.isin(ret)
    r1["week"] = paris(r1.submitted_ts_utc).dt.to_period("W-SUN").dt.start_time
    a["week"] = paris(a.alert_ts_utc).dt.to_period("W-SUN").dt.start_time
    fr_a = a[a.desk == "FR"].groupby("week").size().rename("alerts")
    fr_r = r1[r1.desk == "FR"].groupby("week").agg(reports=("report_id", "size"), median_days=("days", "median"),
                                                   on_time=("on_time", "sum"), complete=("complete", "sum"),
                                                   returned=("returned", "sum"))
    dups = (r[r.desk == "FR"].assign(week=paris(r[r.desk == "FR"].submitted_ts_utc).dt.to_period("W-SUN").dt.start_time)
            .groupby("week").size().rename("submission_rows"))
    w = pd.concat([fr_a, fr_r, dups], axis=1).fillna(0).reset_index().rename(columns={"index": "week"})
    w = w[(w.week >= "2025-11-03") & (w.week <= "2026-10-26")]
    return w


def style_header(ws, row, ncol):
    for j in range(1, ncol + 1):
        cell = ws.cell(row, j)
        cell.font, cell.fill = BOLD, HEAD
        cell.alignment = Alignment(wrap_text=True, vertical="top")


def widths(ws, w):
    for i, x in enumerate(w, start=1):
        ws.column_dimensions[get_column_letter(i)].width = x


def main():
    wb = Workbook()
    # ---------------------------------------------------------------- README
    ws = wb.active
    ws.title = "README"
    lines = ["Reporting operations tracker - SIMULATED data (independent case study, not bunq data)",
             "Yellow cells are inputs. Every other number is a formula or simulated data.",
             "Weekly KPIs: France desk, weeks Monday-Sunday in Paris time; reports counted once per report_id.",
             "CAP tracker: status by formula from the as-of date; a closed item without evidence counts as not done.",
             "SLA calculator: internal 14-day target (not a legal deadline) and 5-working-day FIU request clock (AMLR art. 69(1), applies from 10 July 2027).",
             "Gap analysis: priority score = impact x likelihood. To be confirmed with Compliance / Legal; not legal advice.",
             "Works in Excel and Google Sheets (no Excel-only functions).",
             "Independent case study based on public data - not affiliated with or endorsed by bunq."]
    for i, t in enumerate(lines, start=1):
        ws.cell(i, 1, t).font = BOLD if i == 1 else Font()
    ws.column_dimensions["A"].width = 120

    # ---------------------------------------------------------------- Weekly KPIs
    ws = wb.create_sheet("Weekly KPIs")
    ws["A1"], ws["B1"] = "Target on-time rate", 0.90
    ws["A2"], ws["B2"] = "Target completeness at submission", 1.0
    ws["A3"], ws["B3"] = "Target QA return rate (max)", 0.05
    for c in ("B1", "B2", "B3"):
        ws[c].fill, ws[c].number_format = INPUT, "0%"
    hdr = ["Week (Mon)", "Alerts", "Reports (distinct)", "Submission rows", "Median days alert to submission",
           "On-time reports", "Complete reports", "Returned reports", "Reports per 100 alerts", "On-time rate",
           "Completeness", "QA return rate", "Duplicate rows", "Status"]
    R0 = 5
    for j, h in enumerate(hdr, start=1):
        ws.cell(R0, j, h)
    style_header(ws, R0, len(hdr))
    w = weekly_kpis()
    for i, row in enumerate(w.itertuples(index=False), start=R0 + 1):
        ws.cell(i, 1, row.week.to_pydatetime()).number_format = "yyyy-mm-dd"
        for j, v in enumerate([row.alerts, row.reports, row.submission_rows, round(float(row.median_days), 2),
                               row.on_time, row.complete, row.returned], start=2):
            ws.cell(i, j, float(v) if j == 5 else int(v))
        ws.cell(i, 9, f'=IF(B{i}=0,"",ROUND(C{i}/B{i}*100,1))')
        ws.cell(i, 10, f'=IF(C{i}=0,"",F{i}/C{i})').number_format = "0.0%"
        ws.cell(i, 11, f'=IF(C{i}=0,"",G{i}/C{i})').number_format = "0.0%"
        ws.cell(i, 12, f'=IF(C{i}=0,"",H{i}/C{i})').number_format = "0.0%"
        ws.cell(i, 13, f"=D{i}-C{i}")
        ws.cell(i, 14, f'=IF(C{i}=0,"",IF(OR(J{i}<$B$1,K{i}<$B$2,L{i}>$B$3,M{i}>0),"CHECK","OK"))')
    last = R0 + len(w)
    ws.conditional_formatting.add(f"N{R0 + 1}:N{last}", FormulaRule(formula=[f'N{R0 + 1}="CHECK"'], fill=RED))
    ws.cell(last + 2, 1, "Year").font = BOLD
    for j, col in [(2, "B"), (3, "C"), (4, "D"), (6, "F"), (7, "G"), (8, "H")]:
        ws.cell(last + 2, j, f"=SUM({col}{R0 + 1}:{col}{last})")
    ws.cell(last + 2, 10, f"=F{last + 2}/C{last + 2}").number_format = "0.0%"
    ws.cell(last + 2, 11, f"=G{last + 2}/C{last + 2}").number_format = "0.0%"
    ws.cell(last + 2, 12, f"=H{last + 2}/C{last + 2}").number_format = "0.0%"
    ws.cell(last + 2, 13, f"=D{last + 2}-C{last + 2}")
    ws.cell(last + 3, 1, "Weeks flagged CHECK")
    ws.cell(last + 3, 2, f'=COUNTIF(N{R0 + 1}:N{last},"CHECK")')
    ws.freeze_panes = f"B{R0 + 1}"
    widths(ws, [14, 9, 10, 11, 13, 10, 10, 10, 11, 10, 11, 10, 10, 9])

    # ---------------------------------------------------------------- CAP tracker
    ws = wb.create_sheet("CAP tracker")
    ws["A1"], ws["B1"] = "As-of date", AS_OF
    ws["B1"].fill, ws["B1"].number_format = INPUT, "yyyy-mm-dd"
    hdr = ["CAP id", "Item", "Owner team", "Opened", "Due", "Closed", "Evidence attached (Yes/No)", "Days to due",
           "Status", "Alert"]
    for j, h in enumerate(hdr, start=1):
        ws.cell(3, j, h)
    style_header(ws, 3, len(hdr))
    cap = pd.read_parquet(SIM / "cap_items.parquet").sort_values("cap_id")
    dv = DataValidation(type="list", formula1='"Yes,No"', allow_blank=False)
    ws.add_data_validation(dv)
    for i, r in enumerate(cap.itertuples(index=False), start=4):
        ws.cell(i, 1, r.cap_id); ws.cell(i, 2, r.item); ws.cell(i, 3, r.owner_team)
        ws.cell(i, 4, r.opened_date.to_pydatetime()).number_format = "yyyy-mm-dd"
        ws.cell(i, 5, r.due_date.to_pydatetime()).number_format = "yyyy-mm-dd"
        if pd.notna(r.closed_date):
            ws.cell(i, 6, r.closed_date.to_pydatetime()).number_format = "yyyy-mm-dd"
        ws.cell(i, 7, "Yes" if r.evidence_attached else "No").fill = INPUT
        dv.add(ws.cell(i, 7))
        ws.cell(i, 6).fill = INPUT
        ws.cell(i, 8, f'=IF(F{i}="",E{i}-$B$1,"")')
        ws.cell(i, 9, f'=IF(F{i}<>"",IF(G{i}="No","Closed - no evidence",IF(F{i}<=E{i},"Closed on time","Closed late")),'
                      f'IF(E{i}<$B$1,"OVERDUE",IF(E{i}-$B$1<=14,"Due within 14 days","On track")))')
        ws.cell(i, 10, f'=IF(OR(I{i}="OVERDUE",I{i}="Closed - no evidence"),"ACTION","")')
    last = 3 + len(cap)
    ws.conditional_formatting.add(f"I4:J{last}", FormulaRule(formula=['$J4="ACTION"'], fill=RED))
    r0 = last + 2
    ws.cell(r0, 1, "Summary").font = BOLD
    for k, s in enumerate(["OVERDUE", "Closed - no evidence", "Due within 14 days", "On track", "Closed on time", "Closed late"]):
        ws.cell(r0 + 1 + k, 1, s)
        ws.cell(r0 + 1 + k, 2, f'=COUNTIF($I$4:$I${last},A{r0 + 1 + k})')
    t0 = r0 + 8
    ws.cell(t0, 1, "Overdue by team").font = BOLD
    for k, t in enumerate(["T1", "T2", "T3", "T4", "T5"]):
        ws.cell(t0 + 1 + k, 1, t)
        ws.cell(t0 + 1 + k, 2, f'=COUNTIFS($C$4:$C${last},A{t0 + 1 + k},$I$4:$I${last},"OVERDUE")')
    ws.freeze_panes = "A4"
    widths(ws, [10, 26, 11, 12, 12, 12, 14, 11, 22, 9])

    # ---------------------------------------------------------------- SLA calculator
    ws = wb.create_sheet("SLA calculator")
    rows = [
        ("1. Internal target (post-execution alerts) - SIMULATED desk rule, not a legal deadline", None, None),
        ("Alert date-time (UTC)", datetime(2026, 6, 1, 9, 0), "input"),
        ("Paris offset at alert (hours: 1 in winter, 2 in summer)", 2, "input"),
        ("Internal target (calendar days)", 14, "input"),
        ("Submission date-time (UTC)", datetime(2026, 6, 15, 22, 30), "input"),
        ("Paris offset at submission (hours)", 2, "input"),
        ("Alert in Paris time", "=B2+B3/24", "out"),
        ("Deadline (Paris date)", "=INT(B7)+B4", "out"),
        ("Submission in Paris time", "=B5+B6/24", "out"),
        ("Status (Paris dates - correct)", '=IF(INT(B9)<=B8,"On time","Late")', "out"),
        ("Status if UTC dates are used (wrong)", '=IF(INT(B5)<=INT(B2)+B4,"On time","Late")', "out"),
        ("Days alert to submission", "=ROUND(B5-B2,2)", "out"),
        (None, None, None),
        ("2. FIU information request (AMLR art. 69(1), from 10 July 2027: 5 working days unless the FIU sets another deadline)", None, None),
        ("Request received (date)", datetime(2027, 7, 12), "input"),
        ("Working days allowed", 5, "input"),
        ("Reply due (French public holidays excluded)", "=WORKDAY(B15,B16,$E$2:$E$23)", "out"),
        ("Reply sent (date)", datetime(2027, 7, 20), "input"),
        ("Status", '=IF(B18="","Open",IF(B18<=B17,"On time","Late"))', "out"),
    ]
    for i, (k, v, kind) in enumerate(rows, start=1):
        if k:
            ws.cell(i, 1, k).font = BOLD if kind is None else Font()
        if v is not None:
            c = ws.cell(i, 2, v)
            if kind == "input":
                c.fill = INPUT
            if isinstance(v, datetime) or (isinstance(v, str) and ("B2+" in v or "B5+" in v or "INT(B7)" in v or "WORKDAY" in v)):
                c.number_format = "yyyy-mm-dd hh:mm" if i in (2, 5, 7, 9) else "yyyy-mm-dd"
    ws["E1"] = "French public holidays 2026-2027 (Whit Monday: check the employer's rule)"
    ws["E1"].font = BOLD
    for k, d in enumerate(FR_HOLIDAYS, start=2):
        ws.cell(k, 5, datetime.fromisoformat(d)).number_format = "yyyy-mm-dd"
    widths(ws, [70, 20, 3, 3, 22])

    # ---------------------------------------------------------------- Gap analysis
    ws = wb.create_sheet("Gap analysis")
    hdr = ["#", "Requirement", "France (Tracfin)", "EU AMLR from 10 July 2027", "Gap (SIMULATED process)", "Action",
           "Impact (1-3)", "Likelihood (1-3)", "Score", "Priority", "Status"]
    for j, h in enumerate(hdr, start=1):
        ws.cell(1, j, h)
    style_header(ws, 1, len(hdr))
    for i, g in enumerate(GAP, start=2):
        ws.cell(i, 1, i - 1)
        for j, v in enumerate(g[:5], start=2):
            ws.cell(i, j, v).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(i, 7, g[5]).fill = INPUT
        ws.cell(i, 8, g[6]).fill = INPUT
        ws.cell(i, 9, f"=G{i}*H{i}")
        ws.cell(i, 10, f'=IF(I{i}>=6,"High",IF(I{i}>=3,"Medium","Low"))')
        ws.cell(i, 11, g[7])
    last = 1 + len(GAP)
    ws.conditional_formatting.add(f"J2:J{last}", FormulaRule(formula=['J2="High"'], fill=RED))
    ws.cell(last + 2, 1, "High-priority open items")
    ws.cell(last + 2, 3, f'=COUNTIFS(J2:J{last},"High",K2:K{last},"Open")')
    ws.cell(last + 3, 1, "To be confirmed with Compliance / Legal. Not legal advice.")
    ws.freeze_panes = "C2"
    widths(ws, [4, 22, 34, 30, 30, 28, 9, 10, 7, 9, 13])

    # ---------------------------------------------------------------- metadata: empty
    p = wb.properties
    p.creator = p.lastModifiedBy = p.title = p.subject = p.description = p.keywords = p.category = ""
    p.created = p.modified = datetime(2026, 11, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    check_expected(w, cap)
    print("written", OUT.relative_to(ROOT))


def check_expected(w, cap):
    """Python recomputation of the main formula results (fallback when the file is not opened in Excel / Sheets)."""
    tot = w[["alerts", "reports", "submission_rows", "on_time", "complete", "returned"]].sum()
    flagged = ((w.on_time / w.reports < .9) | (w.complete / w.reports < 1) | (w.returned / w.reports > .05)
               | (w.submission_rows > w.reports)).sum()
    st = []
    for r in cap.itertuples():
        if pd.notna(r.closed_date):
            st.append("Closed - no evidence" if not r.evidence_attached else
                      ("Closed on time" if r.closed_date <= r.due_date else "Closed late"))
        else:
            st.append("OVERDUE" if r.due_date < AS_OF else ("Due within 14 days" if (r.due_date - AS_OF).days <= 14 else "On track"))
    s = pd.Series(st)
    gap_high_open = sum(1 for g in GAP if g[5] * g[6] >= 6 and g[7] == "Open")
    wd = np.busday_offset(np.datetime64("2027-07-12"), 5, roll="forward", holidays=FR_HOLIDAYS)
    print(f"expected: year on-time {tot.on_time / tot.reports:.1%}, completeness {tot.complete / tot.reports:.1%}, "
          f"returns {tot.returned / tot.reports:.1%}, duplicate rows {int(tot.submission_rows - tot.reports)}, "
          f"weeks CHECK {flagged} | CAP {s.value_counts().to_dict()} | gap high&open {gap_high_open} | "
          f"FIU reply due {wd} | SLA example: Paris 'Late', UTC 'On time'")


if __name__ == "__main__":
    main()
