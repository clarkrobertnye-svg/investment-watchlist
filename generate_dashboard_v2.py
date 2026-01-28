import json
from pathlib import Path
from datetime import datetime

cache_dir = Path("cache/ticker_data")
tickers_data = []

for f in cache_dir.glob("*.json"):
    with open(f) as file:
        data = json.load(file)
        if data.get("data_quality") == "complete":
            tickers_data.append(data)



def deduplicate_by_company(data_list):
    """
    Keep only one listing per company - prefer most robust data.
    Priority: Primary listing > Data completeness > Market cap
    """
    from collections import defaultdict
    
    def data_quality_score(t):
        """Score ticker by data robustness (higher = better)"""
        score = 0
        ticker = t.get("ticker", "")
        
        # Preferred tickers (higher US liquidity) - add 5000 to always win
        PREFERRED_TICKERS = {"EVVTY", "ATDRY", "NVO", "RELX"}
        if ticker in PREFERRED_TICKERS:
            score += 5000
        
        # Prefer primary listings over OTC (F/Y suffix = OTC pink sheets)
        if not ticker.endswith("F") and not ticker.endswith("Y"):
            score += 1000  # Strong preference for primary listings
        
        # Prefer shorter tickers (usually primary: RELX vs RLXXF)
        score += (10 - len(ticker)) * 10
        
        # Data completeness - count non-null key fields
        key_fields = ["roic_current", "roic_3y_avg", "gross_margin", "revenue_growth_3y",
                      "fcf_conversion", "incremental_roic", "value_creation_ratio", 
                      "market_cap", "price", "enterprise_yield"]
        for field in key_fields:
            if t.get(field) is not None and t.get(field) != 0:
                score += 10
        
        # Market cap as tiebreaker
        mcap = t.get("market_cap", 0) or 0
        score += mcap / 1e12  # Add fraction based on market cap
        
        return score
    
    by_company = defaultdict(list)
    for t in data_list:
        name = t.get("company_name", "").strip().lower()
        for suffix in [" inc.", " inc", " ltd.", " ltd", " plc", " corp.", " corp", 
                       " n.v.", " a/s", " ag", " se", " sa", " limited", " group"]:
            name = name.replace(suffix, "")
        name = name.strip()
        if name:
            by_company[name].append(t)
    
    deduped = []
    removed_count = 0
    for name, listings in by_company.items():
        if len(listings) == 1:
            deduped.append(listings[0])
        else:
            # Sort by data quality score (highest first)
            listings.sort(key=data_quality_score, reverse=True)
            deduped.append(listings[0])
            removed = [l.get("ticker") for l in listings[1:]]
            removed_count += len(removed)
            print(f"  Dedup: Kept {listings[0].get('ticker'):8} | Removed: {', '.join(removed)}")
    
    print(f"  Total: {len(data_list)} -> {len(deduped)} ({removed_count} duplicates removed)")
    return deduped


# Apply deduplication
print("Deduplicating by company name...")
tickers_data = deduplicate_by_company(tickers_data)

def passes_filters(t):
    roic = t.get("roic_3y_avg") or t.get("roic_current") or 0
    roic_ex_gw = t.get("roic_ex_goodwill_3y_avg") or t.get("roic_ex_goodwill") or 0
    inc_roic = t.get("incremental_roic", 0)
    gm = t.get("gross_margin", 0)
    fcf = t.get("fcf_conversion", 0)
    growth = t.get("revenue_growth_3y", 0)
    capex = t.get("capex_to_revenue", 0)
    leverage = t.get("net_debt_ebitda", 0)
    vcr = t.get("value_creation_ratio", 0)
    
    roic_pass = (roic >= 0.20) or (roic_ex_gw >= 0.20)
    capex_pass = (capex <= 0.07) or (inc_roic >= 0.15)
    fcf_pass = (fcf >= 0.80) or (fcf >= 0.60 and inc_roic >= 0.15)
    inc_roic_pass = inc_roic >= -0.05
    vcr_pass = vcr >= 1.0
    
    # Growth Override: High-growth disruptors get a pass on low VCR
    growth_override = (growth >= 0.15 and gm >= 0.70)
    if growth_override and not vcr_pass:
        vcr_pass = True
    
    # Value Trap Filter: VCR < 1.2 AND declining trend (unless growth override)
    trend = t.get("roic_trend", 0) or 0
    is_value_trap = (vcr < 1.2 and trend < -0.10 and not growth_override)
    if is_value_trap:
        vcr_pass = False  # Force fail for value traps
    
    return roic_pass and gm >= 0.60 and fcf_pass and growth >= 0.09 and capex_pass and leverage <= 3.0 and inc_roic_pass and vcr_pass

def get_filter_failures(t):
    failures = []
    roic = t.get("roic_3y_avg") or t.get("roic_current") or 0
    roic_ex_gw = t.get("roic_ex_goodwill_3y_avg") or t.get("roic_ex_goodwill") or 0
    inc_roic = t.get("incremental_roic", 0)
    gm = t.get("gross_margin", 0)
    fcf = t.get("fcf_conversion", 0)
    growth = t.get("revenue_growth_3y", 0)
    capex = t.get("capex_to_revenue", 0)
    leverage = t.get("net_debt_ebitda", 0)
    vcr = t.get("value_creation_ratio", 0)
    
    if not ((roic >= 0.20) or (roic_ex_gw >= 0.20)):
        failures.append(f"ROIC {max(roic, roic_ex_gw)*100:.0f}% < 20%")
    if gm < 0.60:
        failures.append(f"GM {gm*100:.0f}% < 60%")
    if not ((fcf >= 0.80) or (fcf >= 0.60 and inc_roic >= 0.15)):
        failures.append(f"FCF {fcf*100:.0f}% < 80%")
    if growth < 0.09:
        failures.append(f"Growth {growth*100:.1f}% < 9%")
    if not ((capex <= 0.07) or (inc_roic >= 0.15)):
        failures.append(f"CapEx {capex*100:.1f}% > 7%")
    if leverage > 3.0:
        failures.append(f"Leverage {leverage:.1f}x > 3x")
    if inc_roic < -0.05:
        failures.append(f"Inc ROIC {inc_roic*100:.0f}% < -5%")
    if vcr < 1.0:
        failures.append(f"VCR {vcr:.1f}x < 1.0 (Value Destroyer)")
    
    return failures

def select_best_model(t):
    fcf_yield = t.get("fcf_yield") or 0
    ent_yield = t.get("enterprise_yield") or 0
    base_yield = max(fcf_yield, ent_yield)
    
    roic = t.get("roic_3y_avg") or t.get("roic_current") or 0
    roic_ex_gw = t.get("roic_ex_goodwill_3y_avg") or t.get("roic_ex_goodwill") or 0
    growth = t.get("revenue_growth_3y", 0)
    inc_roic = t.get("incremental_roic", 0)
    gm = t.get("gross_margin", 0)
    capex = t.get("capex_to_revenue", 0)
    goodwill_pct = t.get("goodwill_pct", 0)
    
    if inc_roic == 0 or inc_roic < 0.05:
        model = "Mature"
        irr = base_yield + min(growth, 0.10)
    elif growth > 0.25 and roic < 0.15:
        model = "DCF-Fade"
        irr = base_yield + min(growth, 0.15) * 0.70
    elif gm > 0.80 and capex < 0.03:
        model = "Platform"
        irr = base_yield + min(growth, 0.20)
    elif goodwill_pct > 0.30 and roic_ex_gw > roic * 1.5:
        model = "Ex-Goodwill"
        capped_roic_ex_gw = min(roic_ex_gw, 0.30)
        blended_roic = (roic + capped_roic_ex_gw) / 2
        sustainable_g = min(growth, blended_roic * 0.8)
        irr = base_yield + sustainable_g
    elif roic > 0.25 and growth > 0.10:
        model = "Compounder"
        sustainable_g = min(growth, roic * 0.6)
        irr = base_yield + sustainable_g
    else:
        model = "Standard"
        irr = base_yield + min(growth, 0.15)
    
    return model, irr

# Use pre-calculated IRR from Stage 4 if available, otherwise calculate
for t in tickers_data:
    if t.get("model_irr"):
        t["val_model"] = t.get("val_model", "Cached")
    else:
        model, irr = select_best_model(t)
        t["model_irr"] = irr
        t["val_model"] = model
    
    t["price_target"] = t.get("price", 0) * (1 + t["model_irr"])
    if t["model_irr"] >= 0.20:
        t["signal"] = "BUY"
    elif t["model_irr"] >= 0.12:
        t["signal"] = "HOLD"
    else:
        t["signal"] = "OFF"

# Filter to displayable (IRR >= 12% and VCR >= 1.0, excluding value traps)
def is_displayable(t):
    irr = t.get("model_irr", 0) or 0
    vcr = t.get("value_creation_ratio", 0) or 0
    trend = t.get("roic_trend", 0) or 0
    growth = t.get("revenue_growth_3y", 0) or 0
    gm = t.get("gross_margin", 0) or 0
    
    # Basic requirements
    if irr < 0.12 or vcr < 1.0:
        return False
    
    # Value Trap Filter: VCR < 1.2 AND declining trend (unless high-growth override)
    growth_override = (growth >= 0.15 and gm >= 0.70)
    is_value_trap = (vcr < 1.2 and trend < -0.10 and not growth_override)
    
    return not is_value_trap

displayable = [t for t in tickers_data if is_displayable(t)]
displayable_sorted = sorted(displayable, key=lambda x: x.get("model_irr", 0), reverse=True)

buy_positions = [t for t in displayable if t["signal"] == "BUY"]
hold_positions = [t for t in displayable if t["signal"] == "HOLD"]

port_irr = sum(t["model_irr"] for t in buy_positions) / len(buy_positions) * 100 if buy_positions else 0
port_roic = sum((t.get("roic_3y_avg") or t.get("roic_current") or 0) for t in buy_positions) / len(buy_positions) * 100 if buy_positions else 0
port_vcr = sum(t.get("value_creation_ratio", 0) for t in buy_positions) / len(buy_positions) if buy_positions else 0

fed_funds = 4.25
ten_year = 4.50
sp500_roic = 12.0
sp500_irr = 10.7

universe_count = len(tickers_data)

# Build all ticker data for search
all_ticker_data = {}
for t in tickers_data:
    roic_curr = t.get("roic_current") or 0
    wacc = t.get("wacc", 0.10)
    vcr = t.get("value_creation_ratio", 0)
    irr = t.get("model_irr", 0)
    
    if irr >= 0.20 and vcr >= 1.0:
        signal = "BUY"
    elif irr >= 0.12 and vcr >= 1.0:
        signal = "HOLD"
    else:
        signal = "FILTERED"
    
    failures = get_filter_failures(t)
    
    all_ticker_data[t["ticker"]] = {
        "name": t.get("company_name", ""),
        "roic": roic_curr * 100,
        "roic_3y": (t.get("roic_3y_avg") or 0) * 100,
        "vcr": vcr,
        "wacc": wacc * 100,
        "ep_spread": (roic_curr - wacc) * 100,
        "roic_trend": t.get("roic_trend", 0) * 100,
        "gm": t.get("gross_margin", 0) * 100,
        "growth_pct": (t.get("revenue_growth_3y") or 0) * 100,
        "model": t.get("val_model", ""),
        "irr": irr * 100,
        "signal": signal,
        "mcap": t.get("market_cap", 0) / 1e9,
        "price": t.get("price", 0),
        "target": t.get("price", 0) * (1 + irr),
        "failures": failures,
    }

all_ticker_json = json.dumps(all_ticker_data)

html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Capital Compounders Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0f; color: #e0e0e0; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; color: #00d4aa; margin-bottom: 10px; }
        .header .subtitle { color: #888; font-size: 1.1em; }
        
        .market-context { display: grid; grid-template-columns: repeat(6, 1fr); gap: 15px; margin-bottom: 30px; }
        .market-card { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #333; }
        .market-card.highlight { border: 1px solid #00d4aa; background: linear-gradient(135deg, #1a2a2e 0%, #162e3e 100%); }
        .market-card .label { color: #888; font-size: 0.85em; margin-bottom: 5px; }
        .market-card .value { font-size: 1.8em; font-weight: bold; color: #00d4aa; }
        .market-card.highlight .value { color: #00ff88; }
        .market-card .detail { color: #666; font-size: 0.8em; margin-top: 5px; }
        
        .compare-section { background: #1a1a2e; border-radius: 12px; padding: 20px; margin-bottom: 30px; border: 1px solid #333; }
        .compare-section h3 { color: #00d4aa; margin-bottom: 15px; }
        .compare-input { display: flex; gap: 10px; margin-bottom: 15px; }
        .compare-input input { flex: 1; padding: 12px 15px; border-radius: 8px; border: 1px solid #333; background: #0a0a0f; color: #fff; font-size: 1em; }
        .compare-input button { padding: 12px 25px; border-radius: 8px; border: none; background: #00d4aa; color: #0a0a0f; font-weight: bold; cursor: pointer; }
        .compare-result { display: none; background: #0a0a0f; border-radius: 8px; padding: 15px; margin-top: 15px; }
        .compare-result.show { display: block; }
        .compare-result table { width: 100%; }
        .compare-result th { text-align: left; color: #888; padding: 8px; font-weight: normal; font-size: 0.75em; }
        .compare-result td { padding: 8px; font-size: 0.85em; }
        .fail-reason { color: #ff6b6b; font-size: 0.85em; margin-top: 10px; }
        
        .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }
        .summary-card { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 12px; padding: 25px; text-align: center; border: 1px solid #333; }
        .summary-card.buy { border: 1px solid #00ff88; background: linear-gradient(135deg, #1a2a1e 0%, #162e1e 100%); }
        .summary-card.hold { border: 1px solid #ffaa00; background: linear-gradient(135deg, #2a2a1e 0%, #2e2e1e 100%); }
        .summary-card .number { font-size: 3em; font-weight: bold; color: #00d4aa; }
        .summary-card.buy .number { color: #00ff88; }
        .summary-card.hold .number { color: #ffaa00; }
        .summary-card .label { color: #888; margin-top: 5px; }
        
        table.main-table { width: 100%; border-collapse: collapse; background: #1a1a2e; border-radius: 12px; overflow: hidden; }
        table.main-table th { background: #16213e; color: #00d4aa; padding: 10px 4px; text-align: left; font-weight: 600; font-size: 0.65em; cursor: pointer; white-space: nowrap; }
        table.main-table th:hover { background: #1a2a3e; }
        table.main-table th.sorted-asc::after { content: " ▲"; }
        table.main-table th.sorted-desc::after { content: " ▼"; }
        table.main-table td { padding: 8px 4px; border-bottom: 1px solid #2a2a3e; font-size: 0.7em; }
        table.main-table tr:hover { background: #252540; }
        table.main-table tr.buy-row { background: rgba(0, 255, 136, 0.05); }
        .ticker { font-weight: bold; color: #00d4aa; }
        .signal-tag { font-size: 0.6em; padding: 2px 4px; border-radius: 4px; font-weight: bold; }
        .signal-BUY { background: #00ff88; color: #0a0a0f; }
        .signal-HOLD { background: #ffaa00; color: #0a0a0f; }
        .model-tag { font-size: 0.55em; padding: 2px 3px; border-radius: 3px; color: #888; background: #252540; }
        .irr-high { color: #00ff88; font-weight: bold; }
        .irr-mid { color: #ffaa00; }
        .vcr-gold { color: #ffd700; font-weight: bold; }
        .vcr-good { color: #00d4aa; }
        .spread-pos { color: #00ff88; }
        .spread-neg { color: #ff6b6b; }
        .trend-up { color: #00ff88; }
        .trend-down { color: #ff6b6b; }
        
        .glossary { background: #1a1a2e; border-radius: 12px; padding: 20px; margin-top: 30px; border: 1px solid #333; }
        .glossary h3 { color: #00d4aa; margin-bottom: 15px; }
        .glossary-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; }
        .glossary-item { background: #0a0a0f; padding: 12px; border-radius: 8px; }
        .glossary-item .term { color: #00d4aa; font-weight: bold; margin-bottom: 5px; font-size: 0.9em; }
        .glossary-item .definition { color: #888; font-size: 0.8em; }
        
        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 0.85em; }
    </style>
</head>
<body>
    <div class="header">
        <h1>💎 Capital Compounders</h1>
        <p class="subtitle">Value-creating businesses (VCR ≥ 1.0) with IRR ≥ 12%</p>
    </div>
    
    <div class="market-context">
        <div class="market-card highlight">
            <div class="label">Portfolio IRR</div>
            <div class="value">''' + f"{port_irr:.1f}%" + '''</div>
            <div class="detail">''' + f"{len(buy_positions)} BUY positions" + '''</div>
        </div>
        <div class="market-card highlight">
            <div class="label">Portfolio VCR</div>
            <div class="value">''' + f"{port_vcr:.1f}x" + '''</div>
            <div class="detail">All value creators</div>
        </div>
        <div class="market-card highlight">
            <div class="label">Portfolio ROIC</div>
            <div class="value">''' + f"{port_roic:.0f}%" + '''</div>
            <div class="detail">''' + f"{port_roic/sp500_roic:.1f}x S&P" + '''</div>
        </div>
        <div class="market-card">
            <div class="label">S&P 500 IRR</div>
            <div class="value">''' + f"{sp500_irr:.1f}%" + '''</div>
            <div class="detail">Earnings + Growth</div>
        </div>
        <div class="market-card">
            <div class="label">Fed Funds</div>
            <div class="value">''' + f"{fed_funds:.2f}%" + '''</div>
            <div class="detail">Target rate</div>
        </div>
        <div class="market-card">
            <div class="label">10Y Treasury</div>
            <div class="value">''' + f"{ten_year:.2f}%" + '''</div>
            <div class="detail">Risk-free rate</div>
        </div>
    </div>
    
    <div class="compare-section">
        <h3>🔍 Analyze Any Ticker</h3>
        <div class="compare-input">
            <input type="text" id="ticker-input" placeholder="Enter ticker (e.g., AAPL, MSFT)" onkeypress="if(event.key==='Enter')analyzeTicker()">
            <button onclick="analyzeTicker()">Analyze</button>
        </div>
        <div class="compare-result" id="compare-result">
            <table>
                <tr><th>Signal</th><th>Ticker</th><th>Company</th><th>Model</th><th>ROIC</th><th>VCR</th><th>EP Spread</th><th>Trend</th><th>IRR</th><th>Price</th><th>Target</th></tr>
                <tr id="compare-row"></tr>
            </table>
            <div id="fail-reasons" class="fail-reason"></div>
        </div>
    </div>
    
    <div class="summary">
        <div class="summary-card buy"><div class="number">''' + str(len(buy_positions)) + '''</div><div class="label">BUY (≥20%)</div></div>
        <div class="summary-card hold"><div class="number">''' + str(len(hold_positions)) + '''</div><div class="label">HOLD (12-20%)</div></div>
        <div class="summary-card"><div class="number">''' + str(universe_count) + '''</div><div class="label">Cached</div></div>
        <div class="summary-card"><div class="number">37,374</div><div class="label">Screened</div></div>
    </div>
    
    <table class="main-table" id="main-table">
        <thead>
            <tr>
                <th data-sort="signal" title="BUY (IRR ≥ 20%), HOLD (IRR 12-20%)">Signal</th>
                <th data-sort="ticker" title="Stock symbol">Ticker</th>
                <th data-sort="name" title="Company name">Company</th>
                <th data-sort="model" title="Valuation: Compounder, Platform, Mature, Ex-Goodwill, DCF-Fade, Standard">Model</th>
                <th data-sort="roic" title="Return on Invested Capital = NOPAT / Adjusted IC (excess cash removed)">ROIC</th>
                <th data-sort="vcr" title="Value Creation Ratio = ROIC / WACC. Above 1.0 creates value, below destroys">VCR</th>
                <th data-sort="spread" title="Economic Profit Spread = ROIC - WACC. Excess return above cost of capital">EP Spread</th>
                <th data-sort="trend" title="ROIC momentum = (Current - 3Y Avg) / 3Y Avg. Negative = deteriorating">Trend</th>
                <th data-sort="gm" title="Gross Margin = Gross Profit / Revenue. Pricing power indicator (≥60% preferred)">GM</th>
                <th data-sort="growth" title="Revenue 3Y CAGR = (Rev_now / Rev_3y_ago)^(1/3) - 1">Growth</th>
                <th data-sort="irr" class="sorted-desc" title="Implied IRR = Base Yield + Sustainable Growth. Your expected annual return">IRR</th>
                <th data-sort="price" title="Current stock price">Price</th>
                <th data-sort="target" title="Price target = Current Price × (1 + IRR)">Target</th>
                <th data-sort="mcap" title="Market capitalization">MCap</th>
            </tr>
        </thead>
        <tbody id="table-body">'''

for t in displayable_sorted:
    ticker = t.get("ticker", "")
    name = t.get("company_name", "")[:16]
    model = t.get("val_model", "")
    signal = t.get("signal", "")
    roic = (t.get("roic_current") or t.get("roic_3y_avg") or 0) * 100
    vcr = t.get("value_creation_ratio", 0)
    wacc = t.get("wacc", 0.10)
    spread = (t.get("roic_current") or 0) - wacc
    spread_pct = spread * 100
    trend = t.get("roic_trend", 0) * 100
    gm = t.get("gross_margin", 0) * 100
    growth = t.get("revenue_growth_3y", 0) * 100
    irr = t.get("model_irr", 0) * 100
    price = t.get("price", 0)
    target = t.get("price_target", 0)
    mcap = t.get("market_cap", 0) / 1e9
    
    row_class = "buy-row" if signal == "BUY" else ""
    irr_class = "irr-high" if irr >= 20 else "irr-mid"
    vcr_class = "vcr-gold" if vcr >= 2.0 else ("vcr-good" if vcr >= 1.0 else "")
    spread_class = "spread-pos" if spread >= 0 else "spread-neg"
    trend_class = "trend-up" if trend >= 0 else "trend-down"
    
    html += f'''
            <tr class="{row_class}" data-ticker="{ticker}" data-name="{name}" data-model="{model}" data-signal="{signal}" data-roic="{roic}" data-vcr="{vcr}" data-spread="{spread_pct}" data-trend="{trend}" data-gm="{gm}" data-growth="{growth}" data-irr="{irr}" data-price="{price}" data-target="{target}" data-mcap="{mcap}">
                <td><span class="signal-tag signal-{signal}">{signal}</span></td>
                <td class="ticker">{ticker}</td>
                <td>{name}</td>
                <td><span class="model-tag">{model}</span></td>
                <td>{roic:.0f}%</td>
                <td class="{vcr_class}">{vcr:.1f}x</td>
                <td class="{spread_class}">{spread_pct:+.0f}%</td>
                <td class="{trend_class}">{trend:+.0f}%</td>
                <td>{gm:.0f}%</td>
                <td>{growth:.0f}%</td>
                <td class="{irr_class}">{irr:.0f}%</td>
                <td>${price:.0f}</td>
                <td>${target:.0f}</td>
                <td>${mcap:.0f}B</td>
            </tr>'''

html += '''
        </tbody>
    </table>
    
    <div class="glossary">
        <h3>📊 Key Metrics</h3>
        <div class="glossary-grid">
            <div class="glossary-item"><div class="term">ROIC</div><div class="definition">Return on Invested Capital - efficiency turning capital into profits</div></div>
            <div class="glossary-item"><div class="term">VCR</div><div class="definition">Value Creation Ratio (ROIC/WACC) - must be ≥1.0</div></div>
            <div class="glossary-item"><div class="term">EP Spread</div><div class="definition">Economic Profit Spread (ROIC - WACC)</div></div>
            <div class="glossary-item"><div class="term">IRR</div><div class="definition">Implied Return Rate (Yield + Growth)</div></div>
        </div>
    </div>
    
    <div class="footer">
        <p>Last updated: ''' + datetime.now().strftime("%B %d, %Y %H:%M") + '''</p>
    </div>
    
    <script>
        const tickerData = ''' + all_ticker_json + ''';
        
        let currentSort = { column: 'irr', direction: 'desc' };
        
        document.querySelectorAll('th[data-sort]').forEach(th => {
            th.addEventListener('click', () => {
                const column = th.dataset.sort;
                const direction = (currentSort.column === column && currentSort.direction === 'desc') ? 'asc' : 'desc';
                document.querySelectorAll('th').forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
                th.classList.add(direction === 'asc' ? 'sorted-asc' : 'sorted-desc');
                currentSort = { column, direction };
                sortTable(column, direction);
            });
        });
        
        function sortTable(column, direction) {
            const tbody = document.getElementById('table-body');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            rows.sort((a, b) => {
                let aVal = a.dataset[column] || '';
                let bVal = b.dataset[column] || '';
                if (['roic', 'vcr', 'spread', 'trend', 'gm', 'growth', 'irr', 'price', 'target', 'mcap'].includes(column)) {
                    aVal = parseFloat(aVal) || 0;
                    bVal = parseFloat(bVal) || 0;
                }
                if (direction === 'asc') return aVal > bVal ? 1 : -1;
                return aVal < bVal ? 1 : -1;
            });
            rows.forEach(row => tbody.appendChild(row));
        }
        
        function analyzeTicker() {
            const ticker = document.getElementById('ticker-input').value.toUpperCase().trim();
            const resultDiv = document.getElementById('compare-result');
            const row = document.getElementById('compare-row');
            const failDiv = document.getElementById('fail-reasons');
            
            if (!ticker) return;
            
            const data = tickerData[ticker];
            if (data) {
                const vcrClass = data.vcr >= 2.0 ? 'vcr-gold' : (data.vcr >= 1.0 ? 'vcr-good' : '');
                const spreadClass = data.ep_spread >= 0 ? 'spread-pos' : 'spread-neg';
                const trendClass = data.roic_trend >= 0 ? 'trend-up' : 'trend-down';
                const irrClass = data.irr >= 20 ? 'irr-high' : 'irr-mid';
                
                row.innerHTML = '<td><span class="signal-tag signal-' + data.signal + '">' + data.signal + '</span></td>' +
                    '<td class="ticker">' + ticker + '</td>' +
                    '<td>' + (data.name || '').substring(0, 16) + '</td>' +
                    '<td><span class="model-tag">' + data.model + '</span></td>' +
                    '<td>' + data.roic.toFixed(0) + '%</td>' +
                    '<td class="' + vcrClass + '">' + data.vcr.toFixed(1) + 'x</td>' +
                    '<td class="' + spreadClass + '">' + (data.ep_spread >= 0 ? '+' : '') + data.ep_spread.toFixed(0) + '%</td>' +
                    '<td class="' + trendClass + '">' + (data.roic_trend >= 0 ? '+' : '') + data.roic_trend.toFixed(0) + '%</td>' +
                    '<td class="' + irrClass + '">' + data.irr.toFixed(0) + '%</td>' +
                    '<td>$' + data.price.toFixed(0) + '</td>' +
                    '<td>$' + data.target.toFixed(0) + '</td>';
                
                failDiv.innerHTML = data.failures && data.failures.length > 0 ? 
                    '❌ ' + data.failures.join(' | ') : '';
                
                resultDiv.classList.add('show');
            } else {
                row.innerHTML = '<td colspan="11" style="color:#ff6b6b;">Ticker not in cache</td>';
                failDiv.innerHTML = '';
                resultDiv.classList.add('show');
            }
        }
    </script>
</body>
</html>'''

with open("capital_compounders_dashboard.html", "w") as f:
    f.write(html)

print(f"✅ Dashboard generated: capital_compounders_dashboard.html")
print(f"   BUY: {len(buy_positions)} | HOLD: {len(hold_positions)} | Total: {len(displayable)}")
