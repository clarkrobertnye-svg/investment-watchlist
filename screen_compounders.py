"""
Capital Compounder Screening Script
Run: python3 screen_compounders.py
"""

import json
from pathlib import Path
from config import FILTERS

def load_cached_data():
    cache_dir = Path("cache/ticker_data")
    tickers = []
    for f in cache_dir.glob("*.json"):
        with open(f) as file:
            data = json.load(file)
            if data.get("data_quality") == "complete":
                tickers.append(data)
    return tickers

def passes_filters(t):
    """Apply Tier 1 filter logic."""
    roic = t.get("roic_3y_avg") or t.get("roic_current") or 0
    roic_ex_gw = t.get("roic_ex_goodwill_3y_avg") or t.get("roic_ex_goodwill") or 0
    inc_roic = t.get("incremental_roic", 0)
    gm = t.get("gross_margin", 0)
    fcf = t.get("fcf_conversion", 0)
    growth = t.get("revenue_growth_3y", 0)
    capex = t.get("capex_to_revenue", 0)
    leverage = t.get("net_debt_ebitda", 0)
    
    # Filter checks with overrides
    roic_pass = (roic >= FILTERS["roic_min"]) or (roic_ex_gw >= FILTERS["roic_min"])
    
    capex_pass = (capex <= FILTERS["capex_to_revenue_max"]) or \
                 (inc_roic >= FILTERS["incremental_roic_override"])
    
    fcf_pass = (fcf >= FILTERS["fcf_conversion_min"]) or \
               (fcf >= FILTERS["fcf_conversion_override_min"] and 
                inc_roic >= FILTERS["incremental_roic_override"])
    
    inc_roic_pass = inc_roic >= FILTERS["incremental_roic_min"]
    
    return (roic_pass and 
            gm >= FILTERS["gross_margin_min"] and 
            fcf_pass and 
            growth >= FILTERS["revenue_growth_min"] and 
            capex_pass and 
            leverage <= FILTERS["net_debt_ebitda_max"] and 
            inc_roic_pass)

def main():
    tickers = load_cached_data()
    passed = [t for t in tickers if passes_filters(t)]
    
    print(f"\nCAPITAL COMPOUNDERS SCREEN: {len(passed)} PASSED / {len(tickers)} TOTAL")
    print("=" * 110)
    print(f"{'':2} {'Ticker':<6} | {'ROIC':>6} | {'IncROIC':>7} | {'GM':>5} | {'FCF%':>5} | {'Grth':>5} | {'FCF Yld':>7} | {'MCap':>8}")
    print("-" * 110)
    
    for t in sorted(passed, key=lambda x: x.get("fcf_yield") or 0, reverse=True):
        ticker = t.get("ticker")
        roic = (t.get("roic_3y_avg") or 0) * 100
        inc_roic = t.get("incremental_roic", 0) * 100
        gm = t.get("gross_margin", 0) * 100
        fcf_conv = t.get("fcf_conversion", 0) * 100
        growth = t.get("revenue_growth_3y", 0) * 100
        fcf_yield = (t.get("fcf_yield") or 0) * 100
        mcap = t.get("market_cap", 0) / 1e9
        capex = t.get("capex_to_revenue", 0) * 100
        
        flags = ""
        if capex > 7: flags += "^"
        if fcf_conv < 80 and inc_roic >= 15: flags += "+"
        if inc_roic == 0: flags += "○"
        flags = flags.ljust(2)
        
        print(f"{flags} {ticker:6} | {roic:5.1f}% | {inc_roic:6.1f}% | {gm:4.0f}% | {fcf_conv:4.0f}% | {growth:4.0f}% | {fcf_yield:6.1f}% | ${mcap:6.0f}B")
    
    print("\n^ = High CapEx override  + = Low FCF override  ○ = Mature compounder")

if __name__ == "__main__":
    main()
