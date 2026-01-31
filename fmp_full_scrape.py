"""Capital Compounders - Full FMP Scrape"""
import os
import json
import requests
import time
import sys
from pathlib import Path
from datetime import datetime

API_KEY = os.environ.get('FMP_API_KEY', '')
CACHE_DIR = Path('cache/full_scrape')
CACHE_DIR.mkdir(parents=True, exist_ok=True)

call_count = 0
start_time = time.time()

def api_get(url, params=None):
    global call_count
    call_count += 1
    params = params or {}
    params['apikey'] = API_KEY
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.ok:
            return resp.json()
    except:
        pass
    return None

def fetch_ticker(ticker):
    data = {'ticker': ticker}
    
    p = api_get('https://financialmodelingprep.com/stable/profile', {'symbol': ticker})
    if p and len(p) > 0:
        p = p[0]
        data.update({
            'company_name': p.get('companyName'), 'sector': p.get('sector'),
            'industry': p.get('industry'), 'country': p.get('country'),
            'market_cap': p.get('mktCap') or p.get('marketCap'), 'price': p.get('price'),
            'beta': p.get('beta'),
        })
    
    m = api_get('https://financialmodelingprep.com/stable/key-metrics-ttm', {'symbol': ticker})
    if m and len(m) > 0:
        m = m[0]
        data.update({
            'roic': m.get('roicTTM'), 'roe': m.get('roeTTM'),
            'fcf_yield': m.get('freeCashFlowYieldTTM'),
            'interest_coverage': m.get('interestCoverageTTM'),
        })
    
    r = api_get('https://financialmodelingprep.com/stable/ratios-ttm', {'symbol': ticker})
    if r and len(r) > 0:
        r = r[0]
        data.update({
            'gross_margin': r.get('grossProfitMarginTTM'),
            'operating_margin': r.get('operatingProfitMarginTTM'),
            'net_margin': r.get('netProfitMarginTTM'),
        })
    
    inc = api_get('https://financialmodelingprep.com/stable/income-statement', 
                  {'symbol': ticker, 'period': 'annual', 'limit': 4})
    if inc and len(inc) > 0:
        data.update({
            'revenue': inc[0].get('revenue'), 'ebitda': inc[0].get('ebitda'),
            'net_income': inc[0].get('netIncome'),
        })
        if len(inc) >= 4:
            r0, r3 = inc[0].get('revenue') or 0, inc[3].get('revenue') or 0
            if r3 > 0 and r0 > 0:
                data['revenue_cagr_3y'] = (r0/r3)**(1/3) - 1
    
    cf = api_get('https://financialmodelingprep.com/stable/cash-flow-statement',
                 {'symbol': ticker, 'period': 'annual', 'limit': 1})
    if cf and len(cf) > 0:
        cf = cf[0]
        data.update({
            'operating_cash_flow': cf.get('operatingCashFlow'),
            'fcf': cf.get('freeCashFlow'), 'sbc': cf.get('stockBasedCompensation'),
        })
    
    bs = api_get('https://financialmodelingprep.com/stable/balance-sheet-statement',
                 {'symbol': ticker, 'period': 'annual', 'limit': 1})
    if bs and len(bs) > 0:
        bs = bs[0]
        data.update({
            'total_equity': bs.get('totalStockholdersEquity'),
            'total_debt': bs.get('totalDebt'),
            'cash_and_equivalents': bs.get('cashAndCashEquivalents'),
        })
    
    # Derived
    fcf, ebitda, rev = data.get('fcf') or 0, data.get('ebitda') or 0, data.get('revenue') or 0
    ocf, ni = data.get('operating_cash_flow') or 0, data.get('net_income') or 0
    data['fcf_to_ebitda'] = fcf/ebitda if ebitda > 0 else None
    data['fcf_to_revenue'] = fcf/rev if rev > 0 else None
    data['ocf_to_net_income'] = ocf/ni if ni > 0 else None
    
    beta = min(max(data.get('beta') or 1, 0.5), 2.5)
    wacc = 0.045 + beta * 0.05
    roic = data.get('roic') or 0
    data['wacc'], data['vcr'], data['roic_wacc_spread'] = wacc, roic/wacc if wacc else None, roic - wacc
    
    return data

def run():
    global call_count, start_time
    
    print("STAGE 1: SCREENER", flush=True)
    results = api_get('https://financialmodelingprep.com/stable/company-screener', {
        'marketCapMoreThan': 850_000_000, 'isEtf': False, 'isFund': False,
        'isActivelyTrading': True, 'limit': 10000
    })
    
    if not results:
        print("Failed!"); return
    
    excluded = ['ETF', 'FUND', 'TRUST', 'INDEX', 'ISHARES', 'VANGUARD', 'SPDR']
    tickers = [r['symbol'] for r in results if not any(k in (r.get('companyName') or '').upper() for k in excluded)]
    print(f"Found {len(tickers)} tickers\n", flush=True)
    
    print(f"STAGE 2: FETCHING DATA", flush=True)
    all_data = []
    batch_time = time.time()
    
    for i, ticker in enumerate(tickers):
        # Print every ticker
        sys.stdout.write(f"\r[{i+1}/{len(tickers)}] {ticker:<8} ({call_count} calls)")
        sys.stdout.flush()
        
        # Rate limit every 280 calls
        if call_count > 0 and call_count % 280 == 0:
            elapsed = time.time() - batch_time
            if elapsed < 61:
                wait = 62 - elapsed
                print(f"\n  Pausing {wait:.0f}s for rate limit...", flush=True)
                time.sleep(wait)
            batch_time = time.time()
        
        data = fetch_ticker(ticker)
        if data.get('company_name'):
            all_data.append(data)
            with open(CACHE_DIR / f"{ticker}.json", 'w') as f:
                json.dump(data, f, indent=2)
    
    print(f"\n\nSTAGE 3: FILTERING", flush=True)
    filtered = [r for r in all_data if (r.get('gross_margin') or 0) > 0.35 and (r.get('fcf_to_ebitda') or 0) > 0.50]
    filtered.sort(key=lambda x: x.get('vcr') or 0, reverse=True)
    
    print(f"Fetched: {len(all_data)} | GM>35%: {len([r for r in all_data if (r.get('gross_margin') or 0) > 0.35])} | +FCF/EB>50%: {len(filtered)}")
    
    with open(CACHE_DIR / 'capital_compounders_universe.json', 'w') as f:
        json.dump({'scrape_date': datetime.now().isoformat(), 'total': len(filtered), 'tickers': filtered}, f, indent=2)
    
    with open(CACHE_DIR / 'universe_tickers.txt', 'w') as f:
        f.write('\n'.join(r['ticker'] for r in filtered))
    
    print(f"\nTOP 30:", flush=True)
    print(f"{'Ticker':<8} {'Name':<25} {'GM':>5} {'FCF/EB':>7} {'ROIC':>6} {'VCR':>5}")
    print("-" * 65)
    for r in filtered[:30]:
        print(f"{r['ticker']:<8} {r.get('company_name','')[:25]:<25} {(r.get('gross_margin') or 0)*100:>4.0f}% {(r.get('fcf_to_ebitda') or 0)*100:>6.0f}% {(r.get('roic') or 0)*100:>5.1f}% {r.get('vcr') or 0:>4.1f}x")
    
    print(f"\n💾 Saved {len(filtered)} tickers | {call_count} calls | {(time.time()-start_time)/60:.1f} min")

if __name__ == "__main__":
    run()
