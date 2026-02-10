#!/usr/bin/env python3
"""Fetch $800M-$10B US stocks from FMP, cache financial data."""
import requests, json, time, sys, os, argparse
from pathlib import Path

try:
    from config import FMP_API_KEY
except ImportError:
    FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
    if not FMP_API_KEY:
        print("ERROR: No API key"); sys.exit(1)

BASE_URL = "https://financialmodelingprep.com/stable"
DELAY = 0.22
CACHE_DIR = Path("cache/raw")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def fetch_universe(min_cap=800e6, max_cap=10e9):
    url = f"{BASE_URL}/company-screener"
    params = {"apikey": FMP_API_KEY, "marketCapMoreThan": int(min_cap),
              "marketCapLessThan": int(max_cap), "isActivelyTrading": True,
              "isEtf": False, "isFund": False, "country": "US",
              "exchange": "NYSE,NASDAQ", "limit": 5000}
    print(f"Fetching US stocks ${min_cap/1e6:.0f}M-${max_cap/1e9:.0f}B...")
    r = requests.get(url, params=params)
    if r.status_code != 200:
        url = f"{BASE_URL}/stock-screener"
        r = requests.get(url, params=params)
        if r.status_code != 200:
            print(f"ERROR: {r.status_code}"); sys.exit(1)
    data = r.json()
    print(f"Raw results: {len(data)}")
    stocks = []
    for item in data:
        sym = item.get("symbol", "")
        if any(x in sym for x in ["-",".","/","^"]) or len(sym) > 5 or not sym:
            continue
        stocks.append({"symbol": sym, "name": item.get("companyName",""),
                       "marketCap": item.get("marketCap",0),
                       "sector": item.get("sector","")})
    stocks.sort(key=lambda x: x["marketCap"], reverse=True)
    print(f"Clean tickers: {len(stocks)}")
    return stocks

def fetch_ticker_data(ticker, force=False):
    endpoints = {
        "profile": f"{BASE_URL}/profile?symbol={ticker}",
        "income": f"{BASE_URL}/income-statement?symbol={ticker}&period=annual&limit=6",
        "cashflow": f"{BASE_URL}/cash-flow-statement?symbol={ticker}&period=annual&limit=6",
        "balance": f"{BASE_URL}/balance-sheet-statement?symbol={ticker}&period=annual&limit=6",
        "metrics": f"{BASE_URL}/key-metrics?symbol={ticker}&period=annual&limit=6",
    }
    fetched = 0
    for name, url in endpoints.items():
        cache_file = CACHE_DIR / f"{ticker}_{name}.json"
        if cache_file.exists() and not force: continue
        try:
            r = requests.get(url, params={"apikey": FMP_API_KEY})
            time.sleep(DELAY)
            if r.status_code == 200:
                with open(cache_file, "w") as f: json.dump(r.json(), f, indent=2)
                fetched += 1
            else: print(f"  W {ticker}/{name}: HTTP {r.status_code}")
        except Exception as e: print(f"  X {ticker}/{name}: {e}")
    return fetched

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--min-cap", type=float, default=800e6)
    parser.add_argument("--max-cap", type=float, default=10e9)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    uf = Path("smallcap_universe.json")
    tf = Path("smallcap_tickers.txt")

    if args.skip_fetch and uf.exists():
        tickers = json.load(open(uf))["tickers"]
        print(f"Loaded {len(tickers)} from {uf}")
    else:
        stocks = fetch_universe(args.min_cap, args.max_cap)
        tickers = [s["symbol"] for s in stocks]
        json.dump({"min_cap":args.min_cap,"max_cap":args.max_cap,"count":len(stocks),
                    "tickers":tickers,"details":stocks}, open(uf,"w"), indent=2)
        open(tf,"w").write("\n".join(tickers))
        print(f"\nSaved {len(tickers)} tickers")
        sectors = {}
        for s in stocks:
            sec = s.get("sector","Unknown"); sectors[sec] = sectors.get(sec,0)+1
        for sec, cnt in sorted(sectors.items(), key=lambda x:-x[1]):
            print(f"  {sec:<30} {cnt:>4}")

    if args.list_only:
        print(f"\nTickers: {', '.join(tickers[:30])}...")
        return

    print(f"\nFETCHING DATA FOR {len(tickers)} TICKERS (~{len(tickers)*5*DELAY/60:.0f} min)")
    total = 0
    for i, t in enumerate(tickers):
        cached = all((CACHE_DIR/f"{t}_{s}.json").exists() for s in ["profile","income","cashflow","balance","metrics"])
        if cached and not args.refresh:
            if i % 50 == 0: print(f"  [{i+1}/{len(tickers)}] cached through here...")
            continue
        print(f"  [{i+1}/{len(tickers)}] {t}...", end="", flush=True)
        n = fetch_ticker_data(t, force=args.refresh); total += n; print(f" {n}")
    print(f"\nDone. {total} new endpoints fetched.")

if __name__ == "__main__": main()
