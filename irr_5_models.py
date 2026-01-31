"""
Run all 5 IRR models on Stage 2 Watchlist
Compare side-by-side with current price
"""
import json
from pathlib import Path
from datetime import datetime
import math

def safe_div(a, b, default=0):
    """Safe division avoiding ZeroDivisionError"""
    if b is None or b == 0:
        return default
    return a / b if a else default

def get_metric(t, *keys, default=0):
    """Get metric trying multiple keys"""
    for k in keys:
        v = t.get(k)
        if v is not None:
            return v
    return default

# ============================================================
# MODEL 1: GEMINI QUICK SCREEN
# IRR = FCF Yield + Growth Engine - Multiple Shift
# ============================================================
def gemini_irr(t):
    """
    Gemini: FCF Yield + (ROIC × RR) ± Δ Valuation
    Fast screening model focused on compounding power
    """
    fcf_yield = get_metric(t, "fcf_yield", "enterprise_yield") or 0
    roic = get_metric(t, "roic_current", "roic_3y_avg") or 0
    
    # Reinvestment rate: 1 - payout ratio (estimate from FCF conversion)
    fcf_conv = get_metric(t, "fcf_conversion") or 0.8
    payout = get_metric(t, "dividend_yield", default=0) / max(fcf_yield, 0.01)
    rr = max(0.3, min(0.8, 1 - payout)) if payout < 1 else 0.5
    
    # Growth engine
    growth_engine = roic * rr
    
    # Multiple shift (assume mean reversion over 5 years)
    # If VCR > 3, expect compression; if VCR < 1.5, expect expansion
    vcr = get_metric(t, "value_creation_ratio") or 2
    if vcr > 3:
        multiple_shift = -0.03 * (vcr - 3)  # 3% penalty per VCR above 3
    elif vcr < 1.5:
        multiple_shift = 0.02 * (1.5 - vcr)  # 2% boost per VCR below 1.5
    else:
        multiple_shift = 0
    
    irr = fcf_yield + growth_engine + multiple_shift
    return irr

# ============================================================
# MODEL 2: CLAUDE EPS POWER
# IRR = (Future EPS × Exit Multiple / Price)^(1/n) - 1
# ============================================================
def claude_irr(t, years=3):
    """
    Claude: EPS growth with multiple normalization
    Conservative model with P/E compression
    """
    price = get_metric(t, "price") or 0
    if price <= 0:
        return 0
    
    # Estimate current EPS from FCF and shares
    fcf = get_metric(t, "fcf_current") or 0
    market_cap = get_metric(t, "market_cap") or 1
    shares = market_cap / price if price > 0 else 1
    
    # Use FCF per share as proxy for owner earnings
    fcf_per_share = fcf / shares if shares > 0 else 0
    
    if fcf_per_share <= 0:
        return 0
    
    # Sustainable growth = MIN(historical, ROIC × RR)
    roic = get_metric(t, "roic_current", "roic_3y_avg") or 0.15
    hist_growth = get_metric(t, "revenue_growth_3y") or 0.05
    rr = 0.6  # Assume 60% reinvestment
    
    sustainable_growth = min(hist_growth, roic * rr, 0.25)  # Cap at 25%
    
    # Future EPS
    future_eps = fcf_per_share * (1 + sustainable_growth) ** years
    
    # Exit multiple: normalize toward 18x over time
    current_pe = price / fcf_per_share if fcf_per_share > 0 else 20
    exit_pe = min(current_pe, 18 + (current_pe - 18) * 0.5)  # Mean revert halfway
    
    # Future value
    future_value = future_eps * exit_pe
    
    # IRR
    if future_value <= 0:
        return 0
    
    irr = (future_value / price) ** (1/years) - 1
    return irr

# ============================================================
# MODEL 3: COPILOT SCALABLE
# Value Growth model with owner earnings
# ============================================================
def copilot_irr(t, years=5):
    """
    Copilot: Owner Earnings × (1 + Value Growth)^n × Terminal PE
    Scalable batch screening model
    """
    price = get_metric(t, "price") or 0
    market_cap = get_metric(t, "market_cap") or 0
    if price <= 0 or market_cap <= 0:
        return 0
    
    shares = market_cap / price
    fcf = get_metric(t, "fcf_current") or 0
    oe_per_share = fcf / shares if shares > 0 else 0
    
    if oe_per_share <= 0:
        return 0
    
    # Value growth = ROIC × RR (capped)
    roic = get_metric(t, "roic_current", "roic_3y_avg") or 0.15
    rr = min(0.6, max(0.3, 1 - get_metric(t, "dividend_yield", default=0) * 10))
    value_growth = min(roic * rr, 0.20)  # Cap at 20%
    
    # Future owner earnings
    future_oe = oe_per_share * (1 + value_growth) ** years
    
    # Terminal multiple (based on growth)
    if value_growth > 0.15:
        terminal_pe = 20
    elif value_growth > 0.10:
        terminal_pe = 17
    else:
        terminal_pe = 14
    
    future_value = future_oe * terminal_pe
    
    irr = (future_value / price) ** (1/years) - 1
    return irr

# ============================================================
# MODEL 4: GROK FULL DCF
# Explicit 5yr FCF projections + Terminal Value
# ============================================================
def grok_irr(t):
    """
    Grok: Full DCF with explicit cash flows
    Most rigorous model with terminal value
    """
    price = get_metric(t, "price") or 0
    market_cap = get_metric(t, "market_cap") or 0
    if price <= 0 or market_cap <= 0:
        return 0
    
    shares = market_cap / price
    fcf = get_metric(t, "fcf_current") or 0
    
    if fcf <= 0:
        return 0
    
    # Growth assumptions
    roic = get_metric(t, "roic_current", "roic_3y_avg") or 0.15
    hist_growth = get_metric(t, "revenue_growth_3y") or 0.05
    
    # Fade growth: start at historical, fade to 3% by year 5
    growth_rates = []
    start_growth = min(hist_growth, 0.25)
    for yr in range(5):
        fade = start_growth + (0.03 - start_growth) * (yr / 4)
        growth_rates.append(fade)
    
    # Project FCF
    wacc = get_metric(t, "wacc") or 0.10
    fcf_projections = []
    current_fcf = fcf
    for g in growth_rates:
        current_fcf = current_fcf * (1 + g)
        fcf_projections.append(current_fcf)
    
    # Terminal value (Gordon Growth)
    terminal_growth = 0.025
    terminal_value = fcf_projections[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    
    # Cash flows for IRR calc
    # Year 0: -Market Cap (investment)
    # Years 1-4: FCF
    # Year 5: FCF + Terminal Value
    cash_flows = [-market_cap]
    for i, cf in enumerate(fcf_projections):
        if i == 4:
            cash_flows.append(cf + terminal_value)
        else:
            cash_flows.append(cf)
    
    # Calculate IRR using Newton-Raphson
    irr = calculate_irr(cash_flows)
    return irr

def calculate_irr(cash_flows, guess=0.1, max_iter=100, tol=1e-6):
    """Newton-Raphson IRR calculation"""
    rate = guess
    for _ in range(max_iter):
        npv = sum(cf / (1 + rate) ** i for i, cf in enumerate(cash_flows))
        dnpv = sum(-i * cf / (1 + rate) ** (i + 1) for i, cf in enumerate(cash_flows))
        if abs(dnpv) < 1e-10:
            break
        new_rate = rate - npv / dnpv
        if abs(new_rate - rate) < tol:
            return new_rate
        rate = new_rate
        # Bound rate to reasonable range
        rate = max(-0.5, min(2.0, rate))
    return rate

# ============================================================
# MODEL 5: DEEPSEEK WEIGHTED
# 60% DCF + 40% EPV blend
# ============================================================
def deepseek_irr(t, years=5):
    """
    DeepSeek: Triangulated IV from DCF and EPV
    Most comprehensive with stress test considerations
    """
    price = get_metric(t, "price") or 0
    market_cap = get_metric(t, "market_cap") or 0
    if price <= 0 or market_cap <= 0:
        return 0
    
    shares = market_cap / price
    fcf = get_metric(t, "fcf_current") or 0
    roic = get_metric(t, "roic_current", "roic_3y_avg") or 0.15
    wacc = get_metric(t, "wacc") or 0.10
    
    # MODEL A: DCF (60% weight)
    if fcf > 0:
        growth = min(get_metric(t, "revenue_growth_3y") or 0.05, 0.20)
        terminal_growth = 0.025
        
        # 10-year projection
        pv_fcf = 0
        current_fcf = fcf
        for yr in range(1, 11):
            fade_growth = growth + (terminal_growth - growth) * (yr / 10)
            current_fcf = current_fcf * (1 + fade_growth)
            pv_fcf += current_fcf / (1 + wacc) ** yr
        
        # Terminal value
        terminal_value = current_fcf * (1 + terminal_growth) / (wacc - terminal_growth)
        pv_terminal = terminal_value / (1 + wacc) ** 10
        
        dcf_value = (pv_fcf + pv_terminal) / shares
    else:
        dcf_value = 0
    
    # MODEL B: EPV (40% weight)
    # EPV = No-Growth Value + Growth Premium
    revenue = get_metric(t, "revenue_annual") or market_cap * 0.5
    gm = get_metric(t, "gross_margin") or 0.5
    operating_margin = gm * 0.4  # Rough estimate
    nopat = revenue * operating_margin * (1 - 0.21)
    
    no_growth_value = nopat / wacc if wacc > 0 else 0
    
    # Growth premium
    rr = 0.5
    if wacc > terminal_growth:
        growth_factor = (rr * (roic - wacc)) / (wacc * (wacc - terminal_growth))
        growth_premium = nopat * max(0, growth_factor)
    else:
        growth_premium = 0
    
    epv_value = (no_growth_value + growth_premium) / shares if shares > 0 else 0
    
    # Triangulated IV: 60% DCF + 40% EPV
    intrinsic_value = 0.60 * dcf_value + 0.40 * epv_value
    
    if intrinsic_value <= 0:
        return 0
    
    # IRR to intrinsic value
    irr = (intrinsic_value / price) ** (1/years) - 1
    return irr


def run_all_models():
    """Run all 5 models on watchlist"""
    
    # Load watchlist
    with open("stage2_master_watchlist.json") as f:
        data = json.load(f)
    
    watchlist_tickers = set(t["ticker"] for t in data["watchlist"])
    
    # Load cache data
    cache_dir = Path("cache/ticker_data")
    results = []
    
    for f in sorted(cache_dir.glob("*.json")):
        ticker = f.stem
        if ticker not in watchlist_tickers:
            continue
        
        with open(f) as file:
            t = json.load(file)
        
        if t.get("data_quality") != "complete":
            continue
        
        price = get_metric(t, "price") or 0
        
        # Run all 5 models
        gemini = gemini_irr(t) * 100
        claude = claude_irr(t) * 100
        copilot = copilot_irr(t) * 100
        grok = grok_irr(t) * 100
        deepseek = deepseek_irr(t) * 100
        
        # Average and consensus
        models = [gemini, claude, copilot, grok, deepseek]
        valid_models = [m for m in models if -50 < m < 100]
        avg_irr = sum(valid_models) / len(valid_models) if valid_models else 0
        
        # Count BUY signals (IRR > 15%)
        buy_count = sum(1 for m in valid_models if m > 15)
        
        results.append({
            "ticker": ticker,
            "name": t.get("company_name", "")[:20],
            "price": price,
            "mcap_b": (t.get("market_cap", 0) or 0) / 1e9,
            "roic": get_metric(t, "roic_current", "roic_3y_avg") * 100,
            "vcr": get_metric(t, "value_creation_ratio"),
            "gemini": gemini,
            "claude": claude,
            "copilot": copilot,
            "grok": grok,
            "deepseek": deepseek,
            "avg_irr": avg_irr,
            "buy_count": buy_count,
        })
    
    # Sort by average IRR
    results.sort(key=lambda x: x["avg_irr"], reverse=True)
    
    # Print results
    print("=" * 120)
    print("5-MODEL IRR COMPARISON - CAPITAL COMPOUNDERS WATCHLIST")
    print("=" * 120)
    print(f"{'Ticker':<8} {'Name':<20} {'Price':>8} {'ROIC':>6} {'VCR':>5} {'Gemini':>8} {'Claude':>8} {'Copilot':>8} {'Grok':>8} {'DeepSk':>8} {'AVG':>7} {'BUY':>4}")
    print("-" * 120)
    
    for r in results[:60]:
        print(f"{r['ticker']:<8} {r['name']:<20} ${r['price']:>6.0f} {r['roic']:>5.0f}% {r['vcr']:>5.1f} {r['gemini']:>7.1f}% {r['claude']:>7.1f}% {r['copilot']:>7.1f}% {r['grok']:>7.1f}% {r['deepseek']:>7.1f}% {r['avg_irr']:>6.1f}% {r['buy_count']:>3}/5")
    
    if len(results) > 60:
        print(f"... +{len(results)-60} more")
    
    # Summary stats
    print()
    print("=" * 120)
    print("SUMMARY BY CONSENSUS")
    print("-" * 120)
    
    unanimous_buy = [r for r in results if r["buy_count"] == 5]
    strong_buy = [r for r in results if r["buy_count"] >= 4]
    buy = [r for r in results if r["buy_count"] >= 3]
    
    print(f"Unanimous BUY (5/5 models): {len(unanimous_buy)}")
    for r in unanimous_buy[:15]:
        print(f"  {r['ticker']:<8} AVG IRR: {r['avg_irr']:>5.1f}% | Price: ${r['price']:.0f}")
    
    print(f"\nStrong BUY (4-5/5 models): {len(strong_buy)}")
    print(f"BUY (3+/5 models): {len(buy)}")
    
    # Save results
    output = {
        "run_date": datetime.now().isoformat(),
        "total_analyzed": len(results),
        "unanimous_buy": len(unanimous_buy),
        "strong_buy": len(strong_buy),
        "results": results,
    }
    
    with open("irr_5_model_comparison.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 irr_5_model_comparison.json ({len(results)} tickers)")

if __name__ == "__main__":
    run_all_models()
