#!/usr/bin/env python3
"""Pull FCF/Net Debt from test9_data.json"""
import json, os

with open(os.path.expanduser("~/Documents/capital_compounders/test9_data.json")) as f:
    data = json.load(f)

print(f"\n{'Sym':<6} {'FCF':>10} {'NetDebt':>12} {'EBITDA':>10} {'FCF/ND':>8} {'ND/EBITDA':>10} {'Note'}")
print("-" * 70)

for s in sorted(data, key=lambda x: x.get("total_value_creation",0), reverse=True):
    sym = s["symbol"]
    # Need to get raw numbers - they're not stored directly, re-derive
    # Actually let's just re-pull from the years data... but that's nested.
    # The json has netDebt_EBITDA but not raw values. Quick re-calc:
    pass

# Need raw data - pull fresh for just this calculation
import time
from urllib.request import urlopen, Request

API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"
BASE = "https://financialmodelingprep.com/stable"

def fetch(url):
    time.sleep(0.3)
    req = Request(url, headers={"User-Agent": "diag/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

print(f"\n{'Sym':<6} {'Trail FCF':>12} {'Net Debt':>12} {'EBITDA':>12} {'FCF/ND':>10} {'ND/EBITDA':>10} {'Yrs to Delev':>13}")
print("-" * 82)

for sym in ["NVDA", "MA", "AAPL", "GOOGL", "V", "ADP", "AZO", "CLS", "MOD"]:
    bs = fetch(f"{BASE}/balance-sheet-statement?symbol={sym}&limit=1&apikey={API_KEY}")
    inc = fetch(f"{BASE}/income-statement?symbol={sym}&limit=1&apikey={API_KEY}")
    cf = fetch(f"{BASE}/cash-flow-statement?symbol={sym}&limit=1&apikey={API_KEY}")
    
    b, i, c = bs[0], inc[0], cf[0]
    
    total_debt = b.get("totalDebt",0) or 0
    cash = b.get("cashAndCashEquivalents",0) or 0
    sti = b.get("shortTermInvestments",0) or 0
    net_debt = total_debt - cash - sti
    
    ebitda = i.get("ebitda",0) or 0
    op_cf = c.get("operatingCashFlow",0) or 0
    capex = abs(c.get("capitalExpenditure",0) or 0)
    fcf = op_cf - capex
    
    if net_debt > 0:
        fcf_nd = fcf / net_debt
        nd_ebitda = net_debt / ebitda if ebitda > 0 else 0
        yrs = net_debt / fcf if fcf > 0 else 999
        note = f"{yrs:.1f} yrs"
        print(f"{sym:<6} ${fcf/1e9:>10.1f}B ${net_debt/1e9:>10.1f}B ${ebitda/1e9:>10.1f}B {fcf_nd*100:>9.1f}% {nd_ebitda:>9.1f}x {note:>13}")
    else:
        nd_ebitda = net_debt / ebitda if ebitda > 0 else 0
        print(f"{sym:<6} ${fcf/1e9:>10.1f}B ${net_debt/1e9:>10.1f}B ${ebitda/1e9:>10.1f}B {'NET CASH':>10} {nd_ebitda:>9.1f}x {'N/A':>13}")

print()
