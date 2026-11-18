"""Pre-fill a structured suspicious-activity report draft from a SIMULATED case, with a blocking completeness check.

For each selected case:
  output/prefill/<case_id>.json   structured draft (fields the system can fill; the analysis stays with the analyst)
  output/prefill/<case_id>.md     human-readable draft for the four-eyes review
  output/prefill/missing_fields_log.csv   one row per blocked draft and missing field
A draft with a missing required field is BLOCKED: it cannot move to QA until the field is filled.
The functions below are also what the tests in tests/test_prefill.py check (deadline, duplicates, clock).
    python src/prefill_report.py                 # 5 example cases, including blocked ones
    python src/prefill_report.py case_000123     # one case
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "data" / "simulated"
OUT = ROOT / "output" / "prefill"
PARIS = "Europe/Paris"
INTERNAL_TARGET_DAYS = 14          # internal target used by the simulated desk (not a legal deadline)
MIN_NARRATIVE_WORDS = 30
REQUIRED = ["case_id", "subject_id", "account_id", "amount_eur", "transaction_dates", "counterparty_country",
            "counterparty_iban", "typology", "narrative_words", "alert_source", "alert_ts_utc"]


# ---------------------------------------------------------------- rules (tested)
def paris_date(ts_utc) -> pd.Timestamp:
    """Calendar date in Paris for a naive UTC timestamp."""
    return pd.Timestamp(ts_utc).tz_localize("UTC").tz_convert(PARIS).tz_localize(None).normalize()


def on_time(alert_ts_utc, submitted_ts_utc, target_days: int = INTERNAL_TARGET_DAYS) -> bool:
    """Submitted no later than the Paris calendar day of the alert + target_days (never compare UTC dates)."""
    return paris_date(submitted_ts_utc) <= paris_date(alert_ts_utc) + pd.Timedelta(days=target_days)


def time_to_file_days(alert_ts_utc, submitted_ts_utc) -> float:
    """KPI clock: starts at the ALERT (first signal), stops at the first submission."""
    return (pd.Timestamp(submitted_ts_utc) - pd.Timestamp(alert_ts_utc)).total_seconds() / 86400


def first_submissions(reports: pd.DataFrame) -> pd.DataFrame:
    """One row per report_id (the earliest submission): removes retry duplicates before any count."""
    return (reports.sort_values("submitted_ts_utc").drop_duplicates("report_id", keep="first")
            .reset_index(drop=True))


def missing_fields(draft: dict) -> list[str]:
    miss = [f for f in REQUIRED if draft.get(f) in (None, "", [], "nan") or
            (isinstance(draft.get(f), float) and pd.isna(draft.get(f)))]
    if "narrative_words" not in miss and draft["narrative_words"] < MIN_NARRATIVE_WORDS:
        miss.append("narrative_words")
    return miss


# ---------------------------------------------------------------- draft builder
def load():
    return {n: pd.read_parquet(SIM / f"{n}.parquet") for n in ["alerts", "cases", "reports"]}


def build_draft(case_id: str, t: dict) -> dict:
    c = t["cases"].set_index("case_id").loc[case_id]
    a = t["alerts"].set_index("alert_id").loc[c.alert_id]
    reps = t["reports"][t["reports"].case_id == case_id]
    r = first_submissions(reps).iloc[0] if len(reps) else None
    # the draft as the schema delivered it (before QA corrections)
    miss_at_draft = (r.missing_fields_at_draft.split(";") if r is not None and r.missing_fields_at_draft else [])
    val = lambda f: None if (r is None or f in miss_at_draft) else (None if pd.isna(r[f]) else r[f])
    draft = {
        "case_id": case_id, "desk": c.desk, "subject_id": c.user_id, "account_id": val("account_id") and f"acct_{c.user_id[5:]}",
        "amount_eur": None if r is None else float(r.amount_eur), "transaction_dates": val("transaction_dates") and "see case file",
        "counterparty_country": val("counterparty_country"), "counterparty_iban": val("counterparty_iban") and "masked in draft",
        "typology": None if r is None else r.typology,
        "narrative_words": 0 if r is None or "narrative" in miss_at_draft else int(r.narrative_words),
        "alert_source": a.source, "alert_ts_utc": str(a.alert_ts_utc),
        "case_opened_ts_utc": str(c.opened_ts_utc),
        "deadline_paris_date": str((paris_date(a.alert_ts_utc) + pd.Timedelta(days=INTERNAL_TARGET_DAYS)).date()),
    }
    draft["missing_fields"] = missing_fields(draft)
    draft["status"] = "BLOCKED - complete the missing fields" if draft["missing_fields"] else "READY FOR QA"
    return draft


def to_markdown(d: dict) -> str:
    rows = "\n".join(f"| {k} | {v} |" for k, v in d.items() if k not in ("missing_fields", "status"))
    miss = ", ".join(d["missing_fields"]) or "none"
    return f"""# Draft suspicious-activity report - {d['case_id']} (SIMULATED)

> CONFIDENTIAL. Never tell the customer, or any third party, that a report is being prepared or has been sent.

**Status:** {d['status']}
**Missing required fields:** {miss}
**Internal deadline (Paris date):** {d['deadline_paris_date']}

| Field | Value |
|---|---|
{rows}

## Analysis (written by the analyst, not pre-filled)
- Why the activity is suspicious (facts, dates, amounts, links between transactions):
- What is known about the customer and the counterparties (CDD / EDD file):
- Documents attached:

Four-eyes review: preparer role / reviewer role, date.
"""


def main(case_ids=None):
    t = load()
    OUT.mkdir(parents=True, exist_ok=True)
    if not case_ids:
        rep = first_submissions(t["reports"])
        broken = [rep[rep.missing_fields_at_draft.str.contains(k)].case_id.iloc[0] for k in ("counterparty", "narrative")]
        clean = rep[rep.missing_fields_at_draft == ""].case_id.head(3).tolist()
        case_ids = clean + broken
    log = []
    for cid in case_ids:
        d = build_draft(cid, t)
        (OUT / f"{cid}.json").write_text(json.dumps(d, indent=2, default=str), encoding="utf-8")
        (OUT / f"{cid}.md").write_text(to_markdown(d), encoding="utf-8")
        log += [{"case_id": cid, "missing_field": m, "status": d["status"]} for m in d["missing_fields"]]
        print(f"{cid}: {d['status']}")
    pd.DataFrame(log, columns=["case_id", "missing_field", "status"]).to_csv(OUT / "missing_fields_log.csv", index=False)


if __name__ == "__main__":
    main(sys.argv[1:])
