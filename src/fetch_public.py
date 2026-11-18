"""Collect the public sources once (polite: robots.txt, >= 3 s between requests, neutral User-Agent).

Raw files go to data/raw/ (never published). Processed, publishable extracts go to data/processed/:
  - ecb_payment_fraud.csv   ECB payment statistics, fraudulent transactions, FR vs NL (semi-annual)
  - bunq_facts.csv          facts quoted from bunq's annual report 2025 ("as stated by bunq"), with page numbers
  - amlr_check.csv          sentences checked in the text of Regulation (EU) 2024/1624 (EUR-Lex)
Tracfin and Legifrance refuse scripted requests (403): their figures are read in a browser and typed in
data/processed/tracfin_2025.csv with the reading date (see data/SOURCES.md). Himalayas is behind Cloudflare: not fetched.
    python src/fetch_public.py
"""
import io
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from polite import get

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
TODAY = date.today().isoformat()

BUNQ_REPORT = "https://static.bunq.com/website/documents/bunq-report-annual-2025-en.pdf"
BUNQ_JOB = "https://careers.bunq.com/o/reporting-agent-france-3"
# FRD_TYP=F: fraudulent transactions; FRD_TYP=_Z: all transactions (to compute a fraud rate). UNIT_MULT=6: millions.
ECB = ("https://data-api.ecb.europa.eu/service/data/PAY/H.FR+NL.W0.CT0+CP0+DD+EMP0.1.F+_Z.N.EUR+PN"
       "?format=csvdata&startPeriod=2022")
AMLR = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32024R1624"

# Phrases searched in bunq's annual report; the matching sentence and page are stored, not typed by hand.
BUNQ_PATTERNS = {
    "users": r"22\s*million",
    "fte_total": r"\b665\b",
    "fte_onboarding_support_compliance": r"Onboarding,?\s+Support,?\s+(and\s+)?Compliance",
    "aml_ai": r"first banks to (win|be granted)[^.]{0,80}(AI|artificial intelligence)",
    "fee_france_belgium": r"France\s*/?\s*(and\s*)?Belgium",
}
AMLR_PATTERNS = {
    "apply_date": r"It shall apply from 10 July 2027",
    "art69_title": r"Article 69\s*Reporting of suspicions",
    "art69_timing": r"within 5 working days",
    "art70_title": r"Article 70\s*",
    "art73_title": r"Article 73\s*Prohibition of disclosure",
}


def save(name, content: bytes):
    p = RAW / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def bunq():
    j = get(BUNQ_JOB)
    if j is not None and j.status_code == 200:
        save("bunq/job_reporting_agent_france.html", j.content)
    # static.bunq.com disallows all robots: the report is not fetched by script. It is saved once by hand
    # from a browser to data/raw/bunq/ and only read here.
    local = RAW / "bunq" / "bunq-report-annual-2025-en.pdf"
    if not local.exists():
        print("bunq report: save it by hand to", local.relative_to(ROOT), "(robots.txt of static.bunq.com disallows scripts)")
        return
    reader = PdfReader(str(local))
    rows = []
    for i, pg in enumerate(reader.pages, start=1):
        txt = re.sub(r"\s+", " ", pg.extract_text() or "")
        for key, pat in BUNQ_PATTERNS.items():
            for m in re.finditer(pat, txt, flags=re.I):
                s, e = max(0, m.start() - 220), min(len(txt), m.end() + 220)
                rows.append({"fact": key, "page": i, "context": txt[s:e]})
    pd.DataFrame(rows).to_csv(RAW / "bunq" / "bunq_report_matches.csv", index=False)
    print("bunq report pages:", len(reader.pages), "matches:", len(rows))


def ecb():
    r = get(ECB, check_robots=False)
    if r is None or r.status_code != 200:
        print("ECB: failed", None if r is None else r.status_code)
        return
    save("ecb/pay_fraud.csv", r.content)
    d = pd.read_csv(io.StringIO(r.text))
    keep = ["KEY", "REF_AREA", "TYP_TRNSCTN", "FRD_TYP", "UNIT_MEASURE", "TIME_PERIOD", "OBS_VALUE", "UNIT_MULT", "TITLE"]
    d = d[[c for c in keep if c in d.columns]].copy()
    d["retrieved"] = TODAY
    d.to_csv(PROC / "ecb_payment_fraud.csv", index=False)
    print("ECB rows:", len(d), "UNIT_MULT:", sorted(d.UNIT_MULT.dropna().unique().tolist()))


def amlr():
    r = None
    for _ in range(3):                      # EUR-Lex may answer 202 (queued) first; crawl-delay is 10 s
        r = get(AMLR)
        if r is not None and r.status_code == 200 and "Article 69" in r.text:
            break
        time.sleep(10)
    if r is None or r.status_code != 200:
        print("EUR-Lex: failed", None if r is None else r.status_code)
        return
    save("eurlex/32024R1624.html", r.content)
    txt = re.sub(r"<[^>]+>", " ", r.text)
    txt = re.sub(r"\s+", " ", txt)
    rows = []
    for key, pat in AMLR_PATTERNS.items():
        m = re.search(pat, txt)
        rows.append({"check": key, "found": bool(m),
                     "excerpt": txt[m.start(): m.start() + 300] if m else "", "retrieved": TODAY, "url": AMLR})
    pd.DataFrame(rows).to_csv(RAW / "eurlex" / "amlr_matches.csv", index=False)
    print("AMLR checks found:", sum(r["found"] for r in rows), "/", len(rows))


def main():
    PROC.mkdir(parents=True, exist_ok=True)
    bunq()
    ecb()
    amlr()


if __name__ == "__main__":
    main()
