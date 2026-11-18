"""Headline numbers used by the notebook, the dashboard and the PDF (one place, nothing typed by hand).

Reads data/processed/*.parquet (from src/run_sql.py) and data/processed/*.csv (public extracts);
adds the bootstrap interval of the difference-in-differences; writes data/processed/findings.json.
    python src/findings.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
SIM = ROOT / "data" / "simulated"


def pq(name):
    return pd.read_parquet(PROC / f"{name}.parquet")


def did_bootstrap(n_boot=2000, seed=7):
    """DiD on log effort; 95% interval from a cluster bootstrap that resamples whole weeks within each desk-period."""
    c = pd.read_parquet(SIM / "cases.parquet")
    c = c[(c.picked_ts_utc >= "2026-05-04") & (c.picked_ts_utc < "2026-11-01")].copy()
    c["post"] = c.picked_ts_utc >= "2026-08-03"
    c["week"] = c.picked_ts_utc.dt.to_period("W").astype(str)
    c["y"] = np.log(c.effort_hours)
    groups = {k: g.groupby("week").y.agg(["sum", "count"]) for k, g in c.groupby(["desk", "post"])}
    rng = np.random.default_rng(seed)

    def est(sample):
        m = {k: v["sum"].sum() / v["count"].sum() for k, v in sample.items()}
        return (m[("FR", True)] - m[("FR", False)]) - (m[("BNL", True)] - m[("BNL", False)])

    point = est(groups)
    draws = []
    for _ in range(n_boot):
        s = {k: v.iloc[rng.integers(0, len(v), len(v))] for k, v in groups.items()}
        draws.append(est(s))
    lo, hi = np.percentile(draws, [2.5, 97.5])
    pct = lambda x: float(np.exp(x) - 1)
    return {"did_log": float(point), "did_pct": pct(point), "ci_low_pct": pct(lo), "ci_high_pct": pct(hi),
            "n_boot": n_boot, "true_effect_pct": -0.25}


def main():
    f = {}
    # ---- public: IBM rules
    r = pq("ibm_rule_results").set_index("rule")
    anyr = r.loc["Any rule (R1-R4)"]
    f["ibm"] = {
        "transactions": int(pq("ibm_overview").transactions[0]),
        "laundering_share": float(pq("ibm_overview").laundering_share[0]),
        "accounts": int(anyr.accounts), "positive_accounts": int(anyr.positive_accounts),
        "base_rate": float(anyr.base_rate), "any_precision": float(anyr.precision), "any_recall": float(anyr.recall),
        "any_alerts_per_1000": float(anyr.alerts_per_1000_accounts), "any_flagged": int(anyr.flagged_accounts),
        "lift": float(anyr.precision / anyr.base_rate),
        "false_alerts_share": float(1 - anyr.precision),
        "review_minutes_assumed": 20,
        "analyst_hours_per_true_positive": float(anyr.flagged_accounts * 20 / 60 / anyr.flagged_positives),
    }
    cov = pq("ibm_typology_coverage")
    f["ibm"]["weakest_typology"] = cov.iloc[0].typology
    f["ibm"]["weakest_detection"] = float(cov.iloc[0].detection_rate)
    # ---- public: ECB fraud
    e = pd.read_csv(PROC / "ecb_payment_fraud.csv")
    w = e.pivot_table(index=["REF_AREA", "TYP_TRNSCTN", "UNIT_MEASURE", "TIME_PERIOD"], columns="FRD_TYP",
                      values="OBS_VALUE").reset_index()
    ct = w[(w.TYP_TRNSCTN == "CT0") & (w.UNIT_MEASURE == "EUR")]
    fr = ct[ct.REF_AREA == "FR"].set_index("TIME_PERIOD").F
    f["ecb"] = {"fr_ct_fraud_2025S2_m": float(fr["2025-S2"]), "fr_ct_fraud_2024S2_m": float(fr["2024-S2"]),
                "fr_ct_fraud_growth": float(fr["2025-S2"] / fr["2024-S2"] - 1), "unit_mult": int(e.UNIT_MULT.iloc[0])}
    cp = w[(w.TYP_TRNSCTN == "CP0") & (w.UNIT_MEASURE == "EUR") & (w.TIME_PERIOD == "2025-S2")].set_index("REF_AREA")
    f["ecb"]["card_fraud_rate_bp_2025S2"] = {k: float(v * 1e4) for k, v in (cp.F / cp._Z).items()}
    # ---- public: Tracfin (read in a browser, typed in tracfin_2025.csv with its source)
    t = pd.read_csv(PROC / "tracfin_2025.csv").set_index("metric").value
    f["tracfin"] = {k: float(v) for k, v in t.items()}
    # ---- simulated desk
    tm = pq("sim_timeliness")
    fr_t = tm[tm.desk == "FR"].set_index(tm[tm.desk == "FR"].month.dt.strftime("%Y-%m"))
    f["sim"] = {
        "tool_aug": float(fr_t.loc["2026-08", "tool_median_days"]), "tool_sep": float(fr_t.loc["2026-09", "tool_median_days"]),
        "true_aug": float(fr_t.loc["2026-08", "true_median_days"]), "true_sep": float(fr_t.loc["2026-09", "true_median_days"]),
        "true_feb": float(fr_t.loc["2026-02", "true_median_days"]), "true_may": float(fr_t.loc["2026-05", "true_median_days"]),
        "ontime_feb": float(fr_t.loc["2026-02", "on_time_rate"]), "ontime_may": float(fr_t.loc["2026-05", "on_time_rate"]),
        "ontime_oct": float(fr_t.loc["2026-10", "on_time_rate"]),
        "utc_misclassified": int(tm.misclassified_by_utc.sum()), "reports": int(tm.reports.sum()),
    }
    f["sim"]["tool_change_pct"] = f["sim"]["tool_sep"] / f["sim"]["tool_aug"] - 1
    f["sim"]["true_change_pct"] = f["sim"]["true_sep"] / f["sim"]["true_aug"] - 1
    f["sim"]["utc_misclassified_share"] = f["sim"]["utc_misclassified"] / f["sim"]["reports"]
    q = pq("sim_quality_monthly")
    fq = q[q.desk == "FR"].set_index(q[q.desk == "FR"].month.dt.strftime("%Y-%m"))
    f["sim"].update({"complete_draft_jun": float(fq.loc["2026-06", "complete_at_draft"]),
                     "complete_sub_jun": float(fq.loc["2026-06", "complete_at_submission"]),
                     "returns_jun": float(fq.loc["2026-06", "qa_return_rate"]),
                     "returns_apr": float(fq.loc["2026-04", "qa_return_rate"]),
                     "duplicate_rows": int(q.duplicate_submission_rows.sum())})
    fun = pq("sim_monthly_funnel")
    ff = fun[fun.desk == "FR"].set_index(fun[fun.desk == "FR"].month.dt.strftime("%Y-%m"))
    f["sim"].update({"alerts_feb": int(ff.loc["2026-02", "alerts"]), "alerts_apr": int(ff.loc["2026-04", "alerts"]),
                     "alerts_dec": int(ff.loc["2025-12", "alerts"]), "alerts_nov": int(ff.loc["2025-11", "alerts"]),
                     "fr_reports_year": int(ff.reports.sum()), "fr_alerts_year": int(ff.alerts.sum())})
    bl = pq("sim_backlog_age")
    fb = bl[bl.desk == "FR"].set_index("month_end").backlog
    f["sim"]["backlog_peak"] = int(fb.max())
    f["sim"]["backlog_peak_month"] = str(pd.Timestamp(fb.idxmax()).strftime("%b %Y"))
    f["sim"]["backlog_feb"] = int(fb.iloc[3])
    cap = pq("sim_cap_status")
    f["cap"] = {"items": int(len(cap)), "overdue": int((cap.cap_state == "overdue").sum()),
                "overdue_teams": sorted(cap[cap.cap_state == "overdue"].owner_team.unique().tolist()),
                "no_evidence": int((cap.cap_state == "closed without evidence").sum()),
                "on_time": int((cap.cap_state == "closed on time").sum())}
    f["did"] = did_bootstrap()
    f["did"].update({k: float(v) for k, v in pq("sim_did_estimate").iloc[0].items()})
    (PROC / "findings.json").write_text(json.dumps(f, indent=1, default=str), encoding="utf-8")
    print("findings.json written:", ", ".join(f))


if __name__ == "__main__":
    main()
