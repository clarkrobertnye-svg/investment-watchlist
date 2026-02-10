#!/usr/bin/env python3
"""
CAPITAL COMPOUNDERS — GATE 5: IRR VALUATION MODEL
===================================================
Tests implied IRR for Tier 1 Pristine Machines using 3 scenarios.
Reads from same cache as v4.1 screener (zero API calls).

Model:
  - 10-year DCF with growth fade
  - Years 1-5: Phase 1 growth rate
  - Years 6-10: Linear fade to 3% terminal growth
  - Terminal value: FCF_10 × terminal multiple
  - Solve for IRR that equates PV of cash flows to current price

Three scenarios:
  Bear: Conservative growth (50% of historical), 15× terminal
  Base: Moderate growth (75% of historical), 20× terminal
  Bull: Optimistic growth (90% of historical), 25× terminal

Pass threshold: Base case IRR ≥ 15%
"""

import json
import csv
from pathlib import Path
from datetime import datetime
import sys

LIVE_MODE = "--live" in sys.argv
FROM_SCREENER = None
EXPORT_TAG = ""
if "--from-screener" in sys.argv:
    idx = sys.argv.index("--from-screener")
    if idx + 1 < len(sys.argv): FROM_SCREENER = sys.argv[idx + 1]
if "--export-tag" in sys.argv:
    idx = sys.argv.index("--export-tag")
    if idx + 1 < len(sys.argv): EXPORT_TAG = sys.argv[idx + 1]

# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════
PROJECT_DIR = Path(".")
CACHE_DIR = PROJECT_DIR / "cache"
RAW_DIR = CACHE_DIR / "raw"
EXPORT_DIR = CACHE_DIR / "exports"

# Pristine Machines from v4.1 run (Tier 1, zero flags, non-financial)
PRISTINE = [
    "MA", "KLAC", "NVMI", "LULU", "FIX", "ADBE", "ANET", "APH", "ASML",
    "AAPL", "BLD", "NYT", "LII", "CAT", "TT", "V", "CSL", "VRSK", "PH",
    "ADP", "BAH", "ITT", "HUBB", "CTAS", "WTS", "ROL", "RMD", "NVS",
    "WSO"
]
# Financial-track pristine (different valuation approach)
PRISTINE_FIN = ["ERIE", "HIG"]

TERMINAL_GROWTH = 0.03
if FROM_SCREENER:
    import csv as _csv
    print(f"Loading tiers from: {FROM_SCREENER}")
    _tm = {}
    with open(FROM_SCREENER) as _f:
        for row in _csv.DictReader(_f):
            tier, tick = row.get("tier",""), row.get("ticker","")
            if tier and tick and tier not in ('T4-Exclude','4'): _tm.setdefault(tier,[]).append(tick)
    T1_PRISTINE = _tm.get("T1-Pristine",[]) or _tm.get("1",[])
    T1_FLAGGED = _tm.get("T1-Flagged",[]) or _tm.get("1f",[])
    T2_CASH_COWS = _tm.get("T2-CashCow",[]) or _tm.get("2",[])
    T3_SPECIAL = _tm.get("T3-Special",[]) or _tm.get("3",[])
    TIERS = {}
    if T1_PRISTINE: TIERS["T1-Pristine"] = T1_PRISTINE
    if T1_FLAGGED: TIERS["T1-Flagged"] = T1_FLAGGED
    if T2_CASH_COWS: TIERS["T2-CashCow"] = T2_CASH_COWS
    if T3_SPECIAL: TIERS["T3-Special"] = T3_SPECIAL
    _tot = sum(len(v) for v in TIERS.values())
    print(f"  Loaded {_tot} tickers: " + ", ".join(f"{k}={len(v)}" for k,v in TIERS.items()))
    PRISTINE = T1_PRISTINE + T1_FLAGGED + T2_CASH_COWS + T3_SPECIAL
    PRISTINE_FIN = []  # 3% perpetuity growth
HOLD_YEARS = 10
FADE_START = 5  # growth fades from year 6 onward

# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════
def load_json(ticker, suffix):
    aliases = {"income-statement":"income","cash-flow-statement":"cashflow","balance-sheet-statement":"balance"}
    alt = aliases.get(suffix)
    p = RAW_DIR / f"{ticker}_{suffix}.json"
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)

def safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b

def cagr(begin, end, years):
    if begin is None or end is None or years <= 0:
        return None
    if begin <= 0 or end <= 0:
        return None
    return (end / begin) ** (1.0 / years) - 1.0

def solve_irr(price, cash_flows, terminal_value, n=10):
    """Binary search for IRR: PV of cash_flows + TV/(1+r)^n = price"""
    if price <= 0:
        return None
    
    def npv(r):
        pv = 0
        for t, cf in enumerate(cash_flows, 1):
            pv += cf / (1 + r) ** t
        pv += terminal_value / (1 + r) ** n
        return pv
    
    lo, hi = -0.30, 1.50  # -30% to 150% IRR range
    # Check bounds
    try:
        if npv(hi) > price:
            return hi  # IRR > 150%
        if npv(lo) < price:
            return lo  # IRR < -30%
    except (OverflowError, ZeroDivisionError):
        return None
    
    for _ in range(200):
        mid = (lo + hi) / 2
        try:
            val = npv(mid)
        except (OverflowError, ZeroDivisionError):
            hi = mid
            continue
        if val > price:
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < 1e-6:
            break
    return (lo + hi) / 2

def project_fcf(fcf_0, g_phase1, n=10, fade_start=5, g_terminal=0.03):
    """Project FCF over n years with growth fade."""
    flows = []
    for t in range(1, n + 1):
        if t <= fade_start:
            g = g_phase1
        else:
            # Linear fade from g_phase1 to g_terminal over years fade_start+1 to n
            fade_frac = (t - fade_start) / (n - fade_start)
            g = g_phase1 + (g_terminal - g_phase1) * fade_frac
        if t == 1:
            flows.append(fcf_0 * (1 + g))
        else:
            flows.append(flows[-1] * (1 + g))
    return flows

# ═══════════════════════════════════════════════════════════════════════
# EXTRACT VALUATION INPUTS FROM CACHE
# ═══════════════════════════════════════════════════════════════════════
def extract_inputs(ticker):
    """Pull all IRR model inputs from cached data."""
    profile = load_json(ticker, "profile")
    inc = load_json(ticker, "income")
    cf = load_json(ticker, "cash-flow-statement") or load_json(ticker, "cashflow")
    bs = load_json(ticker, "balance-sheet-statement") or load_json(ticker, "balance")
    
    if not all([profile, inc, cf, bs]):
        return {"ticker": ticker, "error": "Missing cache data"}
    
    if isinstance(profile, list):
        profile = profile[0] if profile else {}
    
    # Current price & market cap
    price = profile.get("price")
    mkt_cap = profile.get("mktCap")
    beta = profile.get("beta", 1.0)
    
    # Sort statements by date (newest first)
    inc = sorted(inc, key=lambda x: x.get("date", ""), reverse=True)
    cf = sorted(cf, key=lambda x: x.get("date", ""), reverse=True)
    bs = sorted(bs, key=lambda x: x.get("date", ""), reverse=True)
    
    n_years = min(len(inc), len(cf), len(bs), 6)
    if n_years < 3:
        return {"ticker": ticker, "error": f"Only {n_years} years of data"}
    
    # Latest values
    shares_latest = inc[0].get("weightedAverageShsOutDil", 0)
    revenue_latest = inc[0].get("revenue", 0)
    ebit_latest = inc[0].get("operatingIncome", 0)
    ni_latest = inc[0].get("netIncome", 0)
    
    fcf_latest = cf[0].get("freeCashFlow", 0)
    ocf_latest = cf[0].get("operatingCashFlow", 0)
    sbc_latest = cf[0].get("stockBasedCompensation", 0)
    capex_latest = abs(cf[0].get("capitalExpenditure", 0))
    divs_latest = abs(cf[0].get("dividendsPaid", 0))
    buybacks_latest = abs(cf[0].get("commonStockRepurchased", 0))
    
    total_debt = bs[0].get("totalDebt", 0)
    cash = bs[0].get("cashAndCashEquivalents", 0) + bs[0].get("shortTermInvestments", 0)
    total_equity = bs[0].get("totalStockholdersEquity", 0)
    
    # Compute per-share values
    if not shares_latest or shares_latest <= 0:
        return {"ticker": ticker, "error": "No share data"}
    
    price_check = safe_div(mkt_cap, shares_latest) if not price else price
    if not price_check:
        return {"ticker": ticker, "error": "No price data"}
    price = price_check
    
    fcf_per_share = fcf_latest / shares_latest
    sbc_adj_fcf_ps = (fcf_latest - sbc_latest) / shares_latest
    nopat_latest = ebit_latest * (1 - 0.21)  # standard tax
    nopat_ps = nopat_latest / shares_latest
    eps = ni_latest / shares_latest
    
    # EV
    mkt_cap = mkt_cap or 0
    ev = mkt_cap + total_debt - cash
    ev_ebit = safe_div(ev, ebit_latest) if ebit_latest > 0 else None
    
    # IC & ROIC for context
    ic = total_equity + total_debt - cash
    roic = safe_div(nopat_latest, ic) if ic > 0 else None
    
    # ─── Historical per-share CAGRs ───
    # Build series going back
    fcf_ps_series = []
    sbc_adj_series = []
    nopat_ps_series = []
    rev_ps_series = []
    
    for i in range(min(n_years, 6)):
        sh = inc[i].get("weightedAverageShsOutDil", 0)
        if not sh or sh <= 0:
            continue
        fcf_i = cf[i].get("freeCashFlow", 0) if i < len(cf) else 0
        sbc_i = cf[i].get("stockBasedCompensation", 0) if i < len(cf) else 0
        ebit_i = inc[i].get("operatingIncome", 0)
        rev_i = inc[i].get("revenue", 0)
        
        fcf_ps_series.append(fcf_i / sh)
        sbc_adj_series.append((fcf_i - sbc_i) / sh)
        nopat_ps_series.append(ebit_i * 0.79 / sh)
        rev_ps_series.append(rev_i / sh)
    
    # Reverse to chronological order
    fcf_ps_series.reverse()
    sbc_adj_series.reverse()
    nopat_ps_series.reverse()
    rev_ps_series.reverse()
    
    yrs = len(fcf_ps_series) - 1
    
    # Per-share CAGRs
    ps_cagr_fcf = cagr(fcf_ps_series[0], fcf_ps_series[-1], yrs) if yrs > 0 else None
    ps_cagr_sbc = cagr(sbc_adj_series[0], sbc_adj_series[-1], yrs) if yrs > 0 else None
    ps_cagr_nopat = cagr(nopat_ps_series[0], nopat_ps_series[-1], yrs) if yrs > 0 else None
    ps_cagr_rev = cagr(rev_ps_series[0], rev_ps_series[-1], yrs) if yrs > 0 else None
    
    # Best per-share CAGR (from screener logic)
    best_ps = max(filter(None, [ps_cagr_nopat, ps_cagr_fcf]), default=None)
    
    # ─── Yields ───
    fcf_yield = safe_div(fcf_per_share, price)
    sbc_adj_yield = safe_div(sbc_adj_fcf_ps, price)
    earnings_yield = safe_div(eps, price)
    owner_earnings = (nopat_latest + sbc_latest - capex_latest) / shares_latest  # rough
    owner_yield = safe_div(owner_earnings, price)
    div_yield = safe_div(divs_latest / shares_latest, price)
    buyback_yield = safe_div(buybacks_latest, mkt_cap)
    shareholder_yield = (div_yield or 0) + (buyback_yield or 0)
    
    # P/FCF
    p_fcf = safe_div(price, fcf_per_share) if fcf_per_share > 0 else None
    p_sbc_fcf = safe_div(price, sbc_adj_fcf_ps) if sbc_adj_fcf_ps > 0 else None
    p_e = safe_div(price, eps) if eps > 0 else None
    
    return {
        "ticker": ticker,
        "error": None,
        "price": price,
        "mkt_cap_B": mkt_cap / 1e9 if mkt_cap else None,
        "ev_B": ev / 1e9 if ev else None,
        "shares_M": shares_latest / 1e6,
        "beta": beta,
        
        # Per-share values
        "fcf_ps": fcf_per_share,
        "sbc_adj_fcf_ps": sbc_adj_fcf_ps,
        "nopat_ps": nopat_ps,
        "eps": eps,
        
        # Growth rates (historical)
        "ps_cagr_fcf": ps_cagr_fcf,
        "ps_cagr_sbc_adj": ps_cagr_sbc,
        "ps_cagr_nopat": ps_cagr_nopat,
        "ps_cagr_rev": ps_cagr_rev,
        "best_ps_cagr": best_ps,
        "n_years": yrs,
        
        # Yields
        "fcf_yield": fcf_yield,
        "sbc_adj_yield": sbc_adj_yield,
        "earnings_yield": earnings_yield,
        "shareholder_yield": shareholder_yield,
        
        # Multiples
        "p_fcf": p_fcf,
        "p_sbc_fcf": p_sbc_fcf,
        "p_e": p_e,
        "ev_ebit": ev_ebit,
        
        # Context
        "roic": roic,
        "sbc_fcf_pct": safe_div(sbc_latest, fcf_latest) if fcf_latest > 0 else None,
    }

# ═══════════════════════════════════════════════════════════════════════
# IRR MODEL
# ═══════════════════════════════════════════════════════════════════════
def compute_irr_scenarios(inp):
    """Compute bear/base/bull IRR for a stock."""
    if inp.get("error"):
        return inp
    
    price = inp["price"]
    
    # Use SBC-adjusted FCF/sh as the cash flow basis
    # If SBC-adj is negative, fall back to FCF/sh with a penalty
    base_fcf = inp["sbc_adj_fcf_ps"]
    if base_fcf is None or base_fcf <= 0:
        base_fcf = inp["fcf_ps"]
        if base_fcf is None or base_fcf <= 0:
            base_fcf = inp["nopat_ps"]  # last resort
            if base_fcf is None or base_fcf <= 0:
                inp["error"] = "No positive cash flow basis"
                return inp
    
    # Forward growth rate derived from historical
    # Use best of SBC-adj or NOPAT/sh CAGR, with sanity bounds
    hist_g = inp.get("ps_cagr_sbc_adj") or inp.get("best_ps_cagr")
    if hist_g is None or hist_g <= 0:
        hist_g = inp.get("ps_cagr_rev") or 0.08  # fallback to revenue growth
    
    # Cap historical growth at 30% for projection (mean reversion)
    hist_g = min(hist_g, 0.30)
    
    scenarios = {}
    
    for label, g_mult, tv_mult in [
        ("bear",  0.50, 15),
        ("base",  0.75, 20),
        ("bull",  0.90, 25),
    ]:
        # Phase 1 growth = historical × multiplier, with floor
        g1 = max(hist_g * g_mult, 0.03)
        
        # Project cash flows
        flows = project_fcf(base_fcf, g1, n=HOLD_YEARS, 
                           fade_start=FADE_START, g_terminal=TERMINAL_GROWTH)
        
        # Terminal value
        tv = flows[-1] * tv_mult
        
        # Solve IRR
        irr = solve_irr(price, flows, tv, n=HOLD_YEARS)
        
        # Also compute implied price at 15% and 20% hurdle
        def implied_price(hurdle):
            pv = 0
            for t, cf in enumerate(flows, 1):
                pv += cf / (1 + hurdle) ** t
            pv += tv / (1 + hurdle) ** HOLD_YEARS
            return pv
        
        iv_15 = implied_price(0.15)
        iv_20 = implied_price(0.20)
        
        scenarios[label] = {
            "growth": g1,
            "tv_multiple": tv_mult,
            "irr": irr,
            "iv_at_15": iv_15,
            "iv_at_20": iv_20,
            "mos_15": (iv_15 - price) / iv_15 if iv_15 > 0 else None,  # margin of safety
            "mos_20": (iv_20 - price) / iv_20 if iv_20 > 0 else None,
            "year10_fcf": flows[-1],
        }
    
    inp["scenarios"] = scenarios
    
    # Gate 5 verdict
    base_irr = scenarios["base"]["irr"]
    inp["g5_pass"] = base_irr is not None and base_irr >= 0.15
    inp["g5_verdict"] = (
        "✅ PASS" if inp["g5_pass"] else
        "⚠️ MARGINAL" if base_irr and base_irr >= 0.12 else
        "❌ FAIL"
    )
    
    return inp

# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════
def fmt_pct(v):
    return f"{v*100:6.1f}%" if v is not None else "   N/A"

def fmt_x(v):
    return f"{v:6.1f}x" if v is not None else "   N/A"

def fmt_usd(v):
    return f"${v:8.2f}" if v is not None else "     N/A"

def fmt_b(v):
    return f"${v:6.1f}B" if v is not None else "   N/A"

def main():
    print("=" * 120)
    print("CAPITAL COMPOUNDERS — GATE 5: IRR VALUATION MODEL")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Universe: {len(PRISTINE)} Pristine Machines + {len(PRISTINE_FIN)} Financial-track")
    print(f"Model: 10yr DCF, growth fade yr 6-10 → 3%, 3 scenarios (bear/base/bull)")
    print("=" * 120)
    
    results = []
    
    all_tickers = PRISTINE + PRISTINE_FIN
    
    for i, ticker in enumerate(all_tickers, 1):
        inp = extract_inputs(ticker)
        
        if inp.get("error"):
            print(f"  [{i:3d}/{len(all_tickers)}] {ticker:6s} ... ❌ {inp['error']}")
            results.append(inp)
            continue
        
        result = compute_irr_scenarios(inp)
        results.append(result)
        
        if result.get("error"):
            print(f"  [{i:3d}/{len(all_tickers)}] {ticker:6s} ... ❌ {result['error']}")
            continue
        
        sc = result["scenarios"]
        base_irr = sc["base"]["irr"]
        bear_irr = sc["bear"]["irr"]
        bull_irr = sc["bull"]["irr"]
        verdict = result["g5_verdict"]
        
        print(f"  [{i:3d}/{len(all_tickers)}] {ticker:6s} "
              f"${result['price']:8.2f}  "
              f"P/FCF {result.get('p_sbc_fcf', 0) or 0:5.1f}x  "
              f"Yld {fmt_pct(result['sbc_adj_yield'])}  "
              f"Bear {fmt_pct(bear_irr)}  "
              f"Base {fmt_pct(base_irr)}  "
              f"Bull {fmt_pct(bull_irr)}  "
              f"{verdict}")
    
    # ─── RESULTS BY CATEGORY ───
    valid = [r for r in results if not r.get("error") and r.get("scenarios")]
    
    # Sort by base IRR descending
    valid.sort(key=lambda x: x["scenarios"]["base"]["irr"] or 0, reverse=True)
    
    passed = [r for r in valid if r.get("g5_pass")]
    marginal = [r for r in valid if not r.get("g5_pass") and 
                r["scenarios"]["base"]["irr"] and r["scenarios"]["base"]["irr"] >= 0.12]
    failed = [r for r in valid if not r.get("g5_pass") and r not in marginal]
    
    print()
    print("=" * 120)
    print(f"✅ GATE 5 PASS — Base IRR ≥ 15%  ({len(passed)} stocks)")
    print("=" * 120)
    print(f"  {'Sym':6s} {'Price':>9s}  {'P/FCFa':>7s} {'Yld%':>6s}  "
          f"{'Bear':>7s} {'BASE':>7s} {'Bull':>7s}  "
          f"{'IV@15%':>9s} {'IV@20%':>9s} {'MoS@20%':>7s}  "
          f"{'Hist g':>7s} {'Base g':>7s} {'ROIC':>6s}")
    print("  " + "-" * 116)
    
    for r in passed:
        sc = r["scenarios"]
        base = sc["base"]
        print(f"  {r['ticker']:6s} "
              f"${r['price']:8.2f}  "
              f"{r.get('p_sbc_fcf', 0) or 0:6.1f}x "
              f"{(r.get('sbc_adj_yield', 0) or 0)*100:5.1f}%  "
              f"{fmt_pct(sc['bear']['irr'])} "
              f"{fmt_pct(base['irr'])} "
              f"{fmt_pct(sc['bull']['irr'])}  "
              f"${base['iv_at_15']:8.2f} "
              f"${base['iv_at_20']:8.2f} "
              f"{(base['mos_20'] or 0)*100:6.1f}%  "
              f"{fmt_pct(r.get('ps_cagr_sbc_adj'))} "
              f"{fmt_pct(base['growth'])} "
              f"{fmt_pct(r.get('roic'))}")
    
    if marginal:
        print()
        print("=" * 120)
        print(f"⚠️  MARGINAL — Base IRR 12-15%  ({len(marginal)} stocks)")
        print("=" * 120)
        print(f"  {'Sym':6s} {'Price':>9s}  {'P/FCFa':>7s} {'Yld%':>6s}  "
              f"{'Bear':>7s} {'BASE':>7s} {'Bull':>7s}  "
              f"{'IV@15%':>9s} {'IV@20%':>9s} {'MoS@20%':>7s}  "
              f"{'Hist g':>7s} {'Base g':>7s} {'ROIC':>6s}")
        print("  " + "-" * 116)
        
        for r in marginal:
            sc = r["scenarios"]
            base = sc["base"]
            print(f"  {r['ticker']:6s} "
                  f"${r['price']:8.2f}  "
                  f"{r.get('p_sbc_fcf', 0) or 0:6.1f}x "
                  f"{(r.get('sbc_adj_yield', 0) or 0)*100:5.1f}%  "
                  f"{fmt_pct(sc['bear']['irr'])} "
                  f"{fmt_pct(base['irr'])} "
                  f"{fmt_pct(sc['bull']['irr'])}  "
                  f"${base['iv_at_15']:8.2f} "
                  f"${base['iv_at_20']:8.2f} "
                  f"{(base['mos_20'] or 0)*100:6.1f}%  "
                  f"{fmt_pct(r.get('ps_cagr_sbc_adj'))} "
                  f"{fmt_pct(base['growth'])} "
                  f"{fmt_pct(r.get('roic'))}")
    
    if failed:
        print()
        print("=" * 120)
        print(f"❌ GATE 5 FAIL — Base IRR < 12%  ({len(failed)} stocks)")
        print("=" * 120)
        print(f"  {'Sym':6s} {'Price':>9s}  {'P/FCFa':>7s} {'Yld%':>6s}  "
              f"{'Bear':>7s} {'BASE':>7s} {'Bull':>7s}  "
              f"{'Hist g':>7s} {'Base g':>7s} {'ROIC':>6s}  Note")
        print("  " + "-" * 116)
        
        for r in failed:
            sc = r["scenarios"]
            base = sc["base"]
            # Diagnose why
            note = ""
            p_sbc = r.get('p_sbc_fcf')
            if p_sbc and p_sbc > 40:
                note = f"Expensive: {p_sbc:.0f}× SBC-adj FCF"
            elif r.get('sbc_adj_yield') and r['sbc_adj_yield'] < 0.02:
                note = f"Low yield: {r['sbc_adj_yield']*100:.1f}%"
            elif r.get('ps_cagr_sbc_adj') and r['ps_cagr_sbc_adj'] < 0.10:
                note = f"Slow growth: {r['ps_cagr_sbc_adj']*100:.1f}%/yr"
            
            print(f"  {r['ticker']:6s} "
                  f"${r['price']:8.2f}  "
                  f"{p_sbc or 0:6.1f}x "
                  f"{(r.get('sbc_adj_yield', 0) or 0)*100:5.1f}%  "
                  f"{fmt_pct(sc['bear']['irr'])} "
                  f"{fmt_pct(base['irr'])} "
                  f"{fmt_pct(sc['bull']['irr'])}  "
                  f"{fmt_pct(r.get('ps_cagr_sbc_adj'))} "
                  f"{fmt_pct(base['growth'])} "
                  f"{fmt_pct(r.get('roic'))}  {note}")
    
    # ─── SUMMARY ───
    print()
    print("=" * 120)
    print("GATE 5 SUMMARY")
    print("=" * 120)
    print(f"  Pristine Machines tested:  {len(all_tickers)}")
    print(f"  Gate 5 PASS (IRR ≥ 15%):   {len(passed)}")
    print(f"  MARGINAL (12-15%):          {len(marginal)}")
    print(f"  FAIL (< 12%):               {len(failed)}")
    print(f"  Errors:                      {len(results) - len(valid)}")
    
    if passed:
        irrs = [r["scenarios"]["base"]["irr"] for r in passed]
        print(f"\n  Pass group base IRR:  median {sorted(irrs)[len(irrs)//2]*100:.1f}%  "
              f"range {min(irrs)*100:.1f}%-{max(irrs)*100:.1f}%")
    
    # ─── EXPORT CSV ───
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    csv_name = f"gate5_irr_{EXPORT_TAG}_LIVE.csv" if LIVE_MODE and EXPORT_TAG else f"gate5_irr_{EXPORT_TAG}.csv" if EXPORT_TAG else ("gate5_irr_LIVE.csv" if LIVE_MODE else "gate5_irr_all_tiers.csv")
    csv_path = EXPORT_DIR / csv_name
    
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "ticker", "price", "mkt_cap_B", "p_fcf", "p_sbc_fcf", "p_e", "ev_ebit",
            "fcf_yield", "sbc_adj_yield", "earnings_yield", "shareholder_yield",
            "roic", "sbc_fcf_pct",
            "hist_fcf_cagr", "hist_sbc_cagr", "hist_nopat_cagr", "hist_rev_cagr",
            "bear_growth", "bear_irr", "bear_tv_mult",
            "base_growth", "base_irr", "base_tv_mult", "base_iv_15", "base_iv_20", "base_mos_20",
            "bull_growth", "bull_irr", "bull_tv_mult",
            "g5_pass", "g5_verdict"
        ])
        for r in valid:
            sc = r["scenarios"]
            w.writerow([
                r["ticker"], f"{r['price']:.2f}",
                f"{r.get('mkt_cap_B', 0):.1f}" if r.get('mkt_cap_B') else "",
                f"{r.get('p_fcf', 0):.1f}" if r.get('p_fcf') else "",
                f"{r.get('p_sbc_fcf', 0):.1f}" if r.get('p_sbc_fcf') else "",
                f"{r.get('p_e', 0):.1f}" if r.get('p_e') else "",
                f"{r.get('ev_ebit', 0):.1f}" if r.get('ev_ebit') else "",
                f"{r.get('fcf_yield', 0)*100:.2f}%" if r.get('fcf_yield') else "",
                f"{r.get('sbc_adj_yield', 0)*100:.2f}%" if r.get('sbc_adj_yield') else "",
                f"{r.get('earnings_yield', 0)*100:.2f}%" if r.get('earnings_yield') else "",
                f"{r.get('shareholder_yield', 0)*100:.2f}%" if r.get('shareholder_yield') else "",
                f"{r.get('roic', 0)*100:.1f}%" if r.get('roic') else "",
                f"{r.get('sbc_fcf_pct', 0)*100:.1f}%" if r.get('sbc_fcf_pct') else "",
                f"{r.get('ps_cagr_fcf', 0)*100:.1f}%" if r.get('ps_cagr_fcf') else "",
                f"{r.get('ps_cagr_sbc_adj', 0)*100:.1f}%" if r.get('ps_cagr_sbc_adj') else "",
                f"{r.get('ps_cagr_nopat', 0)*100:.1f}%" if r.get('ps_cagr_nopat') else "",
                f"{r.get('ps_cagr_rev', 0)*100:.1f}%" if r.get('ps_cagr_rev') else "",
                f"{sc['bear']['growth']*100:.1f}%", f"{sc['bear']['irr']*100:.1f}%", sc['bear']['tv_multiple'],
                f"{sc['base']['growth']*100:.1f}%", f"{sc['base']['irr']*100:.1f}%", sc['base']['tv_multiple'],
                f"{sc['base']['iv_at_15']:.2f}", f"{sc['base']['iv_at_20']:.2f}",
                f"{(sc['base']['mos_20'] or 0)*100:.1f}%",
                f"{sc['bull']['growth']*100:.1f}%", f"{sc['bull']['irr']*100:.1f}%", sc['bull']['tv_multiple'],
                r.get("g5_pass", False), r.get("g5_verdict", "")
            ])
    
    print(f"\n✅ CSV exported: {csv_path}")
    print()
    print("=" * 120)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"NOTE: Prices are from cached profile data (may be days old).")
    print(f"      For live trading decisions, refresh prices via API.")
    print("=" * 120)

if __name__ == "__main__":
    main()
