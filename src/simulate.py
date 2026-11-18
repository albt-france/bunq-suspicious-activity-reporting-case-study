"""SIMULATED reporting desk: 12 months (Nov 2025 - Oct 2026), two desks, seed 42.

Nothing here describes bunq's real volumes, processes or failures. The desk is a generic online bank's
suspicious-activity reporting team, sized to be plausible, with eight hidden events to find.
  FR   France desk (reports to Tracfin)          - receives the August pre-fill automation
  BNL  Benelux desk (control, no automation)
Identifiers only (case_000123, user_04567): no names anywhere.

Outputs data/simulated/{alerts,cases,reports,quality_returns,cap_items}.parquet
        data/_hidden_truth.csv (answer key, local only, removed before publishing)
    python src/simulate.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "simulated"
TRUTH = ROOT / "data" / "_hidden_truth.csv"
SEED = 42
START, END = pd.Timestamp("2025-11-01"), pd.Timestamp("2026-10-31")
AS_OF = pd.Timestamp("2026-10-31 23:59")
PARIS = "Europe/Paris"

# ---------------------------------------------------------------- assumptions (all SIMULATED, see DECISIONS.md)
BASE_ALERTS = {"FR": 55, "BNL": 40}                 # alerts per day before any event
SOURCE_MIX = {"monitoring_rule": 0.75, "internal_referral": 0.20, "external_request": 0.05}
P_CASE = {"monitoring_rule": 0.28, "internal_referral": 0.40, "external_request": 0.90}   # alert -> case
P_REPORT = 0.40                                     # case -> suspicious-activity report
TRIAGE_CAP = {"FR": 90, "BNL": 70}                  # alerts triaged per working day
TRIAGE_BASE_MEDIAN_D = 3.8                          # triage wait without backlog (calendar days)
EFFORT_MEDIAN_H = {"FR": 5.0, "BNL": 5.5}           # analyst effort per case (hours)
INTERNAL_TARGET_D = 14                              # internal target: alert -> submission, calendar days (SIMULATED)
REQUIRED = ["subject_id", "account_id", "amount_eur", "transaction_dates", "counterparty_country",
            "counterparty_iban", "typology", "narrative"]

EV = {
    "new_rule": pd.Timestamp("2026-03-02"),          # 1 FR monitoring alerts x1.8
    "capacity_up": pd.Timestamp("2026-04-20"),       #   FR triage capacity reinforced (response to 1)
    "schema_break": (pd.Timestamp("2026-05-11"), pd.Timestamp("2026-07-14")),   # 2 FR drafts lose 2 fields (14%)
    "retry_bug": (pd.Timestamp("2026-06-01"), pd.Timestamp("2026-07-31")),      # 3 3% duplicate submissions
    "clock_change": pd.Timestamp("2026-09-01"),      # 4 tool clock starts at case opening
    "prefill": pd.Timestamp("2026-08-03"),           # 5 FR pre-fill: effort -25%
    "dec_spike": (pd.Timestamp("2025-12-08"), pd.Timestamp("2026-01-04")),      # 6 scam season x1.5 (both desks)
    "common_shift": pd.Timestamp("2026-09-01"),      #   both desks: harder case mix, effort +8% (makes naive before/after wrong)
}


def lognormal(rng, median, sigma, n):
    return rng.lognormal(np.log(median), sigma, n)


def daily_alerts(rng):
    days = pd.date_range(START, END, freq="D")
    rows = []
    for desk, base in BASE_ALERTS.items():
        for d in days:
            for src, share in SOURCE_MIX.items():
                lam = base * share
                if src == "monitoring_rule":
                    if desk == "FR" and d >= EV["new_rule"]:
                        lam *= 1.8
                    if EV["dec_spike"][0] <= d <= EV["dec_spike"][1]:
                        lam *= 1.5
                if src == "internal_referral" and d.weekday() >= 5:
                    lam *= 0.4
                rows.append((desk, d, src, rng.poisson(lam)))
    return pd.DataFrame(rows, columns=["desk", "day", "source", "n"])


def triage_backlog(counts: pd.DataFrame) -> pd.DataFrame:
    """Fluid queue per desk: backlog(t+1) = max(0, backlog(t) + arrivals(t) - capacity(t)). Extra wait = backlog / capacity."""
    out = []
    for desk, g in counts.groupby("desk"):
        arr = g.groupby("day").n.sum()
        b = 0.0
        for d, a in arr.items():
            cap = TRIAGE_CAP[desk] * (5 / 3 if desk == "FR" and d >= EV["capacity_up"] else 1)
            cap = cap if d.weekday() < 5 else 0
            extra = b / (TRIAGE_CAP[desk] * (5 / 3 if desk == "FR" and d >= EV["capacity_up"] else 1)) * 7 / 5
            out.append((desk, d, b, extra))
            b = max(0.0, b + a - cap)
    return pd.DataFrame(out, columns=["desk", "day", "backlog", "extra_wait_d"])


def to_utc_from_paris_clock(day_utc_naive, hour_paris):
    """Build a UTC-naive timestamp from a Paris calendar day and a Paris clock time (hours, may be > 24)."""
    local = (pd.to_datetime(day_utc_naive).dt.tz_localize(PARIS, nonexistent="shift_forward", ambiguous="NaT")
             + pd.to_timedelta(hour_paris, unit="h"))
    return local.dt.tz_convert("UTC").dt.tz_localize(None)


def main():
    rng = np.random.default_rng(SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ alerts
    counts = daily_alerts(rng)
    a = counts.loc[counts.index.repeat(counts.n)].drop(columns="n").reset_index(drop=True)
    a["alert_ts_utc"] = a.day + pd.to_timedelta(rng.uniform(0, 24, len(a)), unit="h")
    a = a.sort_values("alert_ts_utc").reset_index(drop=True)
    a["alert_id"] = [f"alert_{i:06d}" for i in range(1, len(a) + 1)]
    a["user_id"] = [f"user_{u:05d}" for u in rng.integers(1, 60000, len(a))]
    spike = (a.source == "monitoring_rule") & a.day.between(*EV["dec_spike"])
    a["typology_hint"] = np.where(spike & (rng.random(len(a)) < 0.35), "APP scam (year-end)",
                                  rng.choice(["fan-out", "fan-in", "structuring", "rapid pass-through", "mule account",
                                              "unusual cash", "other"], len(a),
                                             p=[.16, .14, .14, .16, .18, .07, .15]))
    a.loc[spike & (a.typology_hint == "APP scam (year-end)"), "is_spike_typology"] = True

    # ------------------------------------------------------------ cases (triage with a backlog-dependent wait)
    bl = triage_backlog(counts)
    a = a.merge(bl, on=["desk", "day"], how="left")
    esc = rng.random(len(a)) < a.source.map(P_CASE).values
    c = a[esc].copy().reset_index(drop=True)
    c["case_id"] = [f"case_{i:06d}" for i in range(1, len(c) + 1)]
    triage_d = lognormal(rng, TRIAGE_BASE_MEDIAN_D, 0.45, len(c)) + c.extra_wait_d.values
    c["opened_ts_utc"] = c.alert_ts_utc + pd.to_timedelta(triage_d, unit="D")
    c["picked_ts_utc"] = c.opened_ts_utc + pd.to_timedelta(lognormal(rng, 1.4, 0.5, len(c)), unit="D")
    eff = lognormal(rng, 1.0, 0.45, len(c)) * c.desk.map(EFFORT_MEDIAN_H).values
    eff *= np.where((c.desk == "FR") & (c.picked_ts_utc >= EV["prefill"]), 0.75, 1.0)          # event 5
    eff *= np.where(c.picked_ts_utc >= EV["common_shift"], 1.08, 1.0)
    c["effort_hours"] = eff.round(2)
    c["decision_ts_utc"] = c.picked_ts_utc + pd.to_timedelta(eff / 2.5 * 1.4, unit="D")
    c["decision"] = np.where(rng.random(len(c)) < P_REPORT, "report", "no_report")
    a["case_id"] = a.alert_id.map(dict(zip(c.alert_id, c.case_id)))

    # ------------------------------------------------------------ reports (draft -> QA -> submission)
    r = c[c.decision == "report"].copy().reset_index(drop=True)
    n = len(r)
    r["report_id"] = [f"rep_{i:06d}" for i in range(1, n + 1)]
    r["draft_ts_utc"] = r.decision_ts_utc + pd.to_timedelta(rng.uniform(0.1, 0.5, n), unit="D")
    r["amount_eur"] = np.round(lognormal(rng, 4200, 1.1, n), 2)
    r["counterparty_country"] = rng.choice(["FR", "NL", "BE", "DE", "ES", "LT", "GB", "AE", "other"], n,
                                           p=[.35, .12, .08, .1, .08, .07, .06, .04, .1])
    r["counterparty_iban"] = "present"
    r["typology"] = r.typology_hint
    r["narrative_words"] = rng.integers(80, 600, n)
    for f in ["subject_id", "account_id", "transaction_dates"]:
        r[f] = "present"
    # baseline gaps: 1% narratives too short
    r.loc[rng.random(n) < 0.01, "narrative_words"] = rng.integers(5, 30)
    # event 2: schema change drops counterparty country and IBAN from 14% of FR drafts
    brk = (r.desk == "FR") & r.draft_ts_utc.between(*EV["schema_break"]) & (rng.random(n) < 0.14)
    r.loc[brk, ["counterparty_country", "counterparty_iban"]] = None
    missing = brk | (r.narrative_words < 30)
    r["missing_fields_at_draft"] = np.where(brk, "counterparty_country;counterparty_iban",
                                            np.where(r.narrative_words < 30, "narrative", ""))
    # QA: catches 70% of incomplete drafts and returns 4% of complete ones (other reasons)
    qa1 = r.draft_ts_utc + pd.to_timedelta(lognormal(rng, 1.0, 0.5, n), unit="D")
    caught = missing & (rng.random(n) < 0.70)
    other = (~missing) & (rng.random(n) < 0.04)
    returned = caught | other
    rework = pd.to_timedelta(np.where(returned, rng.uniform(1.5, 3.0, n), 0.0), unit="D")
    r["qa_ts_utc"] = qa1 + rework
    r.loc[caught, ["counterparty_country", "counterparty_iban"]] = r.loc[caught, ["counterparty_country",
                                                                               "counterparty_iban"]].fillna("present")
    r.loc[caught & (r.narrative_words < 30), "narrative_words"] = rng.integers(120, 300)
    qr = pd.DataFrame({"report_id": r.report_id[returned].values, "desk": r.desk[returned].values,
                       "return_ts_utc": qa1[returned].values,
                       "reason": np.where(caught[returned], np.where(brk[returned], "missing counterparty fields",
                                                                     "narrative too short"),
                                          rng.choice(["unclear narrative", "amount mismatch", "missing supporting document"],
                                                     returned.sum()))})
    qr["return_id"] = [f"ret_{i:05d}" for i in range(1, len(qr) + 1)]

    # submission time: Paris office hours; deadline rush near midnight (event 8)
    planned = r.qa_ts_utc + pd.to_timedelta(rng.uniform(0.05, 0.6, n), unit="D")
    deadline_paris_day = (r.alert_ts_utc.dt.tz_localize("UTC").dt.tz_convert(PARIS).dt.tz_localize(None).dt.normalize()
                          + pd.Timedelta(days=INTERNAL_TARGET_D))
    planned_paris = planned.dt.tz_localize("UTC").dt.tz_convert(PARIS).dt.tz_localize(None)
    # move to office hours: after 18:00 -> next day; weekends -> Monday; time 09:00-18:00 Paris
    day = planned_paris.dt.normalize() + pd.to_timedelta((planned_paris.dt.hour >= 18).astype(int), unit="D")
    day = day + pd.to_timedelta((7 - day.dt.day_of_week).where(day.dt.day_of_week >= 5, 0), unit="D")
    planned = to_utc_from_paris_clock(day, rng.uniform(9, 18, n))
    planned_paris = planned.dt.tz_localize("UTC").dt.tz_convert(PARIS).dt.tz_localize(None)
    days_late = (planned_paris.dt.normalize() - deadline_paris_day).dt.days
    rush = (days_late.between(0, 3)) & (rng.random(n) < 0.22)
    rush_hour = rng.uniform(20.5, 25.5, n)                     # 20:30 to 01:30 Paris on the deadline day
    sub = planned.copy()
    sub[rush] = to_utc_from_paris_clock(deadline_paris_day[rush], rush_hour[rush])
    r["submitted_ts_utc"] = sub
    # event 4: the reporting tool's own 'time to file' field changes its clock start on 1 Sep
    clock_alert = r.submitted_ts_utc < EV["clock_change"]
    r["tool_clock_start"] = np.where(clock_alert, "alert_ts", "case_opened_ts")
    start = np.where(clock_alert, r.alert_ts_utc, r.opened_ts_utc)
    r["tool_time_to_file_days"] = ((r.submitted_ts_utc - pd.to_datetime(start)).dt.total_seconds() / 86400).round(3)
    r["submission_id"] = [f"sub_{i:06d}" for i in range(1, n + 1)]
    r = r[r.submitted_ts_utc <= AS_OF]
    # event 3: retry bug duplicates 3% of submissions in June-July (new submission_id, same case and report)
    dup = r[r.submitted_ts_utc.between(*EV["retry_bug"]) & (rng.random(len(r)) < 0.03)].copy()
    dup["submitted_ts_utc"] += pd.to_timedelta(rng.uniform(2, 15, len(dup)), unit="min")
    dup["submission_id"] = [f"sub_{i:06d}" for i in range(n + 1, n + 1 + len(dup))]
    reports = pd.concat([r, dup]).sort_values("submitted_ts_utc").reset_index(drop=True)

    # ------------------------------------------------------------ CAP items (event 7)
    caps = []
    themes = ["QA checklist update", "narrative template", "field validation rule", "timeliness dashboard",
              "training refresh", "four-eyes review", "archive retention check", "FIU feedback loop",
              "alert tuning review", "procedure update", "data lineage note", "UTC/Paris time check"]
    for i in range(24):
        opened = START + pd.Timedelta(days=int(rng.integers(0, 300)))
        due = opened + pd.Timedelta(days=int(rng.choice([30, 45, 60, 90])))
        team = f"T{int(rng.integers(1, 6))}"
        if team == "T3":
            team = "T4"
        closed = opened + pd.Timedelta(days=int(rng.integers(5, (due - opened).days)))
        caps.append([f"cap_{i + 1:03d}", themes[i % len(themes)], team, opened, due,
                     closed if closed <= AS_OF else pd.NaT, True])
    cap = pd.DataFrame(caps, columns=["cap_id", "item", "owner_team", "opened_date", "due_date", "closed_date",
                                      "evidence_attached"])
    cap.loc[cap.closed_date.isna(), "evidence_attached"] = False
    # two overdue items, both owned by team T3
    for k, (od, dd) in enumerate([("2026-06-15", "2026-08-31"), ("2026-07-20", "2026-09-30")]):
        cap.loc[len(cap)] = [f"cap_{25 + k:03d}", ["four-eyes review", "FIU feedback loop"][k], "T3",
                             pd.Timestamp(od), pd.Timestamp(dd), pd.NaT, False]
    # one item in T3 on track (so T3 is not 'all late')
    cap.loc[len(cap)] = ["cap_027", "training refresh", "T3", pd.Timestamp("2026-09-15"), pd.Timestamp("2026-12-15"),
                         pd.NaT, False]
    # one item closed without evidence
    cap.loc[cap.cap_id == "cap_005", "evidence_attached"] = False
    cap.loc[cap.cap_id == "cap_005", "closed_date"] = cap.loc[cap.cap_id == "cap_005", "due_date"] - pd.Timedelta(days=3)
    cap["status"] = np.where(cap.closed_date.notna(), "closed",
                             np.where(cap.due_date < AS_OF.normalize(), "open", "open"))

    # ------------------------------------------------------------ save
    alerts = a[["alert_id", "desk", "source", "typology_hint", "alert_ts_utc", "user_id", "case_id"]]
    cases = c[["case_id", "alert_id", "desk", "user_id", "opened_ts_utc", "picked_ts_utc", "decision_ts_utc",
               "decision", "effort_hours"]]
    cases = cases[cases.opened_ts_utc <= AS_OF]
    alerts = alerts.assign(case_id=alerts.case_id.where(alerts.case_id.isin(cases.case_id)))
    rep_cols = ["submission_id", "report_id", "case_id", "desk", "draft_ts_utc", "qa_ts_utc", "submitted_ts_utc",
                "amount_eur", "typology", *[f for f in REQUIRED if f not in ("amount_eur", "typology", "narrative")],
                "narrative_words", "missing_fields_at_draft", "tool_clock_start", "tool_time_to_file_days"]
    reports = reports.rename(columns={})[rep_cols]
    qr = qr[qr.report_id.isin(reports.report_id)][["return_id", "report_id", "desk", "return_ts_utc", "reason"]]
    for name, df in {"alerts": alerts, "cases": cases, "reports": reports, "quality_returns": qr,
                     "cap_items": cap}.items():
        df.to_parquet(OUT / f"{name}.parquet", index=False)
        print(f"{name}: {len(df):,} rows")

    truth = pd.DataFrame([
        [1, "new monitoring rule", "2026-03-02", "", "FR", "monitoring alerts x1.8; triage backlog and time to file worsen until capacity is reinforced on 2026-04-20"],
        [2, "schema change", "2026-05-11", "2026-07-14", "FR", "counterparty_country and counterparty_iban missing in 14% of drafts; QA catches 70%, the rest are submitted incomplete"],
        [3, "retry bug", "2026-06-01", "2026-07-31", "FR+BNL", "3% of submissions duplicated (same report_id, new submission_id)"],
        [4, "clock definition change", "2026-09-01", "", "FR+BNL", "tool_time_to_file_days starts at case opening instead of the alert: median falls ~40% with no real change"],
        [5, "pre-fill automation", "2026-08-03", "", "FR", "analyst effort per case x0.75 (true effect -25%); BNL unchanged; both desks +8% from 2026-09-01"],
        [6, "year-end scam spike", "2025-12-08", "2026-01-04", "FR+BNL", "monitoring alerts x1.5, 35% tagged APP scam: real inflow"],
        [7, "CAP items", "", "", "T3", "cap_025 and cap_026 overdue, both team T3; cap_005 closed without evidence"],
        [8, "UTC timestamps", "", "", "FR+BNL", "deadline-rush submissions after midnight Paris look on time when the check uses UTC dates"],
    ], columns=["event", "name", "start", "end", "scope", "truth"])
    truth.to_csv(TRUTH, index=False)


if __name__ == "__main__":
    main()
