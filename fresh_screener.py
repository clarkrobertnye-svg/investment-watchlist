#!/usr/bin/env python3
"""
CAPITAL COMPOUNDER SCREENER - Fresh Start
Uses FMP Stable API endpoints
Saves progress so can resume if interrupted
"""

import requests
import json
import time
import os
from datetime import datetime

API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"
BASE = "https://financialmodelingprep.com/stable"

# Thresholds
MIN_MCAP = 500_000_000      # $500M
MIN_GM = 0.25               # 25%
MIN_ROIC = 0.15             # 15%
MIN_VCR = 1.5               # 1.5x
MIN_FCF_NI = 0.70           # 70%
MIN_FCF_DEBT = 0.25         # 25%
MIN_ROIIC = 0.20            # 20%

calls = 0
start_time = None

def api(endpoint, params={}):
    global calls
    params['apikey'] = API_KEY
    try:
        r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
        calls += 1
        if calls % 100 == 0:
            elapsed = (time.time() - start_time) / 60
            print(f"    [{calls} calls, {elapsed:.1f} min]")
        if r.status_code == 429:
            print("    Rate limited, waiting 60s...")
            time.sleep(60)
            return api(endpoint, params)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def save(name, data):
    with open(f"{name}.json", 'w') as f:
        json.dump(data, f, indent=2)

def load(name):
    try:
        with open(f"{name}.json") as f:
            return json.load(f)
    except:
        return None

def stage0():
    """Get all symbols"""
    print("\n" + "="*60)
    print("STAGE 0: Get all symbols")
    print("="*60)
    
    cached = load("s0_symbols")
    if cached:
        print(f"  Cached: {len(cached)} symbols")
        return cached
    
    data = api("stock-list")
    if not data:
        return []
    
    symbols = [s['symbol'] for s in data if s.get('symbol') and '.' not in s['symbol'] and '-' not in s['symbol'] and len(s['symbol']) <= 5]
    print(f"  Found {len(symbols)} symbols")
    save("s0_symbols", symbols)
    return symbols

def stage1(symbols):
    """Filter by market cap > $500M"""
    print("\n" + "="*60)
    print("STAGE 1: Market Cap > $500M")
    print("="*60)
    
    cached = load("s1_mcap")
    if cached:
        print(f"  Cached: {len(cached)} stocks")
        return cached
    
    # Load progress
    progress = load("s1_progress") or {'done': [], 'passed': []}
    done = set(progress['done'])
    passed = progress['passed']
    
    todo = [s for s in symbols if s not in done]
    print(f"  Todo: {len(todo)}, Done: {len(done)}, Passed: {len(passed)}")
    
    for i, sym in enumerate(todo):
        q = api("quote", {"symbol": sym})
        if q and len(q) > 0:
            mcap = q[0].get('marketCap', 0) or 0
            if mcap >= MIN_MCAP:
                passed.append({'symbol': sym, 'marketCap': mcap})
        
        done.add(sym)
        
        if (i+1) % 500 == 0:
            progress = {'done': list(done), 'passed': passed}
            save("s1_progress", progress)
            print(f"  {i+1}/{len(todo)}, passed: {len(passed)}")
    
    save("s1_mcap", passed)
    print(f"  PASSED: {len(passed)} stocks")
    return passed

def stage2(stocks):
    """Filter by GM > 25%, ROIC > 15%"""
    print("\n" + "="*60)
    print("STAGE 2: GM > 25%, ROIC > 15%")
    print("="*60)
    
    cached = load("s2_quality")
    if cached:
        print(f"  Cached: {len(cached)} stocks")
        return cached
    
    progress = load("s2_progress") or {'done': [], 'passed': []}
    done = set(progress['done'])
    passed = progress['passed']
    
    todo = [s for s in stocks if s['symbol'] not in done]
    print(f"  Todo: {len(todo)}, Done: {len(done)}, Passed: {len(passed)}")
    
    for i, stock in enumerate(todo):
        sym = stock['symbol']
        
        inc = api("income-statement", {"symbol": sym, "period": "annual", "limit": 1})
        bal = api("balance-sheet-statement", {"symbol": sym, "period": "annual", "limit": 1})
        
        if not inc or not bal or len(inc) == 0 or len(bal) == 0:
            done.add(sym)
            continue
        
        inc, bal = inc[0], bal[0]
        
        rev = inc.get('revenue', 0) or 0
        gp = inc.get('grossProfit', 0) or 0
        op_inc = inc.get('operatingIncome', 0) or 0
        
        assets = bal.get('totalAssets', 0) or 0
        curr_liab = bal.get('totalCurrentLiabilities', 0) or 0
        cash = bal.get('cashAndCashEquivalents', 0) or 0
        debt = bal.get('totalDebt', 0) or 0
        
        if rev <= 0 or op_inc <= 0:
            done.add(sym)
            continue
        
        gm = gp / rev
        nopat = op_inc * 0.75
        ic = assets - curr_liab - cash
        roic = nopat / ic if ic > 0 else 0
        
        if gm >= MIN_GM and roic >= MIN_ROIC:
            passed.append({
                **stock,
                'grossMargin': gm,
                'roic': roic,
                'nopat': nopat,
                'ic': ic,
                'debt': debt
            })
        
        done.add(sym)
        
        if (i+1) % 100 == 0:
            save("s2_progress", {'done': list(done), 'passed': passed})
            print(f"  {i+1}/{len(todo)}, passed: {len(passed)}")
    
    save("s2_quality", passed)
    print(f"  PASSED: {len(passed)} stocks")
    return passed

def stage3(stocks):
    """Filter by VCR > 1.5, FCF/NI > 70%, FCF/Debt > 25%"""
    print("\n" + "="*60)
    print("STAGE 3: VCR, FCF/NI, FCF/Debt")
    print("="*60)
    
    cached = load("s3_fcf")
    if cached:
        print(f"  Cached: {len(cached)} stocks")
        return cached
    
    passed = []
    
    for i, stock in enumerate(stocks):
        sym = stock['symbol']
        
        cf = api("cash-flow-statement", {"symbol": sym, "period": "annual", "limit": 1})
        if not cf or len(cf) == 0:
            continue
        
        cf = cf[0]
        ocf = cf.get('operatingCashFlow', 0) or 0
        fcf = cf.get('freeCashFlow', 0) or 0
        ni = cf.get('netIncome', 1) or 1
        
        vcr = stock['roic'] / 0.10
        fcf_ni = ocf / ni if ni > 0 else 0
        fcf_debt = fcf / stock['debt'] if stock['debt'] > 0 else 10
        
        if vcr >= MIN_VCR and fcf_ni >= MIN_FCF_NI and fcf_debt >= MIN_FCF_DEBT:
            passed.append({**stock, 'vcr': vcr, 'fcfNi': fcf_ni, 'fcfDebt': fcf_debt})
        
        if (i+1) % 50 == 0:
            print(f"  {i+1}/{len(stocks)}, passed: {len(passed)}")
    
    save("s3_fcf", passed)
    print(f"  PASSED: {len(passed)} stocks")
    return passed

def stage4(stocks):
    """Calculate ROIIC and Compounding Power"""
    print("\n" + "="*60)
    print("STAGE 4: ROIIC > 20%, Compounding Power")
    print("="*60)
    
    cached = load("s4_final")
    if cached:
        print(f"  Cached: {len(cached)} stocks")
        return cached
    
    passed = []
    
    for i, stock in enumerate(stocks):
        sym = stock['symbol']
        
        inc = api("income-statement", {"symbol": sym, "period": "annual", "limit": 5})
        bal = api("balance-sheet-statement", {"symbol": sym, "period": "annual", "limit": 5})
        cf = api("cash-flow-statement", {"symbol": sym, "period": "annual", "limit": 1})
        
        if not inc or not bal or not cf or len(inc) < 2 or len(bal) < 2:
            continue
        
        # ROIIC
        nopat_new = (inc[0].get('operatingIncome', 0) or 0) * 0.75
        nopat_old = (inc[-1].get('operatingIncome', 0) or 0) * 0.75
        
        def get_ic(b):
            return (b.get('totalAssets',0) or 0) - (b.get('totalCurrentLiabilities',0) or 0) - (b.get('cashAndCashEquivalents',0) or 0)
        
        ic_new = get_ic(bal[0])
        ic_old = get_ic(bal[-1])
        
        d_nopat = nopat_new - nopat_old
        d_ic = ic_new - ic_old
        
        roiic = d_nopat / d_ic if d_ic > 0 else (5.0 if d_nopat > 0 else 0)
        
        # Reinvestment rate
        cf0 = cf[0]
        capex = abs(cf0.get('capitalExpenditure', 0) or 0)
        depr = cf0.get('depreciationAndAmortization', 0) or 0
        dwc = -(cf0.get('changeInWorkingCapital', 0) or 0)
        acq = abs(cf0.get('acquisitionsNet', 0) or 0)
        
        reinv = capex - depr + dwc + acq
        reinv_rate = reinv / nopat_new if nopat_new > 0 else 0
        comp_power = roiic * max(reinv_rate, 0)
        
        if roiic >= MIN_ROIIC and roiic >= stock['roic']:
            passed.append({
                **stock,
                'roiic': roiic,
                'reinvRate': reinv_rate,
                'compPower': comp_power
            })
        
        if (i+1) % 25 == 0:
            print(f"  {i+1}/{len(stocks)}, passed: {len(passed)}")
    
    passed.sort(key=lambda x: x['compPower'], reverse=True)
    save("s4_final", passed)
    print(f"  PASSED: {len(passed)} stocks")
    return passed

def main():
    global start_time
    start_time = time.time()
    
    print("\n" + "="*60)
    print("  CAPITAL COMPOUNDER SCREENER")
    print("  37,000 stocks -> ~50 compounders")
    print("="*60)
    
    s0 = stage0()
    s1 = stage1(s0)
    s2 = stage2(s1)
    s3 = stage3(s2)
    s4 = stage4(s3)
    
    elapsed = (time.time() - start_time) / 60
    
    print("\n" + "="*60)
    print("  RESULTS")
    print("="*60)
    print(f"  API calls: {calls}")
    print(f"  Time: {elapsed:.1f} min")
    print(f"  Compounders: {len(s4)}")
    
    compounders = [s for s in s4 if s['compPower'] >= 0.20]
    cows = [s for s in s4 if s['compPower'] < 0.20]
    
    print(f"\n  COMPOUNDING MACHINES ({len(compounders)}):")
    print(f"  {'Ticker':<7} {'ROIIC':>7} {'Reinv':>7} {'CompPwr':>8} {'ROIC':>7}")
    for s in compounders[:25]:
        print(f"  {s['symbol']:<7} {s['roiic']*100:>6.0f}% {s['reinvRate']*100:>6.0f}% {s['compPower']*100:>7.0f}% {s['roic']*100:>6.0f}%")
    
    print(f"\n  CASH COWS ({len(cows)}):")
    for s in cows[:10]:
        print(f"  {s['symbol']:<7} ROIIC: {s['roiic']*100:.0f}%")

if __name__ == "__main__":
    main()
