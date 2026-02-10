#!/usr/bin/env python3
"""Test batch quote and other approaches for market cap filtering."""
import json, time
from urllib.request import urlopen, Request
from urllib.error import HTTPError

API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"

tests = [
    # Batch quote — comma-separated symbols
    ("batch quote (stable)", 
     f"https://financialmodelingprep.com/stable/quote?symbol=AAPL,MSFT,NVDA,MA,V&apikey={API_KEY}"),
    ("batch quote (v3)",
     f"https://financialmodelingprep.com/api/v3/quote/AAPL,MSFT,NVDA,MA,V?apikey={API_KEY}"),
    # Batch profile
    ("batch profile (stable)",
     f"https://financialmodelingprep.com/stable/profile?symbol=AAPL,MSFT,NVDA,MA,V&apikey={API_KEY}"),
    # Market cap batch
    ("market-cap batch",
     f"https://financialmodelingprep.com/stable/market-capitalization?symbol=AAPL,MSFT,NVDA&apikey={API_KEY}"),
]

for name, url in tests:
    time.sleep(0.5)
    try:
        req = Request(url, headers={"User-Agent": "test/1.0"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                print(f"OK  ({len(data)} results) — {name}")
                for item in data[:3]:
                    sym = item.get("symbol","?")
                    mc = item.get("marketCap", item.get("mktCap", "N/A"))
                    if isinstance(mc, (int,float)) and mc > 1e9:
                        print(f"    {sym}: ${mc/1e12:.2f}T")
                    else:
                        print(f"    {sym}: mc={mc}")
            else:
                print(f"OK  (not list) — {name}: {str(data)[:150]}")
    except HTTPError as e:
        print(f"FAIL ({e.code}) — {name}")
    except Exception as e:
        print(f"FAIL ({e}) — {name}")

# Also check: how many symbols in stock-list look like US stocks?
print("\n--- Stock list filtering test ---")
url = f"https://financialmodelingprep.com/stable/stock-list?apikey={API_KEY}"
req = Request(url, headers={"User-Agent": "test/1.0"})
with urlopen(req, timeout=30) as resp:
    stocks = json.loads(resp.read().decode())

print(f"Total: {len(stocks)}")

# Filter heuristics for US-listed
us_like = []
for s in stocks:
    sym = s.get("symbol","")
    if not sym: continue
    if len(sym) > 5: continue  # skip long symbols
    if '.' in sym or '-' in sym: continue  # skip preferred/units
    if len(sym) == 5 and sym[-1] in ('F','Y'): continue  # skip OTC foreign
    if any(c.isdigit() for c in sym): continue  # skip warrants etc
    us_like.append(sym)

print(f"US-like (heuristic): {len(us_like)}")
print(f"Sample: {us_like[:20]}")
