#!/usr/bin/env python3
"""Test which FMP screener endpoint works."""
import json, time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"

urls = [
    f"https://financialmodelingprep.com/stable/stock-screener?marketCapMoreThan=10000000000&exchange=NYSE,NASDAQ,AMEX&apikey={API_KEY}",
    f"https://financialmodelingprep.com/api/v3/stock-screener?marketCapMoreThan=10000000000&exchange=NYSE,NASDAQ,AMEX&apikey={API_KEY}",
    f"https://financialmodelingprep.com/stable/stock-screener?marketCapMoreThan=10000000000&apikey={API_KEY}",
    f"https://financialmodelingprep.com/api/v3/stock-screener?marketCapMoreThan=10000000000&apikey={API_KEY}",
]

for url in urls:
    time.sleep(0.5)
    short = url.split("apikey=")[0] + "apikey=..."
    try:
        req = Request(url, headers={"User-Agent": "test/1.0"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                print(f"OK  ({len(data):>4} results) — {short}")
            else:
                print(f"ERR (not list: {type(data)}) — {short}")
                print(f"    Response: {str(data)[:200]}")
    except Exception as e:
        print(f"FAIL ({e}) — {short}")
