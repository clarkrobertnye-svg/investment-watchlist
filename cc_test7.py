#!/usr/bin/env python3
"""
Capital Compounders v2 — Full Screening Pipeline
Uses FMP /stable/ endpoints to pull 3-year averaged metrics
and apply all 4 gates from the v2 spec.

Usage:
  python3 capital_compounders_v2.py

Output:
  compounders_v2_results.csv — scored and ranked results
  compounders_v2_log.txt    — detailed screening log
"""

import json
import csv
import time
import sys
import os
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"
BASE_URL = "https://financialmodelingprep.com/stable"
OUTPUT_DIR = os.path.expanduser("~/Documents/capital_compounders")
RATE_LIMIT_DELAY = 0.25  # seconds between API calls

# Universe built dynamically — no hardcoded tickers
MIN_MARKET_CAP = 10_000_000_000  # $10B
MIN_GROSS_MARGIN = 0.15          # 15% (Gate 1 pre-filter to reduce API calls)


# ============================================================
# API HELPERS
# ============================================================
api_calls = 0

def fetch_json(url):
    """Fetch JSON from URL with rate limiting and error handling."""
    global api_calls
    time.sleep(RATE_LIMIT_DELAY)
    api_calls += 1
    try:
        req = Request(url, headers={"User-Agent": "CapitalCompounders/2.0"})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except (URLError, HTTPError, json.JSONDecodeError) as e:
        print(f"  ⚠ API error: {e}")
        return None

def get_income_statements(symbol, limit=6):
    url = f"{BASE_URL}/income-statement?symbol={symbol}&limit={limit}&apikey={API_KEY}"
    return fetch_json(url)

def get_balance_sheets(symbol, limit=6):
    url = f"{BASE_URL}/balance-sheet-statement?symbol={symbol}&limit={limit}&apikey={API_KEY}"
    return fetch_json(url)

def get_cash_flows(symbol, limit=6):
    url = f"{BASE_URL}/cash-flow-statement?symbol={symbol}&limit={limit}&apikey={API_KEY}"
    return fetch_json(url)

def get_profile(symbol):
    url = f"{BASE_URL}/profile?symbol={symbol}&apikey={API_KEY}"
    data = fetch_json(url)
    if data and isinstance(data, list) and len(data) > 0:
        return data[0]
    return data


# ============================================================
# UNIVERSE BUILDER
# ============================================================

def build_universe():
    """
    Dynamically pull all US-listed stocks with market cap >= $10B.
    No hardcoded tickers — the screen catches what the screen catches.
    """
    print("Building universe from FMP screener...")
    
    # FMP stock screener — pull $10B+ from US exchanges
    url = (f"{BASE_URL}/stock-screener?"
           f"marketCapMoreThan={MIN_MARKET_CAP}"
           f"&exchange=NYSE,NASDAQ,AMEX"
           f"&apikey={API_KEY}")
    data = fetch_json(url)
    
    if not data or not isinstance(data, list):
        print("  ⚠ Screener returned no data, trying alternative endpoint...")
        # Fallback: try without exchange filter
        url = (f"{BASE_URL}/stock-screener?"
               f"marketCapMoreThan={MIN_MARKET_CAP}"
               f"&apikey={API_KEY}")
        data = fetch_json(url)
    
    if not data or not isinstance(data, list):
        print("  ✗ Screener failed. Cannot build universe.")
        sys.exit(1)
    
    print(f"  Raw screener results: {len(data)} stocks")
    
    # Filter to US-traded (USD currency, major exchanges)
    us_exchanges = {"NYSE", "NASDAQ", "AMEX", "New York Stock Exchange", 
                    "NASDAQ Global Select", "NASDAQ Global Market", "NASDAQ Capital Market",
                    "Nasdaq Global Select", "Nasdaq", "Nyse"}
    
    universe = []
    for stock in data:
        symbol = stock.get("symbol", "")
        exchange = stock.get("exchangeShortName", "") or stock.get("exchange", "")
        mkt_cap = stock.get("marketCap", 0) or stock.get("mktCap", 0) or 0
        
        # Skip if no symbol
        if not symbol:
            continue
        
        # Skip OTC foreign tickers (5-char ending in F or Y)
        if len(symbol) == 5 and symbol[-1] in ('F', 'Y'):
            continue
        
        # Skip if not on a US exchange (if exchange data available)
        if exchange and exchange not in us_exchanges and "NYSE" not in exchange.upper() and "NASDAQ" not in exchange.upper():
            continue
        
        # Skip ETFs, funds, warrants, units
        if any(symbol.endswith(s) for s in ['-UN', '-WT', '.WS', '.U']):
            continue
        
        # Pre-filter: gross margin > 15% if available (saves API calls)
        gm = stock.get("grossProfitMargin", stock.get("grossMargin"))
        if gm is not None:
            # Handle both decimal (0.15) and percentage (15.0) formats
            if gm > 1:
                gm = gm / 100
            if gm <= MIN_GROSS_MARGIN:
                continue
        
        universe.append({
            "symbol": symbol,
            "mktCap": mkt_cap,
            "exchange": exchange,
        })
    
    print(f"  After US-listed filter: {len(universe)} stocks")
    
    # Deduplicate dual-class listings (GOOG/GOOGL, FOX/FOXA, etc.)
    # Group by first 3 chars, keep highest market cap
    from collections import defaultdict
    
    # Known dual-class pairs — keep the more liquid one
    dual_class_remove = set()
    symbol_set = {s["symbol"] for s in universe}
    
    dual_pairs = [
        ("GOOG", "GOOGL"),   # keep GOOGL (Class A)
        ("FOX", "FOXA"),     # keep FOXA (Class A)  
        ("BRK.A", "BRK.B"),  # keep BRK.B (more liquid)
        ("NWS", "NWSA"),     # keep NWSA
        ("LSXMA", "LSXMK"),  # keep LSXMK
    ]
    for remove, keep in dual_pairs:
        if remove in symbol_set and keep in symbol_set:
            dual_class_remove.add(remove)
    
    universe = [s for s in universe if s["symbol"] not in dual_class_remove]
    
    if dual_class_remove:
        print(f"  Removed {len(dual_class_remove)} dual-class duplicates: {dual_class_remove}")
    
    # Sort by market cap descending
    universe.sort(key=lambda x: x["mktCap"], reverse=True)
    
    tickers = [s["symbol"] for s in universe]
    print(f"  Final universe: {len(tickers)} tickers")
    
    # Show top 20 and check for expected names
    print(f"\n  Top 20 by market cap:")
    for s in universe[:20]:
        mc = f"${s['mktCap']/1e12:.1f}T" if s['mktCap'] >= 1e12 else f"${s['mktCap']/1e9:.0f}B"
        print(f"    {s['symbol']:<8} {mc:>10}")
    
    # Sanity check: are key names present?
    expected = ["NVDA", "AAPL", "GOOGL", "V", "MA", "MSFT"]
    found = [t for t in expected if t in tickers]
    missing = [t for t in expected if t not in tickers]
    print(f"\n  Sanity check — found: {found}")
    if missing:
        print(f"  ⚠ Missing expected names: {missing}")
    
    return tickers

# ============================================================
# METRIC CALCULATIONS
# ============================================================

def safe_div(a, b, default=None):
    """Safe division, returns default if b is 0 or None."""
    if b is None or b == 0 or a is None:
        return default
    return a / b

def calc_nopat(inc):
    """NOPAT = Operating Income × (1 - effective tax rate)"""
    op_inc = inc.get("operatingIncome", 0) or 0
    tax = inc.get("incomeTaxExpense", 0) or 0
    pretax = inc.get("incomeBeforeTax", 0) or 0
    if pretax > 0 and tax >= 0:
        eff_tax = tax / pretax
    else:
        eff_tax = 0.21  # default to US corporate rate
    return op_inc * (1 - eff_tax)

def calc_invested_capital(bs):
    """Invested Capital = Total Equity + Total Debt - Cash"""
    equity = bs.get("totalStockholdersEquity", 0) or 0
    total_debt = bs.get("totalDebt", 0) or 0
    # Try shortTermDebt + longTermDebt if totalDebt not available
    if total_debt == 0:
        short = bs.get("shortTermDebt", 0) or 0
        long_term = bs.get("longTermDebt", 0) or 0
        total_debt = short + long_term
    cash = bs.get("cashAndCashEquivalents", 0) or 0
    ic = equity + total_debt - cash
    return ic if ic > 0 else None

def calc_fcf(cf):
    """Free Cash Flow = Operating CF - CapEx"""
    op_cf = cf.get("operatingCashFlow", 0) or 0
    capex = abs(cf.get("capitalExpenditure", 0) or 0)
    return op_cf - capex

def process_ticker(symbol):
    """Pull all data and calculate v2 metrics for one ticker."""
    result = {"symbol": symbol, "error": None}
    
    # Pull data
    inc_stmts = get_income_statements(symbol, 7)
    bal_sheets = get_balance_sheets(symbol, 7)
    cash_flows = get_cash_flows(symbol, 7)
    profile = get_profile(symbol)
    
    if not inc_stmts or not bal_sheets or not cash_flows:
        result["error"] = "Missing financial statements"
        return result
    
    # Sort by date descending (most recent first)
    inc_stmts.sort(key=lambda x: x.get("date", ""), reverse=True)
    bal_sheets.sort(key=lambda x: x.get("date", ""), reverse=True)
    cash_flows.sort(key=lambda x: x.get("date", ""), reverse=True)
    
    # Need at least 4 years for 3-year calculations
    if len(inc_stmts) < 4 or len(bal_sheets) < 4:
        result["error"] = f"Insufficient history (inc={len(inc_stmts)}, bs={len(bal_sheets)})"
        return result
    
    # ---- Profile data ----
    if profile:
        result["mktCap"] = profile.get("mktCap", 0) or 0
        result["sector"] = profile.get("sector", "")
        result["industry"] = profile.get("industry", "")
        result["companyName"] = profile.get("companyName", symbol)
    else:
        result["mktCap"] = 0
        result["companyName"] = symbol
    
    # ---- Calculate yearly metrics ----
    years = []
    for i in range(min(len(inc_stmts), len(bal_sheets), len(cash_flows))):
        inc = inc_stmts[i]
        bs = bal_sheets[i]
        cf = cash_flows[i]
        
        nopat = calc_nopat(inc)
        ic = calc_invested_capital(bs)
        fcf = calc_fcf(cf)
        revenue = inc.get("revenue", 0) or 0
        gross_profit = inc.get("grossProfit", 0) or 0
        net_income = inc.get("netIncome", 0) or 0
        ebitda = inc.get("ebitda", 0) or 0
        total_debt = (bs.get("totalDebt", 0) or 0) or ((bs.get("shortTermDebt", 0) or 0) + (bs.get("longTermDebt", 0) or 0))
        cash = bs.get("cashAndCashEquivalents", 0) or 0
        shares = inc.get("weightedAverageShsOutDil", 0) or cf.get("weightedAverageShsOutDil", 0) or 0
        
        gm = safe_div(gross_profit, revenue, 0)
        roic = safe_div(nopat, ic) if ic and ic > 0 else None
        fcf_ni = safe_div(fcf, net_income) if net_income and net_income > 0 else None
        
        years.append({
            "date": inc.get("date", "?"),
            "nopat": nopat,
            "ic": ic,
            "fcf": fcf,
            "revenue": revenue,
            "net_income": net_income,
            "gross_margin": gm,
            "roic": roic,
            "fcf_ni": fcf_ni,
            "ebitda": ebitda,
            "total_debt": total_debt,
            "cash": cash,
            "net_debt": total_debt - cash,
            "shares": shares,
            "fcf_per_share": safe_div(fcf, shares) if shares > 0 else None,
        })
    
    result["years"] = [y["date"] for y in years]
    
    # ---- Current / trailing metrics ----
    result["grossMargin"] = years[0]["gross_margin"] if years else 0
    result["currentROIC"] = years[0]["roic"]
    
    # ---- 3-Year Average ROIC ----
    roics_3yr = [y["roic"] for y in years[:3] if y["roic"] is not None]
    result["avg3yr_ROIC"] = sum(roics_3yr) / len(roics_3yr) if roics_3yr else None
    
    # ---- 3-Year Cumulative ROIIC ----
    if len(years) >= 4 and years[0]["nopat"] and years[3]["nopat"] and years[0]["ic"] and years[3]["ic"]:
        delta_nopat = years[0]["nopat"] - years[3]["nopat"]
        delta_ic = years[0]["ic"] - years[3]["ic"]
        if delta_ic > 0:
            result["cum3yr_ROIIC"] = delta_nopat / delta_ic
        elif delta_ic < 0:
            result["cum3yr_ROIIC"] = None  # IC shrank — capital-light compounder
            result["ic_shrinking"] = True
        else:
            result["cum3yr_ROIIC"] = None
    else:
        result["cum3yr_ROIIC"] = None
    
    if "ic_shrinking" not in result:
        result["ic_shrinking"] = False
    
    # ---- 3-Year CUMULATIVE Reinvestment Rate ----
    # Uses total ΔIC / total NOPAT over 3-year window
    # This avoids one bad year (e.g., NVDA FY2023 at -193%) destroying the average
    if len(years) >= 4 and years[0]["ic"] and years[3]["ic"]:
        total_delta_ic = years[0]["ic"] - years[3]["ic"]
        total_nopat = sum(y["nopat"] for y in years[:3] if y["nopat"])
        if total_nopat > 0:
            result["cum3yr_ReinvRate"] = total_delta_ic / total_nopat
        else:
            result["cum3yr_ReinvRate"] = None
    else:
        result["cum3yr_ReinvRate"] = None
    
    # ---- 3-Year Cumulative Power ----
    if result.get("cum3yr_ROIIC") is not None and result.get("cum3yr_ReinvRate") is not None:
        # Cap ROIIC at 350% and reinvestment at 200% for power calc
        capped_roiic = min(result["cum3yr_ROIIC"], 3.50)
        capped_reinv = min(result["cum3yr_ReinvRate"], 2.00)
        result["cum3yr_Power"] = capped_roiic * capped_reinv if capped_reinv > 0 else 0
    else:
        result["cum3yr_Power"] = None
    
    # ---- 3-Year Average ROIIC (annual basis) ----
    annual_roiics = []
    for i in range(min(3, len(years) - 1)):
        if years[i]["nopat"] and years[i+1]["nopat"] and years[i]["ic"] and years[i+1]["ic"]:
            dn = years[i]["nopat"] - years[i+1]["nopat"]
            di = years[i]["ic"] - years[i+1]["ic"]
            if di > 0:
                annual_roiics.append(dn / di)
    result["avg3yr_ROIIC_annual"] = sum(annual_roiics) / len(annual_roiics) if annual_roiics else None
    
    # ---- 5-Year FCF/Share CAGR ----
    if len(years) >= 6:
        fcf_ps_current = years[0]["fcf_per_share"]
        fcf_ps_5yr = years[5]["fcf_per_share"]
        if fcf_ps_current and fcf_ps_5yr and fcf_ps_5yr > 0 and fcf_ps_current > 0:
            result["fcf_share_cagr_5yr"] = (fcf_ps_current / fcf_ps_5yr) ** (1/5) - 1
        else:
            result["fcf_share_cagr_5yr"] = None
    elif len(years) >= 4:
        # Fall back to 3-year if 5-year not available
        fcf_ps_current = years[0]["fcf_per_share"]
        fcf_ps_3yr = years[3]["fcf_per_share"]
        if fcf_ps_current and fcf_ps_3yr and fcf_ps_3yr > 0 and fcf_ps_current > 0:
            result["fcf_share_cagr_5yr"] = (fcf_ps_current / fcf_ps_3yr) ** (1/3) - 1
            result["fcf_cagr_note"] = "3yr (insufficient 5yr data)"
        else:
            result["fcf_share_cagr_5yr"] = None
    else:
        result["fcf_share_cagr_5yr"] = None
    
    # ---- 3-Year Average FCF/NI ----
    fcf_nis = [y["fcf_ni"] for y in years[:3] if y["fcf_ni"] is not None and y["fcf_ni"] > 0]
    result["avg3yr_FCF_NI"] = sum(fcf_nis) / len(fcf_nis) if fcf_nis else None
    
    # ---- Net Debt / EBITDA ----
    if years and years[0]["ebitda"] and years[0]["ebitda"] > 0:
        result["netDebt_EBITDA"] = years[0]["net_debt"] / years[0]["ebitda"]
    else:
        result["netDebt_EBITDA"] = None
    
    # ---- 3-Year Average VCR (ROIC / 0.10 assumed WACC) ----
    if result["avg3yr_ROIC"] is not None:
        result["avg3yr_VCR"] = result["avg3yr_ROIC"] / 0.10
    else:
        result["avg3yr_VCR"] = None
    
    return result


# ============================================================
# GATE FILTERS
# ============================================================

def apply_gates(stock):
    """Apply all 4 gates, returns (pass, gate_failed, reasons)."""
    reasons = []
    
    # ---- GATE 1: Minimum Quality ----
    # Market cap ≥ $10B (already filtered by ticker list, but double-check)
    mc = stock.get("mktCap", 0) or 0
    
    # Gross Margin > 15%
    gm = stock.get("grossMargin", 0) or 0
    if gm <= 0.15:
        reasons.append(f"GM {gm*100:.1f}% ≤ 15%")
    
    # 3yr avg ROIC ≥ 12% OR latest ROIC ≥ 18%
    avg_roic = stock.get("avg3yr_ROIC")
    curr_roic = stock.get("currentROIC")
    roic_pass = False
    if avg_roic is not None and avg_roic >= 0.12:
        roic_pass = True
    if curr_roic is not None and curr_roic >= 0.18:
        roic_pass = True
    if not roic_pass:
        r1 = f"3yr ROIC {avg_roic*100:.1f}%" if avg_roic else "no ROIC"
        r2 = f"curr {curr_roic*100:.1f}%" if curr_roic else "no curr"
        reasons.append(f"ROIC fail ({r1}, {r2})")
    
    if reasons:
        return False, "Gate 1", reasons
    
    # ---- GATE 2: Compounding Engine ----
    reinv = stock.get("cum3yr_ReinvRate")
    fcf_cagr = stock.get("fcf_share_cagr_5yr")
    
    # Cap reinvestment rate at 200% for scoring (avoids artifacts like SPOT)
    if reinv is not None and reinv > 2.0:
        stock["reinv_capped"] = True
        reinv_for_power = 2.0
    else:
        stock["reinv_capped"] = False
        reinv_for_power = reinv
    
    # PATH A: Capital-light compounder (IC shrinking)
    if stock.get("ic_shrinking", False):
        # Needs: 3yr avg ROIC ≥ 20% AND FCF/share CAGR > 15%
        if avg_roic is None or avg_roic < 0.20:
            reasons.append(f"Capital-light but 3yr ROIC {avg_roic*100:.1f}% < 20%")
        if fcf_cagr is None or fcf_cagr < 0.15:
            cagr_str = f"{fcf_cagr*100:.1f}%" if fcf_cagr else "N/A"
            reasons.append(f"Capital-light but FCF/sh CAGR {cagr_str} < 15%")
        if reasons:
            return False, "Gate 2 (capital-light path)", reasons
        else:
            stock["path"] = "capital-light"
    
    # PATH B: Buyback compounder (low reinvestment, high ROIC, proven per-share growth)
    elif reinv is not None and reinv < 0.12 and avg_roic is not None and avg_roic >= 0.25:
        if fcf_cagr is not None and fcf_cagr >= 0.12:
            stock["path"] = "buyback-compounder"
        else:
            cagr_str = f"{fcf_cagr*100:.1f}%" if fcf_cagr else "N/A"
            reasons.append(f"Low reinv ({reinv*100:.1f}%) + high ROIC ({avg_roic*100:.1f}%) but FCF/sh CAGR {cagr_str} < 12%")
            return False, "Gate 2 (buyback path)", reasons
    
    # PATH C: Standard compounder
    else:
        stock["path"] = "compounder"
        
        if reinv is not None and reinv < 0.12:
            reasons.append(f"Reinv {reinv*100:.1f}% < 12%")
        elif reinv is None:
            reasons.append("Reinv rate unavailable")
        
        # 3yr cumulative ROIIC ≥ 15%
        roiic = stock.get("cum3yr_ROIIC")
        if roiic is not None and roiic < 0.15:
            reasons.append(f"ROIIC {roiic*100:.1f}% < 15%")
        elif roiic is None:
            roiic_ann = stock.get("avg3yr_ROIIC_annual")
            if roiic_ann is not None and roiic_ann < 0.15:
                reasons.append(f"ROIIC annual avg {roiic_ann*100:.1f}% < 15%")
        
        # 3yr cumulative power ≥ 12% (lowered from 15%)
        power = stock.get("cum3yr_Power")
        if power is not None and power < 0.12:
            reasons.append(f"Power {power*100:.1f}% < 12%")
    
    if reasons:
        return False, "Gate 2", reasons
    
    # ---- GATE 3: Proof of Compounding ----
    # 5yr FCF/share CAGR > 12% (or owner earnings — using FCF as proxy)
    fcf_cagr = stock.get("fcf_share_cagr_5yr")
    if fcf_cagr is not None and fcf_cagr >= 0.12:
        pass  # passes
    elif fcf_cagr is not None:
        reasons.append(f"FCF/sh CAGR {fcf_cagr*100:.1f}% < 12%")
    else:
        reasons.append("FCF/share CAGR unavailable")
    
    if reasons:
        return False, "Gate 3", reasons
    
    # ---- GATE 4: Financial Health ----
    # 3yr avg FCF/NI ≥ 70%
    fcf_ni = stock.get("avg3yr_FCF_NI")
    if fcf_ni is not None and fcf_ni < 0.70:
        reasons.append(f"FCF/NI {fcf_ni*100:.1f}% < 70%")
    elif fcf_ni is None:
        reasons.append("FCF/NI unavailable")
    
    # Net Debt / EBITDA ≤ 2.5× (or ≤ 3.0× with FCF/Debt > 0.5×)
    nd_ebitda = stock.get("netDebt_EBITDA")
    if nd_ebitda is not None:
        if nd_ebitda > 2.5:
            # Check escape hatch
            if nd_ebitda <= 3.0:
                # Would need FCF/Debt check — approximate with FCF/total_debt
                reasons.append(f"NetDebt/EBITDA {nd_ebitda:.1f}× > 2.5× (check FCF/Debt for escape)")
            else:
                reasons.append(f"NetDebt/EBITDA {nd_ebitda:.1f}× > 2.5×")
    # Negative net debt (net cash) always passes
    
    if reasons:
        return False, "Gate 4", reasons
    
    return True, "PASS", []


# ============================================================
# SCORING
# ============================================================

def percentile_rank(value, all_values):
    """Calculate percentile rank of value within list."""
    if not all_values or value is None:
        return 0.5
    valid = [v for v in all_values if v is not None]
    if not valid:
        return 0.5
    return sum(1 for v in valid if v <= value) / len(valid)

def score_stocks(passers):
    """Score passing stocks using composite model."""
    powers = [s.get("cum3yr_Power") for s in passers]
    roics = [s.get("avg3yr_ROIC") for s in passers]
    cagrs = [s.get("fcf_share_cagr_5yr") for s in passers]
    # For balance sheet, lower net debt/ebitda is better — invert
    nd_scores = []
    for s in passers:
        nd = s.get("netDebt_EBITDA")
        nd_scores.append(-nd if nd is not None else 5)  # penalize missing
    
    for s in passers:
        p_pct = percentile_rank(s.get("cum3yr_Power"), powers)
        r_pct = percentile_rank(s.get("avg3yr_ROIC"), roics)
        c_pct = percentile_rank(s.get("fcf_share_cagr_5yr"), cagrs)
        nd = s.get("netDebt_EBITDA")
        b_pct = percentile_rank(-nd if nd is not None else 5, nd_scores)
        
        s["composite_score"] = 0.40 * p_pct + 0.25 * r_pct + 0.20 * c_pct + 0.15 * b_pct


# ============================================================
# MAIN
# ============================================================

def main():
    global api_calls
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, "test7_log.txt")
    csv_path = os.path.join(OUTPUT_DIR, "test7_results.csv")
    all_data_path = os.path.join(OUTPUT_DIR, "test7_data.json")
    
    log = open(log_path, "w")
    def out(msg):
        print(msg)
        log.write(msg + "\n")
    
    out(f"Capital Compounders v2 Screen")
    out(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ---- TEST RUN: 7 tickers ----
    TICKERS = ["NVDA", "AZO", "GOOGL", "MA", "ADP", "CLS", "MOD"]
    out(f"TEST RUN: {len(TICKERS)} tickers")
    out(f"{'='*70}\n")
    
    # ---- Phase 1: Data Pull ----
    all_stocks = []
    errors = []
    
    for i, ticker in enumerate(TICKERS):
        pct = (i + 1) / len(TICKERS) * 100
        print(f"\r[{pct:5.1f}%] Processing {ticker:<6} ({i+1}/{len(TICKERS)}) — {api_calls} API calls", end="", flush=True)
        
        result = process_ticker(ticker)
        
        if result.get("error"):
            errors.append((ticker, result["error"]))
            out(f"  ✗ {ticker}: {result['error']}")
        else:
            all_stocks.append(result)
    
    print()  # newline after progress
    out(f"\nData pull complete: {len(all_stocks)} stocks loaded, {len(errors)} errors, {api_calls} API calls")
    
    if errors:
        out(f"\nErrors:")
        for t, e in errors:
            out(f"  {t}: {e}")
    
    # Save all raw data
    with open(all_data_path, "w") as f:
        json.dump(all_stocks, f, indent=2, default=str)
    out(f"\nRaw data saved to {all_data_path}")
    
    # ---- Phase 2: Apply Gates ----
    out(f"\n{'='*70}")
    out(f"APPLYING GATES")
    out(f"{'='*70}\n")
    
    gate_counts = {"Gate 1": 0, "Gate 2": 0, "Gate 2 (capital-light path)": 0, "Gate 3": 0, "Gate 4": 0}
    passers = []
    failures = {1: [], 2: [], 3: [], 4: []}
    
    for stock in all_stocks:
        passed, gate, reasons = apply_gates(stock)
        if passed:
            passers.append(stock)
        else:
            gate_num = int(gate.split()[1][0]) if gate[0] != "P" else 0
            if gate_num in failures:
                failures[gate_num].append((stock["symbol"], reasons))
            gate_counts[gate] = gate_counts.get(gate, 0) + 1
    
    out(f"Gate Results:")
    out(f"  Entered:         {len(all_stocks)}")
    out(f"  Failed Gate 1:   {len(failures[1])} (Quality)")
    out(f"  Failed Gate 2:   {len(failures[2])} (Compounding Engine)")
    out(f"  Failed Gate 3:   {len(failures[3])} (Proof)")
    out(f"  Failed Gate 4:   {len(failures[4])} (Financial Health)")
    out(f"  PASSED ALL:      {len(passers)}")
    
    # Show failures
    for gate_num, gate_name in [(1, "Quality"), (2, "Compounding Engine"), (3, "Proof"), (4, "Financial Health")]:
        if failures[gate_num]:
            out(f"\n  Gate {gate_num} failures ({gate_name}):")
            for sym, reasons in sorted(failures[gate_num]):
                out(f"    {sym:<8} — {'; '.join(reasons)}")
    
    # ---- Phase 3: Score and Rank ----
    if passers:
        score_stocks(passers)
        passers.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
        
        out(f"\n{'='*70}")
        out(f"FINAL RANKED RESULTS: {len(passers)} Capital Compounders")
        out(f"{'='*70}\n")
        
        header = f"{'#':<3} {'Symbol':<7} {'Name':<20} {'MktCap':>10} {'3yr ROIC':>9} {'3yr ROIIC':>10} {'Reinv%':>8} {'Power':>7} {'FCF/sh':>8} {'FCF/NI':>7} {'ND/EB':>6} {'Score':>6} {'Path'}"
        out(header)
        out("-" * 130)
        
        for i, s in enumerate(passers):
            mc = s.get("mktCap", 0)
            if mc >= 1e12:
                mc_str = f"${mc/1e12:.1f}T"
            elif mc >= 1e9:
                mc_str = f"${mc/1e9:.0f}B"
            else:
                mc_str = f"${mc/1e6:.0f}M"
            
            name = s.get("companyName", "")[:19]
            roic = f"{s['avg3yr_ROIC']*100:.1f}%" if s.get("avg3yr_ROIC") else "—"
            roiic = f"{s['cum3yr_ROIIC']*100:.1f}%" if s.get("cum3yr_ROIIC") else "—"
            reinv = f"{s['cum3yr_ReinvRate']*100:.1f}%" if s.get("cum3yr_ReinvRate") else "—"
            power = f"{s['cum3yr_Power']*100:.1f}%" if s.get("cum3yr_Power") else "—"
            cagr = f"{s['fcf_share_cagr_5yr']*100:.1f}%" if s.get("fcf_share_cagr_5yr") else "—"
            fcf_ni = f"{s['avg3yr_FCF_NI']*100:.0f}%" if s.get("avg3yr_FCF_NI") else "—"
            nd = f"{s['netDebt_EBITDA']:.1f}×" if s.get("netDebt_EBITDA") is not None else "—"
            score = f"{s.get('composite_score', 0):.2f}"
            path = s.get("path", "?")
            
            out(f"{i+1:<3} {s['symbol']:<7} {name:<20} {mc_str:>10} {roic:>9} {roiic:>10} {reinv:>8} {power:>7} {cagr:>8} {fcf_ni:>7} {nd:>6} {score:>6} {path}")
        
        # ---- Write CSV ----
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Rank", "Symbol", "CompanyName", "Sector", "Industry", "MktCap",
                "GrossMargin%", "3yr_Avg_ROIC%", "Current_ROIC%",
                "3yr_Cum_ROIIC%", "3yr_Avg_ROIIC_Annual%",
                "3yr_Cum_ReinvRate%", "3yr_Cum_Power%",
                "5yr_FCF_Share_CAGR%", "3yr_Avg_FCF_NI%",
                "NetDebt_EBITDA", "Composite_Score", "Path"
            ])
            for i, s in enumerate(passers):
                writer.writerow([
                    i + 1,
                    s["symbol"],
                    s.get("companyName", ""),
                    s.get("sector", ""),
                    s.get("industry", ""),
                    s.get("mktCap", 0),
                    round(s.get("grossMargin", 0) * 100, 2),
                    round(s["avg3yr_ROIC"] * 100, 2) if s.get("avg3yr_ROIC") else "",
                    round(s["currentROIC"] * 100, 2) if s.get("currentROIC") else "",
                    round(s["cum3yr_ROIIC"] * 100, 2) if s.get("cum3yr_ROIIC") else "",
                    round(s["avg3yr_ROIIC_annual"] * 100, 2) if s.get("avg3yr_ROIIC_annual") else "",
                    round(s["cum3yr_ReinvRate"] * 100, 2) if s.get("cum3yr_ReinvRate") else "",
                    round(s["cum3yr_Power"] * 100, 2) if s.get("cum3yr_Power") else "",
                    round(s["fcf_share_cagr_5yr"] * 100, 2) if s.get("fcf_share_cagr_5yr") else "",
                    round(s["avg3yr_FCF_NI"] * 100, 2) if s.get("avg3yr_FCF_NI") else "",
                    round(s["netDebt_EBITDA"], 2) if s.get("netDebt_EBITDA") is not None else "",
                    round(s.get("composite_score", 0), 4),
                    s.get("path", ""),
                ])
        
        out(f"\nResults saved to {csv_path}")
    else:
        out("\nNo stocks passed all gates.")
    
    out(f"\nLog saved to {log_path}")
    out(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.close()
    
    print(f"\n{'='*70}")
    print(f"DONE — {len(passers)} compounders found")
    print(f"Results: {csv_path}")
    print(f"Log:     {log_path}")
    print(f"Raw:     {all_data_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
