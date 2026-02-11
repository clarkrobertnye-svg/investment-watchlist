#!/usr/bin/env python3
"""
Fetch CapEx/Revenue and Gross Margin Trend for 72 Buffett Compounders
Run from: ~/Documents/capital_compounders/
Uses FMP stable API
"""

import json, time, urllib.request, os

API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"
BASE = "https://financialmodelingprep.com/stable"

TICKERS = [
    "AAPL","ADBE","ADP","AMG","ANET","APH","ASML","ASO","AX","AXP",
    "BAH","BKNG","BLD","BMI","BRC","CAT","COCO","COKE","CROX","CRUS",
    "CSL","CTAS","CVCO","DDS","DECK","EME","ERIE","FIX","GMAB","HALO",
    "HUBB","IBP","IDCC","IDT","IESC","IPAR","IT","ITT","KLAC","LII",
    "LOGI","LULU","MA","MATX","MEDP","MSFT","NEU","NSSC","NTES","NVDA",
    "NVMI","NVR","NVS","POOL","POWL","PRDO","PRI","QCOM","RLI","RMD",
    "ROL","SKY","SYF","TT","UFPI","ULTA","V","VRSK","WSM","WSO","WTS","XPEL"
]

def fetch_json(url):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return None

results = {}

for i, t in enumerate(TICKERS):
    print(f"[{i+1}/72] {t}...", end=" ", flush=True)
    
    # Fetch income statement (5 years) for revenue and gross profit
    url_inc = f"{BASE}/income-statement?symbol={t}&period=annual&limit=6&apikey={API_KEY}"
    inc = fetch_json(url_inc)
    
    # Fetch cash flow statement for capex
    url_cf = f"{BASE}/cash-flow-statement?symbol={t}&period=annual&limit=6&apikey={API_KEY}"
    cf = fetch_json(url_cf)
    
    if not inc or not cf:
        print("SKIP (no data)")
        continue
    
    # Sort by year descending
    inc.sort(key=lambda x: x.get('calendarYear', '0'), reverse=True)
    cf.sort(key=lambda x: x.get('calendarYear', '0'), reverse=True)
    
    # CapEx/Rev for most recent year
    rev_now = inc[0].get('revenue', 0) if inc else 0
    capex_now = abs(cf[0].get('capitalExpenditure', 0)) if cf else 0
    capex_rev = (capex_now / rev_now * 100) if rev_now else None
    
    # 5yr avg CapEx/Rev
    capex_revs = []
    for j in range(min(5, len(inc), len(cf))):
        r = inc[j].get('revenue', 0)
        c = abs(cf[j].get('capitalExpenditure', 0))
        if r > 0:
            capex_revs.append(c / r * 100)
    capex_rev_avg = sum(capex_revs) / len(capex_revs) if capex_revs else None
    
    # GM trend: collect 5 years of gross margins
    gm_years = []
    for entry in inc[:6]:
        r = entry.get('revenue', 0)
        gp = entry.get('grossProfit', 0)
        yr = entry.get('calendarYear', '?')
        if r > 0:
            gm_years.append({'year': yr, 'gm': gp / r * 100})
    
    # GM trend: newest vs oldest (5yr change)
    gm_now = gm_years[0]['gm'] if gm_years else None
    gm_old = gm_years[-1]['gm'] if len(gm_years) >= 4 else None
    gm_delta = (gm_now - gm_old) if (gm_now is not None and gm_old is not None) else None
    
    # GM trend direction
    if gm_delta is not None:
        if gm_delta > 3:
            gm_trend = "EXPANDING"
        elif gm_delta < -3:
            gm_trend = "ERODING"
        else:
            gm_trend = "STABLE"
    else:
        gm_trend = "N/A"
    
    results[t] = {
        'capex_rev': round(capex_rev, 1) if capex_rev else None,
        'capex_rev_avg': round(capex_rev_avg, 1) if capex_rev_avg else None,
        'gm_now': round(gm_now, 1) if gm_now else None,
        'gm_old': round(gm_old, 1) if gm_old else None,
        'gm_delta': round(gm_delta, 1) if gm_delta else None,
        'gm_trend': gm_trend,
        'gm_years': gm_years,
    }
    
    tag = f"CapEx/Rev {capex_rev:.1f}% (avg {capex_rev_avg:.1f}%)" if capex_rev else "no data"
    gm_tag = f"GM {gm_now:.1f}% → Δ{gm_delta:+.1f}pp ({gm_trend})" if gm_delta else "no GM data"
    print(f"{tag} | {gm_tag}")
    
    time.sleep(0.3)

# Save results
os.makedirs('cache/exports', exist_ok=True)
with open('cache/exports/capex_gm_data.json', 'w') as f:
    json.dump(results, f, indent=2)

# ============================================================
# ANALYSIS REPORT
# ============================================================
print("\n" + "=" * 110)
print("CAPEX/REVENUE ANALYSIS — 72 Buffett Compounders")
print("=" * 110)
print(f"\n{'Ticker':<7} {'CapEx/Rev':>9} {'5yr Avg':>8} {'Category':<15} {'GM Now':>7} {'GM Δ5yr':>8} {'GM Trend':<12}")
print("-" * 110)

sorted_results = sorted(results.items(), key=lambda x: x[1].get('capex_rev_avg') or 99)
for t, d in sorted_results:
    cr = f"{d['capex_rev']:.1f}%" if d['capex_rev'] else "—"
    cra = f"{d['capex_rev_avg']:.1f}%" if d['capex_rev_avg'] else "—"
    
    avg = d['capex_rev_avg'] or 0
    if avg <= 5:
        cat = "ASSET-LIGHT"
    elif avg <= 10:
        cat = "MODERATE"
    elif avg <= 15:
        cat = "MOD-HEAVY"
    else:
        cat = "CAPITAL-HEAVY"
    
    gm = f"{d['gm_now']:.1f}%" if d['gm_now'] else "—"
    gmd = f"{d['gm_delta']:+.1f}pp" if d['gm_delta'] is not None else "—"
    
    flag = ""
    if avg > 15:
        flag = " ⚠️ HEAVY"
    if d['gm_trend'] == "ERODING":
        flag += " 🔴 ERODING GM"
    
    print(f"  {t:<7} {cr:>9} {cra:>8} {cat:<15} {gm:>7} {gmd:>8} {d['gm_trend']:<12}{flag}")

# Summary
print(f"\n{'=' * 110}")
print("SUMMARY")
print(f"{'=' * 110}")

light = sum(1 for _,d in results.items() if (d.get('capex_rev_avg') or 0) <= 5)
moderate = sum(1 for _,d in results.items() if 5 < (d.get('capex_rev_avg') or 0) <= 10)
mod_heavy = sum(1 for _,d in results.items() if 10 < (d.get('capex_rev_avg') or 0) <= 15)
heavy = sum(1 for _,d in results.items() if (d.get('capex_rev_avg') or 0) > 15)

print(f"  Asset-Light (≤5%):     {light}")
print(f"  Moderate (5-10%):      {moderate}")
print(f"  Mod-Heavy (10-15%):    {mod_heavy}")
print(f"  Capital-Heavy (>15%):  {heavy}")

expanding = sum(1 for _,d in results.items() if d['gm_trend'] == 'EXPANDING')
stable = sum(1 for _,d in results.items() if d['gm_trend'] == 'STABLE')
eroding = sum(1 for _,d in results.items() if d['gm_trend'] == 'ERODING')

print(f"\n  GM Expanding (>+3pp):   {expanding}")
print(f"  GM Stable (±3pp):       {stable}")
print(f"  GM Eroding (<-3pp):     {eroding}")

if heavy > 0:
    print(f"\n  ⚠️  Capital-Heavy tickers (potential Buffett 5f failures):")
    for t, d in sorted_results:
        if (d.get('capex_rev_avg') or 0) > 15:
            print(f"     {t}: {d['capex_rev_avg']:.1f}% avg CapEx/Rev")

if eroding > 0:
    print(f"\n  🔴 Eroding GM tickers (moat deterioration signal):")
    for t, d in sorted_results:
        if d['gm_trend'] == 'ERODING':
            print(f"     {t}: GM {d['gm_now']:.1f}% (was {d['gm_old']:.1f}%, Δ{d['gm_delta']:+.1f}pp)")

print(f"\n✅ Data saved to cache/exports/capex_gm_data.json")
