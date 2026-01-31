"""
5-MODEL IRR + INTRINSIC VALUE TARGETS
Shows implied price from each model vs current price
"""
import json
from pathlib import Path
from datetime import datetime
import math

def safe_div(a, b, default=0):
    if b is None or b == 0:
        return default
    return a / b if a else default

def get_metric(t, *keys, default=0):
    for k in keys:
        v = t.get(k)
        if v is not None:
            return v
    return default

# ============================================================
# MODEL 1: GEMINI - FCF Yield + Growth Engine
# ============================================================
def gemini_model(t):
    price = get_metric(t, "price") or 0
    fcf_yield = get_metric(t, "fcf_yield", "enterprise_yield") or 0
    roic = get_metric(t, "roic_current", "roic_3y_avg") or 0
    
    payout = get_metric(t, "dividend_yield", default=0) / max(fcf_yield, 0.01)
    rr = max(0.3, min(0.8, 1 - payout)) if payout < 1 else 0.5
    growth_engine = roic * rr
    
    vcr = get_metric(t, "value_creation_ratio") or 2
    if vcr > 3:
        multiple_shift = -0.03 * (vcr - 3)
    elif vcr < 1.5:
        multiple_shift = 0.02 * (1.5 - vcr)
    else:
        multiple_shift = 0
    
    irr = fcf_yield + growth_engine + multiple_shift
    
    # IV: What price gives 15% IRR?
    # 15% = fcf_yield_new + growth_engine + multiple_shift
    # fcf_yield_new = FCF / IV
    # Solve: 0.15 = (FCF/IV) + growth_engine + multiple_shift
    fcf = get_metric(t, "fcf_current") or 0
    target_yield = 0.15 - growth_engine - multiple_shift
    
    if target_yield > 0.01 and fcf > 0:
        market_cap = get_metric(t, "market_cap") or 0
        shares = market_cap / price if price > 0 else 1
        iv = fcf / target_yield / shares if shares > 0 else 0
    else:
        # High growth = IV is much higher
        iv = price * (1 + irr) ** 5 / (1.15) ** 5 if irr > 0 else price
    
    return irr * 100, max(0, iv)

# ============================================================
# MODEL 2: CLAUDE - EPS Power with P/E Compression
# ============================================================
def claude_model(t, years=3):
    price = get_metric(t, "price") or 0
    if price <= 0:
        return 0, 0
    
    fcf = get_metric(t, "fcf_current") or 0
    market_cap = get_metric(t, "market_cap") or 1
    shares = market_cap / price if price > 0 else 1
    fcf_per_share = fcf / shares if shares > 0 else 0
    
    if fcf_per_share <= 0:
        return 0, 0
    
    roic = get_metric(t, "roic_current", "roic_3y_avg") or 0.15
    hist_growth = get_metric(t, "revenue_growth_3y") or 0.05
    rr = 0.6
    sustainable_growth = min(hist_growth, roic * rr, 0.25)
    
    future_eps = fcf_per_share * (1 + sustainable_growth) ** years
    
    current_pe = price / fcf_per_share if fcf_per_share > 0 else 20
    exit_pe = min(current_pe, 18 + (current_pe - 18) * 0.5)
    
    future_value = future_eps * exit_pe
    irr = (future_value / price) ** (1/years) - 1 if future_value > 0 else 0
    
    # IV: Price where IRR = 15%
    # 0.15 = (FV / IV)^(1/3) - 1
    # 1.15^3 = FV / IV
    # IV = FV / 1.15^3
    iv = future_value / (1.15 ** years) if future_value > 0 else 0
    
    return irr * 100, max(0, iv)

# ============================================================
# MODEL 3: COPILOT - Value Growth
# ============================================================
def copilot_model(t, years=5):
    price = get_metric(t, "price") or 0
    market_cap = get_metric(t, "market_cap") or 0
    if price <= 0 or market_cap <= 0:
        return 0, 0
    
    shares = market_cap / price
    fcf = get_metric(t, "fcf_current") or 0
    oe_per_share = fcf / shares if shares > 0 else 0
    
    if oe_per_share <= 0:
        return 0, 0
    
    roic = get_metric(t, "roic_current", "roic_3y_avg") or 0.15
    rr = min(0.6, max(0.3, 1 - get_metric(t, "dividend_yield", default=0) * 10))
    value_growth = min(roic * rr, 0.20)
    
    future_oe = oe_per_share * (1 + value_growth) ** years
    
    if value_growth > 0.15:
        terminal_pe = 20
    elif value_growth > 0.10:
        terminal_pe = 17
    else:
        terminal_pe = 14
    
    future_value = future_oe * terminal_pe
    irr = (future_value / price) ** (1/years) - 1 if future_value > 0 else 0
    
    # IV = FV / 1.15^5
    iv = future_value / (1.15 ** years) if future_value > 0 else 0
    
    return irr * 100, max(0, iv)

# ============================================================
# MODEL 4: GROK - Full DCF
# ============================================================
def grok_model(t):
    price = get_metric(t, "price") or 0
    market_cap = get_metric(t, "market_cap") or 0
    if price <= 0 or market_cap <= 0:
        return 0, 0
    
    shares = market_cap / price
    fcf = get_metric(t, "fcf_current") or 0
    
    if fcf <= 0:
        return 0, 0
    
    hist_growth = get_metric(t, "revenue_growth_3y") or 0.05
    wacc = get_metric(t, "wacc") or 0.10
    
    growth_rates = []
    start_growth = min(hist_growth, 0.25)
    for yr in range(5):
        fade = start_growth + (0.03 - start_growth) * (yr / 4)
        growth_rates.append(fade)
    
    fcf_projections = []
    current_fcf = fcf
    for g in growth_rates:
        current_fcf = current_fcf * (1 + g)
        fcf_projections.append(current_fcf)
    
    terminal_growth = 0.025
    terminal_value = fcf_projections[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    
    cash_flows = [-market_cap]
    for i, cf in enumerate(fcf_projections):
        if i == 4:
            cash_flows.append(cf + terminal_value)
        else:
            cash_flows.append(cf)
    
    irr = calculate_irr(cash_flows)
    
    # IV = Sum of PV of cash flows at 15% discount
    iv_total = 0
    for i, cf in enumerate(fcf_projections):
        iv_total += cf / (1.15 ** (i + 1))
    iv_total += terminal_value / (1.15 ** 5)
    iv = iv_total / shares if shares > 0 else 0
    
    return irr * 100, max(0, iv)

def calculate_irr(cash_flows, guess=0.1, max_iter=100, tol=1e-6):
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
        rate = max(-0.5, min(2.0, rate))
    return rate

# ============================================================
# MODEL 5: DEEPSEEK - 60% DCF + 40% EPV
# ============================================================
def deepseek_model(t, years=5):
    price = get_metric(t, "price") or 0
    market_cap = get_metric(t, "market_cap") or 0
    if price <= 0 or market_cap <= 0:
        return 0, 0
    
    shares = market_cap / price
    fcf = get_metric(t, "fcf_current") or 0
    roic = get_metric(t, "roic_current", "roic_3y_avg") or 0.15
    wacc = get_metric(t, "wacc") or 0.10
    
    # DCF (60%)
    if fcf > 0:
        growth = min(get_metric(t, "revenue_growth_3y") or 0.05, 0.20)
        terminal_growth = 0.025
        
        pv_fcf = 0
        current_fcf = fcf
        for yr in range(1, 11):
            fade_growth = growth + (terminal_growth - growth) * (yr / 10)
            current_fcf = current_fcf * (1 + fade_growth)
            pv_fcf += current_fcf / (1 + wacc) ** yr
        
        terminal_value = current_fcf * (1 + terminal_growth) / (wacc - terminal_growth)
        pv_terminal = terminal_value / (1 + wacc) ** 10
        
        dcf_value = (pv_fcf + pv_terminal) / shares
    else:
        dcf_value = 0
    
    # EPV (40%)
    revenue = get_metric(t, "revenue_annual") or market_cap * 0.5
    gm = get_metric(t, "gross_margin") or 0.5
    operating_margin = gm * 0.4
    nopat = revenue * operating_margin * (1 - 0.21)
    
    no_growth_value = nopat / wacc if wacc > 0 else 0
    
    rr = 0.5
    terminal_growth = 0.025
    if wacc > terminal_growth:
        growth_factor = (rr * (roic - wacc)) / (wacc * (wacc - terminal_growth))
        growth_premium = nopat * max(0, growth_factor)
    else:
        growth_premium = 0
    
    epv_value = (no_growth_value + growth_premium) / shares if shares > 0 else 0
    
    # Triangulated IV
    iv = 0.60 * dcf_value + 0.40 * epv_value
    
    irr = (iv / price) ** (1/years) - 1 if iv > 0 else 0
    
    return irr * 100, max(0, iv)


def run_all_models():
    with open("stage2_master_watchlist.json") as f:
        data = json.load(f)
    
    watchlist_tickers = set(t["ticker"] for t in data["watchlist"])
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
        if price <= 0:
            continue
        
        # Run all models
        gem_irr, gem_iv = gemini_model(t)
        cla_irr, cla_iv = claude_model(t)
        cop_irr, cop_iv = copilot_model(t)
        gro_irr, gro_iv = grok_model(t)
        dee_irr, dee_iv = deepseek_model(t)
        
        # Filter outliers for averages
        irrs = [gem_irr, cla_irr, cop_irr, gro_irr, dee_irr]
        ivs = [gem_iv, cla_iv, cop_iv, gro_iv, dee_iv]
        
        valid_irrs = [i for i in irrs if -50 < i < 150]
        valid_ivs = [i for i in ivs if 0 < i < price * 10]
        
        avg_irr = sum(valid_irrs) / len(valid_irrs) if valid_irrs else 0
        avg_iv = sum(valid_ivs) / len(valid_ivs) if valid_ivs else price
        
        # Upside/downside
        upside = (avg_iv / price - 1) * 100 if price > 0 else 0
        
        buy_count = sum(1 for i in valid_irrs if i > 15)
        
        results.append({
            "ticker": ticker,
            "name": t.get("company_name", "")[:18],
            "price": price,
            "roic": get_metric(t, "roic_current", "roic_3y_avg") * 100,
            "vcr": get_metric(t, "value_creation_ratio"),
            "gem_irr": gem_irr, "gem_iv": gem_iv,
            "cla_irr": cla_irr, "cla_iv": cla_iv,
            "cop_irr": cop_irr, "cop_iv": cop_iv,
            "gro_irr": gro_irr, "gro_iv": gro_iv,
            "dee_irr": dee_irr, "dee_iv": dee_iv,
            "avg_irr": avg_irr,
            "avg_iv": avg_iv,
            "upside": upside,
            "buy_count": buy_count,
        })
    
    # Sort by upside
    results.sort(key=lambda x: x["upside"], reverse=True)
    
    print("=" * 160)
    print("5-MODEL IRR + INTRINSIC VALUE COMPARISON")
    print("=" * 160)
    print(f"{'Ticker':<7} {'Name':<18} {'Price':>7} {'Gemini':>18} {'Claude':>18} {'Copilot':>18} {'Grok':>18} {'DeepSeek':>18} {'AVG IV':>8} {'Upside':>8}")
    print(f"{'':7} {'':18} {'':>7} {'IRR':>8} {'IV':>8} {'IRR':>8} {'IV':>8} {'IRR':>8} {'IV':>8} {'IRR':>8} {'IV':>8} {'IRR':>8} {'IV':>8} {'':>8} {'':>8}")
    print("-" * 160)
    
    for r in results[:60]:
        print(f"{r['ticker']:<7} {r['name']:<18} ${r['price']:>5.0f}  "
              f"{r['gem_irr']:>6.0f}% ${r['gem_iv']:>6.0f}  "
              f"{r['cla_irr']:>6.0f}% ${r['cla_iv']:>6.0f}  "
              f"{r['cop_irr']:>6.0f}% ${r['cop_iv']:>6.0f}  "
              f"{r['gro_irr']:>6.0f}% ${r['gro_iv']:>6.0f}  "
              f"{r['dee_irr']:>6.0f}% ${r['dee_iv']:>6.0f}  "
              f"${r['avg_iv']:>6.0f}  {r['upside']:>+6.0f}%")
    
    if len(results) > 60:
        print(f"... +{len(results)-60} more")
    
    # Summary
    print()
    print("=" * 160)
    print("TOP OPPORTUNITIES BY UPSIDE TO INTRINSIC VALUE")
    print("-" * 160)
    
    big_upside = [r for r in results if r["upside"] > 50 and r["buy_count"] >= 3]
    print(f"\n🎯 HIGH CONVICTION (>50% upside, 3+ models BUY): {len(big_upside)}")
    for r in big_upside[:20]:
        print(f"  {r['ticker']:<7} Price: ${r['price']:<6.0f} → Avg IV: ${r['avg_iv']:<6.0f} ({r['upside']:+.0f}%) | {r['buy_count']}/5 BUY")
    
    fair_value = [r for r in results if -10 < r["upside"] < 10]
    print(f"\n⚖️  FAIRLY VALUED (±10%): {len(fair_value)}")
    
    overvalued = [r for r in results if r["upside"] < -20]
    print(f"\n⚠️  POTENTIALLY OVERVALUED (>20% downside): {len(overvalued)}")
    for r in overvalued[:10]:
        print(f"  {r['ticker']:<7} Price: ${r['price']:<6.0f} → Avg IV: ${r['avg_iv']:<6.0f} ({r['upside']:+.0f}%)")
    
    # Save
    output = {
        "run_date": datetime.now().isoformat(),
        "total": len(results),
        "high_conviction": len(big_upside),
        "results": results,
    }
    
    with open("irr_5_model_iv.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 irr_5_model_iv.json ({len(results)} tickers)")

if __name__ == "__main__":
    run_all_models()
