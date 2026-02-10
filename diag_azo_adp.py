#!/usr/bin/env python3
"""Quick diagnostic: show raw yearly data for AZO and ADP to find the issue."""

import json
import os

DATA_PATH = os.path.expanduser("~/Documents/capital_compounders/test7_data.json")

with open(DATA_PATH) as f:
    data = json.load(f)

for stock in data:
    if stock["symbol"] not in ("AZO", "ADP"):
        continue
    
    print(f"\n{'='*80}")
    print(f"  {stock['symbol']} — {stock.get('companyName','')}")
    print(f"{'='*80}")
    print(f"  3yr avg ROIC:     {stock.get('avg3yr_ROIC',0)*100:.1f}%")
    print(f"  3yr cum ROIIC:    {stock.get('cum3yr_ROIIC','N/A')}")
    if stock.get('cum3yr_ROIIC'):
        print(f"                    {stock['cum3yr_ROIIC']*100:.1f}%")
    print(f"  3yr cum ReinvRate:{stock.get('cum3yr_ReinvRate','N/A')}")
    if stock.get('cum3yr_ReinvRate'):
        print(f"                    {stock['cum3yr_ReinvRate']*100:.1f}%")
    print(f"  3yr cum Power:    {stock.get('cum3yr_Power','N/A')}")
    if stock.get('cum3yr_Power'):
        print(f"                    {stock['cum3yr_Power']*100:.1f}%")
    print(f"  IC shrinking:     {stock.get('ic_shrinking', False)}")
    print(f"  Path:             {stock.get('path','?')}")
    print(f"  FCF/sh CAGR 5yr:  {stock.get('fcf_share_cagr_5yr','N/A')}")
    if stock.get('fcf_share_cagr_5yr'):
        print(f"                    {stock['fcf_share_cagr_5yr']*100:.1f}%")
    
    # Show yearly breakdown
    # Reconstruct from the raw data we saved
    # The years data isn't in the JSON directly, so let's re-pull it
    print(f"\n  Need raw financial data — re-pulling from FMP...")

print("\n\nNow pulling raw financials for detailed breakdown...\n")

import time
from urllib.request import urlopen, Request

API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"
BASE = "https://financialmodelingprep.com/stable"

def fetch(url):
    time.sleep(0.3)
    req = Request(url, headers={"User-Agent": "diag/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

for sym in ["AZO", "ADP"]:
    inc = fetch(f"{BASE}/income-statement?symbol={sym}&limit=6&apikey={API_KEY}")
    bs = fetch(f"{BASE}/balance-sheet-statement?symbol={sym}&limit=6&apikey={API_KEY}")
    cf = fetch(f"{BASE}/cash-flow-statement?symbol={sym}&limit=6&apikey={API_KEY}")
    
    inc.sort(key=lambda x: x.get("date",""), reverse=True)
    bs.sort(key=lambda x: x.get("date",""), reverse=True)
    cf.sort(key=lambda x: x.get("date",""), reverse=True)
    
    print(f"\n{'='*90}")
    print(f"  {sym} — YEAR BY YEAR BREAKDOWN")
    print(f"{'='*90}")
    
    print(f"\n  {'Date':<12} {'Revenue':>12} {'OpInc':>12} {'NOPAT':>12} {'NetInc':>12} {'FCF':>12} {'Shares':>12}")
    print(f"  {'-'*84}")
    
    for i in range(min(len(inc), len(cf), 6)):
        d = inc[i]
        c = cf[i]
        rev = d.get("revenue",0) or 0
        op_inc = d.get("operatingIncome",0) or 0
        tax = d.get("incomeTaxExpense",0) or 0
        pretax = d.get("incomeBeforeTax",0) or 0
        eff_tax = tax/pretax if pretax > 0 and tax >= 0 else 0.21
        nopat = op_inc * (1 - eff_tax)
        ni = d.get("netIncome",0) or 0
        op_cf = c.get("operatingCashFlow",0) or 0
        capex = abs(c.get("capitalExpenditure",0) or 0)
        fcf = op_cf - capex
        shares = d.get("weightedAverageShsOutDil",0) or 0
        
        print(f"  {d.get('date','?'):<12} ${rev/1e9:>10.2f}B ${op_inc/1e9:>10.2f}B ${nopat/1e9:>10.2f}B ${ni/1e9:>10.2f}B ${fcf/1e9:>10.2f}B {shares/1e6:>10.1f}M")
    
    print(f"\n  {'Date':<12} {'Equity':>12} {'TotalDebt':>12} {'Cash':>12} {'IC':>14} {'ROIC':>8}")
    print(f"  {'-'*72}")
    
    ics = []
    nopats = []
    for i in range(min(len(inc), len(bs), 6)):
        d = inc[i]
        b = bs[i]
        
        equity = b.get("totalStockholdersEquity",0) or 0
        total_debt = b.get("totalDebt",0) or 0
        if total_debt == 0:
            total_debt = (b.get("shortTermDebt",0) or 0) + (b.get("longTermDebt",0) or 0)
        cash = b.get("cashAndCashEquivalents",0) or 0
        ic = equity + total_debt - cash
        
        op_inc = d.get("operatingIncome",0) or 0
        tax = d.get("incomeTaxExpense",0) or 0
        pretax = d.get("incomeBeforeTax",0) or 0
        eff_tax = tax/pretax if pretax > 0 and tax >= 0 else 0.21
        nopat = op_inc * (1 - eff_tax)
        
        roic = nopat / ic * 100 if ic > 0 else float('inf')
        roic_str = f"{roic:.1f}%" if ic > 0 else "INF (IC≤0)"
        
        print(f"  {b.get('date','?'):<12} ${equity/1e9:>10.2f}B ${total_debt/1e9:>10.2f}B ${cash/1e9:>10.2f}B ${ic/1e9:>12.2f}B {roic_str:>8}")
        ics.append(ic)
        nopats.append(nopat)
    
    # Show the 3yr calc
    if len(ics) >= 4 and len(nopats) >= 4:
        delta_ic = ics[0] - ics[3]
        delta_nopat = nopats[0] - nopats[3]
        total_nopat_3yr = sum(nopats[:3])
        cum_reinv = delta_ic / total_nopat_3yr if total_nopat_3yr > 0 else 0
        cum_roiic = delta_nopat / delta_ic if delta_ic > 0 else None
        
        print(f"\n  3yr Cumulative Calculations:")
        print(f"    IC[0]={ics[0]/1e9:.2f}B  IC[3]={ics[3]/1e9:.2f}B  ΔIC={delta_ic/1e9:.2f}B")
        print(f"    NOPAT[0]={nopats[0]/1e9:.2f}B  NOPAT[3]={nopats[3]/1e9:.2f}B  ΔNOPAT={delta_nopat/1e9:.2f}B")
        print(f"    Total NOPAT (3yr)={total_nopat_3yr/1e9:.2f}B")
        print(f"    Cum Reinv Rate = ΔIC/Total NOPAT = {cum_reinv*100:.1f}%")
        if cum_roiic:
            print(f"    Cum ROIIC = ΔNOPAT/ΔIC = {cum_roiic*100:.1f}%")
            print(f"    Power = {cum_roiic*100:.1f}% × {cum_reinv*100:.1f}% = {cum_roiic*cum_reinv*100:.1f}%")
        elif delta_ic <= 0:
            print(f"    ΔIC ≤ 0 → IC SHRINKING → Capital-light path")
            print(f"    (Buyback path needs: ROIC≥25% + FCF/sh CAGR≥12%)")

    # Buyback analysis
    print(f"\n  Share Buyback Analysis:")
    for i in range(min(len(cf), 6)):
        c = cf[i]
        buyback = c.get("commonStockRepurchased", 0) or 0
        div = c.get("dividendsPaid", 0) or 0
        print(f"    {c.get('date','?'):<12} Buybacks: ${buyback/1e9:.2f}B  Dividends: ${div/1e9:.2f}B")

print("\nDone.")
