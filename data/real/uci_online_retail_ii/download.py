"""Fetch the original UCI file and verify it byte-for-byte.

    backend/.venv/bin/python data/real/uci_online_retail_ii/download.py

The raw archive (45.6 MB) is not committed; this script restores it from the
official UCI Machine Learning Repository and refuses a file whose SHA-256
differs from the one recorded when the dataset was first retrieved.
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
EXPECTED_SHA256 = "572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb"
DEST = Path(__file__).resolve().parent / "raw" / "online_retail_ii.zip"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if DEST.exists() and sha256(DEST) == EXPECTED_SHA256:
        print(f"already present and verified: {DEST}")
        return 0
    DEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEST.with_suffix(".part")
    print(f"downloading {URL}")
    urllib.request.urlretrieve(URL, tmp)
    got = sha256(tmp)
    if got != EXPECTED_SHA256:
        tmp.unlink()
        print(f"hash mismatch: got {got}, expected {EXPECTED_SHA256}", file=sys.stderr)
        return 1
    tmp.replace(DEST)
    print(f"saved and verified: {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
