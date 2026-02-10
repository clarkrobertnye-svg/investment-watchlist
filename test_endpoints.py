#!/usr/bin/env python3
"""Test alternative FMP endpoints for universe building."""
import json, time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"

tests = [
    ("stock list (stable)", f"https://financialmodelingprep.com/stable/stock-list?apikey={API_KEY}"),
    ("stock list (v3)", f"https://financialmodelingprep.com/api/v3/stock/list?apikey={API_KEY}"),
    ("available traded (stable)", f"https://financialmodelingprep.com/stable/available-traded/list?apikey={API_KEY}"),
    ("market cap (stable)", f"https://financialmodelingprep.com/stable/market-capitalization?symbol=AAPL&apikey={API_KEY}"),
    ("sp500 (stable)", f"https://financialmodelingprep.com/stable/sp500-constituent?apikey={API_KEY}"),
    ("sp500 (v3)", f"https://financialmodelingprep.com/api/v3/sp500_constituent?apikey={API_KEY}"),
    ("nasdaq (stable)", f"https://financialmodelingprep.com/stable/nasdaq-constituent?apikey={API_KEY}"),
    ("dowjones (stable)", f"https://financialmodelingprep.com/stable/dowjones-constituent?apikey={API_KEY}"),
]

for name, url in tests:
    time.sleep(0.5)
    try:
        req = Request(url, headers={"User-Agent": "test/1.0"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                print(f"OK  ({len(data):>5} results) — {name}")
                if data:
                    print(f"    Sample keys: {list(data[0].keys())[:8]}")
                    # Check for market cap field
                    sample = data[0]
                    for k in ['marketCap','mktCap','market_cap']:
                        if k in sample:
                            print(f"    Has {k}: {sample[k]}")
            elif isinstance(data, dict):
                print(f"OK  (dict)         — {name}")
                print(f"    Keys: {list(data.keys())[:8]}")
            else:
                print(f"ERR (type={type(data)}) — {name}")
    except HTTPError as e:
        print(f"FAIL ({e.code})            — {name}")
    except Exception as e:
        print(f"FAIL ({e})    — {name}")
