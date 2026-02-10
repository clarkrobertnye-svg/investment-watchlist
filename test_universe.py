#!/usr/bin/env python3
"""Test universe builder — just count candidates, check first 100 for market cap."""
import json, time
from urllib.request import urlopen, Request

API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"
BASE_URL = "https://financialmodelingprep.com/stable"

# Step 1: Get all symbols
print("Pulling stock list...")
req = Request(f"{BASE_URL}/stock-list?apikey={API_KEY}", headers={"User-Agent": "test/1.0"})
with urlopen(req, timeout=30) as resp:
    stock_list = json.loads(resp.read().decode())

print(f"Total symbols: {len(stock_list)}")

# Apply tight filter
candidates = []
for s in stock_list:
    sym = s.get("symbol", "")
    if not sym: continue
    if not sym.isalpha(): continue
    if len(sym) > 5: continue
    if len(sym) == 5 and sym[-1] in ('F', 'Y'): continue
    if len(sym) >= 4 and sym[-1] == 'X': continue
    if sym[-1] in ('Q', 'W'): continue
    if len(sym) == 5 and sym[-1] not in ('L','K','A','B'): continue
    candidates.append(sym)

print(f"After filter: {len(candidates)} candidates")
print(f"Estimated market-cap check time: {len(candidates) * 0.1 / 60:.1f} min")

# Spot check first 200 to see hit rate
print(f"\nSpot checking first 200 for $10B+ market cap...")
hits = 0
for i, sym in enumerate(candidates[:200]):
    time.sleep(0.1)
    try:
        url = f"{BASE_URL}/market-capitalization?symbol={sym}&apikey={API_KEY}"
        req = Request(url, headers={"User-Agent": "test/1.0"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, list) and data:
            mc = data[0].get("marketCap", 0) or 0
        else:
            continue
        if mc >= 10_000_000_000:
            hits += 1
            if hits <= 10:
                mc_str = f"${mc/1e12:.1f}T" if mc >= 1e12 else f"${mc/1e9:.0f}B"
                print(f"  {sym:<6} {mc_str}")
    except:
        continue

print(f"\nHit rate: {hits}/200 = {hits/200*100:.0f}%")
print(f"Estimated total $10B+ stocks: {int(hits/200 * len(candidates))}")
print(f"\nBreakdown by symbol length:")
for n in range(1, 6):
    count = sum(1 for c in candidates if len(c) == n)
    print(f"  {n}-char: {count}")
