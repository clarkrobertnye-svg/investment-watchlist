#!/usr/bin/env python3
"""Compare 3 Invested Capital methods on AZO, MA, GOOGL, AAPL."""

import json, time
from urllib.request import urlopen, Request

API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"
BASE = "https://financialmodelingprep.com/stable"

def fetch(url):
    time.sleep(0.3)
    req = Request(url, headers={"User-Agent": "diag/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

def fmt(val):
    if val is None:
        return "   N/A    "
    return f"${val/1e9:>9.2f}B"

for sym in ["AZO", "MA", "GOOGL", "AAPL"]:
    bs_list = fetch(f"{BASE}/balance-sheet-statement?symbol={sym}&limit=4&apikey={API_KEY}")
    inc_list = fetch(f"{BASE}/income-statement?symbol={sym}&limit=4&apikey={API_KEY}")
    bs_list.sort(key=lambda x: x.get("date",""), reverse=True)
    inc_list.sort(key=lambda x: x.get("date",""), reverse=True)
    
    print(f"\n{'='*95}")
    print(f"  {sym} — 3 INVESTED CAPITAL METHODS")
    print(f"{'='*95}")
    
    # Show raw fields first
    print(f"\n  {'Field':<40} ", end="")
    for b in bs_list[:4]:
        print(f"{b.get('date','?'):>14}", end="")
    print()
    print(f"  {'-'*40} ", end="")
    for _ in bs_list[:4]:
        print(f"{'':->14}", end="")
    print()
    
    raw_fields = [
        ("totalCurrentAssets", "Current Assets"),
        ("cashAndCashEquivalents", "  Cash & Equiv"),
        ("shortTermInvestments", "  Short Term Investments"),
        ("otherCurrentAssets", "  Other Current Assets"),
        ("totalCurrentLiabilities", "Current Liabilities"),
        ("shortTermDebt", "  Short Term Debt"),
        ("currentPortionOfLongTermDebt", "  Current Portion LTD"),
        ("propertyPlantEquipmentNet", "PP&E Net"),
        ("goodwill", "Goodwill"),
        ("intangibleAssets", "Intangible Assets"),
        ("goodwillAndIntangibleAssets", "Goodwill & Intangibles"),
        ("capitalLeaseObligations", "Capital Lease Obligations"),
        ("operatingLeaseObligations", "Operating Lease Oblig"),
        ("totalDebt", "Total Debt"),
        ("longTermDebt", "Long Term Debt"),
        ("totalStockholdersEquity", "Total Equity"),
        ("netDebt", "Net Debt"),
        ("totalAssets", "Total Assets"),
        ("totalLiabilities", "Total Liabilities"),
    ]
    
    for field, label in raw_fields:
        print(f"  {label:<40} ", end="")
        for b in bs_list[:4]:
            val = b.get(field)
            if val is not None and val != 0:
                print(f"  {val/1e9:>10.2f}B", end="")
            elif val == 0:
                print(f"  {'0':>10}B", end="")
            else:
                print(f"  {'---':>10} ", end="")
            
        print()
    
    # Calculate 3 methods for each year
    print(f"\n  {'IC METHOD':<40} ", end="")
    for b in bs_list[:4]:
        print(f"{b.get('date','?'):>14}", end="")
    print()
    print(f"  {'='*40} ", end="")
    for _ in bs_list[:4]:
        print(f"{'':=<14}", end="")
    print()
    
    ic_methods = {1: [], 2: [], 3: []}
    nopats = []
    
    for i, b in enumerate(bs_list[:4]):
        # Pull values
        tca = b.get("totalCurrentAssets", 0) or 0
        cash = b.get("cashAndCashEquivalents", 0) or 0
        sti = b.get("shortTermInvestments", 0) or 0
        tcl = b.get("totalCurrentLiabilities", 0) or 0
        std = b.get("shortTermDebt", 0) or 0
        cpltd = b.get("currentPortionOfLongTermDebt", 0) or 0
        ppe = b.get("propertyPlantEquipmentNet", 0) or 0
        gw = b.get("goodwill", 0) or 0
        intang = b.get("intangibleAssets", 0) or 0
        gw_intang = b.get("goodwillAndIntangibleAssets", 0) or 0
        total_debt = b.get("totalDebt", 0) or 0
        equity = b.get("totalStockholdersEquity", 0) or 0
        cap_lease = b.get("capitalLeaseObligations", 0) or 0
        op_lease = b.get("operatingLeaseObligations", 0) or 0
        
        # Interest-bearing current debt = short term debt + current portion of LTD
        ibd = std + cpltd
        # If shortTermDebt already includes cpltd, just use std
        # FMP's shortTermDebt field varies; use the larger of std alone or ibd
        
        # Goodwill & intangibles: use combined field if available, else sum
        gi = gw_intang if gw_intang > 0 else (gw + intang)
        
        # Net working capital (operating)
        nwc = tca - cash - sti - tcl + ibd
        
        # NOPAT
        if i < len(inc_list):
            inc = inc_list[i]
            op_inc = inc.get("operatingIncome", 0) or 0
            tax = inc.get("incomeTaxExpense", 0) or 0
            pretax = inc.get("incomeBeforeTax", 0) or 0
            eff_tax = tax/pretax if pretax > 0 and tax >= 0 else 0.21
            nopat = op_inc * (1 - eff_tax)
        else:
            nopat = 0
        nopats.append(nopat)
        
        # === METHOD 1: NWC + PP&E + Goodwill & Intangibles ===
        ic1 = nwc + ppe + gi
        
        # === METHOD 2: Total Debt + Equity + Leases - Cash ===
        leases = op_lease  # operating lease obligations
        ic2 = total_debt + equity + leases - cash
        
        # === METHOD 3: (CA - Cash) - (CL - IBD) + Net Fixed Assets ===
        ic3 = (tca - cash) - (tcl - ibd) + ppe
        
        ic_methods[1].append(ic1)
        ic_methods[2].append(ic2)
        ic_methods[3].append(ic3)
    
    labels = {
        1: "M1: NWC + PP&E + GW&Intang",
        2: "M2: Debt + Equity + Leases - Cash",
        3: "M3: (CA-Cash)-(CL-IBD) + PP&E",
    }
    
    for m in [1, 2, 3]:
        print(f"  {labels[m]:<40} ", end="")
        for val in ic_methods[m]:
            print(f"  {val/1e9:>10.2f}B", end="")
        print()
    
    # ROIC for each method
    print()
    for m in [1, 2, 3]:
        print(f"  ROIC ({labels[m][:20]}...)  ", end="")
        for i, val in enumerate(ic_methods[m]):
            if val > 0 and i < len(nopats):
                roic = nopats[i] / val * 100
                print(f"  {roic:>9.1f}%", end="")
            elif val <= 0:
                print(f"  {'NEG IC':>10}", end="")
            else:
                print(f"  {'---':>10} ", end="")
        print()
    
    # 3yr cumulative ROIIC for each method
    if len(nopats) >= 4:
        print(f"\n  3yr Cumulative ROIIC & Power:")
        for m in [1, 2, 3]:
            ics = ic_methods[m]
            delta_nopat = nopats[0] - nopats[3]
            delta_ic = ics[0] - ics[3]
            total_nopat = sum(nopats[:3])
            
            if delta_ic > 0 and total_nopat > 0:
                roiic = delta_nopat / delta_ic
                reinv = delta_ic / total_nopat
                power = roiic * reinv
                print(f"    {labels[m][:35]:<38} ROIIC={roiic*100:>7.1f}%  Reinv={reinv*100:>6.1f}%  Power={power*100:>6.1f}%")
            elif delta_ic <= 0:
                reinv = delta_ic / total_nopat if total_nopat > 0 else 0
                print(f"    {labels[m][:35]:<38} ΔIC={delta_ic/1e9:>+.2f}B (shrinking)  Reinv={reinv*100:>6.1f}%")
            else:
                print(f"    {labels[m][:35]:<38} Insufficient data")
    
    # Buyback context
    cf_list = fetch(f"{BASE}/cash-flow-statement?symbol={sym}&limit=4&apikey={API_KEY}")
    cf_list.sort(key=lambda x: x.get("date",""), reverse=True)
    
    total_bb = sum(abs(c.get("commonStockRepurchased", 0) or 0) for c in cf_list[:3])
    total_div = sum(abs(c.get("dividendsPaid", 0) or 0) for c in cf_list[:3])
    total_nopat_3yr = sum(nopats[:3])
    
    print(f"\n  3yr Capital Return:")
    print(f"    Total Buybacks:   ${total_bb/1e9:.2f}B")
    print(f"    Total Dividends:  ${total_div/1e9:.2f}B")
    print(f"    Total NOPAT:      ${total_nopat_3yr/1e9:.2f}B")
    if total_nopat_3yr > 0:
        print(f"    Buyback Intensity:{total_bb/total_nopat_3yr*100:>6.1f}%")
        print(f"    Total Return %:   {(total_bb+total_div)/total_nopat_3yr*100:>6.1f}%")

print("\n\nDone.")
