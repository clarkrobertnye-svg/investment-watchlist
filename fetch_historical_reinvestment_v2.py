"""
Fetch 5-year historical reinvestment components for Elite Compounders
Using FMP's NEW stable endpoints (v3 is deprecated as of Aug 2025)

Run: python3 fetch_historical_reinvestment_v2.py
"""

import json
import urllib.request
import time
from pathlib import Path

FMP_API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"

# Elite compounders (38 tickers)
ELITE_TICKERS = [
    "FTNT", "UI", "MA", "NVO", "DOCU", "NVDA", "ORLY", "TPL", "V", "WDFC",
    "ALKS", "DECK", "KLAC", "LULU", "BOX", "EXEL", "ADP", "OMAB", "MRK", "GOOG",
    "GOOGL", "BKE", "IDXX", "DBX", "CTAS", "LNTH", "WSM", "HALO", "ROL", "INOD",
    "NU", "USLM", "ZTS", "NTAP", "IRMD", "TRI", "UTHR", "MSI"
]


def fetch_json(url):
    """Fetch JSON from URL"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"    Error: {e}")
        return None


def fetch_ticker_data(ticker):
    """Fetch all financial data using NEW stable endpoints"""
    base_url = "https://financialmodelingprep.com/stable"
    
    # Cash flow statement - NEW endpoint
    cf_url = f"{base_url}/cash-flow-statement?symbol={ticker}&period=annual&apikey={FMP_API_KEY}"
    cf_data = fetch_json(cf_url)
    
    # Income statement - NEW endpoint
    is_url = f"{base_url}/income-statement?symbol={ticker}&period=annual&apikey={FMP_API_KEY}"
    is_data = fetch_json(is_url)
    
    # Balance sheet - NEW endpoint
    bs_url = f"{base_url}/balance-sheet-statement?symbol={ticker}&period=annual&apikey={FMP_API_KEY}"
    bs_data = fetch_json(bs_url)
    
    return cf_data, is_data, bs_data


def process_ticker(ticker, cf_data, is_data, bs_data):
    """Process financial data into reinvestment components"""
    if not cf_data or not is_data:
        return None
    
    # Ensure we have lists
    if isinstance(cf_data, dict):
        cf_data = [cf_data]
    if isinstance(is_data, dict):
        is_data = [is_data]
    if isinstance(bs_data, dict):
        bs_data = [bs_data]
    
    years_data = []
    
    for j in range(min(len(cf_data), len(is_data), 5)):
        cf = cf_data[j]
        inc = is_data[j]
        bs = bs_data[j] if bs_data and j < len(bs_data) else {}
        
        # CapEx components
        capex = abs(cf.get('capitalExpenditure', 0) or 0)
        depreciation = cf.get('depreciationAndAmortization', 0) or 0
        net_capex = capex - depreciation
        
        # Acquisitions
        acquisitions = abs(cf.get('acquisitionsNet', 0) or 0)
        
        # Working capital from balance sheet
        current_assets = bs.get('totalCurrentAssets', 0) or 0
        current_liab = bs.get('totalCurrentLiabilities', 0) or 0
        cash = bs.get('cashAndCashEquivalents', 0) or 0
        short_debt = bs.get('shortTermDebt', 0) or 0
        
        # Operating working capital (exclude cash and short-term debt)
        working_capital = (current_assets - cash) - (current_liab - short_debt)
        
        # NOPAT = Operating Income x (1 - Tax Rate)
        operating_income = inc.get('operatingIncome', 0) or 0
        income_tax = inc.get('incomeTaxExpense', 0) or 0
        income_before_tax = inc.get('incomeBeforeTax', 0) or 0
        
        if income_before_tax > 0:
            tax_rate = min(income_tax / income_before_tax, 0.35)
        else:
            tax_rate = 0.21
        
        nopat = operating_income * (1 - tax_rate)
        
        years_data.append({
            'year': cf.get('calendarYear', cf.get('date', '')[:4]),
            'capex': capex,
            'depreciation': depreciation,
            'net_capex': net_capex,
            'acquisitions': acquisitions,
            'working_capital': working_capital,
            'operating_income': operating_income,
            'nopat': nopat,
        })
    
    # Calculate delta working capital (YoY change)
    for j in range(len(years_data) - 1):
        years_data[j]['delta_wc'] = years_data[j]['working_capital'] - years_data[j+1]['working_capital']
    
    if years_data:
        years_data[-1]['delta_wc'] = 0
    
    # Calculate total reinvestment and Inc ROIC Needed
    for d in years_data:
        d['total_reinvestment'] = d['net_capex'] + d['delta_wc'] + d['acquisitions']
        
        if d['nopat'] > 0:
            d['inc_roic_needed'] = d['total_reinvestment'] / (0.20 * d['nopat'])
        else:
            d['inc_roic_needed'] = None
    
    return years_data


def main():
    print("=" * 100)
    print("FETCHING 5-YEAR HISTORICAL REINVESTMENT DATA (NEW FMP STABLE API)")
    print("=" * 100)
    print(f"Tickers: {len(ELITE_TICKERS)}")
    print()
    
    results = {}
    
    for i, ticker in enumerate(ELITE_TICKERS):
        print(f"[{i+1}/{len(ELITE_TICKERS)}] {ticker}...", end=" ", flush=True)
        
        cf_data, is_data, bs_data = fetch_ticker_data(ticker)
        
        if cf_data and is_data:
            years_data = process_ticker(ticker, cf_data, is_data, bs_data)
            if years_data:
                results[ticker] = years_data
                print(f"OK ({len(years_data)} years)")
            else:
                print("No data")
        else:
            print("Failed")
        
        time.sleep(0.3)
    
    # Save results
    output_file = Path("elite_historical_reinvestment.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print()
    print("=" * 100)
    print(f"Saved: {output_file} ({len(results)} tickers)")
    print("=" * 100)
    
    # Print summary
    print()
    print("SUMMARY - Inc ROIC Needed by Year")
    print("-" * 80)
    
    for ticker, data in sorted(results.items()):
        row = f"{ticker:<8}"
        for d in data[:5]:
            if d.get('inc_roic_needed') is not None:
                val = d['inc_roic_needed'] * 100
                if abs(val) > 999:
                    row += f"{'999+%':>12}"
                else:
                    row += f"{val:>11.0f}%"
            else:
                row += f"{'--':>12}"
        print(row)


if __name__ == "__main__":
    main()
