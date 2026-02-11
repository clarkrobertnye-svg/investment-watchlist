#!/usr/bin/env python3
"""
Supplemental ROE fetch — 101 missing tickers from Capital Compounders Universe.
Merges results into existing cache/exports/roe_data.json.

Run from: ~/Documents/capital_compounders/
Command:  python3 fetch_roe_supplemental.py
"""

import json, os, time, urllib.request, urllib.error
from datetime import datetime

FMP_API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"
BASE = "https://financialmodelingprep.com/stable"

TICKERS = [
    "ASIC","COKE","LRN","CROX","PLMR","IESC","HGTY","MA","COCO","MEDP",
    "IDT","MATX","KLAC","HLNE","CPRX","DDS","LOGI","NVMI","LULU","LMB",
    "NVR","AMPH","FIX","BKNG","HALO","EAT","ESQ","APH","ASML","AAPL",
    "LYV","NSSC","BLD","BLBD","SKY","IBP","NYT","DECK","LII","CSW",
    "POWL","CAT","XPEL","TT","CVCO","IT","CSL","CCB","CRUS","BMI",
    "VRSK","MSFT","LQDT","PH","MORN","TXRH","ALRM","IPAR","BAH","AMG",
    "OZK","CTAS","NTES","IRMD","ASO","KFY","AX","PRI","NMIH","HRMY",
    "GOLF","PRDO","WTS","ROL","MSA","RMD","BRC","NVS","MWA","FBK",
    "FSS","KAI","FELE","DAVE","APP","CELH","AVGO","CARG","ATEN","CDNS",
    "GOOGL","GMAB","YETI","EXLS","EBAY","QCOM","PIPR","OFG","FFIV","MNR",
    "SYF"
]

def fetch_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

def get_roe(ticker):
    """Compute ROE from income-statement + balance-sheet via stable API."""
    inc_url = f"{BASE}/income-statement?symbol={ticker}&apikey={FMP_API_KEY}"
    bs_url  = f"{BASE}/balance-sheet-statement?symbol={ticker}&apikey={FMP_API_KEY}"
    
    inc = fetch_json(inc_url)
    bs  = fetch_json(bs_url)
    
    if not inc or not bs:
        return None
    
    # Build year→data maps
    inc_map = {}
    for row in inc:
        yr = row.get("calendarYear") or row.get("date","")[:4]
        if yr: inc_map[yr] = row
    
    bs_map = {}
    for row in bs:
        yr = row.get("calendarYear") or row.get("date","")[:4]
        if yr: bs_map[yr] = row
    
    years = sorted(set(inc_map.keys()) & set(bs_map.keys()), reverse=True)[:6]
    
    roe_annual = {}
    equity_negative = False
    
    for yr in years:
        ni = inc_map[yr].get("netIncome", 0)
        eq = bs_map[yr].get("totalStockholdersEquity", 0)
        if eq and eq != 0:
            roe = round((ni / eq) * 100, 2)
            if eq < 0:
                equity_negative = True
            roe_annual[yr] = roe
        elif eq == 0 or eq is None:
            equity_negative = True
    
    if not roe_annual:
        return None
    
    sorted_years = sorted(roe_annual.keys(), reverse=True)
    roe_current = roe_annual[sorted_years[0]]
    
    # 5yr avg (exclude extreme negative-equity distortions)
    vals = [roe_annual[y] for y in sorted_years[:5] if abs(roe_annual[y]) < 500]
    roe_5yr_avg = round(sum(vals) / len(vals), 2) if vals else roe_current
    
    return {
        "ticker": ticker,
        "roe_current": roe_current,
        "roe_5yr_avg": roe_5yr_avg,
        "roe_annual": {y: roe_annual[y] for y in sorted_years[:5]},
        "equity_negative": equity_negative
    }

def main():
    out_path = os.path.join("cache", "exports", "roe_data.json")
    
    # Load existing data
    if os.path.exists(out_path):
        with open(out_path) as f:
            existing = json.load(f)
        data = existing.get("data", {})
        print(f"Loaded existing ROE data: {len(data)} tickers")
    else:
        data = {}
        print("No existing file found, starting fresh")
    
    errors = []
    new_count = 0
    
    for i, ticker in enumerate(TICKERS, 1):
        if ticker in data:
            print(f"  [{i}/{len(TICKERS)}] {ticker} — already in cache, skipping")
            continue
        
        try:
            result = get_roe(ticker)
            if result:
                data[ticker] = result
                new_count += 1
                print(f"  [{i}/{len(TICKERS)}] {ticker} — ROE: {result['roe_current']:.1f}% (5yr: {result['roe_5yr_avg']:.1f}%)"
                      + (" ⚠️ NEG_EQ" if result['equity_negative'] else ""))
            else:
                errors.append(ticker)
                print(f"  [{i}/{len(TICKERS)}] {ticker} — no data")
        except Exception as e:
            errors.append(ticker)
            print(f"  [{i}/{len(TICKERS)}] {ticker} — ERROR: {e}")
        
        time.sleep(0.15)
    
    # Save merged output
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    output = {
        "generated_at": datetime.now().isoformat(),
        "ticker_count": len(data),
        "errors": errors,
        "data": dict(sorted(data.items()))
    }
    
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Done! {new_count} new tickers fetched, {len(data)} total in {out_path}")
    if errors:
        print(f"⚠️  Errors ({len(errors)}): {', '.join(errors)}")

if __name__ == "__main__":
    main()
