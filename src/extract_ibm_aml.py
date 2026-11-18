"""Load IBM "AML" HI-Small (synthetic, AMLSim, CDLA-Sharing-1.0) into a local DuckDB file with DuckDB.

Input  data/raw/ibm/HI-Small_Trans.csv (475 MB) and HI-Small_Patterns.txt (from src/download_ibm.py)
Output data/raw/ibm/ibm.duckdb (never published) with tables:
  trans     one row per transaction; the two 'Account' columns renamed from_account / to_account;
            accounts keyed as bank|account; amounts converted to USD with rates implied by the data itself
  patterns  one row per transaction listed in a laundering attempt, with attempt_id and typology
Only aggregates computed by sql/01_ibm_profile.sql and sql/02_alert_rules.sql leave this file (src/run_sql.py).
    python src/extract_ibm_aml.py
"""
import re
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IBM = ROOT / "data" / "raw" / "ibm"
DB = IBM / "ibm.duckdb"


def parse_patterns(path: Path) -> pd.DataFrame:
    rows, attempt, typ = [], 0, None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("BEGIN LAUNDERING ATTEMPT"):
            attempt += 1
            typ = re.match(r"BEGIN LAUNDERING ATTEMPT - ([A-Z\-]+)", line).group(1)
        elif line.startswith("END LAUNDERING ATTEMPT") or not line.strip():
            continue
        else:
            f = line.split(",")
            rows.append({"attempt_id": attempt, "typology": typ, "ts": f[0], "from_acct": f"{f[1]}|{f[2]}",
                         "to_acct": f"{f[3]}|{f[4]}", "amount_paid": float(f[7]), "pay_currency": f[8]})
    return pd.DataFrame(rows)


def main():
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    csv = (IBM / "HI-Small_Trans.csv").as_posix()
    con.execute(f"""
        CREATE TABLE raw AS SELECT * FROM read_csv('{csv}', header=true, all_varchar=true,
            names=['ts','from_bank','from_account','to_bank','to_account','amount_received','receiving_currency',
                   'amount_paid','payment_currency','payment_format','is_laundering'])""")
    # USD rate per currency, implied by cross-currency rows paid in that currency and received in US Dollar.
    con.execute("""
        CREATE TABLE fx AS
        SELECT payment_currency AS currency,
               median(CAST(amount_received AS DOUBLE) / CAST(amount_paid AS DOUBLE)) AS usd_per_unit
        FROM raw
        WHERE receiving_currency = 'US Dollar' AND payment_currency <> 'US Dollar' AND CAST(amount_paid AS DOUBLE) > 0
        GROUP BY 1
        UNION ALL SELECT 'US Dollar', 1.0""")
    con.execute("""
        CREATE TABLE trans AS
        SELECT strptime(r.ts, '%Y/%m/%d %H:%M') AS ts,
               r.from_bank || '|' || r.from_account AS from_acct,
               r.to_bank || '|' || r.to_account AS to_acct,
               CAST(r.amount_paid AS DOUBLE) AS amount_paid, r.payment_currency,
               CAST(r.amount_paid AS DOUBLE) * f.usd_per_unit AS amount_usd,
               r.payment_format, CAST(r.is_laundering AS INTEGER) AS is_laundering
        FROM (SELECT DISTINCT * FROM raw) r LEFT JOIN fx f ON f.currency = r.payment_currency""")
    # Row-count guard: a join must never add rows (a duplicated currency in fx once inflated the table by 37%).
    n_raw, n_distinct = con.execute("SELECT count(*), (SELECT count(*) FROM (SELECT DISTINCT * FROM raw)) FROM raw").fetchone()
    assert con.execute("SELECT count(*) FROM trans").fetchone()[0] == n_distinct, "join added rows"
    con.execute("DROP TABLE raw")
    pat = parse_patterns(IBM / "HI-Small_Patterns.txt")
    con.register("pat_df", pat)
    con.execute("CREATE TABLE patterns AS SELECT attempt_id, typology, strptime(ts, '%Y/%m/%d %H:%M') AS ts, "
                "from_acct, to_acct, amount_paid, pay_currency FROM pat_df")
    n, lab, nfx = con.execute("SELECT count(*), sum(is_laundering), count(*) FILTER (WHERE amount_usd IS NULL) FROM trans").fetchone()
    accts = con.execute("SELECT count(DISTINCT a) FROM (SELECT from_acct a FROM trans UNION SELECT to_acct FROM trans)").fetchone()[0]
    span = con.execute("SELECT min(ts)::DATE, max(ts)::DATE FROM trans").fetchone()
    PROC = ROOT / "data" / "processed"
    PROC.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"rows_in_file": n_raw, "rows_after_exact_dedup": n, "exact_duplicates_removed": n_raw - n,
                   "laundering_rows": int(lab), "accounts_seen": accts, "first_day": str(span[0]), "last_day": str(span[1]),
                   "pattern_rows": len(pat), "laundering_attempts": int(pat.attempt_id.nunique())}]
                 ).to_csv(PROC / "ibm_load_checks.csv", index=False)
    print(f"file rows {n_raw:,} | trans rows {n:,} | laundering {lab:,} | rows without USD rate {nfx} | pattern rows {len(pat):,} "
          f"| attempts {pat.attempt_id.nunique()}")
    con.close()


if __name__ == "__main__":
    main()
