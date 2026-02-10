#!/usr/bin/env python3
"""
Capital Compounders v4.1 — Institutional Gate Screener
=======================================================
Reads from existing v4 raw cache (zero API calls).
Applies Gates 1–4 + calibrated flag layer from v4.1 methodology.
Classifies stocks into Tier 1 (Machines), Tier 2 (Cash Cows),
Tier 3 (Special Situations), Tier 4 (Exclude).

Gate 5 (IRR Valuation) deferred — run after reviewing G1–G4 results.

Usage:
  python3 capital_compounders_v41_screener.py              # Full run from cache
  python3 capital_compounders_v41_screener.py --verbose     # Show per-ticker gate detail
  python3 capital_compounders_v41_screener.py --ticker AAPL # Single ticker deep dive

Requires: cache/raw/ populated by capital_intensity_v4.py
Output:   cache/exports/v41_screener_results.csv
          cache/exports/v41_tier_summary.txt
"""

import json
import csv
import math
import sys
import argparse
from pathlib import Path
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────────────────────
PROJECT_DIR = Path(".")
CACHE_DIR = PROJECT_DIR / "cache"
RAW_DIR = CACHE_DIR / "raw"
EXPORT_DIR = CACHE_DIR / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

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

TICKER_MAP = {"ANTM": "ELV", "COG": "CTRA"}

# Financial sector tickers — evaluated on ROE/ROA instead of ROIC
FINANCIALS = {"JPM", "PNC", "BAP", "IBN", "AXP", "SYF", "ACGL", "ERIE", "HIG",
              "CB", "RNR", "BX"}


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def safe_div(a, b, default=None):
    if a is None or b is None or b == 0:
        return default
    return a / b

def get(d, *keys, default=0):
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
    vals = [v for v in values if v is not None]
    if len(vals) < 3:
        return None
    mean = sum(vals) / len(vals)
    variance = sum((v - mean)**2 for v in vals) / len(vals)
    return math.sqrt(variance)

def fmt_pct(v, w=7):
    return f"{v:>{w}.1%}" if v is not None else f"{'---':>{w}}"

def fmt_pct2(v, w=7):
    return f"{v:>{w}.2%}" if v is not None else f"{'---':>{w}}"

def fmt_x(v, w=6):
    return f"{v:>{w}.1f}x" if v is not None else f"{'---':>{w}}"

def fmt_f(v, w=7):
    return f"{v:>{w}.3f}" if v is not None else f"{'---':>{w}}"

def fmt_b(v, w=7):
    return f"${v:>{w-1}.1f}B" if v is not None else f"{'---':>{w}}"


# ═════════════════════════════════════════════════════════════════════════════
# DATA LOADING — Read from raw cache
# ═════════════════════════════════════════════════════════════════════════════

def load_raw(ticker, stmt):
    path = RAW_DIR / f"{ticker}_{stmt}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None

def load_ticker_data(ticker):
    """Load all raw statements from cache."""
    data = {}
    for stmt in ["income", "balance", "cashflow", "profile", "metrics"]:
        data[stmt] = load_raw(ticker, stmt)
    return data


# ═════════════════════════════════════════════════════════════════════════════
# COMPUTE ALL METRICS (same as v4, extended for v4.1 gates)
# ═════════════════════════════════════════════════════════════════════════════

def compute_metrics(ticker, raw_data):
    """Full metric computation from raw API data."""

    inc_list = raw_data.get("income") or []
    bs_list = raw_data.get("balance") or []
    cf_list = raw_data.get("cashflow") or []
    profile = raw_data.get("profile")
    km = raw_data.get("metrics")

    if not inc_list or not bs_list or not cf_list:
        return {"ticker": ticker, "error": "missing_statements"}

    # Sort oldest → newest
    inc_list = sorted(inc_list, key=lambda x: x.get("date", ""))
    bs_list = sorted(bs_list, key=lambda x: x.get("date", ""))
    cf_list = sorted(cf_list, key=lambda x: x.get("date", ""))

    p = profile[0] if isinstance(profile, list) and profile else (profile or {})
    k = km[0] if isinstance(km, list) and km else (km or {})

    mkt_cap = get(p, "marketCap", "mktCap")
    ev = get(k, "enterpriseValueTTM")
    sector = get(p, "sector", default="")
    industry = get(p, "industry", default="")

    # ═══════════════════════════════════════════════════════════════════════
    # YEAR-BY-YEAR SERIES
    # ═══════════════════════════════════════════════════════════════════════
    years, roic_s, roic_ec_s, gm_s, rev_s, shares_s = [], [], [], [], [], []
    nd_ebitda_s, fcf_ni_s, sbc_rev_s = [], [], []
    nopat_s, ic_s, ic_ec_s, ocf_s, capex_s, dep_s = [], [], [], [], [], []
    fcf_s, sbc_s, ppe_s, ni_s = [], [], [], []
    buyback_s, dividend_s, ebit_s, ebitda_s = [], [], [], []
    total_equity_s, total_assets_s, net_debt_s = [], [], []
    op_margin_s = []

    n_years = min(len(inc_list), len(bs_list), len(cf_list))

    for idx in range(n_years):
        i, b, c = inc_list[idx], bs_list[idx], cf_list[idx]

        yr = get(i, "calendarYear", "date", default="?")
        if isinstance(yr, str) and len(yr) > 4:
            yr = yr[:4]
        years.append(yr)

        revenue = get(i, "revenue")
        gross_profit = get(i, "grossProfit")
        ebit = get(i, "ebit", "operatingIncome")
        op_income = get(i, "operatingIncome")
        tax_exp = get(i, "incomeTaxExpense")
        pretax = get(i, "incomeBeforeTax")
        net_inc = get(i, "netIncome")
        dep_inc = get(i, "depreciationAndAmortization")

        total_assets = get(b, "totalAssets")
        cash = get(b, "cashAndCashEquivalents")
        st_invest = get(b, "shortTermInvestments")
        lt_invest = get(b, "longTermInvestments")
        total_equity = get(b, "totalStockholdersEquity")
        total_debt = get(b, "totalDebt") or (get(b, "shortTermDebt") + get(b, "longTermDebt"))
        total_liabs = get(b, "totalLiabilities")
        total_ca = get(b, "totalCurrentAssets")
        total_cl = get(b, "totalCurrentLiabilities")
        net_ppe = get(b, "propertyPlantEquipmentNet")
        st_debt = get(b, "shortTermDebt")
        shares = get(b, "commonStockSharesOutstanding",
                      default=get(i, "weightedAverageShsOut", "weightedAverageShsOutDil"))

        ocf = get(c, "operatingCashFlow")
        capex = abs(get(c, "capitalExpenditure", default=0))
        fcf = get(c, "freeCashFlow")
        sbc = get(c, "stockBasedCompensation")
        dep_cf = get(c, "depreciationAndAmortization")
        buybacks = abs(get(c, "commonStockRepurchased", default=0))
        dividends = abs(get(c, "dividendsPaid", default=0))
        int_exp = get(i, "interestExpense", default=0)

        dep = dep_cf if dep_cf else dep_inc

        # Tax rate
        eff_tax = safe_div(tax_exp, pretax, default=0.21)
        if eff_tax is not None and (eff_tax < 0 or eff_tax > 0.5):
            eff_tax = 0.21

        nopat = ebit * (1 - eff_tax) if ebit else None
        ic = total_equity + total_debt - cash if total_equity else None
        ic_excash = total_equity + total_debt if total_equity else None

        roic = safe_div(nopat, ic) if ic and ic > 0 else None
        roic_excash = safe_div(nopat, ic_excash) if ic_excash and ic_excash > 0 else None
        gm = safe_div(gross_profit, revenue)
        op_margin = safe_div(ebit, revenue)
        net_debt_val = total_debt - cash
        ebitda_val = (ebit + dep) if ebit and dep else None
        nd_ebitda = safe_div(net_debt_val, ebitda_val) if ebitda_val and ebitda_val > 0 else None
        fcf_ni = safe_div(fcf, net_inc) if net_inc and net_inc > 0 else None
        sbc_rev = safe_div(sbc, revenue)

        # ROE/ROA for financials
        roe = safe_div(net_inc, total_equity) if total_equity and total_equity > 0 else None
        roa = safe_div(net_inc, total_assets) if total_assets and total_assets > 0 else None

        roic_s.append(roic)
        roic_ec_s.append(roic_excash)
        gm_s.append(gm)
        rev_s.append(revenue)
        shares_s.append(shares)
        nd_ebitda_s.append(nd_ebitda)
        fcf_ni_s.append(fcf_ni)
        sbc_rev_s.append(sbc_rev)
        nopat_s.append(nopat)
        ic_s.append(ic)
        ic_ec_s.append(ic_excash)
        ocf_s.append(ocf)
        capex_s.append(capex)
        dep_s.append(dep)
        fcf_s.append(fcf)
        sbc_s.append(sbc)
        ppe_s.append(net_ppe)
        ni_s.append(net_inc)
        buyback_s.append(buybacks)
        dividend_s.append(dividends)
        ebit_s.append(ebit)
        ebitda_s.append(ebitda_val)
        total_equity_s.append(total_equity)
        total_assets_s.append(total_assets)
        net_debt_s.append(net_debt_val)
        op_margin_s.append(op_margin)

    # ═══════════════════════════════════════════════════════════════════════
    # TREND METRICS
    # ═══════════════════════════════════════════════════════════════════════
    roic_slope = linear_slope(roic_s)
    roic_std = std_dev(roic_s)
    gm_slope = linear_slope(gm_s)
    nd_ebitda_slope = linear_slope(nd_ebitda_s)

    roic_vals = [r for r in roic_s if r is not None]
    roic_min = min(roic_vals) if roic_vals else None
    roic_max = max(roic_vals) if roic_vals else None
    roic_avg = sum(roic_vals)/len(roic_vals) if roic_vals else None
    roic_latest = roic_vals[-1] if roic_vals else None

    roic_ec_vals = [r for r in roic_ec_s if r is not None]
    roic_ec_avg = sum(roic_ec_vals)/len(roic_ec_vals) if roic_ec_vals else None
    roic_ec_latest = roic_ec_vals[-1] if roic_ec_vals else None

    gm_vals = [g for g in gm_s if g is not None]
    gm_avg = sum(gm_vals)/len(gm_vals) if gm_vals else None
    gm_latest = gm_vals[-1] if gm_vals else None

    op_m_vals = [o for o in op_margin_s if o is not None]
    op_margin_avg = sum(op_m_vals)/len(op_m_vals) if op_m_vals else None

    # ROE / ROA for financials
    roe_vals = [safe_div(ni_s[i], total_equity_s[i])
                for i in range(n_years) if ni_s[i] and total_equity_s[i] and total_equity_s[i] > 0]
    roe_avg = sum(roe_vals)/len(roe_vals) if roe_vals else None
    roe_latest = roe_vals[-1] if roe_vals else None

    roa_vals = [safe_div(ni_s[i], total_assets_s[i])
                for i in range(n_years) if ni_s[i] and total_assets_s[i] and total_assets_s[i] > 0]
    roa_avg = sum(roa_vals)/len(roa_vals) if roa_vals else None

    # Revenue & share count CAGRs
    rev_v = [r for r in rev_s if r and r > 0]
    rev_cagr = cagr(rev_v[0], rev_v[-1], len(rev_v)-1) if len(rev_v) >= 2 else None
    sh_v = [s for s in shares_s if s and s > 0]
    shares_cagr = cagr(sh_v[0], sh_v[-1], len(sh_v)-1) if len(sh_v) >= 2 else None

    # ═══════════════════════════════════════════════════════════════════════
    # ROIIC / POWER / CRYld / TVCR
    # ═══════════════════════════════════════════════════════════════════════

    # Full-period ROIIC (endpoint to endpoint)
    roiic_full = None
    if len(nopat_s) >= 2 and len(ic_s) >= 2:
        n_first, n_last = nopat_s[0], nopat_s[-1]
        c_first, c_last = ic_s[0], ic_s[-1]
        if all(v is not None for v in [n_first, n_last, c_first, c_last]):
            delta_ic = c_last - c_first
            if delta_ic != 0:
                roiic_full = (n_last - n_first) / delta_ic

    # ROIIC capped at 100% for scoring
    roiic_capped = min(roiic_full, 1.0) if roiic_full is not None and roiic_full > 1.0 else roiic_full

    # Reinvestment Rate = ΔIC / Beginning NOPAT (avg of first 2 years)
    reinvest_rate = None
    if len(nopat_s) >= 2 and len(ic_s) >= 2:
        c_first, c_last = ic_s[0], ic_s[-1]
        nopat_begin = nopat_s[0]
        if all(v is not None for v in [c_first, c_last, nopat_begin]) and nopat_begin > 0:
            yrs = len(ic_s) - 1
            annual_reinvest = (c_last - c_first) / yrs if yrs > 0 else 0
            reinvest_rate = safe_div(annual_reinvest, nopat_begin)

    # Power = ROIIC × Reinvestment Rate
    power = None
    if roiic_capped is not None and reinvest_rate is not None:
        power = roiic_capped * reinvest_rate

    # CRYld = (Buybacks + Dividends) / Beginning IC
    cryld = None
    if ic_s and ic_s[0] and ic_s[0] > 0:
        # Average annual capital returns over the period
        total_returns = sum(buyback_s[i] + dividend_s[i] for i in range(n_years))
        avg_annual_returns = total_returns / n_years if n_years > 0 else 0
        cryld = safe_div(avg_annual_returns, ic_s[0])

    # TVCR = Power + CRYld
    tvcr = None
    p_val = power if power is not None else 0
    c_val = cryld if cryld is not None else 0
    if power is not None or cryld is not None:
        tvcr = p_val + c_val

    # ═══════════════════════════════════════════════════════════════════════
    # PER-SHARE GROWTH
    # ═══════════════════════════════════════════════════════════════════════

    # NOPAT/sh CAGR
    nopat_per_sh = [safe_div(nopat_s[i], shares_s[i]) for i in range(n_years)]
    nps_v = [v for v in nopat_per_sh if v is not None and v > 0]
    nopat_sh_cagr = cagr(nps_v[0], nps_v[-1], len(nps_v)-1) if len(nps_v) >= 2 else None

    # FCF/sh CAGR
    fcf_per_sh = [safe_div(fcf_s[i], shares_s[i]) for i in range(n_years)]
    fps_v = [v for v in fcf_per_sh if v is not None and v > 0]
    fcf_sh_cagr = cagr(fps_v[0], fps_v[-1], len(fps_v)-1) if len(fps_v) >= 2 else None

    # SBC-adjusted FCF/sh CAGR
    sbc_adj_per_sh = []
    for i in range(n_years):
        if fcf_s[i] is not None and sbc_s[i] is not None and shares_s[i] and shares_s[i] > 0:
            sbc_adj_per_sh.append((fcf_s[i] - sbc_s[i]) / shares_s[i])
        else:
            sbc_adj_per_sh.append(None)
    sbc_v = [v for v in sbc_adj_per_sh if v is not None and v > 0]
    sbc_adj_fcf_cagr = cagr(sbc_v[0], sbc_v[-1], len(sbc_v)-1) if len(sbc_v) >= 2 else None

    # Best per-share CAGR (for Gate 3)
    best_per_sh_cagr = None
    if nopat_sh_cagr is not None and fcf_sh_cagr is not None:
        best_per_sh_cagr = max(nopat_sh_cagr, fcf_sh_cagr)
    elif nopat_sh_cagr is not None:
        best_per_sh_cagr = nopat_sh_cagr
    elif fcf_sh_cagr is not None:
        best_per_sh_cagr = fcf_sh_cagr

    # ═══════════════════════════════════════════════════════════════════════
    # CAPITAL INTENSITY (latest year)
    # ═══════════════════════════════════════════════════════════════════════
    b_l = bs_list[-1] if bs_list else {}
    c_l = cf_list[-1] if cf_list else {}
    i_l = inc_list[-1] if inc_list else {}

    revenue_latest = get(i_l, "revenue")
    net_ppe_l = get(b_l, "propertyPlantEquipmentNet")
    ocf_l = get(c_l, "operatingCashFlow")
    capex_l = abs(get(c_l, "capitalExpenditure", default=0))
    dep_l = dep_s[-1] if dep_s else 0
    fcf_l = get(c_l, "freeCashFlow")
    sbc_l = get(c_l, "stockBasedCompensation")
    int_exp_l = get(i_l, "interestExpense", default=0)

    ta_l = get(b_l, "totalAssets")
    cash_l = get(b_l, "cashAndCashEquivalents")
    si_l = get(b_l, "shortTermInvestments")
    li_l = get(b_l, "longTermInvestments")
    tl_l = get(b_l, "totalLiabilities")
    td_l = get(b_l, "totalDebt") or (get(b_l, "shortTermDebt") + get(b_l, "longTermDebt"))
    tca_l = get(b_l, "totalCurrentAssets")
    tcl_l = get(b_l, "totalCurrentLiabilities")
    sd_l = get(b_l, "shortTermDebt")

    # NOA
    fin_assets = cash_l + si_l + li_l
    op_assets = ta_l - fin_assets
    op_liabs = tl_l - td_l
    noa = op_assets - op_liabs

    ppe_to_rev = safe_div(net_ppe_l, revenue_latest)
    ocf_to_ppe = safe_div(ocf_l, net_ppe_l)
    capex_to_dep = safe_div(capex_l, dep_l)
    maint_capex = min(capex_l, dep_l) if dep_l and dep_l > 0 else dep_l or 0
    maint_to_ocf = safe_div(maint_capex, ocf_l)
    noa_to_ev = safe_div(noa, ev)
    sbc_to_fcf = safe_div(sbc_l, fcf_l) if fcf_l and fcf_l > 0 else None

    # FCF/NI latest
    fcf_ni_latest = fcf_ni_s[-1] if fcf_ni_s else None

    # ND/EBITDA latest
    nd_ebitda_latest = nd_ebitda_s[-1] if nd_ebitda_s else None

    # IC latest
    ic_latest = ic_s[-1] if ic_s else None

    # Interest coverage
    ebit_latest = ebit_s[-1] if ebit_s else None
    int_coverage = safe_div(ebit_latest, int_exp_l) if int_exp_l and int_exp_l > 0 else None

    # CF recapture period
    nd_latest = net_debt_s[-1] if net_debt_s else None
    cf_recapture = safe_div(nd_latest, fcf_l) if fcf_l and fcf_l > 0 and nd_latest and nd_latest > 0 else None

    # ═══════════════════════════════════════════════════════════════════════
    # ASSEMBLE
    # ═══════════════════════════════════════════════════════════════════════
    return {
        "ticker": ticker,
        "error": None,
        "sector": sector,
        "industry": industry,
        "is_financial": ticker in FINANCIALS,
        "mkt_cap_B": safe_div(mkt_cap, 1e9),
        "ev_B": safe_div(ev, 1e9),
        "n_years": n_years,
        "years": years,

        # ROIC
        "roic_latest": roic_latest, "roic_avg": roic_avg,
        "roic_min": roic_min, "roic_max": roic_max,
        "roic_slope": roic_slope, "roic_std": roic_std,
        "roic_ec_avg": roic_ec_avg, "roic_ec_latest": roic_ec_latest,

        # ROE/ROA (financials)
        "roe_avg": roe_avg, "roe_latest": roe_latest, "roa_avg": roa_avg,

        # Margins
        "gm_latest": gm_latest, "gm_avg": gm_avg, "gm_slope": gm_slope,
        "op_margin_avg": op_margin_avg,

        # Compounding engine
        "roiic_full": roiic_full, "roiic_capped": roiic_capped,
        "reinvest_rate": reinvest_rate,
        "power": power, "cryld": cryld, "tvcr": tvcr,

        # Per-share growth
        "nopat_sh_cagr": nopat_sh_cagr, "fcf_sh_cagr": fcf_sh_cagr,
        "sbc_adj_fcf_cagr": sbc_adj_fcf_cagr,
        "best_per_sh_cagr": best_per_sh_cagr,
        "rev_cagr": rev_cagr, "shares_cagr": shares_cagr,

        # Financial health
        "fcf_ni_latest": fcf_ni_latest, "nd_ebitda_latest": nd_ebitda_latest,
        "nd_ebitda_slope": nd_ebitda_slope,
        "ic_latest_B": safe_div(ic_latest, 1e9),
        "int_coverage": int_coverage, "cf_recapture": cf_recapture,

        # Capital intensity
        "noa_B": safe_div(noa, 1e9),
        "ppe_to_rev": ppe_to_rev, "ocf_to_ppe": ocf_to_ppe,
        "capex_to_dep": capex_to_dep, "maint_to_ocf": maint_to_ocf,
        "noa_to_ev": noa_to_ev,

        # SBC
        "sbc_to_fcf": sbc_to_fcf,

        # Series (for detailed output)
        "roic_by_year": {y: r for y, r in zip(years, roic_s)},
        "gm_by_year": {y: g for y, g in zip(years, gm_s)},
    }


# ═════════════════════════════════════════════════════════════════════════════
# GATE LOGIC — v4.1 Methodology
# ═════════════════════════════════════════════════════════════════════════════

def apply_gate1(m):
    """Gate 1 — Quality Floor. Returns (pass, reasons)."""
    reasons = []
    is_fin = m["is_financial"]

    if is_fin:
        # Financial sector: ROE ≥ 15%, ROA ≥ 1.2%
        roe_pass = m["roe_avg"] is not None and m["roe_avg"] >= 0.15
        roa_pass = m["roa_avg"] is not None and m["roa_avg"] >= 0.012
        if not roe_pass:
            reasons.append(f"ROE avg {fmt_pct(m['roe_avg'])} < 15%")
        if not roa_pass:
            reasons.append(f"ROA avg {fmt_pct(m['roa_avg'])} < 1.2%")
        passed = roe_pass and roa_pass
    else:
        # Standard: GM ≥ 15%, ROIC ≥ 12% avg OR ≥ 18% current
        gm_pass = m["gm_latest"] is not None and m["gm_latest"] >= 0.15
        roic_avg_pass = m["roic_avg"] is not None and m["roic_avg"] >= 0.12
        roic_cur_pass = m["roic_latest"] is not None and m["roic_latest"] >= 0.18
        roic_pass = roic_avg_pass or roic_cur_pass

        if not gm_pass:
            reasons.append(f"GM {fmt_pct(m['gm_latest'])} < 15%")
        if not roic_pass:
            reasons.append(f"ROIC avg {fmt_pct(m['roic_avg'])}/cur {fmt_pct(m['roic_latest'])} < 12%/18%")
        passed = gm_pass and roic_pass

    return passed, reasons


def apply_gate2(m):
    """Gate 2 — Compounding Engine (TVCR ≥ 20%). Returns (pass, reasons)."""
    reasons = []

    if m["is_financial"]:
        # Financials: use ROE as proxy for compounding — ROE ≥ 15% already passed G1
        # TVCR not meaningful for banks. Pass if ROE supports 20%+ compounding.
        roe = m["roe_avg"] or 0
        if roe >= 0.15:
            return True, []
        reasons.append(f"Financial ROE {fmt_pct(m['roe_avg'])} insufficient for 20% compounding")
        return False, reasons

    tvcr = m["tvcr"]
    if tvcr is None:
        reasons.append("TVCR not computable")
        return False, reasons

    if tvcr >= 0.20:
        return True, reasons
    else:
        reasons.append(f"TVCR {tvcr:.1%} < 20% (Power {fmt_pct(m['power'])}, CRYld {fmt_pct(m['cryld'])})")
        return False, reasons


def apply_gate3(m):
    """Gate 3 — Proof of Compounding. Returns (pass, reasons)."""
    reasons = []

    if m["is_financial"]:
        # Financials: use EPS/BV growth instead of NOPAT/sh
        # If ROE > 15% and shares not diluting, proof is sufficient
        if m["shares_cagr"] is not None and m["shares_cagr"] < 0.03:
            return True, []
        elif m["shares_cagr"] is not None:
            reasons.append(f"Financial with share dilution {m['shares_cagr']:.1%}/yr — proof unclear")
            return False, reasons
        return True, []  # Insufficient data, pass with caveat

    best = m["best_per_sh_cagr"]
    if best is not None and best >= 0.15:
        return True, reasons

    # 3yr fallback — try last 3 years of data
    # (the CAGR is already computed over available period)
    if best is not None and best >= 0.12:
        reasons.append(f"Best per-share CAGR {best:.1%} — borderline (12-15%), passed with flag")
        return True, reasons

    if best is not None:
        reasons.append(f"Best per-share CAGR {best:.1%} < 15% (NOPAT/sh {fmt_pct(m['nopat_sh_cagr'])}, FCF/sh {fmt_pct(m['fcf_sh_cagr'])})")
    else:
        reasons.append("Per-share CAGR not computable (negative or missing values)")
    return False, reasons


def apply_gate4(m):
    """Gate 4 — Financial Health. Returns (pass, reasons)."""
    reasons = []
    passed = True

    if m["is_financial"]:
        # Financials: lighter health check — just leverage and IC
        return True, []

    # FCF/NI ≥ 70%
    fcf_ni = m["fcf_ni_latest"]
    if fcf_ni is not None and fcf_ni < 0.70:
        reasons.append(f"FCF/NI {fcf_ni:.0%} < 70%")
        passed = False

    # ND/EBITDA ≤ 2.5× (3.0× escape hatch)
    nd_eb = m["nd_ebitda_latest"]
    if nd_eb is not None and nd_eb > 3.0:
        reasons.append(f"ND/EBITDA {nd_eb:.1f}x > 3.0x")
        passed = False
    elif nd_eb is not None and nd_eb > 2.5:
        reasons.append(f"ND/EBITDA {nd_eb:.1f}x — escape hatch (2.5-3.0x)")

    # IC ≥ $1B
    ic_b = m["ic_latest_B"]
    if ic_b is not None and ic_b < 1.0 and ic_b > 0:
        reasons.append(f"IC ${ic_b:.1f}B < $1B — ratio instability")
        # Flag but don't fail

    return passed, reasons


# ═════════════════════════════════════════════════════════════════════════════
# FLAG LAYER — v4.1 Calibrated Thresholds
# ═════════════════════════════════════════════════════════════════════════════

def apply_flags(m):
    """v4.1 calibrated flag layer. Returns list of (flag_name, severity, detail)."""
    flags = []
    is_fin = m["is_financial"]

    # ─── TREND STABILITY ──────────────────────────────────────────────────

    # ROIC Declining (slope < -0.02)
    if not is_fin and m["roic_slope"] is not None and m["roic_slope"] < -0.02:
        flags.append(("ROIC_DECLINING", "HIGH",
                       f"Slope {m['roic_slope']:.3f} — returns deteriorating"))

    # ROIC Cyclical (corrected: StdDev > 10% AND (slope ≤ 0 OR min < 10%))
    if not is_fin and m["roic_std"] is not None and m["roic_std"] > 0.10:
        slope_ok = m["roic_slope"] is not None and m["roic_slope"] > 0
        min_ok = m["roic_min"] is not None and m["roic_min"] >= 0.15
        if not (slope_ok and min_ok):
            flags.append(("ROIC_CYCLICAL", "MEDIUM",
                           f"StdDev {m['roic_std']:.1%}, slope {fmt_f(m['roic_slope'])}, min {fmt_pct(m['roic_min'])}"))

    # GM Eroding
    if m["gm_slope"] is not None and m["gm_slope"] < -0.005:
        flags.append(("GM_ERODING", "HIGH",
                       f"GM slope {m['gm_slope']:.4f} — moat degradation"))

    # Leverage Rising
    if m["nd_ebitda_slope"] is not None and m["nd_ebitda_slope"] > 0.2:
        flags.append(("LEVERAGE_RISING", "MEDIUM",
                       f"ND/EBITDA slope +{m['nd_ebitda_slope']:.2f}"))

    # ─── DILUTION ─────────────────────────────────────────────────────────

    # Share Dilution (>3%/yr)
    if m["shares_cagr"] is not None and m["shares_cagr"] > 0.03:
        sev = "CRITICAL" if m["shares_cagr"] > 0.08 else "MEDIUM"
        flags.append(("SHARE_DILUTION", sev,
                       f"Shares CAGR +{m['shares_cagr']:.1%}/yr"))

    # SBC/FCF > 30%
    if m["sbc_to_fcf"] is not None and m["sbc_to_fcf"] > 0.30:
        sev = "CRITICAL" if m["sbc_to_fcf"] > 0.50 else "HIGH"
        flags.append(("SBC_DILUTION", sev,
                       f"SBC/FCF {m['sbc_to_fcf']:.0%}"))

    # SBC-adj FCF negative while raw positive (phantom growth)
    raw_pos = m["fcf_sh_cagr"] is not None and m["fcf_sh_cagr"] > 0
    adj_neg = m["sbc_adj_fcf_cagr"] is not None and m["sbc_adj_fcf_cagr"] < 0
    if raw_pos and adj_neg:
        flags.append(("PHANTOM_GROWTH", "CRITICAL",
                       f"FCF/sh +{m['fcf_sh_cagr']:.1%} but SBC-adj {m['sbc_adj_fcf_cagr']:.1%} — illusory"))

    # FCF/NI > 200% (distortion)
    if m["fcf_ni_latest"] is not None and m["fcf_ni_latest"] > 2.0:
        flags.append(("FCF_NI_DISTORTION", "MEDIUM",
                       f"FCF/NI {m['fcf_ni_latest']:.0%} — SBC-driven divergence likely"))

    # ─── CAPITAL INTENSITY ────────────────────────────────────────────────

    if not is_fin:
        # Infrastructure play
        if m["ppe_to_rev"] is not None and m["ppe_to_rev"] > 0.80:
            flags.append(("INFRASTRUCTURE", "MEDIUM",
                           f"PP&E/Rev {m['ppe_to_rev']:.0%} — capital-intensive"))

        # Low asset productivity
        if m["ocf_to_ppe"] is not None and m["ocf_to_ppe"] < 0.5:
            flags.append(("LOW_ASSET_PROD", "MEDIUM",
                           f"OCF/PP&E {m['ocf_to_ppe']:.1f}x — impairment risk"))

        # Aggressive capex
        if m["capex_to_dep"] is not None and m["capex_to_dep"] > 3.0:
            flags.append(("AGGRESSIVE_CAPEX", "LOW",
                           f"CapEx/Dep {m['capex_to_dep']:.1f}x — verify ROIIC"))

        # High maintenance burden
        if m["maint_to_ocf"] is not None and m["maint_to_ocf"] > 0.50:
            flags.append(("HIGH_MAINTENANCE", "MEDIUM",
                           f"MaintCX/OCF {m['maint_to_ocf']:.0%}"))

    # ─── STRUCTURAL ──────────────────────────────────────────────────────

    # Negative Power
    if not is_fin and m["power"] is not None and m["power"] <= 0:
        flags.append(("NEGATIVE_POWER", "HIGH",
                       f"Power {m['power']:.1%} — no organic compounding"))

    # Small IC
    if m["ic_latest_B"] is not None and 0 < m["ic_latest_B"] < 1.0:
        flags.append(("SMALL_IC", "LOW",
                       f"IC ${m['ic_latest_B']:.1f}B — ratio instability"))

    # Negative NOA (non-financial)
    if not is_fin and m["noa_B"] is not None and m["noa_B"] < 0:
        flags.append(("NEGATIVE_NOA", "LOW",
                       f"NOA ${m['noa_B']:.1f}B — investigate"))

    return flags


# ═════════════════════════════════════════════════════════════════════════════
# HARD EXCLUSIONS — v4.1
# ═════════════════════════════════════════════════════════════════════════════

def check_hard_exclusions(m, flags):
    """Return list of hard exclusion reasons. Any = Tier 4 auto-exclude."""
    exclusions = []
    flag_names = {f[0] for f in flags}

    # 1. SBC-adj FCF negative while raw positive
    if "PHANTOM_GROWTH" in flag_names:
        # Only hard-exclude if SBC/FCF also > 30%
        if m["sbc_to_fcf"] is not None and m["sbc_to_fcf"] > 0.30:
            exclusions.append("Phantom growth + SBC/FCF > 30%")

    # 2. Extreme dilution > 10%
    if m["shares_cagr"] is not None and m["shares_cagr"] > 0.10:
        exclusions.append(f"Extreme dilution {m['shares_cagr']:.1%}/yr")

    # 3. SBC/FCF > 50%
    if m["sbc_to_fcf"] is not None and m["sbc_to_fcf"] > 0.50:
        exclusions.append(f"SBC/FCF {m['sbc_to_fcf']:.0%} — majority phantom")

    # 4. Dead engine: ROIIC < 10% AND reinvestment < 10%
    if (m["roiic_capped"] is not None and m["roiic_capped"] < 0.10 and
            m["reinvest_rate"] is not None and m["reinvest_rate"] < 0.10):
        exclusions.append(f"Dead engine: ROIIC {m['roiic_capped']:.1%}, RR {m['reinvest_rate']:.1%}")

    # 5. Declining + volatile ROIC
    if (not m["is_financial"] and
            m["roic_slope"] is not None and m["roic_slope"] < -0.02 and
            m["roic_std"] is not None and m["roic_std"] > 0.10 and
            m["roic_min"] is not None and m["roic_min"] < 0.15):
        exclusions.append(f"Declining+volatile ROIC: slope {m['roic_slope']:.3f}, std {m['roic_std']:.1%}, min {m['roic_min']:.1%}")

    return exclusions


# ═════════════════════════════════════════════════════════════════════════════
# TIER CLASSIFICATION
# ═════════════════════════════════════════════════════════════════════════════

def classify_tier(m, g1, g2, g3, g4, flags, exclusions):
    """Classify into Tier 1-4."""
    flag_names = {f[0] for f in flags}
    high_crit = sum(1 for f in flags if f[1] in ("HIGH", "CRITICAL"))

    # Tier 4: Hard exclusion or failed essential gates
    if exclusions:
        return 4, "Excluded: " + "; ".join(exclusions)
    if not g1[0]:
        return 4, "Failed Gate 1 (Quality Floor)"
    if not g2[0]:
        return 4, "Failed Gate 2 (TVCR < 20%)"

    # Failed G3 or G4 → Tier 3 at best
    if not g3[0] or not g4[0]:
        return 3, "Failed " + ("G3" if not g3[0] else "") + (" + " if not g3[0] and not g4[0] else "") + ("G4" if not g4[0] else "")

    # Passed all 4 gates — classify by quality
    # Tier 1: Machines — high ROIIC, reinvesting, low SBC, stable
    is_machine = True
    machine_notes = []

    if high_crit >= 2:
        is_machine = False
        machine_notes.append(f"{high_crit} HIGH/CRITICAL flags")

    if m["power"] is not None and m["power"] <= 0:
        is_machine = False
        machine_notes.append("Negative Power (cash cow)")

    if m["sbc_to_fcf"] is not None and m["sbc_to_fcf"] > 0.25:
        is_machine = False
        machine_notes.append(f"SBC/FCF {m['sbc_to_fcf']:.0%}")

    if is_machine:
        return 1, "All gates passed, clean profile"
    else:
        # Tier 2: Cash Cows — passed gates but has structural limitations
        return 2, "Passed gates, but: " + "; ".join(machine_notes)


# ═════════════════════════════════════════════════════════════════════════════
# MAIN SCREENING ENGINE
# ═════════════════════════════════════════════════════════════════════════════

def run_screening(tickers, verbose=False, single_ticker=None, export_tag=""):
    """Run the full v4.1 screening on all tickers."""

    print("=" * 120)
    print("CAPITAL COMPOUNDERS v4.1 — INSTITUTIONAL GATE SCREENER")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Universe: {len(tickers)} stocks | Gates: 1–4 (Gate 5 IRR deferred)")
    print("=" * 120)

    results = []
    errors = []
    gate_counts = {1: 0, 2: 0, 3: 0, 4: 0}  # pass counts
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}

    for idx, ticker in enumerate(tickers):
        print(f"  [{idx+1:3d}/{len(tickers)}] {ticker:6s} ... ", end="", flush=True)

        raw = load_ticker_data(ticker)
        if not raw.get("income") or not raw.get("balance") or not raw.get("cashflow"):
            print("⚠️  No cache data")
            errors.append(ticker)
            continue

        m = compute_metrics(ticker, raw)
        if m.get("error"):
            print(f"⚠️  {m['error']}")
            errors.append(ticker)
            continue

        # Apply gates
        g1 = apply_gate1(m)
        g2 = apply_gate2(m) if g1[0] else (False, ["Skipped (G1 failed)"])
        g3 = apply_gate3(m) if g2[0] else (False, ["Skipped (G2 failed)"])
        g4 = apply_gate4(m) if g3[0] else (False, ["Skipped (G3 failed)"])

        # Count passes
        if g1[0]: gate_counts[1] += 1
        if g2[0]: gate_counts[2] += 1
        if g3[0]: gate_counts[3] += 1
        if g4[0]: gate_counts[4] += 1

        # Apply flags
        flags = apply_flags(m)

        # Hard exclusions
        exclusions = check_hard_exclusions(m, flags)

        # Classify
        tier, tier_reason = classify_tier(m, g1, g2, g3, g4, flags, exclusions)
        tier_counts[tier] += 1

        m["gate1"] = g1
        m["gate2"] = g2
        m["gate3"] = g3
        m["gate4"] = g4
        m["flags_v41"] = flags
        m["exclusions"] = exclusions
        m["tier"] = tier
        m["tier_reason"] = tier_reason

        results.append(m)

        # Console summary
        gate_str = ("✅" if g1[0] else "❌") + ("✅" if g2[0] else "❌") + \
                   ("✅" if g3[0] else "❌") + ("✅" if g4[0] else "❌")
        flag_str = f"{len(flags)}F" if flags else "0F"
        tier_emoji = {1: "🏆", 2: "💰", 3: "⚡", 4: "🚫"}
        print(f"{gate_str} T{tier}{tier_emoji[tier]} {flag_str:>4}", end="")

        if m["is_financial"]:
            print(f"  ROE {fmt_pct(m['roe_avg'])} | FIN")
        else:
            print(f"  ROIC {fmt_pct(m['roic_avg'])} TVCR {fmt_pct(m['tvcr'])} PS {fmt_pct(m['best_per_sh_cagr'])}")

        if verbose or single_ticker:
            for reason in g1[1] + g2[1] + g3[1] + g4[1]:
                print(f"         → {reason}")
            for fn, sev, detail in flags:
                print(f"         🚩 [{sev}] {fn}: {detail}")
            if exclusions:
                for ex in exclusions:
                    print(f"         🛑 HARD EXCLUDE: {ex}")

    # ═══════════════════════════════════════════════════════════════════════
    # SUMMARY REPORTS
    # ═══════════════════════════════════════════════════════════════════════

    print("\n" + "=" * 120)
    print("GATE FUNNEL")
    print("=" * 120)
    total = len(results)
    print(f"  Universe:     {total:3d} stocks")
    print(f"  Gate 1 pass:  {gate_counts[1]:3d}  ({gate_counts[1]/total*100:.0f}%) — Quality Floor")
    print(f"  Gate 2 pass:  {gate_counts[2]:3d}  ({gate_counts[2]/total*100:.0f}%) — Compounding Engine")
    print(f"  Gate 3 pass:  {gate_counts[3]:3d}  ({gate_counts[3]/total*100:.0f}%) — Proof of Compounding")
    print(f"  Gate 4 pass:  {gate_counts[4]:3d}  ({gate_counts[4]/total*100:.0f}%) — Financial Health")

    # ─── TIER REPORTS ─────────────────────────────────────────────────────

    for tier_num in [1, 2, 3, 4]:
        tier_label = {1: "TIER 1 — MACHINES (20%+ Compounders)",
                      2: "TIER 2 — CASH COWS (High Quality, Structural Limits)",
                      3: "TIER 3 — SPECIAL SITUATIONS (Gate Failures, Potential)",
                      4: "TIER 4 — EXCLUDE (Value Destroyers / Misclassified)"}
        tier_emoji = {1: "🏆", 2: "💰", 3: "⚡", 4: "🚫"}

        tier_stocks = [r for r in results if r["tier"] == tier_num]
        if not tier_stocks:
            continue

        print(f"\n{'=' * 120}")
        print(f"{tier_emoji[tier_num]} {tier_label[tier_num]}  ({len(tier_stocks)} stocks)")
        print(f"{'=' * 120}")

        if tier_num in (1, 2):
            # Detailed table for Tier 1 & 2
            print(f"  {'Sym':6} {'ROIC':>7} {'RoICec':>7} {'TVCR':>7} {'Power':>7} {'CRYld':>7} "
                  f"{'ROIIC':>7} {'PS_CAGR':>8} {'SBCadj':>8} {'SBC/F':>6} {'ShrCAGR':>8} "
                  f"{'GM':>6} {'ND/EB':>6} {'Flags':>6} {'Reason'}")
            print(f"  {'-'*116}")

            for r in sorted(tier_stocks, key=lambda x: -(x.get("tvcr") or 0)):
                flag_str = ",".join(f[0][:6] for f in r["flags_v41"]) if r["flags_v41"] else "clean"
                is_fin = " [FIN]" if r["is_financial"] else ""
                roic_show = fmt_pct(r["roe_avg"]) if r["is_financial"] else fmt_pct(r["roic_avg"])
                print(f"  {r['ticker']:6} {roic_show} {fmt_pct(r['roic_ec_avg'])} "
                      f"{fmt_pct(r['tvcr'])} {fmt_pct(r['power'])} {fmt_pct(r['cryld'])} "
                      f"{fmt_pct(r.get('roiic_capped'))} {fmt_pct(r['best_per_sh_cagr'],8)} "
                      f"{fmt_pct(r['sbc_adj_fcf_cagr'],8)} {fmt_pct(r['sbc_to_fcf'],6)} "
                      f"{fmt_pct(r['shares_cagr'],8)} {fmt_pct(r['gm_latest'],6)} "
                      f"{fmt_x(r['nd_ebitda_latest'])} {len(r['flags_v41']):>3}F{is_fin}")

        elif tier_num == 3:
            # Show which gate failed
            for r in tier_stocks:
                failed = []
                if not r["gate1"][0]: failed.append("G1")
                if not r["gate2"][0]: failed.append("G2")
                if not r["gate3"][0]: failed.append("G3")
                if not r["gate4"][0]: failed.append("G4")
                flag_ct = len(r["flags_v41"])
                is_fin = " [FIN]" if r["is_financial"] else ""
                print(f"  {r['ticker']:6} Failed: {','.join(failed):8} | "
                      f"ROIC {fmt_pct(r['roic_avg'])} TVCR {fmt_pct(r['tvcr'])} "
                      f"PS {fmt_pct(r['best_per_sh_cagr'])} | {flag_ct}F{is_fin} | {r['tier_reason']}")

        elif tier_num == 4:
            for r in tier_stocks:
                is_fin = " [FIN]" if r["is_financial"] else ""
                excl_str = "; ".join(r["exclusions"]) if r["exclusions"] else r["tier_reason"]
                print(f"  {r['ticker']:6} {excl_str}{is_fin}")

    # ─── FLAG DISTRIBUTION ────────────────────────────────────────────────

    print(f"\n{'=' * 120}")
    print("FLAG DISTRIBUTION (Tier 1 & 2 only)")
    print(f"{'=' * 120}")

    t12 = [r for r in results if r["tier"] in (1, 2)]
    flag_dist = {}
    for r in t12:
        for fn, sev, detail in r["flags_v41"]:
            if fn not in flag_dist:
                flag_dist[fn] = []
            flag_dist[fn].append((r["ticker"], sev, detail))

    if flag_dist:
        for fn in sorted(flag_dist.keys()):
            entries = flag_dist[fn]
            print(f"\n  {fn} ({len(entries)} stocks):")
            for tk, sev, detail in sorted(entries, key=lambda x: x[1]):
                print(f"    [{sev:8}] {tk:6} — {detail}")
    else:
        print("  No flags in Tier 1/2 — all clean!")

    # ─── CLEAN MACHINES LIST ─────────────────────────────────────────────

    clean_t1 = [r for r in results if r["tier"] == 1 and len(r["flags_v41"]) == 0]
    if clean_t1:
        print(f"\n{'=' * 120}")
        print(f"🏆 PRISTINE MACHINES — Tier 1, Zero Flags ({len(clean_t1)} stocks)")
        print(f"{'=' * 120}")
        for r in sorted(clean_t1, key=lambda x: -(x.get("tvcr") or 0)):
            is_fin = " [FIN]" if r["is_financial"] else ""
            roic_show = fmt_pct(r["roe_avg"]) if r["is_financial"] else fmt_pct(r["roic_avg"])
            print(f"  {r['ticker']:6} ROIC {roic_show} | TVCR {fmt_pct(r['tvcr'])} | "
                  f"PS CAGR {fmt_pct(r['best_per_sh_cagr'])} | "
                  f"SBC-adj {fmt_pct(r['sbc_adj_fcf_cagr'])} | "
                  f"GM {fmt_pct(r['gm_latest'])} | ND/EB {fmt_x(r['nd_ebitda_latest'])}{is_fin}")

    # ─── CSV EXPORT ──────────────────────────────────────────────────────

    export_results(results, export_tag=export_tag)

    # ─── SUMMARY ─────────────────────────────────────────────────────────

    print(f"\n{'=' * 120}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Processed: {len(results)} | Errors: {len(errors)}")
    print(f"Tier 1 (Machines):    {tier_counts[1]:3d}")
    print(f"Tier 2 (Cash Cows):   {tier_counts[2]:3d}")
    print(f"Tier 3 (Special Sit): {tier_counts[3]:3d}")
    print(f"Tier 4 (Exclude):     {tier_counts[4]:3d}")
    if errors:
        print(f"Errors: {', '.join(errors)}")
    print(f"\nExports: {EXPORT_DIR}")
    print("=" * 120)

    return results


def export_results(results, export_tag=""):
    """Export screening results to CSV."""
    fname = f"v41_screener_{export_tag}.csv" if export_tag else "v41_screener_results.csv"
    outpath = EXPORT_DIR / fname
    rows = []
    for r in results:
        rows.append({
            "ticker": r["ticker"],
            "tier": r["tier"],
            "tier_reason": r["tier_reason"],
            "is_financial": r["is_financial"],
            "sector": r.get("sector", ""),
            "mkt_cap_B": r.get("mkt_cap_B"),
            "gate1_pass": r["gate1"][0],
            "gate2_pass": r["gate2"][0],
            "gate3_pass": r["gate3"][0],
            "gate4_pass": r["gate4"][0],
            "gate1_reasons": "; ".join(r["gate1"][1]),
            "gate2_reasons": "; ".join(r["gate2"][1]),
            "gate3_reasons": "; ".join(r["gate3"][1]),
            "gate4_reasons": "; ".join(r["gate4"][1]),
            "roic_avg": r.get("roic_avg"),
            "roic_latest": r.get("roic_latest"),
            "roic_ec_avg": r.get("roic_ec_avg"),
            "roic_slope": r.get("roic_slope"),
            "roic_std": r.get("roic_std"),
            "roic_min": r.get("roic_min"),
            "roe_avg": r.get("roe_avg"),
            "roa_avg": r.get("roa_avg"),
            "gm_latest": r.get("gm_latest"),
            "gm_slope": r.get("gm_slope"),
            "op_margin_avg": r.get("op_margin_avg"),
            "tvcr": r.get("tvcr"),
            "power": r.get("power"),
            "cryld": r.get("cryld"),
            "roiic_full": r.get("roiic_full"),
            "roiic_capped": r.get("roiic_capped"),
            "reinvest_rate": r.get("reinvest_rate"),
            "nopat_sh_cagr": r.get("nopat_sh_cagr"),
            "fcf_sh_cagr": r.get("fcf_sh_cagr"),
            "sbc_adj_fcf_cagr": r.get("sbc_adj_fcf_cagr"),
            "best_per_sh_cagr": r.get("best_per_sh_cagr"),
            "rev_cagr": r.get("rev_cagr"),
            "shares_cagr": r.get("shares_cagr"),
            "fcf_ni_latest": r.get("fcf_ni_latest"),
            "nd_ebitda_latest": r.get("nd_ebitda_latest"),
            "nd_ebitda_slope": r.get("nd_ebitda_slope"),
            "ic_latest_B": r.get("ic_latest_B"),
            "int_coverage": r.get("int_coverage"),
            "cf_recapture": r.get("cf_recapture"),
            "noa_B": r.get("noa_B"),
            "noa_to_ev": r.get("noa_to_ev"),
            "ppe_to_rev": r.get("ppe_to_rev"),
            "ocf_to_ppe": r.get("ocf_to_ppe"),
            "capex_to_dep": r.get("capex_to_dep"),
            "maint_to_ocf": r.get("maint_to_ocf"),
            "sbc_to_fcf": r.get("sbc_to_fcf"),
            "flag_count": len(r["flags_v41"]),
            "flags": " | ".join(f"{n}[{s}]" for n, s, _ in r["flags_v41"]),
            "flag_details": " | ".join(f"{n}: {d}" for n, _, d in r["flags_v41"]),
            "exclusions": "; ".join(r["exclusions"]),
        })

    if rows:
        keys = list(rows[0].keys())
        with open(outpath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n✅ CSV exported: {outpath}")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Capital Compounders v4.1 Gate Screener")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-ticker gate detail")
    parser.add_argument("--ticker", "-t", type=str, help="Single ticker deep dive")
    parser.add_argument("--tickers-file", type=str, help="File with one ticker per line")
    parser.add_argument("--export-tag", type=str, default="", help="Tag for export filename")
    args = parser.parse_args()

    if args.ticker:
        tickers = [args.ticker.upper()]
    elif args.tickers_file:
        with open(args.tickers_file) as f:
            tickers = [l.strip().upper() for l in f if l.strip() and not l.startswith('#')]
        print(f'Loaded {len(tickers)} tickers from {args.tickers_file}')
    else:
        tickers = ALL_TICKERS

    run_screening(tickers, verbose=args.verbose, single_ticker=args.ticker, export_tag=args.export_tag)


if __name__ == "__main__":
    main()
