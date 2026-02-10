#!/usr/bin/env python3
"""Check FMP fields for dividends and market cap."""
import json, time
from urllib.request import urlopen, Request

API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"
BASE = "https://financialmodelingprep.com/stable"

def fetch(url):
    time.sleep(0.3)
    req = Request(url, headers={"User-Agent": "diag/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

# Check ADP cash flow for dividend fields
print("=== ADP Cash Flow Fields (looking for dividends) ===")
cf = fetch(f"{BASE}/cash-flow-statement?symbol=ADP&limit=1&apikey={API_KEY}")
for k, v in sorted(cf[0].items()):
    if v and isinstance(v, (int, float)) and v != 0:
        if 'div' in k.lower() or 'stock' in k.lower() or 'repurch' in k.lower() or 'pay' in k.lower():
            print(f"  {k:<45} {v/1e9:>10.2f}B")

print("\n=== ALL non-zero cash flow fields ===")
for k, v in sorted(cf[0].items()):
    if v and isinstance(v, (int, float)) and abs(v) > 1e6:
        print(f"  {k:<45} {v/1e9:>10.2f}B")

# Check profile for mktCap
print("\n=== ADP Profile Fields ===")
p = fetch(f"{BASE}/profile?symbol=ADP&apikey={API_KEY}")
if isinstance(p, list): p = p[0]
for k, v in sorted(p.items()):
    if 'cap' in k.lower() or 'market' in k.lower() or 'price' in k.lower() or 'mkt' in k.lower():
        print(f"  {k:<35} {v}")

print("\n=== NVDA Profile Fields ===")
p2 = fetch(f"{BASE}/profile?symbol=NVDA&apikey={API_KEY}")
if isinstance(p2, list): p2 = p2[0]
for k, v in sorted(p2.items()):
    if 'cap' in k.lower() or 'market' in k.lower() or 'price' in k.lower() or 'mkt' in k.lower():
        print(f"  {k:<35} {v}")

print("\nDone.")
