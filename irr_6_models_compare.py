#!/usr/bin/env python3
"""
Capital Compounders — 6 IRR Models Comparison
Runs all 6 IRR models independently on a set of tickers.
Reads from cache/raw/ (zero API calls).
"""

import json
import math
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
RAW_DIR = PROJECT_DIR / "cache" / "raw"

# ─── Helpers ───

def load_json(ticker, suffix):
    aliases = {"income-statement":"income","cash-flow-statement":"cashflow",
               "balance-sheet-statement":"balance","income":"income-statement",
               "cashflow":"cash-flow-statement","balance":"balance-sheet-statement"}
    p = RAW_DIR / f"{ticker}_{suffix}.json"
    if not p.exists() and suffix in aliases:
        p = RAW_DIR / f"{ticker}_{aliases[suffix]}.json"
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)

def safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b

def cagr(begin, end, years):
    if begin is None or end is None or years <= 0 or begin <= 0 or end <= 0:
        return None
    return (end / begin) ** (1 / years) - 1

def get(obj, *keys, default=None):
    for k in keys:
        if obj and k in obj:
            return obj[k]
    return default

# ─── Data Extraction ───

def extract_all(ticker):
    """Pull everything needed for all 6 models."""
    profile = load_json(ticker, "profile")
    inc = load_json(ticker, "income")
    cf = load_json(ticker, "cashflow")
    bs = load_json(ticker, "balance")
    metrics = load_json(ticker, "metrics")

    if not all([profile, inc, cf, bs]):
        return {"ticker": ticker, "error": "Missing cache data"}

    # Handle profile as list or dict
    prof = profile[0] if isinstance(profile, list) else profile
    price = prof.get("price") or prof.get("lastPrice") or 0
    mkt_cap = prof.get("mktCap") or prof.get("marketCap") or 0
    shares = safe_div(mkt_cap, price) if price else None

    n_years = min(len(inc), len(cf), len(bs), 6)
    if n_years < 3:
        return {"ticker": ticker, "error": f"Only {n_years} years of data"}

    # ─── Annual series (most recent first) ───
    nopat_s, ic_s, fcf_s, eps_s, rev_s, ocf_s, capex_s, dep_s = [], [], [], [], [], [], [], []
    sbc_s, div_s, buyback_s, debt_s, ebitda_s = [], [], [], [], []
    shares_s = []

    for i in range(n_years):
        inc_i, cf_i, bs_i = inc[i], cf[i], bs[i]

        # NOPAT
        op_inc = get(inc_i, "operatingIncome", default=0)
        tax_exp = get(inc_i, "incomeTaxExpense", default=0)
        pretax = get(inc_i, "incomeBeforeTax", default=0)
        eff_tax = safe_div(tax_exp, pretax) if pretax and pretax > 0 else 0.21
        eff_tax = max(0, min(eff_tax, 0.40))
        nopat = op_inc * (1 - eff_tax)
        nopat_s.append(nopat)

        # IC = Total Debt + Total Equity + Capital Leases - Cash
        total_debt = get(bs_i, "totalDebt", "longTermDebt", default=0)
        total_equity = get(bs_i, "totalStockholdersEquity", "totalEquity", default=0)
        cash = get(bs_i, "cashAndCashEquivalents", "cashAndShortTermInvestments", default=0)
        ic = total_debt + total_equity - cash
        ic_s.append(ic)

        # FCF
        ocf = get(cf_i, "operatingCashFlow", default=0)
        capex = abs(get(cf_i, "capitalExpenditure", "capitalExpenditures", default=0))
        fcf = ocf - capex
        fcf_s.append(fcf)
        ocf_s.append(ocf)
        capex_s.append(capex)

        # Depreciation
        dep = get(cf_i, "depreciationAndAmortization", default=0)
        dep_s.append(dep)

        # EPS
        ni = get(inc_i, "netIncome", default=0)
        shares_out = get(inc_i, "weightedAverageShsOut", "weightedAverageShsOutDil", default=shares)
        eps = safe_div(ni, shares_out)
        eps_s.append(eps if eps else 0)
        shares_s.append(shares_out or shares)

        # Revenue
        rev = get(inc_i, "revenue", default=0)
        rev_s.append(rev)

        # SBC
        sbc = get(cf_i, "stockBasedCompensation", default=0)
        sbc_s.append(sbc)

        # Dividends & Buybacks
        divs = abs(get(cf_i, "dividendsPaid", "commonDividendsPaid", default=0))
        bbacks = abs(get(cf_i, "commonStockRepurchased", default=0))
        div_s.append(divs)
        buyback_s.append(bbacks)

        # Debt & EBITDA
        debt_s.append(total_debt)
        ebitda = get(inc_i, "ebitda", default=op_inc + dep)
        ebitda_s.append(ebitda)

    # ─── Computed Metrics ───

    # Current values
    nopat_cur = nopat_s[0]
    ic_cur = ic_s[0]
    fcf_cur = fcf_s[0]
    ocf_cur = ocf_s[0]
    capex_cur = capex_s[0]
    rev_cur = rev_s[0]
    shares_cur = shares_s[0] or shares
    ni_cur = get(inc[0], "netIncome", default=0)

    # ROIC
    roic = safe_div(nopat_cur, ic_cur) if ic_cur and ic_cur > 0 else None

    # ROIC ex-cash (IC without subtracting cash)
    total_debt_cur = debt_s[0]
    total_equity_cur = get(bs[0], "totalStockholdersEquity", "totalEquity", default=0)
    ic_ex_cash = total_debt_cur + total_equity_cur
    roic_ex_cash = safe_div(nopat_cur, ic_ex_cash) if ic_ex_cash and ic_ex_cash > 0 else roic

    # Gross Margin
    gp = get(inc[0], "grossProfit", default=0)
    gm = safe_div(gp, rev_cur)

    # FCF Yield
    fcf_yield = safe_div(fcf_cur, mkt_cap)

    # SBC-adjusted FCF
    sbc_adj_fcf = fcf_cur - sbc_s[0]
    sbc_adj_yield = safe_div(sbc_adj_fcf, mkt_cap)

    # Owner Earnings (Buffett: NI + D&A - maintenance capex)
    maint_capex = min(capex_cur, dep_s[0]) if dep_s[0] else capex_cur
    owner_earnings = nopat_cur + dep_s[0] - maint_capex

    # VCR = ROIC / WACC (assume 10%)
    wacc = 0.10
    vcr = safe_div(roic, wacc) if roic else None

    # ROIIC (5yr if available, else 3yr)
    roiic = None
    yrs_roiic = min(n_years - 1, 5)
    delta_nopat = nopat_s[0] - nopat_s[yrs_roiic]
    delta_ic = ic_s[0] - ic_s[yrs_roiic]
    if delta_ic > 0:
        roiic = safe_div(delta_nopat, delta_ic)

    # Reinvestment Rate (cumulative)
    cum_nopat = sum(nopat_s[:yrs_roiic])
    reinvest_rate = safe_div(delta_ic, cum_nopat) if cum_nopat > 0 else None
    if reinvest_rate and reinvest_rate > 2.0:
        reinvest_rate = 2.0

    # Power = ROIIC × Reinvest Rate
    roiic_capped = min(roiic, 3.5) if roiic else None
    power = (roiic_capped * reinvest_rate) if roiic_capped and reinvest_rate else 0

    # Capital Return Yield
    avg_buybacks = sum(buyback_s[:yrs_roiic]) / yrs_roiic
    avg_divs = sum(div_s[:yrs_roiic]) / yrs_roiic
    ic_begin = ic_s[yrs_roiic] if ic_s[yrs_roiic] and ic_s[yrs_roiic] > 0 else ic_cur
    cr_yield = safe_div(avg_buybacks + avg_divs, ic_begin) if ic_begin else 0

    # TVCR
    tvcr = power + (cr_yield or 0)

    # Shareholder Yield (on mkt cap)
    sh_yield = safe_div(buyback_s[0] + div_s[0], mkt_cap) if mkt_cap else 0

    # Per-share growth rates
    def ps_cagr(series, yr):
        if len(series) <= yr or not shares_s[0] or not shares_s[min(yr, len(shares_s)-1)]:
            return None
        ps_end = series[0] / shares_s[0]
        ps_beg = series[yr] / shares_s[min(yr, len(shares_s)-1)]
        return cagr(ps_beg, ps_end, yr)

    yrs = min(n_years - 1, 5)
    nopat_ps_cagr = ps_cagr(nopat_s, yrs)
    fcf_ps_cagr = ps_cagr(fcf_s, yrs)
    rev_ps_cagr = ps_cagr(rev_s, yrs)
    eps_cagr_val = cagr(eps_s[yrs], eps_s[0], yrs) if eps_s[0] > 0 and eps_s[yrs] > 0 else None

    # SBC-adjusted FCF/share CAGR
    sbc_adj_series = [fcf_s[i] - sbc_s[i] for i in range(n_years)]
    sbc_adj_cagr = None
    if shares_s[0] and shares_s[yrs]:
        beg = sbc_adj_series[yrs] / shares_s[yrs]
        end = sbc_adj_series[0] / shares_s[0]
        sbc_adj_cagr = cagr(beg, end, yrs)

    # P/E
    pe = safe_div(price, eps_s[0]) if eps_s[0] and eps_s[0] > 0 else None

    # Net Debt / EBITDA
    cash_cur = get(bs[0], "cashAndCashEquivalents", "cashAndShortTermInvestments", default=0)
    nd = total_debt_cur - cash_cur
    nd_ebitda = safe_div(nd, ebitda_s[0]) if ebitda_s[0] and ebitda_s[0] > 0 else None

    return {
        "ticker": ticker, "price": price, "mkt_cap": mkt_cap, "shares": shares_cur,
        "nopat": nopat_cur, "ic": ic_cur, "fcf": fcf_cur, "ocf": ocf_cur,
        "capex": capex_cur, "ni": ni_cur, "rev": rev_cur, "gm": gm,
        "roic": roic, "roic_ex_cash": roic_ex_cash, "vcr": vcr,
        "fcf_yield": fcf_yield, "sbc_adj_yield": sbc_adj_yield,
        "owner_earnings": owner_earnings, "eps": eps_s[0], "pe": pe,
        "roiic": roiic, "roiic_capped": roiic_capped,
        "reinvest_rate": reinvest_rate, "power": power,
        "cr_yield": cr_yield, "tvcr": tvcr, "sh_yield": sh_yield,
        "nd_ebitda": nd_ebitda,
        # Growth rates
        "nopat_ps_cagr": nopat_ps_cagr,
        "fcf_ps_cagr": fcf_ps_cagr,
        "sbc_adj_cagr": sbc_adj_cagr,
        "rev_ps_cagr": rev_ps_cagr,
        "eps_cagr": eps_cagr_val,
        "n_years": n_years,
        # Raw series for DCF
        "fcf_series": fcf_s, "eps_series": eps_s, "sbc_series": sbc_s,
        "shares_series": shares_s, "nopat_series": nopat_s,
    }

# ─── IRR Solver ───

def solve_irr(price, cash_flows, terminal_value, n=None):
    """Binary search for IRR given initial price, annual CFs, and terminal value."""
    if n is None:
        n = len(cash_flows)
    if price <= 0:
        return None

    lo, hi = -0.30, 1.50
    for _ in range(200):
        mid = (lo + hi) / 2
        pv = sum(cf / (1 + mid) ** (t + 1) for t, cf in enumerate(cash_flows))
        pv += terminal_value / (1 + mid) ** n
        if pv > price:
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < 0.0001:
            break
    return (lo + hi) / 2

# ─── 6 IRR MODELS ───

def model1_gemini_quick(d):
    """Model 1 — Gemini Quick Screen
    IRR = FCF Yield + (ROIC × Reinvestment Rate) ± ΔMultiple
    ΔMultiple: VCR > 3 → -3% penalty per unit above 3; VCR < 1.5 → +2% boost
    """
    if not d.get("fcf_yield") or not d.get("roic") or d.get("reinvest_rate") is None:
        return None
    base = d["fcf_yield"] + (d["roic"] * max(d["reinvest_rate"], 0))
    # Multiple adjustment
    vcr = d.get("vcr") or 0
    if vcr > 3:
        base -= 0.03 * (vcr - 3)
    elif vcr < 1.5:
        base += 0.02
    return base

def model2_claude_eps(d, growth_rate):
    """Model 2 — Claude EPS Power
    IRR = (Future EPS × Exit PE / Current Price)^(1/5) - 1
    Uses provided growth rate to project EPS forward 5 years.
    Exit PE = current PE capped at 25.
    """
    if not d.get("eps") or d["eps"] <= 0 or not d.get("price") or not growth_rate:
        return None
    future_eps = d["eps"] * (1 + growth_rate) ** 5
    exit_pe = min(d.get("pe") or 20, 25)  # cap exit PE at 25
    future_price = future_eps * exit_pe
    if future_price <= 0 or d["price"] <= 0:
        return None
    return (future_price / d["price"]) ** (1/5) - 1

def model3_copilot_scalable(d, growth_rate):
    """Model 3 — Copilot Scalable
    IRR = Owner Earnings × (1 + Value Growth)^5 × Terminal PE / Price
    Owner Earnings based on reinvestment at ROIC.
    """
    if not d.get("owner_earnings") or d["owner_earnings"] <= 0 or not d.get("price"):
        return None
    if not growth_rate or growth_rate <= 0:
        return None
    oe_ps = d["owner_earnings"] / d["shares"] if d.get("shares") else 0
    if oe_ps <= 0:
        return None
    future_oe = oe_ps * (1 + growth_rate) ** 5
    terminal_pe = 20
    future_val = future_oe * terminal_pe
    if future_val <= 0:
        return None
    return (future_val / d["price"]) ** (1/5) - 1

def model4_grok_dcf(d, growth_rate):
    """Model 4 — Grok Full DCF
    Explicit 5yr projected cash flows + terminal value.
    Uses SBC-adjusted FCF per share.
    """
    if not d.get("shares") or d["shares"] <= 0 or not d.get("price"):
        return None
    sbc_adj_fcf_ps = (d["fcf"] - d.get("sbc_series", [0])[0]) / d["shares"]
    if sbc_adj_fcf_ps <= 0 or not growth_rate:
        return None

    cfs = []
    for yr in range(1, 6):
        cf = sbc_adj_fcf_ps * (1 + growth_rate) ** yr
        cfs.append(cf)

    # Terminal value at 20x year-5 FCF
    tv = cfs[-1] * 20
    return solve_irr(d["price"], cfs, tv, n=5)

def model5_deepseek_weighted(d, growth_rate):
    """Model 5 — DeepSeek Weighted
    IRR = 60% DCF + 40% EPV (Earnings Power Value) + Stress Tests
    EPV = normalized earnings / cost of capital (no growth assumed)
    """
    # DCF component (60%)
    dcf_irr = model4_grok_dcf(d, growth_rate)

    # EPV component (40%) — no growth, just current earnings power
    if not d.get("nopat") or d["nopat"] <= 0 or not d.get("mkt_cap") or d["mkt_cap"] <= 0:
        epv_irr = None
    else:
        # EPV = NOPAT / WACC; IRR from EPV = NOPAT / Price (earnings yield on IC)
        nopat_ps = d["nopat"] / d["shares"] if d.get("shares") else 0
        epv_irr = safe_div(nopat_ps, d["price"])

    if dcf_irr is not None and epv_irr is not None:
        blended = 0.60 * dcf_irr + 0.40 * epv_irr
        # Stress test: penalize high leverage
        nd_eb = d.get("nd_ebitda") or 0
        if nd_eb > 2.0:
            blended -= 0.02 * (nd_eb - 2.0)
        return blended
    elif dcf_irr is not None:
        return dcf_irr
    elif epv_irr is not None:
        return epv_irr
    return None

def model6_perplexity_quick(d):
    """Model 6 — Perplexity Quick
    IRR = FCF Yield + (ROIC_ex_cash × 0.35) - 1.5%
    """
    if not d.get("fcf_yield") or not d.get("roic_ex_cash"):
        return None
    return d["fcf_yield"] + (d["roic_ex_cash"] * 0.35) - 0.015

# ─── Main ───

def run_comparison(tickers):
    # Growth input labels
    growth_labels = ["SBC-adj FCF/sh", "FCF/sh", "NOPAT/sh", "Rev/sh", "EPS"]
    growth_keys = ["sbc_adj_cagr", "fcf_ps_cagr", "nopat_ps_cagr", "rev_ps_cagr", "eps_cagr"]

    for ticker in tickers:
        d = extract_all(ticker)
        if d.get("error"):
            print(f"\n{'='*100}")
            print(f"  {ticker}: {d['error']}")
            continue

        print(f"\n{'='*100}")
        print(f"  {ticker}  |  ${d['price']:.2f}  |  ROIC {d['roic']*100:.1f}%  |  "
              f"GM {d['gm']*100:.1f}%  |  P/E {d['pe']:.1f}x  |  "
              f"FCF Yld {d['fcf_yield']*100:.1f}%  |  VCR {d['vcr']:.1f}x  |  "
              f"ND/EB {(d['nd_ebitda'] or 0):.1f}x")
        print(f"  Power {d['power']*100:.1f}%  |  CR Yld {(d['cr_yield'] or 0)*100:.1f}%  |  "
              f"TVCR {d['tvcr']*100:.1f}%  |  ROIIC {(d['roiic'] or 0)*100:.1f}%  |  "
              f"Reinv {(d['reinvest_rate'] or 0)*100:.1f}%")
        print(f"{'='*100}")

        # Growth rates
        print(f"\n  {'Growth Input':<18s} {'CAGR':>8s}  {'Capped?':>8s}")
        print(f"  {'-'*38}")
        growths = {}
        for label, key in zip(growth_labels, growth_keys):
            val = d.get(key)
            if val is not None:
                capped = val > 0.30
                capped_val = min(val, 0.30)
                flag = ">>> YES" if capped else ""
                print(f"  {label:<18s} {val*100:7.1f}%  {flag:>8s}")
                growths[key] = val
            else:
                print(f"  {label:<18s}     N/A")
                growths[key] = None

        # ─── Model Results ───
        print(f"\n  {'Model':<25s}", end="")
        print(f"{'No Growth':>10s}", end="")
        for label in growth_labels:
            print(f"{label:>16s}", end="")
        print()
        print(f"  {'-'*91}")

        # Model 1 — Gemini (no growth input needed)
        m1 = model1_gemini_quick(d)
        print(f"  {'1. Gemini Quick':<25s}", end="")
        print(f"{m1*100:9.1f}%" if m1 else f"{'N/A':>10s}", end="")
        print(f"{'—':>16s}" * 5)

        # Model 6 — Perplexity (no growth input needed)
        m6 = model6_perplexity_quick(d)
        print(f"  {'6. Perplexity Quick':<25s}", end="")
        print(f"{m6*100:9.1f}%" if m6 else f"{'N/A':>10s}", end="")
        print(f"{'—':>16s}" * 5)

        # Models 2-5 — growth-dependent
        for model_name, model_fn in [
            ("2. Claude EPS Power", model2_claude_eps),
            ("3. Copilot Scalable", model3_copilot_scalable),
            ("4. Grok Full DCF", model4_grok_dcf),
            ("5. DeepSeek Weighted", model5_deepseek_weighted),
        ]:
            print(f"  {model_name:<25s}", end="")
            print(f"{'—':>10s}", end="")  # no "no growth" column for these
            for key in growth_keys:
                g = growths.get(key)
                if g is not None and g > 0:
                    g_capped = min(g, 0.30)
                    irr = model_fn(d, g_capped)
                    if irr is not None:
                        print(f"{irr*100:15.1f}%", end="")
                    else:
                        print(f"{'N/A':>16s}", end="")
                else:
                    print(f"{'N/A':>16s}", end="")
            print()

        # ─── Consensus Summary ───
        all_irrs = []
        if m1: all_irrs.append(("M1-Gemini", m1))
        if m6: all_irrs.append(("M6-Perplexity", m6))

        # Use SBC-adj growth (primary) for consensus
        primary_g = growths.get("sbc_adj_cagr") or growths.get("fcf_ps_cagr")
        if primary_g and primary_g > 0:
            pg = min(primary_g, 0.30)
            for name, fn in [("M2-EPS", model2_claude_eps), ("M3-Copilot", model3_copilot_scalable),
                             ("M4-DCF", model4_grok_dcf), ("M5-DeepSeek", model5_deepseek_weighted)]:
                r = fn(d, pg)
                if r: all_irrs.append((name, r))

        if all_irrs:
            all_irrs.sort(key=lambda x: x[1], reverse=True)
            median_irr = sorted([x[1] for x in all_irrs])[len(all_irrs)//2]
            agree_15 = sum(1 for _, v in all_irrs if v >= 0.15)
            print(f"\n  CONSENSUS ({len(all_irrs)} models):  Median {median_irr*100:.1f}%  |  "
                  f"{agree_15}/{len(all_irrs)} agree ≥15%  |  "
                  f"Range {all_irrs[-1][1]*100:.1f}% – {all_irrs[0][1]*100:.1f}%")
            verdict = "✅ HIGH CONVICTION" if agree_15 >= 4 else "⚠️ MIXED" if agree_15 >= 2 else "❌ WEAK"
            print(f"  Verdict: {verdict}")

    print(f"\n{'='*100}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        tickers = [t.upper() for t in sys.argv[1:]]
    else:
        tickers = ["ADP", "NVDA", "POOL", "ADBE", "DDS"]
    run_comparison(tickers)
