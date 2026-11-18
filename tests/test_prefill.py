"""Tests for the reporting rules in src/prefill_report.py (run: pytest)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import prefill_report as pr  # noqa: E402

FULL = {"case_id": "case_000001", "subject_id": "user_00001", "account_id": "acct_00001", "amount_eur": 1200.0,
        "transaction_dates": "see case file", "counterparty_country": "FR", "counterparty_iban": "masked",
        "typology": "fan-out", "narrative_words": 150, "alert_source": "monitoring_rule",
        "alert_ts_utc": "2026-03-01 10:00:00"}


def test_complete_draft_is_not_blocked():
    assert pr.missing_fields(dict(FULL)) == []


def test_missing_required_field_blocks_the_draft():
    d = dict(FULL, counterparty_iban=None, counterparty_country="")
    assert set(pr.missing_fields(d)) == {"counterparty_iban", "counterparty_country"}


def test_short_narrative_blocks_the_draft():
    assert pr.missing_fields(dict(FULL, narrative_words=12)) == ["narrative_words"]


def test_duplicates_are_counted_once():
    rep = pd.DataFrame({"report_id": ["r1", "r1", "r2"], "submission_id": ["s1", "s2", "s3"],
                        "submitted_ts_utc": pd.to_datetime(["2026-06-02 10:00", "2026-06-02 10:07", "2026-06-03 09:00"])})
    out = pr.first_submissions(rep)
    assert len(out) == 2
    assert out.set_index("report_id").loc["r1", "submission_id"] == "s1"


def test_submission_after_midnight_paris_is_late_even_if_utc_date_is_on_time():
    # alert 1 Jun 2026 09:00 UTC -> deadline Paris date 15 Jun. Submitted 15 Jun 22:30 UTC = 16 Jun 00:30 Paris.
    alert, sub = pd.Timestamp("2026-06-01 09:00"), pd.Timestamp("2026-06-15 22:30")
    assert sub.normalize() <= alert.normalize() + pd.Timedelta(days=14)        # the UTC check says on time
    assert pr.on_time(alert, sub) is False                                      # the Paris check says late


def test_winter_time_offset_is_one_hour():
    alert = pd.Timestamp("2026-01-05 09:00")
    assert pr.on_time(alert, pd.Timestamp("2026-01-19 22:59")) is True          # 23:59 Paris
    assert pr.on_time(alert, pd.Timestamp("2026-01-19 23:01")) is False         # 00:01 Paris next day


def test_time_to_file_clock_starts_at_the_alert():
    alert, opened, sub = (pd.Timestamp("2026-09-01 08:00"), pd.Timestamp("2026-09-05 08:00"),
                          pd.Timestamp("2026-09-11 08:00"))
    assert pr.time_to_file_days(alert, sub) == 10.0
    assert pr.time_to_file_days(alert, sub) != pr.time_to_file_days(opened, sub)
