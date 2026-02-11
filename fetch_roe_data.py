#!/usr/bin/env python3
"""
Fetch ROE (current + 5yr avg) for Capital Compounders universe.
Uses FMP stable API. Computes ROE = Net Income / Stockholders Equity.
Run from ~/Documents/capital_compounders/
Output: cache/exports/roe_data.json
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

FMP_API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"
BASE_URL = "https://financialmodelingprep.com/stable"
CACHE_DIR = Path("cache/exports")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

UNIVERSE = [
    "ACGL","ACIW","ACT","ADBE","ADP","AEHR","AFG","AJG","ANET","APPF",
    "ARES","AXP","BFAM","BRO","BX","CACC","CASH","CASY","CB","CINF",
    "CME","CNA","COHR","COIN","CPRT","CRM","CSWI","DHR","DLB","DKNG",
    "DOCU","DSGX","EFX","EME","ENSG","EQIX","ERIE","EVR","FCNCA",
    "FI","FICO","FIS","FLR","FNF","FTNT","GDDY","GPN","GWW","HIG",
    "HLI","HSC","HUBB","HWKN","ICE","IDCC","INTU","ISRG","ITT","KNSL",
    "KVYO","MANH","MCO","MELI","MNDY","MPWR","MSCI","MSTR","MYE","NEU",
    "NOW","NSP","NVDA","ODFL","ORI","ORLY","PAYC","PGR","PINS","PLTR",
    "PNFP","POOL","PSA","PSTG","RGA","RLI","RNR","RPM","RS","RYAN",
    "S","SAIA","SFM","SPGI","TDG","TOST","TPG","TPL","TRV","TSCO",
    "TW","UFPI","UHAL","ULTA","UNM","USFD","V","VIRT","VRNS","WCC",
    "WRB","WSM","WSO","WTW","ZS"
]

def api_get(endpoint):
    url = f"{BASE_URL}/{endpoint}"
    sep = "&" if "?" in endpoint else "?"
    url += f"{sep}apikey={FMP_API_KEY}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            print(" rate limited, waiting 5s...", end="")
            time.sleep(5)
            return api_get(endpoint)
        else:
            return None
    except:
        return None

def fetch_roe(ticker):
    result = {"ticker": ticker, "roe_current": None, "roe_5yr_avg": None, "roe_annual": {}, "equity_negative": False}

    inc = api_get(f"income-statement?symbol={ticker}&period=annual&limit=5")
    bs = api_get(f"balance-sheet-statement?symbol={ticker}&period=annual&limit=5")

    if not inc or not bs:
        return result

    roe_values = []
    for i in range(min(len(inc), len(bs))):
        ni = inc[i].get("netIncome")
        eq = bs[i].get("totalStockholdersEquity")
        year = str(inc[i].get("calendarYear", inc[i].get("date", "?")[:4]))

        if ni is not None and eq is not None and eq != 0:
            roe = round(ni / eq * 100, 2)
            result["roe_annual"][year] = roe
            if eq < 0:
                result["equity_negative"] = True
            if -200 < roe < 500:
                roe_values.append(roe)
            else:
                result["equity_negative"] = True

    if roe_values:
        result["roe_current"] = roe_values[0]
        result["roe_5yr_avg"] = round(sum(roe_values) / len(roe_values), 2)

    return result

def main():
    universe = sorted(set(UNIVERSE))
    print(f"Fetching ROE for {len(universe)} tickers (2 calls each)...")
    print(f"Total API calls: {len(universe) * 2}\n")

    results = {}
    errors = []

    for i, ticker in enumerate(universe):
        print(f"  [{i+1}/{len(universe)}] {ticker}...", end=" ", flush=True)
        data = fetch_roe(ticker)
        results[ticker] = data

        if data["roe_current"] is not None:
            flag = " NEG_EQ" if data["equity_negative"] else ""
            avg = f"{data['roe_5yr_avg']:.1f}%" if data["roe_5yr_avg"] else "N/A"
            print(f"ROE: {data['roe_current']:.1f}% | 5yr: {avg}{flag}")
        else:
            print("NO DATA")
            errors.append(ticker)

    output = {"generated_at": datetime.now().isoformat(), "ticker_count": len(results), "errors": errors, "data": results}
    out_path = CACHE_DIR / "roe_data.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDone! Saved to {out_path}")
    print(f"  {len(results) - len(errors)} success, {len(errors)} errors")

    valid = [r["roe_current"] for r in results.values() if r["roe_current"] and not r["equity_negative"]]
    if valid:
        valid.sort()
        print(f"\n  ROE Current -- Median: {valid[len(valid)//2]:.1f}% | Mean: {sum(valid)/len(valid):.1f}% | Range: {valid[0]:.1f}% to {valid[-1]:.1f}%")

    neg = [t for t, r in results.items() if r["equity_negative"]]
    if neg:
        print(f"  Negative equity: {', '.join(neg)}")

if __name__ == "__main__":
    main()
