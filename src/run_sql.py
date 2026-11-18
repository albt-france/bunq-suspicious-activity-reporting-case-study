"""Run every query in sql/*.sql with DuckDB and save each named result to data/processed/<name>.parquet.

A file holds several queries, each introduced by a line '-- name: <result_name>'.
  01-02  read data/raw/ibm/ibm.duckdb (built by src/extract_ibm_aml.py). If it is absent (fresh clone),
         the published aggregates already in data/processed/ are kept and these files are skipped.
  03-06  read the simulated tables in data/simulated/*.parquet (built by src/simulate.py).
    python src/run_sql.py
"""
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql"
PROC = ROOT / "data" / "processed"
SIM = ROOT / "data" / "simulated"
IBM_DB = ROOT / "data" / "raw" / "ibm" / "ibm.duckdb"


def split_named(text: str):
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.M)
    for i in range(1, len(parts), 2):
        yield parts[i], parts[i + 1].strip().rstrip(";")


def connect(file: Path):
    if file.name[:2] in {"01", "02"}:
        if not IBM_DB.exists():
            return None
        return duckdb.connect(str(IBM_DB), read_only=True)
    con = duckdb.connect()
    for p in sorted(SIM.glob("*.parquet")):
        con.execute(f"CREATE VIEW {p.stem} AS SELECT * FROM read_parquet('{p.as_posix()}')")
    return con


def main():
    PROC.mkdir(parents=True, exist_ok=True)
    for f in sorted(SQL.glob("*.sql")):
        con = connect(f)
        if con is None:
            print(f"{f.name}: raw IBM database absent, published aggregates kept")
            continue
        for name, q in split_named(f.read_text(encoding="utf-8")):
            df = con.execute(q).df()
            df.to_parquet(PROC / f"{name}.parquet", index=False)
            print(f"{f.name} -> {name}: {df.shape}")
        con.close()


if __name__ == "__main__":
    main()
