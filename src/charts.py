"""Matplotlib charts for the PDF (report/img/*.png). Every number is read from data/processed or data/simulated.

Style: light grey-beige page, white cards, blue for the data, grey for comparison, red for alerts and thresholds,
dashed lines for events, Segoe UI. Each chart title states its data type in the PDF card (PUBLIC DATA / SIMULATED).
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
SIM = ROOT / "data" / "simulated"
IMG = ROOT / "report" / "img"

BLUE, GREY, RED, INK, MUTED, GRID, ORANGE, AQUA = "#2A78D6", "#A3A19A", "#D03B3B", "#0B0B0B", "#52514E", "#E1E0D9", "#EB6834", "#1BAF7A"
LIGHT = "#C9DDF5"
plt.rcParams.update({
    "font.family": "Segoe UI", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "figure.facecolor": "white", "axes.facecolor": "white", "legend.frameon": False,
    "axes.titlesize": 11, "axes.titleweight": "semibold", "axes.titlecolor": INK, "axes.titlelocation": "left",
})


def pq(n):
    return pd.read_parquet(PROC / f"{n}.parquet")


def save(fig, name):
    IMG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(IMG / f"{name}.png", dpi=200)
    plt.close(fig)
    return f"img/{name}.png"


def month_axis(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[11, 1, 3, 5, 7, 9]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))


def event(ax, date, label, y=0.97, color=RED):
    d = pd.Timestamp(date)
    ax.axvline(d, color=color, ls="--", lw=1)
    ax.text(d, ax.get_ylim()[1] * y, " " + label, color=color, fontsize=8.5, va="top")


# ------------------------------------------------------------------ page 1: bunq (PUBLIC DATA)
def bunq_fee():
    d = pd.read_csv(PROC / "bunq_fee_income_geography.csv").iloc[::-1]
    fig, ax = plt.subplots(figsize=(5.2, 4.3))
    y = np.arange(len(d))
    ax.barh(y + 0.2, d.fee_income_2024_keur / 1000, 0.38, color=GREY, label="2024")
    ax.barh(y - 0.2, d.fee_income_2025_keur / 1000, 0.38, color=[RED if g == "France/Belgium" else BLUE for g in d.geography], label="2025")
    ax.set_yticks(y, d.geography)
    for yy, v in zip(y, d.fee_income_2025_keur):
        ax.text(v / 1000 + 0.4, yy - 0.2, f"€{v / 1000:.1f}m", va="center", fontsize=8.5, color=MUTED)
    ax.set_xlabel("Fee income, € million (by customer address)")
    ax.set_title("Fee income by geography, 2025 vs 2024")
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)
    return save(fig, "p1_fee_geo")


def bunq_staff():
    f = pd.read_csv(PROC / "bunq_facts.csv").set_index("fact")
    tot, osc = f.loc["fte_total"], f.loc["fte_onboarding_support_compliance"]
    fig, ax = plt.subplots(figsize=(4.8, 4.3))
    yrs = ["2024", "2025"]
    o = [osc.value_2024, osc.value_2025]
    rest = [tot.value_2024 - osc.value_2024, tot.value_2025 - osc.value_2025]
    ax.bar(yrs, o, color=BLUE, label="Onboarding, Support, Compliance")
    ax.bar(yrs, rest, bottom=o, color=GREY, label="All other functions")
    for i in range(2):
        ax.text(i, o[i] / 2, f"{o[i]:.0f}\n({o[i] / (o[i] + rest[i]):.0%})", ha="center", va="center", color="white", fontsize=9, fontweight="bold")
        ax.text(i, o[i] + rest[i] + 8, f"{o[i] + rest[i]:.0f} FTE", ha="center", fontsize=9, color=MUTED)
    ax.set_ylim(0, 760)
    ax.set_title("Staff at year end (FTE)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, fontsize=8)
    ax.grid(axis="x", visible=False)
    return save(fig, "p1_staff")


# ------------------------------------------------------------------ page 2: France (PUBLIC DATA)
def tracfin():
    t = pd.read_csv(PROC / "tracfin_2025.csv").set_index("metric").value
    fin, tot = t["financial_sector_str"], t["str_total_2025"]
    fig, ax = plt.subplots(figsize=(4.8, 3.2))
    ax.bar(["Financial sector", "Non-financial"], [fin / 1000, (tot - fin) / 1000], color=[BLUE, GREY])
    ax.text(0, fin / 1000 + 5, f"{fin:,.0f}\n{t['financial_sector_share']:.0%} · +{t['financial_sector_growth']:.0%}", ha="center", fontsize=9)
    ax.text(1, (tot - fin) / 1000 + 5, f"{tot - fin:,.0f}\n{t['non_financial_share']:.0%} · +{t['non_financial_growth']:.0%}", ha="center", fontsize=9)
    ax.set_ylim(0, 320)
    ax.set_ylabel("thousand reports")
    ax.set_title(f"Reports received by Tracfin in 2025: {tot:,.0f}")
    ax.grid(axis="x", visible=False)
    return save(fig, "p2_tracfin")


def ecb():
    e = pd.read_csv(PROC / "ecb_payment_fraud.csv")
    w = e.pivot_table(index=["REF_AREA", "TYP_TRNSCTN", "UNIT_MEASURE", "TIME_PERIOD"], columns="FRD_TYP", values="OBS_VALUE").reset_index()
    cp = w[(w.TYP_TRNSCTN == "CP0") & (w.UNIT_MEASURE == "EUR")].copy()
    cp["bp"] = cp.F / cp._Z * 1e4
    fig, axs = plt.subplots(1, 2, figsize=(9.4, 3.2))
    for area, col in [("FR", BLUE), ("NL", ORANGE)]:
        s = cp[cp.REF_AREA == area].sort_values("TIME_PERIOD")
        axs[0].plot(s.TIME_PERIOD, s.bp, marker="o", color=col, label={"FR": "France", "NL": "Netherlands"}[area])
    axs[0].set_ylim(0, cp.bp.max() * 1.15)
    axs[0].set_title("Card payment fraud, basis points of value")
    axs[0].legend()
    axs[0].tick_params(axis="x", labelrotation=45, labelsize=8)
    ct = w[(w.TYP_TRNSCTN == "CT0") & (w.UNIT_MEASURE == "EUR")]
    for area, col, off in [("FR", BLUE, -0.2), ("NL", ORANGE, 0.2)]:
        s = ct[ct.REF_AREA == area].sort_values("TIME_PERIOD")
        x = np.arange(len(s))
        axs[1].bar(x + off, s.F, 0.4, color=col, label={"FR": "France", "NL": "Netherlands"}[area])
        axs[1].set_xticks(x, s.TIME_PERIOD, rotation=45, fontsize=8)
    axs[1].set_title("Credit-transfer fraud, € million (sent)")
    axs[1].legend()
    axs[1].grid(axis="x", visible=False)
    return save(fig, "p2_ecb")


# ------------------------------------------------------------------ page 3: IBM (PUBLIC DATA, synthetic)
def ibm_rules():
    r = pq("ibm_rule_results")
    r["short"] = r.rule.str.split(" \\(").str[0]
    r = r.sort_values("rule")
    base = r.base_rate.iloc[0]
    fig, ax = plt.subplots(figsize=(6, 3.3))
    y = np.arange(len(r))
    ax.barh(y + 0.2, r.precision, 0.38, color=BLUE, label="Precision")
    ax.barh(y - 0.2, r.recall, 0.38, color=LIGHT, label="Recall")
    ax.axvline(base, color=RED, ls="--", lw=1)
    ax.text(base, -0.75, f" base rate {base:.1%}", color=RED, fontsize=8.5)
    ax.set_yticks(y, r.short)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    for yy, p, rc in zip(y, r.precision, r.recall):
        ax.text(p + 0.003, yy + 0.2, f"{p:.1%}", va="center", fontsize=8)
        ax.text(rc + 0.003, yy - 0.2, f"{rc:.1%}", va="center", fontsize=8, color=MUTED)
    ax.set_title("Four simple rules vs the labels (account level)")
    ax.legend(loc="upper right")
    ax.grid(axis="y", visible=False)
    return save(fig, "p3_rules")


def ibm_curve():
    c = pq("ibm_fanout_curve")
    fig, ax = plt.subplots(figsize=(4.6, 3.3))
    ax.plot(c.recall, c.precision, color=BLUE, marker="o", ms=3)
    for _, r in c[c.threshold.isin([3, 5, 8, 12, 20])].iterrows():
        ax.annotate(f"≥{int(r.threshold)}", (r.recall, r.precision), textcoords="offset points", xytext=(5, 4), fontsize=8, color=MUTED)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Fan-out threshold: precision vs recall")
    return save(fig, "p3_curve")


def ibm_typ():
    t = pq("ibm_typology_coverage").sort_values("detection_rate")
    fig, ax = plt.subplots(figsize=(4.6, 3.3))
    ax.barh(t.typology, t.detection_rate, color=[RED if v == t.detection_rate.min() else BLUE for v in t.detection_rate])
    for i, v in enumerate(t.detection_rate):
        ax.text(v + 0.01, i, f"{v:.0%}", va="center", fontsize=8)
    ax.set_xlim(0, 1.1)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    ax.set_title("Attempts touched by at least one alert")
    ax.grid(axis="y", visible=False)
    return save(fig, "p3_typ")


# ------------------------------------------------------------------ page 4: volume and timeliness (SIMULATED)
def sim_alerts():
    f = pq("sim_monthly_funnel")
    f = f[f.desk == "FR"]
    fig, ax = plt.subplots(figsize=(6, 3.2))
    x = pd.to_datetime(f.month)
    ax.bar(x, f.alerts_rule, 25, color=BLUE, label="Monitoring rules")
    ax.bar(x, f.alerts_internal, 25, bottom=f.alerts_rule, color=LIGHT, label="Internal referrals")
    ax.bar(x, f.alerts_external, 25, bottom=f.alerts_rule + f.alerts_internal, color=GREY, label="External requests")
    ax.set_ylim(0, f.alerts.max() * 1.25)
    month_axis(ax)
    event(ax, "2026-03-02", "new rule (x1.8)")
    event(ax, "2025-12-08", "", color=ORANGE)
    ax.text(pd.Timestamp("2025-12-08"), ax.get_ylim()[1] * 0.97, "year-end\nscams ", color=ORANGE, fontsize=8.5, va="top", ha="right")
    ax.set_title("France desk: alerts per month by source")
    ax.legend(loc="upper left", fontsize=8, bbox_to_anchor=(0.36, 1.0))
    ax.grid(axis="x", visible=False)
    return save(fig, "p4_alerts")


def sim_backlog():
    b = pq("sim_backlog_age")
    b = b[b.desk == "FR"]
    x = pd.to_datetime(b.month_end)
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    bottom = np.zeros(len(b))
    for col, c, lab in [("age_0_6", LIGHT, "0-6 days"), ("age_7_13", BLUE, "7-13"), ("age_14_29", RED, "14-29"), ("age_30_plus", INK, "30+")]:
        ax.bar(x, b[col], 22, bottom=bottom, color=c, label=lab)
        bottom += b[col].values
    ax.set_ylim(0, bottom.max() * 1.12)
    month_axis(ax)
    ax.set_title("Triage backlog at month end, by age")
    ax.legend(fontsize=8, title="age", title_fontsize=8)
    ax.grid(axis="x", visible=False)
    return save(fig, "p4_backlog")


def sim_clock():
    t = pq("sim_timeliness")
    t = t[t.desk == "FR"]
    x = pd.to_datetime(t.month)
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.plot(x, t.tool_median_days, color=RED, marker="o", label="Tool field (clock moved in Sep)")
    ax.plot(x, t.true_median_days, color=BLUE, marker="o", lw=2.2, label="Recomputed from the alert")
    ax.set_ylim(0, t.true_median_days.max() * 1.2)
    month_axis(ax)
    event(ax, "2026-09-01", "clock change", y=0.99)
    a, s = t.set_index(x.dt.strftime("%Y-%m")).loc[["2026-08", "2026-09"], "tool_median_days"]
    ax.annotate(f"{s / a - 1:+.0%} on paper", (pd.Timestamp("2026-09-01"), s), textcoords="offset points", xytext=(-75, -22),
                color=RED, fontsize=9, fontweight="bold")
    ax.set_ylabel("median days to file")
    ax.set_title("Median time to file: the metric that lied")
    ax.legend(loc="upper left", fontsize=8)
    return save(fig, "p4_clock")


def sim_ontime():
    t = pq("sim_timeliness")
    t = t[t.desk == "FR"]
    x = pd.to_datetime(t.month)
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    ax.plot(x, t.on_time_rate, color=BLUE, marker="o", label="Paris dates (correct)")
    ax.plot(x, t.on_time_rate_utc_check, color=GREY, ls="--", label="UTC dates (overstated)")
    ax.axhline(0.9, color=RED, ls=":", lw=1)
    ax.text(x.iloc[-1], 0.84, "target 90%", color=RED, fontsize=8, ha="right")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    ax.set_ylim(0, 1.05)
    month_axis(ax)
    ax.set_title("Reports filed within 14 days")
    ax.legend(fontsize=8, loc="lower left")
    return save(fig, "p4_ontime")


# ------------------------------------------------------------------ page 5: quality (SIMULATED)
def sim_quality():
    q = pq("sim_quality_monthly")
    q = q[q.desk == "FR"]
    x = pd.to_datetime(q.month)
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.plot(x, q.complete_at_draft, color=RED, marker="o", label="Complete at draft")
    ax.plot(x, q.complete_at_submission, color=BLUE, marker="o", label="Complete at submission")
    ax.bar(x, q.qa_return_rate, 20, color=LIGHT, label="QA return rate")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    ax.set_ylim(0, 1.08)
    month_axis(ax)
    event(ax, "2026-05-11", "schema change", y=0.6)
    ax.set_title("Completeness and QA returns, France desk")
    ax.legend(fontsize=8, loc="lower left")
    return save(fig, "p5_quality")


def sim_did():
    w = pq("sim_weekly_effort")
    fig, ax = plt.subplots(figsize=(6, 3.2))
    for desk, col, lab in [("FR", BLUE, "France (pre-fill from 3 Aug)"), ("BNL", GREY, "Benelux (control)")]:
        s = w[w.desk == desk]
        ax.plot(pd.to_datetime(s.week), s.geo_mean_hours, color=col, marker="o", ms=3, label=lab)
    ax.axvspan(pd.Timestamp("2026-05-04"), pd.Timestamp("2026-08-02"), color=GRID, alpha=0.5, lw=0)
    ax.set_ylim(0, w.geo_mean_hours.max() * 1.25)
    event(ax, "2026-08-03", "pre-fill", color=AQUA)
    ax.text(pd.Timestamp("2026-05-08"), ax.get_ylim()[1] * 0.08, "pre period", fontsize=8, color=MUTED)
    month_axis(ax)
    ax.set_ylabel("analyst hours per case (geo. mean)")
    ax.set_title("Effort per case: treated vs control")
    ax.legend(fontsize=8, loc="lower right")
    return save(fig, "p5_did")


# ------------------------------------------------------------------ page 6: CAP (SIMULATED)
def sim_cap():
    s = pq("sim_cap_status")
    order = ["closed on time", "open, on track", "closed without evidence", "overdue"]
    colors = {"closed on time": LIGHT, "open, on track": BLUE, "closed without evidence": ORANGE, "overdue": RED}
    t = s.pivot_table(index="owner_team", columns="cap_state", values="cap_id", aggfunc="count", fill_value=0)
    t = t.reindex(columns=[c for c in order if c in t.columns])
    fig, ax = plt.subplots(figsize=(4.8, 4.2))
    left = np.zeros(len(t))
    for c in t.columns:
        ax.barh(t.index, t[c], left=left, color=colors[c], label=c)
        left += t[c].values
    ax.invert_yaxis()
    ax.set_title("CAP items by owner team, 31 Oct 2026")
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2)
    ax.grid(axis="y", visible=False)
    return save(fig, "p6_cap")


def build_all():
    return {f.__name__: f() for f in [bunq_fee, bunq_staff, tracfin, ecb, ibm_rules, ibm_curve, ibm_typ, sim_alerts,
                                       sim_backlog, sim_clock, sim_ontime, sim_quality, sim_did, sim_cap]}


if __name__ == "__main__":
    print(build_all())
