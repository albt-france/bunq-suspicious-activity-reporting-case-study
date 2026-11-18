"""Download IBM "AML" HI-Small (synthetic, AMLSim; licence CDLA-Sharing-1.0) from its Hugging Face mirror
into data/raw/ibm/. The raw files are never published; only aggregates go to data/processed/.
    python src/download_ibm.py
"""
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "ibm"
BASE = "https://huggingface.co/datasets/OsamaMIT/IBM-AML-HI-Small/resolve/main/"
FILES = ["HI-Small_Patterns.txt", "HI-Small_Trans.csv"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        dest = OUT / f
        if dest.exists() and dest.stat().st_size > 0:
            print("exists", f)
            continue
        with requests.get(BASE + f, headers={"User-Agent": "reporting-case-study/1.0"}, stream=True, timeout=120) as r:
            r.raise_for_status()
            tmp = dest.with_suffix(".part")
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
            tmp.rename(dest)
        print("downloaded", f, dest.stat().st_size // 1_000_000, "MB")


if __name__ == "__main__":
    main()
