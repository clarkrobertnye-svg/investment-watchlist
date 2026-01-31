"""Stage 2 Quality Filter - Full Criteria"""
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Industries to EXCLUDE
EXCLUDED_INDUSTRIES = [
    "Banks - Regional",
    "Banks - Diversified", 
    "Insurance - Property & Casualty",
    "Insurance - Diversified",
    "Insurance - Life",
    "Insurance - Reinsurance",
    "Gold",
    "Coal",
    "Steel",
    "Oil & Gas Exploration & Production",
    "Oil & Gas Integrated",
    "Oil & Gas Equipment & Services",
    "Oil & Gas Midstream",
    "Other Precious Metals & Mining",
    "Silver",
    "Copper",
    "Uranium",
    "Marine Shipping",
    "Tobacco",
]

# Specific tickers to WHITELIST (override industry exclusion)
WHITELIST_TICKERS = [
    "BRK-A", "BRK-B",  # Berkshire - conglomerate
    "BBSEY",           # BB Seguridade - insurance distributor
    "DFS",             # Discover - credit card
    "MA", "V",         # Card networks
    "AXP",             # Amex
]

# Industries with ROIC cap (data often unreliable)
ROIC_CAPPED_INDUSTRIES = [
    "Asset Management",
    "Financial - Capital Markets",
]

def get_fcf_yield(t):
    return t.get("fcf_yield", 0) or 0

def passes_stage2(t, ticker):
    industry = t.get("industry", "")
    
    # ============================================
    # HARD STOPS (Stage 1)
    # ============================================
    mcap = (t.get("market_cap", 0) or 0) / 1e9
    gm = t.get("gross_margin", 0) or 0
    
    # Market Cap >= $1B
    if mcap < 1.0:
        return False, [f"HARD STOP: MCap ${mcap:.2f}B < $1B"], {
            "roic_ex": 0, "vcr_ex": 0, "spread_ex": 0, "wacc": 0,
            "pass_roic": False, "pass_vcr": False, "pass_spread": False
        }
    
    # Gross Margin >= 20%
    if gm < 0.20:
        return False, [f"HARD STOP: GM {gm*100:.0f}% < 20%"], {
            "roic_ex": 0, "vcr_ex": 0, "spread_ex": 0, "wacc": 0,
            "pass_roic": False, "pass_vcr": False, "pass_spread": False
        }
    
    # Check whitelist first for industry exclusion
    if ticker not in WHITELIST_TICKERS:
        if industry in EXCLUDED_INDUSTRIES:
            return False, [f"EXCLUDED: {industry}"], {
                "roic_ex": 0, "vcr_ex": 0, "spread_ex": 0, "wacc": 0,
                "pass_roic": False, "pass_vcr": False, "pass_spread": False
            }
    
    # ============================================
    # ROIC CALCULATIONS
    # ============================================
    roic = max(
        t.get("roic_current", 0) or 0,
        t.get("roic_3y_avg", 0) or 0
    )
    
    roic_ex_gw = max(
        t.get("roic_ex_goodwill", 0) or 0,
        t.get("roic_ex_goodwill_3y_avg", 0) or 0
    )
    
    if roic_ex_gw > 0 and roic_ex_gw <= roic * 2 and roic_ex_gw <= 1.0:
        roic_ex = roic_ex_gw
    elif roic <= 1.0:
        roic_ex = roic
    else:
        roic_ex = roic
    
    wacc = t.get("wacc", 0.10) or 0.10
    vcr_ex = roic_ex / wacc if wacc > 0 else 0
    spread_ex = roic_ex - wacc
    
    fcf_yield = get_fcf_yield(t)
    
    # Data error check
    data_error = False
    if industry in ROIC_CAPPED_INDUSTRIES:
        if roic_ex > 0.60:
            data_error = True
    else:
        if roic_ex > 1.50:
            data_error = True
    
    if data_error:
        return False, [f"ROICex {roic_ex*100:.0f}% DATA ERROR"], {
            "roic_ex": roic_ex, "vcr_ex": vcr_ex, "spread_ex": spread_ex, "wacc": wacc,
            "pass_roic": False, "pass_vcr": False, "pass_spread": False, 
            "fcf_yield": fcf_yield
        }
    
    # ============================================
    # FCF YIELD FILTER (3yr avg > 1%)
    # ============================================
    if fcf_yield <= 0.01:
        return False, [f"FCF Yield {fcf_yield*100:.1f}% ≤ 1%"], {
            "roic_ex": roic_ex, "vcr_ex": vcr_ex, "spread_ex": spread_ex, "wacc": wacc,
            "pass_roic": False, "pass_vcr": False, "pass_spread": False, 
            "fcf_yield": fcf_yield
        }
    
    # ============================================
    # QUALITY GATES (ANY of 3)
    # ============================================
    pass_roic = roic_ex > 0.15
    pass_vcr = vcr_ex > 1.5
    pass_spread = spread_ex > 0.05
    
    passes = pass_roic or pass_vcr or pass_spread
    
    failures = []
    if not passes:
        failures.append(f"ROICex {roic_ex*100:.1f}%≤15%, VCRex {vcr_ex:.2f}≤1.5, Spread {spread_ex*100:.1f}%≤5%")
    
    return passes, failures, {
        "roic_ex": roic_ex,
        "vcr_ex": vcr_ex,
        "spread_ex": spread_ex,
        "wacc": wacc,
        "pass_roic": pass_roic,
        "pass_vcr": pass_vcr,
        "pass_spread": pass_spread,
        "fcf_yield": fcf_yield,
    }

def data_quality_score(t, raw_data):
    score = 0
    ticker = t["ticker"]
    
    if len(ticker) == 5 and ticker[-1] in "FY":
        score -= 100
    elif len(ticker) >= 5 and ticker[-1] in "FY":
        score -= 50
    
    score -= len(ticker) * 5
    
    key_fields = [
        "roic_current", "roic_3y_avg", "roic_ex_goodwill", "gross_margin",
        "revenue_growth_3y", "fcf_conversion", "fcf_yield", "value_creation_ratio",
        "market_cap", "price", "wacc", "net_debt_ebitda"
    ]
    for field in key_fields:
        val = raw_data.get(field)
        if val is not None and val != 0:
            score += 10
    
    mcap = raw_data.get("market_cap", 0) or 0
    score += mcap / 1e11
    
    if raw_data.get("fcf_current", 0) > 0:
        score += 20
    
    return score

def deduplicate(passed_list, raw_data_map):
    by_company = defaultdict(list)
    
    for t in passed_list:
        name = t["name"].lower().strip()
        for suffix in [" inc", " ltd", " plc", " corp", " sa", " ag", " se", " nv", 
                       " ab", " asa", " limited", " group", " holding", " co"]:
            name = name.replace(suffix, "")
        name = name.strip()
        by_company[name].append(t)
    
    deduped = []
    removed = []
    
    for name, listings in by_company.items():
        if len(listings) == 1:
            deduped.append(listings[0])
        else:
            for listing in listings:
                listing["_score"] = data_quality_score(listing, raw_data_map.get(listing["ticker"], {}))
            
            listings.sort(key=lambda x: x["_score"], reverse=True)
            deduped.append(listings[0])
            
            for dup in listings[1:]:
                removed.append(f"{dup['ticker']} (dup of {listings[0]['ticker']})")
    
    for t in deduped:
        t.pop("_score", None)
    
    return deduped, removed

def run_filter():
    cache_dir = Path("cache/ticker_data")
    passed, failed = [], []
    hard_stops = []
    excluded_by_industry = []
    low_fcf = []
    raw_data_map = {}
    
    for f in sorted(cache_dir.glob("*.json")):
        with open(f) as file:
            t = json.load(file)
        if t.get("data_quality") != "complete":
            continue
        
        ticker = t.get("ticker", f.stem)
        raw_data_map[ticker] = t
        
        passes, failures, metrics = passes_stage2(t, ticker)
        
        criteria_met = sum([metrics.get("pass_roic", False), 
                           metrics.get("pass_vcr", False), 
                           metrics.get("pass_spread", False)])
        
        result = {
            "ticker": ticker,
            "name": t.get("company_name", "")[:22],
            "industry": t.get("industry", "")[:25],
            "mcap_b": (t.get("market_cap", 0) or 0) / 1e9,
            "roic_ex": metrics["roic_ex"],
            "vcr_ex": metrics["vcr_ex"],
            "spread_ex": metrics["spread_ex"],
            "wacc": metrics["wacc"],
            "gm": t.get("gross_margin", 0) or 0,
            "growth": t.get("revenue_growth_3y", 0) or 0,
            "fcf_yield": metrics.get("fcf_yield", 0),
            "pass_roic": metrics.get("pass_roic", False),
            "pass_vcr": metrics.get("pass_vcr", False),
            "pass_spread": metrics.get("pass_spread", False),
            "criteria_met": criteria_met,
            "failures": failures,
        }
        
        if passes:
            passed.append(result)
        elif failures and "HARD STOP" in failures[0]:
            hard_stops.append(result)
        elif failures and "EXCLUDED" in failures[0]:
            excluded_by_industry.append(result)
        elif failures and "FCF Yield" in failures[0]:
            low_fcf.append(result)
        else:
            failed.append(result)
    
    print(f"Before dedup: {len(passed)} passed")
    passed, removed = deduplicate(passed, raw_data_map)
    print(f"After dedup:  {len(passed)} passed ({len(removed)} duplicates removed)")
    print(f"Hard stops (MCap/GM): {len(hard_stops)}")
    print(f"Excluded by industry: {len(excluded_by_industry)}")
    print(f"Excluded by FCF Yield ≤1%: {len(low_fcf)}")
    print()
    
    if removed:
        print("Removed duplicates:")
        for r in removed[:10]:
            print(f"  {r}")
        if len(removed) > 10:
            print(f"  ... +{len(removed)-10} more")
        print()
    
    passed.sort(key=lambda x: (x["criteria_met"], x["vcr_ex"]), reverse=True)
    
    all_three = len([p for p in passed if p["criteria_met"] == 3])
    two_of_three = len([p for p in passed if p["criteria_met"] == 2])
    one_of_three = len([p for p in passed if p["criteria_met"] == 1])
    
    print("=" * 130)
    print("STAGE 2: MCap≥$1B + GM≥20% + FCF Yield>1% + (ROIC>15% OR VCR>1.5 OR Spread>5%)")
    print("=" * 130)
    print(f"PASSED: {len(passed)} | All 3: {all_three} | 2 of 3: {two_of_three} | 1 of 3: {one_of_three}")
    print()
    print(f"{'Ticker':<8} {'Name':<22} {'Industry':<26} {'ROICex':>7} {'VCRex':>6} {'Spread':>7} {'FCFYld':>7} {'GM':>5} {'MCap':>8}")
    print("-" * 130)
    
    for t in passed[:60]:
        print(f"{t['ticker']:<8} {t['name']:<22} {t['industry']:<26} {t['roic_ex']*100:>6.1f}% {t['vcr_ex']:>6.2f} {t['spread_ex']*100:>6.1f}% {t['fcf_yield']*100:>6.1f}% {t['gm']*100:>4.0f}% ${t['mcap_b']:>6.1f}B")
    
    if len(passed) > 60:
        print(f"... +{len(passed)-60} more")
    
    print()
    print("HARD STOPS:")
    print("-" * 80)
    for t in hard_stops:
        print(f"  {t['ticker']:<8} {t['name']:<22} | {t['failures'][0]}")
    
    print()
    print("EXCLUDED - FCF YIELD ≤1%:")
    print("-" * 80)
    low_fcf.sort(key=lambda x: x["roic_ex"], reverse=True)
    for t in low_fcf[:15]:
        print(f"  {t['ticker']:<8} {t['name']:<22} | FCF: {t['fcf_yield']*100:>5.1f}% | ROIC: {t['roic_ex']*100:>5.1f}%")
    if len(low_fcf) > 15:
        print(f"  ... +{len(low_fcf)-15} more")
    
    with open("stage2_watchlist_tickers.txt", "w") as f:
        f.write("\n".join(t["ticker"] for t in passed))
    
    output = {
        "filter_date": datetime.now().isoformat(),
        "criteria": "MCap≥$1B + GM≥20% + FCF Yield>1% + (ROIC>15% OR VCR>1.5 OR Spread>5%)",
        "excluded_industries": EXCLUDED_INDUSTRIES,
        "whitelisted_tickers": WHITELIST_TICKERS,
        "passed": len(passed),
        "all_three": all_three,
        "two_of_three": two_of_three,
        "one_of_three": one_of_three,
        "hard_stops": len(hard_stops),
        "removed_duplicates": removed,
        "excluded_by_industry": len(excluded_by_industry),
        "excluded_low_fcf": len(low_fcf),
        "watchlist": passed
    }
    with open("stage2_master_watchlist.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 stage2_master_watchlist.json ({len(passed)} tickers)")

if __name__ == "__main__":
    run_filter()
