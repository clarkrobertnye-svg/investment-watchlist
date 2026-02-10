#!/usr/bin/env python3
"""
Capital Compounders v4 — Deep Metrics Layer
============================================
Pulls 6 years of FMP data, computes year-by-year series, trend analysis,
capital intensity metrics, SBC adjustments, and red flags.

All raw API data cached to JSON for offline analysis and sync.

Usage:
  python3 capital_intensity_v4.py                  # Run all 93
  python3 capital_intensity_v4.py --tickers AAPL MSFT  # Test specific tickers
  python3 capital_intensity_v4.py --refresh         # Force re-fetch (ignore cache)
  python3 capital_intensity_v4.py --cache-only      # Compute from cache only (no API)

Cache: ./cache/raw/{TICKER}_{statement}.json
Output: ./cache/exports/
"""

import requests
import json
import csv
import os
import sys
import time
import math
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────────────────
try:
    from config import FMP_API_KEY
except ImportError:
    FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
    if not FMP_API_KEY:
        print("ERROR: No API key. Create config.py with FMP_API_KEY = 'your_key'")
        sys.exit(1)

BASE_URL = "https://financialmodelingprep.com/stable"
DELAY = 0.22  # seconds between API calls (stays under 300/min)
CACHE_TTL_DAYS = 7  # re-fetch if cache older than this
YEARS_TO_FETCH = 6  # 6 annual reports = 5 year-over-year deltas

# Project paths
PROJECT_DIR = Path(".")
CACHE_DIR = PROJECT_DIR / "cache"
RAW_DIR = CACHE_DIR / "raw"
COMPUTED_DIR = CACHE_DIR / "computed"
EXPORT_DIR = CACHE_DIR / "exports"

for d in [CACHE_DIR, RAW_DIR, COMPUTED_DIR, EXPORT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# The 93 Capital Compounders from v3
ALL_TICKERS = [
    "NVDA", "ZM", "GMAB", "ANET", "ASML", "DDS", "MA", "NTES", "MEDP", "RNR",
    "PSTG", "ADSK", "KLAC", "DECK", "LOGI", "ANTM", "BKNG", "BAP", "CELH", "GOOGL",
    "LULU", "MELI", "COKE", "MPWR", "TTD", "AAPL", "FIX", "SYF", "ADBE", "EME",
    "DXCM", "CB", "AXP", "BKR", "ADP", "CDNS", "LYV", "V", "VST", "AVGO",
    "MSFT", "JPM", "NVR", "FER", "ACGL", "META", "APH", "QCOM", "BX", "EOG",
    "NVMI", "WSM", "DELL", "TT", "IT", "THC", "ULS", "PR", "NYT", "COG",
    "ERIE", "IBN", "TS", "LII", "HIG", "PYPL", "BLD", "FFIV", "SBS", "CF",
    "APP", "ITT", "INTU", "RMD", "NVS", "BAH", "EBAY", "CAT", "CSL", "TXRH",
    "ULTA", "ROL", "WSO", "VRSK", "CTAS", "HUBB", "WTS", "GRMN", "HWM", "PNC",
    "ETN", "PH", "TTEK",
]

# Known ticker changes
TICKER_MAP = {"ANTM": "ELV", "COG": "CTRA"}

# Cache index
CACHE_INDEX_PATH = CACHE_DIR / "_cache_index.json"


# ═════════════════════════════════════════════════════════════════════════════
# CACHE LAYER
# ═════════════════════════════════════════════════════════════════════════════

def load_cache_index():
    if CACHE_INDEX_PATH.exists():
        with open(CACHE_INDEX_PATH) as f:
            return json.load(f)
    return {}

def save_cache_index(index):
    with open(CACHE_INDEX_PATH, "w") as f:
        json.dump(index, f, indent=2, default=str)

def cache_path(ticker, statement):
    """Path for a cached raw API response."""
    return RAW_DIR / f"{ticker}_{statement}.json"

def is_cache_fresh(ticker, index):
    """Check if cached data is within TTL."""
    if ticker not in index:
        return False
    fetched = index[ticker].get("fetched_at", "")
    if not fetched:
        return False
    try:
        dt = datetime.fromisoformat(fetched)
        return (datetime.now() - dt) < timedelta(days=CACHE_TTL_DAYS)
    except:
        return False

def save_raw_cache(ticker, statement, data):
    path = cache_path(ticker, statement)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

def load_raw_cache(ticker, statement):
    path = cache_path(ticker, statement)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None

def save_computed(ticker, data):
    path = COMPUTED_DIR / f"{ticker}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ═════════════════════════════════════════════════════════════════════════════
# FMP API LAYER
# ═════════════════════════════════════════════════════════════════════════════

def api_call(endpoint, params):
    params["apikey"] = FMP_API_KEY
    url = f"{BASE_URL}/{endpoint}"
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        time.sleep(DELAY)
        data = r.json()
        if isinstance(data, dict) and "Error Message" in data:
            return None
        return data
    except Exception as e:
        print(f"    API error [{endpoint}]: {e}")
        return None

def fetch_ticker_data(ticker, force_refresh=False):
    """Fetch all statements for a ticker, using cache when available."""
    api_ticker = TICKER_MAP.get(ticker, ticker)
    index = load_cache_index()

    if not force_refresh and is_cache_fresh(ticker, index):
        # Load from cache
        data = {}
        for stmt in ["income", "balance", "cashflow", "profile", "metrics"]:
            cached = load_raw_cache(ticker, stmt)
            if cached is not None:
                data[stmt] = cached
            else:
                # Partial cache miss — refetch all
                break
        else:
            return data  # All found in cache

    # Fetch from API
    statements = {
        "income": ("income-statement", {"symbol": api_ticker, "period": "annual", "limit": YEARS_TO_FETCH}),
        "balance": ("balance-sheet-statement", {"symbol": api_ticker, "period": "annual", "limit": YEARS_TO_FETCH}),
        "cashflow": ("cash-flow-statement", {"symbol": api_ticker, "period": "annual", "limit": YEARS_TO_FETCH}),
        "profile": ("profile", {"symbol": api_ticker}),
        "metrics": ("key-metrics-ttm", {"symbol": api_ticker}),
    }

    data = {}
    api_calls = 0
    for key, (endpoint, params) in statements.items():
        result = api_call(endpoint, params)
        api_calls += 1
        if result is not None:
            data[key] = result
            save_raw_cache(ticker, key, result)
        else:
            data[key] = None

    # Update index
    index[ticker] = {
        "fetched_at": datetime.now().isoformat(),
        "api_calls": api_calls,
        "api_ticker": api_ticker,
        "status": "ok" if all(data.get(k) for k in ["income", "balance", "cashflow"]) else "partial",
    }
    save_cache_index(index)
    return data


# ═════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def safe(val, default=0):
    return val if val is not None else default

def safe_div(a, b, default=None):
    if a is None or b is None or b == 0:
        return default
    return a / b

def get(d, *keys, default=0):
    """Get first available key from dict."""
    if not d:
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default

def cagr(begin, end, years):
    if begin is None or end is None or years <= 0:
        return None
    if begin <= 0 or end <= 0:
        return None
    try:
        return (end / begin) ** (1 / years) - 1
    except:
        return None

def linear_slope(values):
    """Simple linear regression slope on a list of (index, value) pairs."""
    pts = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(pts) < 3:
        return None
    n = len(pts)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sxx = sum(p[0]**2 for p in pts)
    sxy = sum(p[0]*p[1] for p in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    return (n * sxy - sx * sy) / denom

def std_dev(values):
    """Standard deviation of non-None values."""
    vals = [v for v in values if v is not None]
    if len(vals) < 3:
        return None
    mean = sum(vals) / len(vals)
    variance = sum((v - mean)**2 for v in vals) / len(vals)
    return math.sqrt(variance)


# ═════════════════════════════════════════════════════════════════════════════
# CORE COMPUTATION
# ═════════════════════════════════════════════════════════════════════════════

def compute_all_metrics(ticker, raw_data):
    """Compute all metrics from raw API data. Returns dict with everything."""

    inc_list = raw_data.get("income") or []
    bs_list = raw_data.get("balance") or []
    cf_list = raw_data.get("cashflow") or []
    profile = raw_data.get("profile")
    km = raw_data.get("metrics")

    if not inc_list or not bs_list or not cf_list:
        return {"ticker": ticker, "error": "missing_statements"}

    # Sort oldest → newest for time-series (FMP returns newest first)
    inc_list = sorted(inc_list, key=lambda x: x.get("date", ""), reverse=False)
    bs_list = sorted(bs_list, key=lambda x: x.get("date", ""), reverse=False)
    cf_list = sorted(cf_list, key=lambda x: x.get("date", ""), reverse=False)

    p = profile[0] if isinstance(profile, list) and profile else (profile or {})
    k = km[0] if isinstance(km, list) and km else (km or {})

    mkt_cap = get(p, "marketCap", "mktCap")
    ev = get(k, "enterpriseValueTTM")

    # ═══════════════════════════════════════════════════════════════════════
    # YEAR-BY-YEAR SERIES
    # ═══════════════════════════════════════════════════════════════════════

    years = []
    roic_series = []
    roic_excash_series = []
    gm_series = []
    rev_series = []
    shares_series = []
    nd_ebitda_series = []
    fcf_ni_series = []
    sbc_rev_series = []
    nopat_series = []
    ic_series = []
    ic_excash_series = []
    ocf_series = []
    capex_series = []
    dep_series = []
    fcf_series = []
    sbc_series = []
    ppe_series = []

    n_years = min(len(inc_list), len(bs_list), len(cf_list))

    for idx in range(n_years):
        i = inc_list[idx]
        b = bs_list[idx]
        c = cf_list[idx]

        yr = get(i, "calendarYear", "date", default="?")
        if isinstance(yr, str) and len(yr) > 4:
            yr = yr[:4]
        years.append(yr)

        # Core fields
        revenue = get(i, "revenue")
        gross_profit = get(i, "grossProfit")
        op_income = get(i, "operatingIncome")
        ebit = get(i, "ebit", "operatingIncome")
        tax_exp = get(i, "incomeTaxExpense")
        pretax = get(i, "incomeBeforeTax")
        net_inc = get(i, "netIncome")
        dep_inc = get(i, "depreciationAndAmortization")

        total_assets = get(b, "totalAssets")
        cash = get(b, "cashAndCashEquivalents")
        st_invest = get(b, "shortTermInvestments")
        lt_invest = get(b, "longTermInvestments")
        total_equity = get(b, "totalStockholdersEquity")
        total_debt_b = get(b, "totalDebt")
        st_debt = get(b, "shortTermDebt")
        lt_debt = get(b, "longTermDebt")
        total_liabs = get(b, "totalLiabilities")
        total_ca = get(b, "totalCurrentAssets")
        total_cl = get(b, "totalCurrentLiabilities")
        net_ppe = get(b, "propertyPlantEquipmentNet")
        goodwill = get(b, "goodwill")
        intangibles = get(b, "intangibleAssets")
        shares = get(b, "commonStockSharesOutstanding",
                      default=get(i, "weightedAverageShsOut",
                                   "weightedAverageShsOutDil"))

        ocf = get(c, "operatingCashFlow")
        capex = abs(get(c, "capitalExpenditure", default=0))
        fcf = get(c, "freeCashFlow")
        sbc = get(c, "stockBasedCompensation")
        dep_cf = get(c, "depreciationAndAmortization")
        buybacks = abs(get(c, "commonStockRepurchased", default=0))
        dividends = abs(get(c, "dividendsPaid", default=0))

        dep = dep_cf if dep_cf else dep_inc

        # Tax rate
        eff_tax = safe_div(tax_exp, pretax, default=0.21)
        if eff_tax is not None and (eff_tax < 0 or eff_tax > 0.5):
            eff_tax = 0.21

        # NOPAT
        nopat = ebit * (1 - eff_tax) if ebit else None

        # Invested Capital = Total Equity + Total Debt - Cash
        if not total_debt_b:
            total_debt_b = st_debt + lt_debt
        ic = total_equity + total_debt_b - cash if total_equity else None

        # IC ex-cash (remove ALL financial assets for cleaner operating view)
        excess_cash = cash + st_invest + lt_invest
        ic_excash = total_equity + total_debt_b  # don't subtract cash
        # Actually, ROIC ex-cash = NOPAT / (IC + excess_cash_back) ... no.
        # Correct: IC ex-cash = Equity + Debt (no cash subtraction)
        # This gives the capital deployed in operations, without netting financial assets

        # ROIC
        roic = safe_div(nopat, ic) if ic and ic > 0 else None
        roic_excash = safe_div(nopat, ic_excash) if ic_excash and ic_excash > 0 else None

        # Gross Margin
        gm = safe_div(gross_profit, revenue)

        # ND/EBITDA
        net_debt = total_debt_b - cash
        ebitda = (ebit + dep) if ebit and dep else (op_income + dep if op_income and dep else None)
        nd_ebitda = safe_div(net_debt, ebitda) if ebitda and ebitda > 0 else None

        # FCF/NI
        fcf_ni = safe_div(fcf, net_inc) if net_inc and net_inc > 0 else None

        # SBC/Rev
        sbc_rev = safe_div(sbc, revenue)

        # Store series
        roic_series.append(roic)
        roic_excash_series.append(roic_excash)
        gm_series.append(gm)
        rev_series.append(revenue)
        shares_series.append(shares)
        nd_ebitda_series.append(nd_ebitda)
        fcf_ni_series.append(fcf_ni)
        sbc_rev_series.append(sbc_rev)
        nopat_series.append(nopat)
        ic_series.append(ic)
        ic_excash_series.append(ic_excash)
        ocf_series.append(ocf)
        capex_series.append(capex)
        dep_series.append(dep)
        fcf_series.append(fcf)
        sbc_series.append(sbc)
        ppe_series.append(net_ppe)

    # ═══════════════════════════════════════════════════════════════════════
    # TREND METRICS (computed from series)
    # ═══════════════════════════════════════════════════════════════════════

    roic_slope = linear_slope(roic_series)
    roic_std = std_dev(roic_series)
    roic_excash_slope = linear_slope(roic_excash_series)
    gm_slope = linear_slope(gm_series)
    nd_ebitda_slope = linear_slope(nd_ebitda_series)

    # Revenue CAGR
    rev_vals = [r for r in rev_series if r and r > 0]
    rev_cagr = cagr(rev_vals[0], rev_vals[-1], len(rev_vals)-1) if len(rev_vals) >= 2 else None

    # Share count CAGR (negative = buyback shrinkage = good)
    sh_vals = [s for s in shares_series if s and s > 0]
    shares_cagr = cagr(sh_vals[0], sh_vals[-1], len(sh_vals)-1) if len(sh_vals) >= 2 else None

    # ROIC range
    roic_vals = [r for r in roic_series if r is not None]
    roic_min = min(roic_vals) if roic_vals else None
    roic_max = max(roic_vals) if roic_vals else None
    roic_avg = sum(roic_vals)/len(roic_vals) if roic_vals else None
    roic_latest = roic_vals[-1] if roic_vals else None

    # ROIC ex-cash
    roic_ec_vals = [r for r in roic_excash_series if r is not None]
    roic_ec_latest = roic_ec_vals[-1] if roic_ec_vals else None
    roic_ec_avg = sum(roic_ec_vals)/len(roic_ec_vals) if roic_ec_vals else None

    # ROIIC (incremental: change in NOPAT / change in IC)
    roiic_pairs = []
    for idx in range(1, len(nopat_series)):
        n0, n1 = nopat_series[idx-1], nopat_series[idx]
        c0, c1 = ic_series[idx-1], ic_series[idx]
        if all(v is not None for v in [n0, n1, c0, c1]):
            delta_nopat = n1 - n0
            delta_ic = c1 - c0
            if delta_ic != 0:
                roiic_pairs.append(safe_div(delta_nopat, delta_ic))

    # ROIIC ex-cash
    roiic_excash_pairs = []
    for idx in range(1, len(nopat_series)):
        n0, n1 = nopat_series[idx-1], nopat_series[idx]
        c0, c1 = ic_excash_series[idx-1], ic_excash_series[idx]
        if all(v is not None for v in [n0, n1, c0, c1]):
            delta_nopat = n1 - n0
            delta_ic = c1 - c0
            if delta_ic != 0:
                roiic_excash_pairs.append(safe_div(delta_nopat, delta_ic))

    # Multi-year ROIIC (endpoints)
    roiic_full = None
    roiic_excash_full = None
    if len(nopat_series) >= 2 and len(ic_series) >= 2:
        n_first, n_last = nopat_series[0], nopat_series[-1]
        c_first, c_last = ic_series[0], ic_series[-1]
        if all(v is not None for v in [n_first, n_last, c_first, c_last]):
            delta_ic = c_last - c_first
            if delta_ic != 0:
                roiic_full = (n_last - n_first) / delta_ic

    if len(nopat_series) >= 2 and len(ic_excash_series) >= 2:
        n_first, n_last = nopat_series[0], nopat_series[-1]
        c_first, c_last = ic_excash_series[0], ic_excash_series[-1]
        if all(v is not None for v in [n_first, n_last, c_first, c_last]):
            delta_ic = c_last - c_first
            if delta_ic != 0:
                roiic_excash_full = (n_last - n_first) / delta_ic

    # ═══════════════════════════════════════════════════════════════════════
    # CAPITAL INTENSITY (most recent year)
    # ═══════════════════════════════════════════════════════════════════════

    # Use most recent data
    b_latest = bs_list[-1] if bs_list else {}
    i_latest = inc_list[-1] if inc_list else {}
    c_latest = cf_list[-1] if cf_list else {}

    revenue_latest = get(i_latest, "revenue")
    net_ppe_latest = get(b_latest, "propertyPlantEquipmentNet")
    ocf_latest = get(c_latest, "operatingCashFlow")
    capex_latest = abs(get(c_latest, "capitalExpenditure", default=0))
    dep_latest = dep_series[-1] if dep_series else 0
    fcf_latest = get(c_latest, "freeCashFlow")
    sbc_latest = get(c_latest, "stockBasedCompensation")

    total_assets_l = get(b_latest, "totalAssets")
    cash_l = get(b_latest, "cashAndCashEquivalents")
    st_inv_l = get(b_latest, "shortTermInvestments")
    lt_inv_l = get(b_latest, "longTermInvestments")
    total_liabs_l = get(b_latest, "totalLiabilities")
    total_debt_l = get(b_latest, "totalDebt") or (get(b_latest, "shortTermDebt") + get(b_latest, "longTermDebt"))
    total_ca_l = get(b_latest, "totalCurrentAssets")
    total_cl_l = get(b_latest, "totalCurrentLiabilities")
    st_debt_l = get(b_latest, "shortTermDebt")

    # 1. NOA
    financial_assets = cash_l + st_inv_l + lt_inv_l
    operating_assets = total_assets_l - financial_assets
    operating_liabilities = total_liabs_l - total_debt_l
    noa = operating_assets - operating_liabilities

    # 2. PP&E / Revenue
    ppe_to_rev = safe_div(net_ppe_latest, revenue_latest)

    # 3. Working Capital / Revenue
    op_ca = total_ca_l - cash_l - st_inv_l
    op_cl = total_cl_l - st_debt_l
    working_capital = op_ca - op_cl
    wc_to_rev = safe_div(working_capital, revenue_latest)

    # 4. OCF / PP&E
    ocf_to_ppe = safe_div(ocf_latest, net_ppe_latest)

    # 5. CapEx / Depreciation
    capex_to_dep = safe_div(capex_latest, dep_latest)

    # 6. Maintenance CapEx / OCF
    maint_capex = min(capex_latest, dep_latest) if dep_latest and dep_latest > 0 else dep_latest or 0
    maint_to_ocf = safe_div(maint_capex, ocf_latest)
    growth_capex = max(0, capex_latest - maint_capex)

    # Derived
    noa_to_ev = safe_div(noa, ev)
    noa_to_mktcap = safe_div(noa, mkt_cap)

    # SBC-adjusted FCF
    sbc_adj_fcf = (fcf_latest - sbc_latest) if fcf_latest and sbc_latest else fcf_latest
    sbc_to_fcf = safe_div(sbc_latest, fcf_latest) if fcf_latest and fcf_latest > 0 else None
    sbc_to_rev_latest = safe_div(sbc_latest, revenue_latest)

    # SBC-adjusted FCF/sh CAGR
    sbc_adj_fcf_series = []
    for idx in range(len(fcf_series)):
        f = fcf_series[idx]
        s = sbc_series[idx]
        sh = shares_series[idx]
        if f is not None and s is not None and sh and sh > 0:
            sbc_adj_fcf_series.append((f - s) / sh)
        else:
            sbc_adj_fcf_series.append(None)
    
    sbc_adj_vals = [v for v in sbc_adj_fcf_series if v is not None and v > 0]
    sbc_adj_fcf_cagr = cagr(sbc_adj_vals[0], sbc_adj_vals[-1], len(sbc_adj_vals)-1) if len(sbc_adj_vals) >= 2 else None

    # NOPAT/sh series
    nopat_per_sh = []
    for idx in range(len(nopat_series)):
        n = nopat_series[idx]
        sh = shares_series[idx]
        if n is not None and sh and sh > 0:
            nopat_per_sh.append(n / sh)
        else:
            nopat_per_sh.append(None)

    nps_vals = [v for v in nopat_per_sh if v is not None and v > 0]
    nopat_sh_cagr = cagr(nps_vals[0], nps_vals[-1], len(nps_vals)-1) if len(nps_vals) >= 2 else None

    # FCF/sh series
    fcf_per_sh = []
    for idx in range(len(fcf_series)):
        f = fcf_series[idx]
        sh = shares_series[idx]
        if f is not None and sh and sh > 0:
            fcf_per_sh.append(f / sh)
        else:
            fcf_per_sh.append(None)

    fps_vals = [v for v in fcf_per_sh if v is not None and v > 0]
    fcf_sh_cagr = cagr(fps_vals[0], fps_vals[-1], len(fps_vals)-1) if len(fps_vals) >= 2 else None

    # ═══════════════════════════════════════════════════════════════════════
    # RED FLAGS
    # ═══════════════════════════════════════════════════════════════════════

    flags = []

    # FCF/NI excessive
    fcf_ni_latest = fcf_ni_series[-1] if fcf_ni_series else None
    if fcf_ni_latest and fcf_ni_latest > 2.0:
        flags.append(f"FCF/NI {fcf_ni_latest:.0%} — SBC distortion likely")

    # SBC/FCF high
    if sbc_to_fcf and sbc_to_fcf > 0.30:
        flags.append(f"SBC/FCF {sbc_to_fcf:.0%} — significant dilution")

    # Share dilution
    if shares_cagr and shares_cagr > 0.03:
        flags.append(f"Shares CAGR +{shares_cagr:.1%}/yr — persistent dilution")

    # ROIC cyclicality
    if roic_std and roic_std > 0.05:
        flags.append(f"ROIC StdDev {roic_std:.1%} — cyclical business")

    # ROIC declining
    if roic_slope is not None and roic_slope < -0.02:
        flags.append(f"ROIC slope {roic_slope:.3f} — declining returns")

    # Gross margin eroding
    if gm_slope is not None and gm_slope < -0.005:
        flags.append(f"GM slope {gm_slope:.4f} — eroding moat")

    # CapEx/Dep aggressive
    if capex_to_dep and capex_to_dep > 2.5:
        flags.append(f"CapEx/Dep {capex_to_dep:.1f}x — aggressive expansion")

    # High maintenance burden
    if maint_to_ocf and maint_to_ocf > 0.50:
        flags.append(f"MaintCX/OCF {maint_to_ocf:.0%} — high maint burden")

    # Leveraging up
    if nd_ebitda_slope is not None and nd_ebitda_slope > 0.2:
        flags.append(f"ND/EBITDA slope +{nd_ebitda_slope:.2f} — leverage rising")

    # Small IC (ratio instability)
    if ic_series and ic_series[-1] is not None and ic_series[-1] < 1e9 and ic_series[-1] > 0:
        flags.append(f"IC ${ic_series[-1]/1e9:.1f}B — below $1B, ratio instability")

    # Negative NOA
    if noa < 0:
        flags.append(f"NOA ${noa/1e9:.1f}B — negative (op liabs > op assets)")

    # ═══════════════════════════════════════════════════════════════════════
    # ASSEMBLE RESULT
    # ═══════════════════════════════════════════════════════════════════════

    result = {
        "ticker": ticker,
        "error": None,
        "years": years,
        "n_years": n_years,
        "mkt_cap_B": safe_div(mkt_cap, 1e9),
        "ev_B": safe_div(ev, 1e9),

        # Year-by-year series
        "roic_by_year": {y: r for y, r in zip(years, roic_series)},
        "roic_excash_by_year": {y: r for y, r in zip(years, roic_excash_series)},
        "gm_by_year": {y: r for y, r in zip(years, gm_series)},
        "revenue_by_year": {y: safe_div(r, 1e9) for y, r in zip(years, rev_series)},
        "shares_by_year": {y: safe_div(s, 1e6) for y, s in zip(years, shares_series)},
        "nd_ebitda_by_year": {y: r for y, r in zip(years, nd_ebitda_series)},
        "fcf_ni_by_year": {y: r for y, r in zip(years, fcf_ni_series)},
        "sbc_rev_by_year": {y: r for y, r in zip(years, sbc_rev_series)},
        "nopat_per_sh_by_year": {y: r for y, r in zip(years, nopat_per_sh)},
        "fcf_per_sh_by_year": {y: r for y, r in zip(years, fcf_per_sh)},
        "sbc_adj_fcf_per_sh_by_year": {y: r for y, r in zip(years, sbc_adj_fcf_series)},
        "ic_by_year": {y: safe_div(c, 1e9) for y, c in zip(years, ic_series)},

        # ROIC summary
        "roic_latest": roic_latest,
        "roic_avg": roic_avg,
        "roic_min": roic_min,
        "roic_max": roic_max,
        "roic_slope": roic_slope,
        "roic_std": roic_std,
        "roic_excash_latest": roic_ec_latest,
        "roic_excash_avg": roic_ec_avg,
        "roic_excash_slope": roic_excash_slope,

        # ROIIC
        "roiic_full_period": roiic_full,
        "roiic_excash_full_period": roiic_excash_full,
        "roiic_annual_pairs": roiic_pairs,
        "roiic_excash_annual_pairs": roiic_excash_pairs,

        # Growth
        "rev_cagr": rev_cagr,
        "nopat_sh_cagr": nopat_sh_cagr,
        "fcf_sh_cagr": fcf_sh_cagr,
        "sbc_adj_fcf_sh_cagr": sbc_adj_fcf_cagr,
        "shares_cagr": shares_cagr,

        # Trends
        "gm_slope": gm_slope,
        "nd_ebitda_slope": nd_ebitda_slope,

        # Capital intensity (6 metrics)
        "noa_B": safe_div(noa, 1e9),
        "ppe_to_rev": ppe_to_rev,
        "wc_to_rev": wc_to_rev,
        "ocf_to_ppe": ocf_to_ppe,
        "capex_to_dep": capex_to_dep,
        "maint_to_ocf": maint_to_ocf,
        "growth_capex_B": safe_div(growth_capex, 1e9),

        # Derived
        "noa_to_ev": noa_to_ev,
        "noa_to_mktcap": noa_to_mktcap,
        "sbc_to_fcf": sbc_to_fcf,
        "sbc_to_rev": sbc_to_rev_latest,
        "sbc_adj_fcf_B": safe_div(sbc_adj_fcf, 1e9),

        # FCF/NI latest
        "fcf_ni_latest": fcf_ni_latest,

        # Red flags
        "flags": flags,
        "flag_count": len(flags),
    }

    return result


# ═════════════════════════════════════════════════════════════════════════════
# OUTPUT / REPORTING
# ═════════════════════════════════════════════════════════════════════════════

def print_summary_table(results):
    """Print the main summary table."""
    print("\n" + "=" * 180)
    print(f"{'#':>3} {'Sym':6} {'ROIC':>6} {'RoIC':>6} {'ROIC':>6} {'ROIC':>6} {'RoIC':>7} "
          f"{'GM':>6} {'GM':>7} {'Rev':>6} {'Shr':>6} {'NOA/':>6} "
          f"{'PP&E/':>6} {'OCF/':>6} {'CX/':>5} {'MCX/':>5} {'SBC/':>5} {'SBC-adj':>8} {'ND/EB':>6} "
          f"{'#F':>3}")
    print(f"{'':>3} {'':6} {'Avg':>6} {'ExC':>6} {'Slope':>6} {'StDv':>6} {'II':>7} "
          f"{'Avg':>6} {'Slope':>7} {'CAGR':>6} {'CAGR':>6} {'EV':>6} "
          f"{'Rev':>6} {'PPE':>6} {'Dep':>5} {'OCF':>5} {'FCF':>5} {'FCF CAGR':>8} {'Slope':>6} "
          f"{'':>3}")
    print("-" * 180)

    for idx, r in enumerate(results):
        def fp(v, w=6):
            return f"{v:>{w}.1%}" if v is not None else f"{'---':>{w}}"
        def fm(v, w=5):
            return f"{v:>{w}.1f}x" if v is not None else f"{'---':>{w}}"
        def ff(v, w=6):
            return f"{v:>{w}.3f}" if v is not None else f"{'---':>{w}}"

        print(f"{idx+1:>3} {r['ticker']:6} "
              f"{fp(r.get('roic_avg'))} "
              f"{fp(r.get('roic_excash_avg'))} "
              f"{ff(r.get('roic_slope'))} "
              f"{fp(r.get('roic_std'))} "
              f"{fp(r.get('roiic_full_period'), 7)} "
              f"{fp(r.get('gm_slope') and sum(v for v in r.get('gm_by_year',{}).values() if v)/max(1,sum(1 for v in r.get('gm_by_year',{}).values() if v)))} "
              f"{ff(r.get('gm_slope'), 7)} "
              f"{fp(r.get('rev_cagr'))} "
              f"{fp(r.get('shares_cagr'))} "
              f"{fp(r.get('noa_to_ev'))} "
              f"{fp(r.get('ppe_to_rev'))} "
              f"{fm(r.get('ocf_to_ppe'))} "
              f"{fm(r.get('capex_to_dep'))} "
              f"{fp(r.get('maint_to_ocf'), 5)} "
              f"{fp(r.get('sbc_to_fcf'), 5)} "
              f"{fp(r.get('sbc_adj_fcf_sh_cagr'), 8)} "
              f"{ff(r.get('nd_ebitda_slope'))} "
              f"{r.get('flag_count', 0):>3}")


def print_roic_series(results):
    """Print ROIC year-by-year for all stocks."""
    # Collect all years
    all_years = sorted(set(y for r in results for y in r.get("years", [])))
    if not all_years:
        return

    print("\n" + "=" * 120)
    print("ROIC BY YEAR (operating returns trend)")
    print("=" * 120)
    header = f"{'Sym':6}" + "".join(f"{y:>10}" for y in all_years) + f"{'Slope':>10} {'StDv':>8} {'ExCash':>8}"
    print(header)
    print("-" * len(header))

    for r in results:
        roic_yr = r.get("roic_by_year", {})
        line = f"{r['ticker']:6}"
        for y in all_years:
            v = roic_yr.get(y)
            line += f"{v:>9.1%} " if v is not None else f"{'---':>10}"
        sl = r.get("roic_slope")
        sd = r.get("roic_std")
        ec = r.get("roic_excash_avg")
        line += f"{sl:>9.3f} " if sl is not None else f"{'---':>10}"
        line += f"{sd:>7.1%} " if sd is not None else f"{'---':>8}"
        line += f"{ec:>7.1%} " if ec is not None else f"{'---':>8}"
        print(line)


def print_red_flags(results):
    """Print all red flags."""
    print("\n" + "=" * 120)
    print("RED FLAGS SUMMARY")
    print("=" * 120)

    flagged = [r for r in results if r.get("flags")]
    clean = [r for r in results if not r.get("flags")]

    for r in sorted(flagged, key=lambda x: -x.get("flag_count", 0)):
        print(f"\n  {r['ticker']} ({r['flag_count']} flags):")
        for f in r["flags"]:
            print(f"    ⚠️  {f}")

    print(f"\n  ✅ Clean (0 flags): {', '.join(r['ticker'] for r in clean)}")
    print(f"\n  Summary: {len(flagged)} stocks flagged, {len(clean)} clean")


def export_csv(results):
    """Export flat CSV for spreadsheet analysis."""
    if not results:
        return

    # Flat row per ticker
    rows = []
    for r in results:
        row = {
            "ticker": r["ticker"],
            "mkt_cap_B": r.get("mkt_cap_B"),
            "ev_B": r.get("ev_B"),
            "roic_latest": r.get("roic_latest"),
            "roic_avg": r.get("roic_avg"),
            "roic_min": r.get("roic_min"),
            "roic_max": r.get("roic_max"),
            "roic_slope": r.get("roic_slope"),
            "roic_std": r.get("roic_std"),
            "roic_excash_latest": r.get("roic_excash_latest"),
            "roic_excash_avg": r.get("roic_excash_avg"),
            "roic_excash_slope": r.get("roic_excash_slope"),
            "roiic_full": r.get("roiic_full_period"),
            "roiic_excash_full": r.get("roiic_excash_full_period"),
            "rev_cagr": r.get("rev_cagr"),
            "nopat_sh_cagr": r.get("nopat_sh_cagr"),
            "fcf_sh_cagr": r.get("fcf_sh_cagr"),
            "sbc_adj_fcf_sh_cagr": r.get("sbc_adj_fcf_sh_cagr"),
            "shares_cagr": r.get("shares_cagr"),
            "gm_slope": r.get("gm_slope"),
            "nd_ebitda_slope": r.get("nd_ebitda_slope"),
            "noa_B": r.get("noa_B"),
            "ppe_to_rev": r.get("ppe_to_rev"),
            "wc_to_rev": r.get("wc_to_rev"),
            "ocf_to_ppe": r.get("ocf_to_ppe"),
            "capex_to_dep": r.get("capex_to_dep"),
            "maint_to_ocf": r.get("maint_to_ocf"),
            "growth_capex_B": r.get("growth_capex_B"),
            "noa_to_ev": r.get("noa_to_ev"),
            "noa_to_mktcap": r.get("noa_to_mktcap"),
            "sbc_to_fcf": r.get("sbc_to_fcf"),
            "sbc_to_rev": r.get("sbc_to_rev"),
            "sbc_adj_fcf_B": r.get("sbc_adj_fcf_B"),
            "fcf_ni_latest": r.get("fcf_ni_latest"),
            "flag_count": r.get("flag_count"),
            "flags": " | ".join(r.get("flags", [])),
        }

        # Add ROIC by year
        for y, v in r.get("roic_by_year", {}).items():
            row[f"roic_{y}"] = v
        for y, v in r.get("gm_by_year", {}).items():
            row[f"gm_{y}"] = v
        for y, v in r.get("revenue_by_year", {}).items():
            row[f"rev_B_{y}"] = v
        for y, v in r.get("shares_by_year", {}).items():
            row[f"shares_M_{y}"] = v
        for y, v in r.get("nd_ebitda_by_year", {}).items():
            row[f"nd_ebitda_{y}"] = v
        for y, v in r.get("sbc_rev_by_year", {}).items():
            row[f"sbc_rev_{y}"] = v
        for y, v in r.get("ic_by_year", {}).items():
            row[f"ic_B_{y}"] = v

        rows.append(row)

    # Write CSV
    outpath = EXPORT_DIR / "v4_metrics_93.csv"
    all_keys = []
    for row in rows:
        for k in row.keys():
            if k not in all_keys:
                all_keys.append(k)

    with open(outpath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ CSV exported: {outpath}")

    # Also export year-by-year series as separate CSV
    series_path = EXPORT_DIR / "v4_yearly_series.csv"
    series_rows = []
    for r in results:
        for yr_idx, yr in enumerate(r.get("years", [])):
            series_rows.append({
                "ticker": r["ticker"],
                "year": yr,
                "roic": (r.get("roic_by_year") or {}).get(yr),
                "roic_excash": (r.get("roic_excash_by_year") or {}).get(yr),
                "gross_margin": (r.get("gm_by_year") or {}).get(yr),
                "revenue_B": (r.get("revenue_by_year") or {}).get(yr),
                "shares_M": (r.get("shares_by_year") or {}).get(yr),
                "nd_ebitda": (r.get("nd_ebitda_by_year") or {}).get(yr),
                "fcf_ni": (r.get("fcf_ni_by_year") or {}).get(yr),
                "sbc_rev": (r.get("sbc_rev_by_year") or {}).get(yr),
                "nopat_per_sh": (r.get("nopat_per_sh_by_year") or {}).get(yr),
                "fcf_per_sh": (r.get("fcf_per_sh_by_year") or {}).get(yr),
                "sbc_adj_fcf_per_sh": (r.get("sbc_adj_fcf_per_sh_by_year") or {}).get(yr),
                "ic_B": (r.get("ic_by_year") or {}).get(yr),
            })

    if series_rows:
        s_keys = list(series_rows[0].keys())
        with open(series_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=s_keys)
            writer.writeheader()
            writer.writerows(series_rows)
        print(f"✅ Year-by-year series: {series_path}")

    return outpath


# ═════════════════════════════════════════════════════════════════════════════
# SYNC HELPER
# ═════════════════════════════════════════════════════════════════════════════

def sync_cache():
    """Copy cache to iCloud and Google Drive if available."""
    import shutil

    sync_targets = [
        Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "capital_compounders" / "cache",
        Path.home() / "Google Drive" / "My Drive" / "capital_compounders" / "cache",
    ]

    for target in sync_targets:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(CACHE_DIR, target)
            print(f"✅ Synced to: {target}")
        except Exception as e:
            print(f"⚠️  Sync failed for {target}: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Capital Compounders v4 Deep Metrics")
    parser.add_argument("--tickers", nargs="+", help="Specific tickers to run")
    parser.add_argument("--refresh", action="store_true", help="Force re-fetch from API")
    parser.add_argument("--cache-only", action="store_true", help="Use cached data only")
    parser.add_argument("--no-sync", action="store_true", help="Skip iCloud/GDrive sync")
    args = parser.parse_args()

    tickers = args.tickers or ALL_TICKERS

    print("=" * 100)
    print("CAPITAL COMPOUNDERS v4 — Deep Metrics Layer")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tickers: {len(tickers)} | Years: {YEARS_TO_FETCH} | Cache TTL: {CACHE_TTL_DAYS}d")
    print(f"Refresh: {args.refresh} | Cache-only: {args.cache_only}")
    print("=" * 100)

    results = []
    errors = []
    cache_hits = 0

    for idx, ticker in enumerate(tickers):
        pct = (idx + 1) / len(tickers) * 100
        print(f"  [{idx+1:3d}/{len(tickers)}] {ticker:6s} ({pct:.0f}%) ... ", end="", flush=True)

        if args.cache_only:
            # Load from computed cache
            comp_path = COMPUTED_DIR / f"{ticker}.json"
            if comp_path.exists():
                with open(comp_path) as f:
                    data = json.load(f)
                results.append(data)
                print("✅ (cached)")
                cache_hits += 1
                continue
            else:
                # Try raw cache
                raw_data = {}
                for stmt in ["income", "balance", "cashflow", "profile", "metrics"]:
                    cached = load_raw_cache(ticker, stmt)
                    if cached:
                        raw_data[stmt] = cached
                if raw_data.get("income") and raw_data.get("balance") and raw_data.get("cashflow"):
                    r = compute_all_metrics(ticker, raw_data)
                    if r.get("error"):
                        print(f"⚠️  {r['error']}")
                        errors.append(ticker)
                    else:
                        save_computed(ticker, r)
                        results.append(r)
                        print(f"✅ (computed from raw cache)")
                    continue
                print("⚠️  no cache available")
                errors.append(ticker)
                continue

        # Check if cache is fresh
        index = load_cache_index()
        if not args.refresh and is_cache_fresh(ticker, index):
            # Load from raw cache and compute
            raw_data = {}
            for stmt in ["income", "balance", "cashflow", "profile", "metrics"]:
                raw_data[stmt] = load_raw_cache(ticker, stmt)
            if raw_data.get("income") and raw_data.get("balance") and raw_data.get("cashflow"):
                r = compute_all_metrics(ticker, raw_data)
                if r.get("error"):
                    print(f"⚠️  {r['error']}")
                    errors.append(ticker)
                else:
                    save_computed(ticker, r)
                    results.append(r)
                    cache_hits += 1
                    print(f"✅ (cache hit) ROIC {r.get('roic_latest','?'):.1%}" if r.get('roic_latest') else "✅ (cache hit)")
                continue

        # Fetch from API
        raw_data = fetch_ticker_data(ticker, force_refresh=args.refresh)
        if not raw_data or not raw_data.get("income"):
            print("❌ API fetch failed")
            errors.append(ticker)
            continue

        r = compute_all_metrics(ticker, raw_data)
        if r.get("error"):
            print(f"⚠️  {r['error']}")
            errors.append(ticker)
        else:
            save_computed(ticker, r)
            results.append(r)
            roic = r.get('roic_latest')
            flags = r.get('flag_count', 0)
            print(f"✅ ROIC {roic:.1%} | {flags} flags" if roic else f"✅ {flags} flags")

    # ─── Reports ─────────────────────────────────────────────────────────
    if results:
        print_summary_table(results)
        print_roic_series(results)
        print_red_flags(results)
        csv_path = export_csv(results)

        # Sync
        if not args.no_sync:
            sync_cache()

    # ─── Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Processed: {len(results)} | Errors: {len(errors)} | Cache hits: {cache_hits}")
    if errors:
        print(f"Failed: {', '.join(errors)}")
    print(f"\nCache: {CACHE_DIR}")
    print(f"Exports: {EXPORT_DIR}")
    print("=" * 100)


if __name__ == "__main__":
    main()
