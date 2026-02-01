"""
Capital Compounders Dashboard Generator - V3
Matching the preferred UI design with:
- 6 top metric cards (Portfolio IRR, VCR, ROIC, S&P IRR, Fed Funds, 10Y Treasury)
- Analyze Any Ticker box
- 4 count boxes (BUY, HOLD, Cached, Screened)
- Full table with Signal, Ticker, Company, Model, ROIC, VCR, EP Spread, Trend, GM, Growth, IRR, Price, Target, MCap
"""

import json
from datetime import datetime

# === CONFIGURATION ===
CHINA_VIE_EXCLUSIONS = ['PDD', 'FUTU', 'FINV', 'NTES', 'YALA', 'ATAT']

# Value signal thresholds (matching screenshot: BUY ≥20%, HOLD 12-20%)
IRR_BUY = 20
IRR_HOLD = 12

# Quality tier thresholds (VCR = ROIC/WACC)
VCR_DIAMOND = 3.0  # ≥3x = DIAMOND
VCR_GOLD = 2.0     # ≥2x = GOLD, <2x = SILVER

# Market reference rates
SP500_IRR = 10.7
FED_FUNDS = 4.25
TREASURY_10Y = 4.50


def load_json(filepath):
    with open(filepath) as f:
        return json.load(f)


def get_tier(vcr):
    """DIAMOND ≥3x, GOLD ≥2x, SILVER 1-2x, SUB <1x"""
    return get_tier_full(vcr)


def get_signal(irr):
    """BUY ≥20%, HOLD 12-20%, below that not shown"""
    if irr >= IRR_BUY:
        return ('BUY', 'buy')
    elif irr >= IRR_HOLD:
        return ('HOLD', 'hold')
    return ('WATCH', 'watch')


def get_tier_full(vcr):
    """DIAMOND ≥3x, GOLD ≥2x, SILVER 1-2x, SUB <1x"""
    if vcr and vcr >= VCR_DIAMOND:
        return ('DIAMOND', '🔷', 'diamond')
    elif vcr and vcr >= VCR_GOLD:
        return ('GOLD', '🥇', 'gold')
    elif vcr and vcr >= 1.0:
        return ('SILVER', '🥈', 'silver')
    return ('SUB', '⬜', 'sub')


def merge_data(irr_results, universe_tickers):
    """Merge IRR results with full universe data (all 857)"""
    universe_lookup = {t['ticker']: t for t in universe_tickers}
    irr_lookup = {r['ticker']: r for r in irr_results}
    
    # Track which tickers we've processed
    processed = set()
    merged = []
    
    # First: process IRR-rated tickers
    for r in irr_results:
        ticker = r['ticker']
        if ticker in CHINA_VIE_EXCLUSIONS:
            continue
        processed.add(ticker)
            
        u = universe_lookup.get(ticker, {})
        
        irr = r.get('avg_irr', 0)
        signal_name, signal_class = get_signal(irr)
        
        # Get metrics
        roic = (u.get('roic', 0) or 0) * 100
        roic_ex_cash = (u.get('roic_ex_cash', 0) or 0) * 100
        
        # ROIC hurdle: must have ROIC >= 15% OR ROICX >= 15%
        if roic < 15 and roic_ex_cash < 15:
            continue
        
        vcr = r.get('vcr') or u.get('vcr', 0) or 0
        wacc = u.get('wacc', 0) or 0
        vcr_ex_cash = (roic_ex_cash / 100) / wacc if wacc > 0 else 0  # VCRX = ROICX / WACC
        incremental_roic = u.get('incremental_roic_5y')
        roic_trend = u.get('roic_trend', 'unknown')
        fcf_to_ni = u.get('ocf_to_net_income', 0) or 0
        fcf_to_debt = u.get('fcf_to_debt')
        
        # CapEx/OCF (capital intensity vs cash generated - lower is better)
        net_capex = u.get('net_capex', 0) or 0
        depreciation = u.get('depreciation', 0) or 0
        ocf = u.get('operating_cash_flow', 0) or 0
        gross_capex = net_capex + depreciation
        capex_to_ocf = gross_capex / ocf if ocf > 0 else None
        
        # Reinvestment rate
        rr = u.get('reinvestment_rate')
        if rr is not None:
            if 0.4 <= rr <= 0.8:
                rr_category = 'in_range'
            elif rr > 0.8:
                rr_category = 'above'
            elif rr < 0:
                rr_category = 'negative'
            else:
                rr_category = 'below'
        else:
            rr_category = 'none'
        
        merged.append({
            'ticker': ticker,
            'name': r.get('name') or u.get('company_name', ticker),
            'sector': u.get('sector', ''),
            'roic': roic,
            'roic_ex_cash': roic_ex_cash,
            'incremental_roic': incremental_roic,
            'vcr': vcr,
            'vcr_ex_cash': vcr_ex_cash,
            'roic_trend': roic_trend,
            'gm_trend': u.get('gm_trend', 'unknown'),
            'fcf_to_ni': fcf_to_ni,
            'fcf_to_debt': fcf_to_debt,
            'gross_margin': (u.get('gross_margin', 0) or 0) * 100,
            'revenue_growth': (u.get('revenue_cagr_3y', 0) or 0) * 100,
            'capex_to_ocf': capex_to_ocf,
            'reinvestment_rate': rr,
            'rr_category': rr_category,
            'market_cap': u.get('market_cap', 0) or 0,
            'avg_irr': r.get('avg_irr', 0),
            'has_irr': True,
        })
    
    # Second: process remaining universe tickers (no IRR data)
    for u in universe_tickers:
        ticker = u['ticker']
        if ticker in processed or ticker in CHINA_VIE_EXCLUSIONS:
            continue
        
        roic = (u.get('roic', 0) or 0) * 100
        roic_ex_cash = (u.get('roic_ex_cash', 0) or 0) * 100
        
        # ROIC hurdle: must have ROIC >= 15% OR ROICX >= 15%
        if roic < 15 and roic_ex_cash < 15:
            continue
        
        vcr = u.get('vcr', 0) or 0
        wacc = u.get('wacc', 0) or 0
        vcr_ex_cash = (roic_ex_cash / 100) / wacc if wacc > 0 else 0  # VCRX = ROICX / WACC
        incremental_roic = u.get('incremental_roic_5y')
        roic_trend = u.get('roic_trend', 'unknown')
        fcf_to_ni = u.get('ocf_to_net_income', 0) or 0
        fcf_to_debt = u.get('fcf_to_debt')
        
        # CapEx/OCF (capital intensity vs cash generated - lower is better)
        net_capex = u.get('net_capex', 0) or 0
        depreciation = u.get('depreciation', 0) or 0
        ocf = u.get('operating_cash_flow', 0) or 0
        gross_capex = net_capex + depreciation
        capex_to_ocf = gross_capex / ocf if ocf > 0 else None
        
        # Reinvestment rate
        rr = u.get('reinvestment_rate')
        if rr is not None:
            if 0.4 <= rr <= 0.8:
                rr_category = 'in_range'
            elif rr > 0.8:
                rr_category = 'above'
            elif rr < 0:
                rr_category = 'negative'
            else:
                rr_category = 'below'
        else:
            rr_category = 'none'
        
        merged.append({
            'ticker': ticker,
            'name': u.get('company_name', ticker),
            'sector': u.get('sector', ''),
            'roic': roic,
            'roic_ex_cash': roic_ex_cash,
            'incremental_roic': incremental_roic,
            'vcr': vcr,
            'vcr_ex_cash': vcr_ex_cash,
            'roic_trend': roic_trend,
            'gm_trend': u.get('gm_trend', 'unknown'),
            'fcf_to_ni': fcf_to_ni,
            'fcf_to_debt': fcf_to_debt,
            'gross_margin': (u.get('gross_margin', 0) or 0) * 100,
            'revenue_growth': (u.get('revenue_cagr_3y', 0) or 0) * 100,
            'capex_to_ocf': capex_to_ocf,
            'reinvestment_rate': rr,
            'rr_category': rr_category,
            'market_cap': u.get('market_cap', 0) or 0,
            'avg_irr': 0,
            'has_irr': False,
        })
    
    # Sort by ROIC descending (primary quality metric)
    merged.sort(key=lambda x: -x['roic'])
    return merged


def generate_dashboard(irr_path, universe_path, output_path='capital_compounders_dashboard.html'):
    """Generate the complete dashboard HTML"""
    
    irr_data = load_json(irr_path)
    universe_data = load_json(universe_path)
    
    companies = merge_data(
        irr_data.get('results', []),
        universe_data.get('tickers', [])
    )
    
    # ROIC Trend counts
    improving_count = sum(1 for c in companies if c['roic_trend'] == 'improving')
    stable_count = sum(1 for c in companies if c['roic_trend'] == 'stable')
    declining_count = sum(1 for c in companies if c['roic_trend'] == 'declining')
    
    # Reinvestment rate counts
    rr_in_range = sum(1 for c in companies if c['rr_category'] == 'in_range')
    rr_above = sum(1 for c in companies if c['rr_category'] == 'above')
    rr_below = sum(1 for c in companies if c['rr_category'] == 'below')
    rr_negative = sum(1 for c in companies if c['rr_category'] == 'negative')
    
    # Calculate universe averages
    avg_roic = sum(c['roic'] for c in companies) / len(companies) if companies else 0
    avg_vcr = sum(c['vcr'] for c in companies) / len(companies) if companies else 0
    
    summary = {
        'universe_count': len(companies),
        'improving_count': improving_count,
        'stable_count': stable_count,
        'declining_count': declining_count,
        'rr_in_range': rr_in_range,
        'rr_above': rr_above,
        'rr_below': rr_below,
        'rr_negative': rr_negative,
        'avg_roic': avg_roic,
        'avg_vcr': avg_vcr,
        'screened_count': 37374,
    }
    
    html = generate_html(companies, companies, summary)
    
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"✅ Dashboard generated: {output_path}")
    print(f"   📈 Improving: {improving_count} | ➡️ Stable: {stable_count} | 📉 Declining: {declining_count}")
    print(f"   📊 Universe: {len(companies)} | Avg ROIC: {avg_roic:.0f}% | Avg VCR: {avg_vcr:.1f}x")
    
    return output_path


def generate_html(active_companies, all_companies, summary):
    """Generate complete HTML matching the preferred design"""
    
    # Build table rows
    rows_html = ""
    for c in active_companies:
        roic_str = f"{c['roic']:.0f}%" if c['roic'] else "—"
        roicx_str = f"{c['roic_ex_cash']:.0f}%" if c['roic_ex_cash'] else "—"
        
        # Incremental ROIC
        inc_roic = c['incremental_roic']
        if inc_roic is not None:
            inc_roic_str = f"{inc_roic*100:.0f}%"
            inc_roic_class = 'positive' if inc_roic > c['roic']/100 else 'negative' if inc_roic < c['roic']/100 * 0.8 else ''
        else:
            inc_roic_str = "—"
            inc_roic_class = ''
        
        vcr_str = f"{c['vcr']:.1f}x" if c['vcr'] else "—"
        vcrx_str = f"{c['vcr_ex_cash']:.1f}x" if c['vcr_ex_cash'] else "—"
        
        # ROIC Trend icon
        trend = c['roic_trend']
        if trend == 'improving':
            trend_icon = '📈'
            trend_class = 'trend-up'
        elif trend == 'declining':
            trend_icon = '📉'
            trend_class = 'trend-down'
        elif trend == 'stable':
            trend_icon = '➡️'
            trend_class = 'trend-flat'
        else:
            trend_icon = '—'
            trend_class = ''
        
        # GM Trend icon
        gm_trend = c['gm_trend']
        if gm_trend == 'expanding':
            gm_trend_icon = '📈'
            gm_trend_class = 'trend-up'
        elif gm_trend == 'contracting':
            gm_trend_icon = '📉'
            gm_trend_class = 'trend-down'
        elif gm_trend == 'stable':
            gm_trend_icon = '➡️'
            gm_trend_class = 'trend-flat'
        else:
            gm_trend_icon = '—'
            gm_trend_class = ''
        
        # FCF/NI
        fcf_ni = c['fcf_to_ni']
        if fcf_ni:
            fcf_ni_str = f"{fcf_ni*100:.0f}%"
            fcf_ni_class = 'positive' if fcf_ni >= 0.8 else 'warning' if fcf_ni >= 0.5 else 'negative'
        else:
            fcf_ni_str = "—"
            fcf_ni_class = ''
        
        # FCF/Debt
        fcf_debt = c['fcf_to_debt']
        if fcf_debt is not None:
            fcf_debt_str = f"{fcf_debt*100:.0f}%"
            fcf_debt_class = 'positive' if fcf_debt >= 0.5 else 'warning' if fcf_debt >= 0.25 else 'negative'
        else:
            fcf_debt_str = "—"
            fcf_debt_class = ''
        
        gm_str = f"{c['gross_margin']:.0f}%" if c['gross_margin'] else "—"
        growth_str = f"{c['revenue_growth']:.0f}%" if c['revenue_growth'] else "—"
        
        # CapEx/OCF (capital intensity vs cash - lower is better)
        capex_ocf = c['capex_to_ocf']
        if capex_ocf is not None:
            capex_ocf_str = f"{capex_ocf*100:.0f}%"
            capex_ocf_class = 'positive' if capex_ocf <= 0.10 else 'warning' if capex_ocf <= 0.25 else 'negative'
        else:
            capex_ocf_str = "—"
            capex_ocf_class = ''
        
        # Reinvestment rate
        rr = c['reinvestment_rate']
        if rr is not None:
            rr_str = f"{rr*100:.0f}%"
        else:
            rr_str = "—"
        rr_class = c['rr_category']
        
        rows_html += f'''
        <tr class="company-row rr-{rr_class}" data-rr="{rr_class}" data-trend="{c['roic_trend']}">
            <td class="ticker-cell"><a href="https://finance.yahoo.com/quote/{c['ticker']}" target="_blank">{c['ticker']}</a></td>
            <td class="name-cell">{c['name'][:25]}</td>
            <td class="metric roic">{roic_str}</td>
            <td class="metric roicx">{roicx_str}</td>
            <td class="metric inc-roic {inc_roic_class}">{inc_roic_str}</td>
            <td class="metric vcr">{vcr_str}</td>
            <td class="metric vcrx">{vcrx_str}</td>
            <td class="metric trend {trend_class}">{trend_icon}</td>
            <td class="metric fcf-ni {fcf_ni_class}">{fcf_ni_str}</td>
            <td class="metric fcf-debt {fcf_debt_class}">{fcf_debt_str}</td>
            <td class="metric">{gm_str}</td>
            <td class="metric gm-trend {gm_trend_class}">{gm_trend_icon}</td>
            <td class="metric">{growth_str}</td>
            <td class="metric capex-ocf {capex_ocf_class}">{capex_ocf_str}</td>
            <td class="metric reinv rr-{rr_class}">{rr_str}</td>
        </tr>'''
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # Generate JSON for JavaScript lookup (for analyze box)
    companies_json = json.dumps([{
        'ticker': c['ticker'],
        'name': c['name'],
        'roic': c['roic'],
        'roic_ex_cash': c['roic_ex_cash'],
        'incremental_roic': c['incremental_roic'],
        'vcr': c['vcr'],
        'vcr_ex_cash': c['vcr_ex_cash'],
        'roic_trend': c['roic_trend'],
        'gm_trend': c['gm_trend'],
        'fcf_to_ni': c['fcf_to_ni'],
        'fcf_to_debt': c['fcf_to_debt'],
        'gross_margin': c['gross_margin'],
        'revenue_growth': c['revenue_growth'],
        'capex_to_ocf': c['capex_to_ocf'],
        'reinvestment_rate': c['reinvestment_rate'],
        'rr_category': c['rr_category'],
        'market_cap': c['market_cap'],
        'avg_irr': c['avg_irr'],
        'has_irr': c['has_irr'],
    } for c in all_companies])
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Capital Compounders</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0f0f;
            --bg-secondary: #0f1a1a;
            --bg-card: #132020;
            --bg-card-accent: #1a2a2a;
            --text-primary: #e0f0f0;
            --text-secondary: #80a0a0;
            --text-muted: #507070;
            --border: #2a4040;
            --accent-cyan: #00d4aa;
            --accent-green: #00d4aa;
            --accent-yellow: #d4aa00;
            --accent-blue: #00a4d4;
            --buy-bg: #0a2a1a;
            --buy-border: #00d4aa;
            --hold-bg: #2a2a0a;
            --hold-border: #d4aa00;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.5;
        }}
        
        .container {{ max-width: 1600px; margin: 0 auto; padding: 20px; }}
        
        /* Header */
        header {{
            text-align: center;
            padding: 30px 0 20px;
        }}
        
        h1 {{
            font-size: 2.5rem;
            color: var(--accent-cyan);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }}
        
        .tagline {{
            color: var(--text-secondary);
            margin-top: 8px;
            font-size: 1rem;
        }}
        
        /* Top Metrics Row */
        .metrics-row {{
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 15px;
            margin-bottom: 25px;
        }}
        
        .metric-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        
        .metric-card.highlight {{
            border-color: var(--accent-cyan);
            background: linear-gradient(180deg, var(--bg-card) 0%, rgba(0,212,170,0.1) 100%);
        }}
        
        .metric-card .label {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 5px;
        }}
        
        .metric-card .value {{
            font-size: 1.8rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: var(--accent-cyan);
        }}
        
        .metric-card .sublabel {{
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 3px;
        }}
        
        /* Analyze Section */
        .analyze-section {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 25px;
        }}
        
        .analyze-section h3 {{
            color: var(--accent-cyan);
            font-size: 1.1rem;
            margin-bottom: 15px;
        }}
        
        .analyze-row {{
            display: flex;
            gap: 12px;
        }}
        
        .analyze-input {{
            flex: 1;
            padding: 12px 16px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 1rem;
            font-family: 'JetBrains Mono', monospace;
        }}
        
        .analyze-input:focus {{
            outline: none;
            border-color: var(--accent-cyan);
        }}
        
        .analyze-btn {{
            padding: 12px 30px;
            background: var(--accent-cyan);
            color: #000;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .analyze-btn:hover {{
            background: #00eebb;
        }}
        
        .analyze-result {{
            margin-top: 15px;
            padding: 15px;
            background: var(--bg-card);
            border-radius: 8px;
            display: none;
        }}
        
        .analyze-result.show {{
            display: block;
        }}
        
        /* Count Boxes */
        .count-boxes {{
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 12px;
            margin-bottom: 25px;
        }}
        
        .count-box {{
            background: var(--bg-card);
            border: 2px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }}
        
        .count-box.buy {{
            background: var(--buy-bg);
            border-color: var(--buy-border);
        }}
        
        .count-box.hold {{
            background: var(--hold-bg);
            border-color: var(--hold-border);
        }}
        
        .count-box.watch-box {{
            background: rgba(128,128,128,0.05);
            border-color: #555;
        }}
        
        .count-box .number {{
            font-size: 2.5rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }}
        
        .count-box.buy .number {{ color: var(--accent-green); }}
        .count-box.hold .number {{ color: var(--accent-yellow); }}
        .count-box.watch-box .number {{ color: #888; }}
        .count-box .number {{ color: var(--text-secondary); }}
        
        .count-box .label {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 5px;
        }}
        
        /* Table */
        .table-container {{
            overflow-x: auto;
            border: 1px solid var(--border);
            border-radius: 10px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }}
        
        th {{
            background: var(--bg-secondary);
            padding: 12px 10px;
            text-align: left;
            font-weight: 600;
            color: var(--accent-cyan);
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            position: relative;
            white-space: nowrap;
        }}
        
        th:hover {{ background: var(--bg-card); }}
        
        th .col-desc {{
            display: block;
            font-size: 0.7rem;
            font-weight: 400;
            color: var(--text-muted);
        }}
        
        /* Tooltip */
        .tooltip-box {{
            display: none;
            position: absolute;
            background: #111;
            color: #fff;
            padding: 10px 14px;
            border-radius: 6px;
            font-size: 0.8rem;
            max-width: 280px;
            z-index: 9999;
            transform: translate(-50%, -100%);
            pointer-events: none;
        }}
        
        th.sort-asc::after {{ content: ' ▲'; font-size: 0.65rem; color: var(--accent-cyan); }}
        th.sort-desc::after {{ content: ' ▼'; font-size: 0.65rem; color: var(--accent-cyan); }}
        
        td {{
            padding: 10px;
            border-bottom: 1px solid var(--border);
            background: var(--bg-card);
        }}
        
        tr:hover td {{ background: var(--bg-card-accent); }}
        
        .ticker-cell a {{
            color: var(--accent-cyan);
            text-decoration: none;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }}
        
        .ticker-cell a:hover {{ text-decoration: underline; }}
        
        .name-cell {{ color: var(--text-secondary); }}
        .model-cell {{ color: var(--text-muted); }}
        
        .metric {{
            text-align: right;
            font-family: 'JetBrains Mono', monospace;
        }}
        
        .metric.vcr {{ color: var(--accent-cyan); }}
        .metric.vcrx {{ color: #7eb8da; }}
        
        /* ROIC columns */
        .metric.roic {{ color: var(--accent-green); font-weight: 600; }}
        .metric.roicx {{ color: #8fcfff; }}
        
        /* Incremental ROIC */
        .metric.inc-roic.positive {{ color: var(--accent-green); font-weight: 600; }}
        .metric.inc-roic.negative {{ color: #ff6b6b; }}
        
        /* ROIC Trend icons */
        .metric.trend {{ font-size: 1rem; }}
        .metric.trend.trend-up {{ }}
        .metric.trend.trend-down {{ }}
        .metric.trend.trend-flat {{ }}
        
        /* GM Trend icons */
        .metric.gm-trend {{ font-size: 1rem; }}
        .metric.gm-trend.trend-up {{ }}
        .metric.gm-trend.trend-down {{ }}
        .metric.gm-trend.trend-flat {{ }}
        
        /* FCF/NI quality */
        .metric.fcf-ni.positive {{ color: var(--accent-green); }}
        .metric.fcf-ni.warning {{ color: var(--accent-yellow); }}
        .metric.fcf-ni.negative {{ color: #ff6b6b; }}
        
        /* FCF/Debt strength */
        .metric.fcf-debt.positive {{ color: var(--accent-green); }}
        .metric.fcf-debt.warning {{ color: var(--accent-yellow); }}
        .metric.fcf-debt.negative {{ color: #ff6b6b; }}
        
        /* CapEx/OCF (lower is better = green) */
        .metric.capex-ocf.positive {{ color: var(--accent-green); }}
        .metric.capex-ocf.warning {{ color: var(--accent-yellow); }}
        .metric.capex-ocf.negative {{ color: #ff6b6b; }}
        
        /* Reinvestment rate colors */
        .metric.reinv.rr-in_range {{ color: var(--accent-green); font-weight: 600; }}
        .metric.reinv.rr-above {{ color: var(--accent-yellow); }}
        .metric.reinv.rr-below {{ color: var(--text-muted); }}
        .metric.reinv.rr-negative {{ color: #ff6b6b; }}
        .metric.reinv.rr-none {{ color: var(--text-muted); }}
        
        .signal-badge {{
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        
        .signal-buy {{ background: var(--buy-bg); color: var(--accent-green); border: 1px solid var(--accent-green); }}
        .signal-hold {{ background: var(--hold-bg); color: var(--accent-yellow); border: 1px solid var(--accent-yellow); }}
        .signal-watch {{ background: rgba(128,128,128,0.1); color: #888; border: 1px solid #555; }}
        .signal-unrated {{ background: rgba(80,80,80,0.1); color: #666; border: 1px solid #444; }}
        
        .tier-badge {{
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        
        .tier-diamond {{ background: rgba(0, 212, 255, 0.15); color: #00d4ff; border: 1px solid #00d4ff; }}
        .tier-gold {{ background: rgba(255, 215, 0, 0.15); color: #ffd700; border: 1px solid #ffd700; }}
        .tier-silver {{ background: rgba(192, 192, 192, 0.15); color: #c0c0c0; border: 1px solid #c0c0c0; }}
        .tier-sub {{ background: rgba(80, 80, 80, 0.15); color: #666; border: 1px solid #444; }}
        
        /* Filters */
        .filters {{
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
        }}
        
        .filter-group {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .filter-group label {{
            color: var(--text-muted);
            font-size: 0.85rem;
        }}
        
        .filter-group select {{
            background: var(--bg-card);
            color: var(--text-primary);
            border: 1px solid var(--border);
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
        }}
        
        .filter-group select:hover {{
            border-color: var(--accent-cyan);
        }}
        
        /* Footer */
        footer {{
            text-align: center;
            padding: 30px;
            color: var(--text-muted);
            font-size: 0.85rem;
        }}
        
        /* Glossary */
        .glossary {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 25px;
            margin-top: 30px;
        }}
        
        .glossary h2 {{
            color: var(--accent-cyan);
            font-size: 1.2rem;
            margin-bottom: 20px;
        }}
        
        .glossary-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }}
        
        .glossary-item {{
            background: var(--bg-card);
            border-left: 3px solid var(--accent-cyan);
            padding: 15px;
            border-radius: 0 8px 8px 0;
        }}
        
        .glossary-item .term {{
            display: block;
            font-weight: 600;
            color: var(--accent-cyan);
            margin-bottom: 5px;
        }}
        
        .glossary-item .formula {{
            display: inline-block;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            color: var(--text-secondary);
            background: var(--bg-primary);
            padding: 2px 8px;
            border-radius: 4px;
            margin-bottom: 8px;
        }}
        
        .glossary-item .desc {{
            font-size: 0.85rem;
            color: var(--text-muted);
            line-height: 1.5;
            margin: 0;
        }}
        
        @media (max-width: 1200px) {{
            .glossary-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        
        @media (max-width: 768px) {{
            .glossary-grid {{ grid-template-columns: 1fr; }}
        }}
        
        @media (max-width: 1200px) {{
            .metrics-row {{ grid-template-columns: repeat(3, 1fr); }}
            .count-boxes {{ grid-template-columns: repeat(3, 1fr); }}
        }}
        
        @media (max-width: 768px) {{
            .metrics-row {{ grid-template-columns: repeat(2, 1fr); }}
            .name-cell, .model-cell {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>💎 Capital Compounders</h1>
            <p class="tagline">Quality compounders with ROIC or ROICX ≥ 15% — high-return capital allocators</p>
        </header>
        
        <!-- Top Metrics -->
        <div class="metrics-row">
            <div class="metric-card highlight">
                <div class="label">Universe</div>
                <div class="value">{summary['universe_count']}</div>
                <div class="sublabel">Quality companies</div>
            </div>
            <div class="metric-card highlight">
                <div class="label">Avg ROIC</div>
                <div class="value">{summary['avg_roic']:.0f}%</div>
                <div class="sublabel">Capital efficiency</div>
            </div>
            <div class="metric-card highlight">
                <div class="label">Avg VCR</div>
                <div class="value">{summary['avg_vcr']:.1f}x</div>
                <div class="sublabel">Value creation</div>
            </div>
            <div class="metric-card">
                <div class="label">📈 Improving</div>
                <div class="value">{summary['improving_count']}</div>
                <div class="sublabel">ROIC trending up</div>
            </div>
            <div class="metric-card">
                <div class="label">📉 Declining</div>
                <div class="value">{summary['declining_count']}</div>
                <div class="sublabel">ROIC trending down</div>
            </div>
            <div class="metric-card">
                <div class="label">From Screened</div>
                <div class="value">{summary['screened_count']:,}</div>
                <div class="sublabel">Total analyzed</div>
            </div>
        </div>
        
        <!-- Analyze Section -->
        <div class="analyze-section">
            <h3>🔍 Analyze Any Ticker</h3>
            <div class="analyze-row">
                <input type="text" id="ticker-input" class="analyze-input" placeholder="Enter ticker (e.g., AAPL, MSFT)" maxlength="6">
                <button class="analyze-btn" onclick="analyzeTicker()">Analyze</button>
            </div>
            <div id="analyze-result" class="analyze-result"></div>
        </div>
        
        <!-- Filters -->
        <div class="filters">
            <div class="filter-group">
                <label>ROIC Trend:</label>
                <select id="trendFilter" onchange="applyFilters()">
                    <option value="all">All ({summary['universe_count']})</option>
                    <option value="improving">📈 Improving ({summary['improving_count']})</option>
                    <option value="stable">➡️ Stable ({summary['stable_count']})</option>
                    <option value="declining">📉 Declining ({summary['declining_count']})</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Reinv:</label>
                <select id="rrFilter" onchange="applyFilters()">
                    <option value="all">All</option>
                    <option value="in_range">🎯 40-80% ({summary['rr_in_range']})</option>
                    <option value="above">🔺 Above 80% ({summary['rr_above']})</option>
                    <option value="below">🔻 Below 40% ({summary['rr_below']})</option>
                    <option value="negative">⬇️ Negative ({summary['rr_negative']})</option>
                </select>
            </div>
            <div class="filter-group">
                <label class="row-count" id="rowCount">{summary['universe_count']} companies</label>
            </div>
        </div>
        
        <!-- Table -->
        <div class="table-container">
            <table id="compoundersTable">
                <thead>
                    <tr>
                        <th data-tooltip="Stock ticker symbol">Ticker</th>
                        <th data-tooltip="Company name">Company</th>
                        <th data-tooltip="Return on Invested Capital">ROIC</th>
                        <th data-tooltip="ROIC excluding excess cash - better for acquirers">ROICX</th>
                        <th data-tooltip="Incremental ROIC - return on NEW capital invested. Higher than ROIC = moat widening">Inc ROIC</th>
                        <th data-tooltip="Value Creation Ratio = ROIC/WACC. Above 1x = creating value">VCR</th>
                        <th data-tooltip="VCRX = ROICX/WACC - value creation using cash-adjusted capital">VCRX</th>
                        <th data-tooltip="ROIC trend over 5 years: 📈 improving, 📉 declining, ➡️ stable">Trend</th>
                        <th data-tooltip="Free Cash Flow / Net Income - cash conversion quality. Target ≥80%">FCF/NI</th>
                        <th data-tooltip="FCF / Total Debt - balance sheet strength. Higher = can pay off debt faster">FCF/Debt</th>
                        <th data-tooltip="Gross Margin - pricing power indicator">GM</th>
                        <th data-tooltip="Gross Margin trend over 5 years: 📈 expanding, 📉 contracting, ➡️ stable">GM▲</th>
                        <th data-tooltip="Revenue 3-year CAGR">Growth</th>
                        <th data-tooltip="CapEx / Operating Cash Flow - lower = more cash available. ≤10% ideal">CapEx</th>
                        <th data-tooltip="Reinvestment Rate - how much profit reinvested for growth. Target 40-80%">Reinv</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        
        <!-- Key Metrics Glossary -->
        <div class="glossary">
            <h2>📖 Key Metrics</h2>
            <div class="glossary-grid">
                <div class="glossary-item">
                    <span class="term">ROIC</span>
                    <span class="formula">NOPAT ÷ Invested Capital</span>
                    <p class="desc">Return on Invested Capital - measures how efficiently a company turns capital into profits. Higher is better.</p>
                </div>
                <div class="glossary-item">
                    <span class="term">ROICX</span>
                    <span class="formula">NOPAT ÷ (IC + Cash)</span>
                    <p class="desc">ROIC excluding excess cash. Better metric for serial acquirers (AVGO, CSU) who hold cash for deals.</p>
                </div>
                <div class="glossary-item">
                    <span class="term">Inc ROIC</span>
                    <span class="formula">ΔNOPAT ÷ ΔInvested Capital</span>
                    <p class="desc">Incremental ROIC - return on NEW capital invested over 5 years. If higher than ROIC, moat is widening.</p>
                </div>
                <div class="glossary-item">
                    <span class="term">VCR</span>
                    <span class="formula">ROIC ÷ WACC</span>
                    <p class="desc">Value Creation Ratio - must be ≥1.0 to create shareholder value. VCR of 3x = earning 3× cost of capital.</p>
                </div>
                <div class="glossary-item">
                    <span class="term">VCRX</span>
                    <span class="formula">ROICX ÷ WACC</span>
                    <p class="desc">Value Creation Ratio excluding cash. More accurate for companies holding excess cash for acquisitions.</p>
                </div>
                <div class="glossary-item">
                    <span class="term">FCF/NI</span>
                    <span class="formula">Operating Cash Flow ÷ Net Income</span>
                    <p class="desc">Cash conversion quality. Target ≥80%. Lower = earnings may not be real cash.</p>
                </div>
                <div class="glossary-item">
                    <span class="term">FCF/Debt</span>
                    <span class="formula">Free Cash Flow ÷ Total Debt</span>
                    <p class="desc">Balance sheet strength. ≥50% = fortress (can pay off debt in 2 years). ≥25% = strong.</p>
                </div>
                <div class="glossary-item">
                    <span class="term">GM</span>
                    <span class="formula">(Revenue − COGS) ÷ Revenue</span>
                    <p class="desc">Gross Margin - pricing power indicator. Higher margins suggest competitive moat. Target ≥40%.</p>
                </div>
                <div class="glossary-item">
                    <span class="term">CapEx/OCF</span>
                    <span class="formula">Gross CapEx ÷ Operating Cash Flow</span>
                    <p class="desc">How much cash is consumed by capex. ≤10% = ultra-light, 10-25% = light, >25% = capital-heavy.</p>
                </div>
                <div class="glossary-item">
                    <span class="term">Reinv Rate</span>
                    <span class="formula">(Net CapEx + ΔWC + Acq) ÷ NOPAT</span>
                    <p class="desc">How much profit is reinvested for growth. Target 40-80%. Below = capital-light, above = heavy reinvestment.</p>
                </div>
            </div>
        </div>
        
        <footer>
            <p>Capital Compounders v3.0 • Generated {now} • Data from FMP API</p>
        </footer>
    </div>
    
    <script>
        const allCompanies = {companies_json};
        const FMP_API_KEY = 'TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU';
        
        let sortState = {{ col: null, asc: false }};
        
        async function analyzeTicker() {{
            const input = document.getElementById('ticker-input');
            const result = document.getElementById('analyze-result');
            const ticker = input.value.trim().toUpperCase();
            
            if (!ticker) return;
            
            const cached = allCompanies.find(c => c.ticker === ticker);
            
            if (cached) {{
                const signalColor = cached.signal === 'BUY' ? 'var(--accent-green)' : cached.signal === 'HOLD' ? 'var(--accent-yellow)' : '#888';
                const tierColor = cached.tier === 'DIAMOND' ? '#00d4ff' : cached.tier === 'GOLD' ? '#ffd700' : cached.tier === 'SILVER' ? '#c0c0c0' : '#666';
                const irrDisplay = cached.has_irr ? cached.avg_irr.toFixed(0) + '%' : '—';
                result.className = 'analyze-result show';
                result.innerHTML = `
                    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                        <strong style="font-size: 1.2rem; color: var(--accent-cyan);">${{cached.ticker}}</strong>
                        <span style="background: var(--bg-secondary); padding: 2px 10px; border-radius: 4px; font-size: 0.75rem;">CACHED</span>
                    </div>
                    <div style="color: var(--text-secondary); margin-bottom: 12px;">${{cached.name}}</div>
                    <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; font-size: 0.85rem;">
                        <div><span style="color: var(--text-muted);">Signal:</span><br><strong style="color: ${{signalColor}}">${{cached.signal}}</strong></div>
                        <div><span style="color: var(--text-muted);">Tier:</span><br><strong style="color: ${{tierColor}}">${{cached.tier_emoji}} ${{cached.tier}}</strong></div>
                        <div><span style="color: var(--text-muted);">ROIC:</span><br>${{cached.roic ? cached.roic.toFixed(0) + '%' : '—'}}</div>
                        <div><span style="color: var(--text-muted);">VCR:</span><br>${{cached.vcr ? cached.vcr.toFixed(1) + 'x' : '—'}}</div>
                        <div><span style="color: var(--text-muted);">GM:</span><br>${{cached.gross_margin ? cached.gross_margin.toFixed(0) + '%' : '—'}}</div>
                        <div><span style="color: var(--text-muted);">IRR:</span><br><strong style="color: var(--accent-cyan);">${{irrDisplay}}</strong></div>
                    </div>
                `;
                return;
            }}
            
            // Fetch live from FMP using new stable endpoints
            result.className = 'analyze-result show';
            result.innerHTML = '<span style="color: var(--text-muted);">Fetching live data...</span>';
            
            try {{
                // Use new /stable/ endpoints
                const [profileRes, ratiosRes, metricsRes] = await Promise.all([
                    fetch(`https://financialmodelingprep.com/stable/profile?symbol=${{ticker}}&apikey=${{FMP_API_KEY}}`),
                    fetch(`https://financialmodelingprep.com/stable/ratios-ttm?symbol=${{ticker}}&apikey=${{FMP_API_KEY}}`),
                    fetch(`https://financialmodelingprep.com/stable/key-metrics-ttm?symbol=${{ticker}}&apikey=${{FMP_API_KEY}}`),
                ]);
                
                const profile = await profileRes.json();
                const ratios = await ratiosRes.json();
                const metrics = await metricsRes.json();
                
                console.log('FMP Profile:', profile);
                console.log('FMP Ratios:', ratios);
                console.log('FMP Metrics:', metrics);
                
                // Check for errors
                if (!profile || profile.length === 0 || profile['Error Message']) {{
                    const errMsg = profile['Error Message'] || 'Ticker not found';
                    result.innerHTML = `<span style="color: var(--accent-yellow);">${{ticker}}: ${{errMsg}}</span>`;
                    return;
                }}
                
                const p = profile[0] || {{}};
                const r = ratios[0] || {{}};
                const m = metrics[0] || {{}};
                
                const roic = (r.returnOnCapitalEmployedTTM || 0) * 100;
                const vcr = roic / 10; // Simplified WACC assumption
                const gm = (r.grossProfitMarginTTM || 0) * 100;
                const fcfYield = (m.freeCashFlowYieldTTM || 0) * 100;
                const pe = p.pe || r.peRatioTTM || 0;
                const earningsYield = pe > 0 ? (1/pe) * 100 : 0;
                const irr = earningsYield + (roic * 0.3);
                
                const signal = irr >= 20 ? 'BUY' : irr >= 12 ? 'HOLD' : 'WATCH';
                const signalColor = signal === 'BUY' ? 'var(--accent-green)' : signal === 'HOLD' ? 'var(--accent-yellow)' : 'var(--text-muted)';
                const tier = vcr >= 3 ? 'DIAMOND' : vcr >= 2 ? 'GOLD' : vcr >= 1 ? 'SILVER' : 'SUB';
                const tierEmoji = vcr >= 3 ? '🔷' : vcr >= 2 ? '🥇' : vcr >= 1 ? '🥈' : '⬜';
                const tierColor = vcr >= 3 ? '#00d4ff' : vcr >= 2 ? '#ffd700' : vcr >= 1 ? '#c0c0c0' : '#666';
                const meetsQuality = roic >= 15 && gm >= 40;
                const epSpread = roic - 10; // ROIC - assumed 10% WACC
                
                result.innerHTML = `
                    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                        <strong style="font-size: 1.2rem; color: var(--accent-cyan);">${{ticker}}</strong>
                        <span style="background: var(--accent-blue); color: #fff; padding: 2px 10px; border-radius: 4px; font-size: 0.75rem;">LIVE</span>
                    </div>
                    <div style="color: var(--text-secondary); margin-bottom: 12px;">${{p.companyName || ticker}} · ${{p.sector || 'N/A'}}</div>
                    <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; font-size: 0.85rem;">
                        <div><span style="color: var(--text-muted);">Signal:</span><br><strong style="color: ${{signalColor}}">${{signal}}</strong></div>
                        <div><span style="color: var(--text-muted);">Tier:</span><br><strong style="color: ${{tierColor}}">${{tierEmoji}} ${{tier}}</strong></div>
                        <div><span style="color: var(--text-muted);">ROIC:</span><br>${{roic.toFixed(0)}}%</div>
                        <div><span style="color: var(--text-muted);">VCR:</span><br>${{vcr.toFixed(1)}}x</div>
                        <div><span style="color: var(--text-muted);">GM:</span><br>${{gm.toFixed(0)}}%</div>
                        <div><span style="color: var(--text-muted);">IRR:</span><br><strong style="color: var(--accent-cyan);">${{irr.toFixed(0)}}%</strong></div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; font-size: 0.85rem; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border);">
                        <div><span style="color: var(--text-muted);">EP Spread:</span><br>${{epSpread >= 0 ? '+' : ''}}${{epSpread.toFixed(0)}}%</div>
                        <div><span style="color: var(--text-muted);">Growth:</span><br>—</div>
                        <div><span style="color: var(--text-muted);">Price:</span><br>$${{(p.price || 0).toFixed(0)}}</div>
                        <div><span style="color: var(--text-muted);">Target:</span><br>—</div>
                        <div><span style="color: var(--text-muted);">MCap:</span><br>$${{((p.mktCap || 0)/1e9).toFixed(0)}}B</div>
                        <div><span style="color: var(--text-muted);">FCF Yield:</span><br>${{fcfYield.toFixed(1)}}%</div>
                    </div>
                    <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); font-size: 0.85rem; color: ${{meetsQuality ? 'var(--accent-green)' : 'var(--accent-yellow)'}};">
                        ${{meetsQuality ? '✅ Meets quality criteria (ROIC ≥15%, GM ≥40%)' : '⚠️ Does not meet quality criteria'}}
                    </div>
                `;
            }} catch (err) {{
                result.innerHTML = `<span style="color: var(--accent-yellow);">Error: ${{err.message}}</span>`;
            }}
        }}
        
        document.getElementById('ticker-input').addEventListener('keypress', e => {{
            if (e.key === 'Enter') analyzeTicker();
        }});
        
        // Filter function
        function applyFilters() {{
            const trendFilter = document.getElementById('trendFilter').value;
            const rrFilter = document.getElementById('rrFilter').value;
            let visible = 0;
            document.querySelectorAll('.company-row').forEach(row => {{
                const matchTrend = trendFilter === 'all' || row.dataset.trend === trendFilter;
                const matchRr = rrFilter === 'all' || row.dataset.rr === rrFilter;
                const show = matchTrend && matchRr;
                row.style.display = show ? '' : 'none';
                if (show) visible++;
            }});
            document.getElementById('rowCount').textContent = visible + ' companies';
        }}
        
        // Sorting
        document.querySelectorAll('th').forEach((th, i) => {{
            th.addEventListener('click', () => {{
                const tbody = document.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                
                if (sortState.col === i) {{
                    sortState.asc = !sortState.asc;
                }} else {{
                    sortState.col = i;
                    sortState.asc = false;
                }}
                
                document.querySelectorAll('th').forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
                th.classList.add(sortState.asc ? 'sort-asc' : 'sort-desc');
                
                const isNumeric = i >= 2 && i !== 7 && i !== 11;  // Exclude Trend and GM Trend columns
                rows.sort((a, b) => {{
                    let aVal = a.cells[i].textContent.trim();
                    let bVal = b.cells[i].textContent.trim();
                    if (isNumeric) {{
                        aVal = parseFloat(aVal.replace(/[$%xB,+]/g, '')) || 0;
                        bVal = parseFloat(bVal.replace(/[$%xB,+]/g, '')) || 0;
                        return sortState.asc ? aVal - bVal : bVal - aVal;
                    }}
                    return sortState.asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                }});
                rows.forEach(r => tbody.appendChild(r));
            }});
        }});
        
        // Tooltips
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip-box';
        document.body.appendChild(tooltip);
        
        document.querySelectorAll('th[data-tooltip]').forEach(th => {{
            th.addEventListener('mouseenter', e => {{
                tooltip.textContent = th.dataset.tooltip;
                tooltip.style.display = 'block';
                const rect = th.getBoundingClientRect();
                tooltip.style.left = (rect.left + rect.width/2) + 'px';
                tooltip.style.top = (rect.top + window.scrollY - 10) + 'px';
            }});
            th.addEventListener('mouseleave', () => tooltip.style.display = 'none');
        }});
    </script>
</body>
</html>'''


if __name__ == '__main__':
    import sys
    irr_path = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/uploads/irr_5_model_results_168.json'
    universe_path = sys.argv[2] if len(sys.argv) > 2 else '/mnt/user-data/uploads/capital_compounders_universe.json'
    output_path = sys.argv[3] if len(sys.argv) > 3 else '/mnt/user-data/outputs/capital_compounders_dashboard.html'
    generate_dashboard(irr_path, universe_path, output_path)
