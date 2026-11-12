"""Record a raw Yahoo payload for tests: python scripts/record_fixture.py TICKER out.json"""
import json
import sys

from dcf.data.yahoo import fetch_raw

ticker, out = sys.argv[1], sys.argv[2]
raw = fetch_raw(ticker)
if raw is None:
    sys.exit(f"{ticker}: not found")
with open(out, "w", encoding="utf-8") as f:
    json.dump(raw, f, indent=1, sort_keys=True)
print(ticker, "->", out, "info keys:", len(raw["info"]), "income rows:", len(raw["income"]))
