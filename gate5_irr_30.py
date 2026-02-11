#!/usr/bin/env python3
"""
Gate 5 IRR Valuations — 30 Buffett Core Compounders
6-model framework: Gemini Quick, Claude EPS Power, Copilot Scalable, 
                   Grok Full DCF, DeepSeek Weighted, Perplexity Quick

Reads from: cache/raw/TICKER_*.json
Fetches live prices from FMP API
Outputs: gate5_irr_results.csv + terminal summary
"""

import json, os, sys, time, math
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────
FMP_API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"  # Your FMP key
CACHE_DIR = Path("cache/raw")
OUTPUT_CSV = "cache/exports/gate5_irr_30.csv"
OUTPUT_JSON = "cache/exports/gate5_irr_30.json"

TICKERS = [
    "AAPL", "ADBE", "ADP", "ANET", "APH", "ASML", "AXP", "BAH", "BKNG", "BMI",
    "BRC", "COKE", "CTAS", "HUBB", "IESC", "IPAR", "IT", "KLAC", "MA", "MSFT",
    "NEU", "NSSC", "NVDA", "NVR", "QCOM", "RMD", "ROL", "TT", "V", "VRSK"
]

# ─── Data Loading ────────────────────────────────────────────────
def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return None

def load_ticker(ticker):
    """Load all cached financial data for a ticker."""
    d = {}
    for suffix in ['income', 'cashflow', 'balance', 'metrics', 'profile']:
        path = CACHE_DIR / f"{ticker}_{suffix}.json"
        data = load_json(path)
        if data is None:
            return None
        d[suffix] = data
    return d

def safe_get(data_list, index, key, default=None):
    """Safely get a value from a list of dicts."""
    try:
        if isinstance(data_list, list) and len(data_list) > index:
            v = data_list[index].get(key, default)
            if v is None:
                return default
            return float(v)
        return default
    except:
        return default

def fetch_live_price(ticker):
    """Fetch live price from FMP API."""
    import urllib.request
    url = f"https://financialmodelingprep.com/stable/profile?symbol={ticker}&apikey={FMP_API_KEY}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                return float(data[0].get('price', 0))
            elif isinstance(data, dict):
                return float(data.get('price', 0))
    except Exception as e:
        pass
    # Fallback to quote endpoint
    try:
        url2 = f"https://financialmodelingprep.com/stable/quote?symbol={ticker}&apikey={FMP_API_KEY}"
        req = urllib.request.Request(url2)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                return float(data[0].get('price', 0))
    except:
        pass
    return None

# ─── Financial Metrics Extraction ────────────────────────────────
def extract_metrics(d):
    """Extract key financial metrics from cached data."""
    inc = d['income'] if isinstance(d['income'], list) else []
    cf = d['cashflow'] if isinstance(d['cashflow'], list) else []
    bal = d['balance'] if isinstance(d['balance'], list) else []
    met = d['metrics'] if isinstance(d['metrics'], list) else []
    prof = d['profile'] if isinstance(d['profile'], list) else d['profile']
    
    m = {}
    
    # Current year (index 0 = most recent)
    m['revenue'] = safe_get(inc, 0, 'revenue', 0)
    m['ebit'] = safe_get(inc, 0, 'operatingIncome', 0)
    m['net_income'] = safe_get(inc, 0, 'netIncome', 0)
    m['eps'] = safe_get(inc, 0, 'eps', 0)
    m['shares'] = safe_get(inc, 0, 'weightedAverageShsOut', 0)
    m['shares_diluted'] = safe_get(inc, 0, 'weightedAverageShsOutDil', 0)
    m['tax_rate'] = safe_get(inc, 0, 'incomeTaxExpense', 0) / max(safe_get(inc, 0, 'incomeBeforeTax', 1), 1)
    m['gross_margin'] = safe_get(inc, 0, 'grossProfitRatio', 0)
    m['op_margin'] = safe_get(inc, 0, 'operatingIncomeRatio', 0)
    
    # Cash flow
    m['fcf'] = safe_get(cf, 0, 'freeCashFlow', 0)
    m['capex'] = abs(safe_get(cf, 0, 'capitalExpenditure', 0))
    m['sbc'] = safe_get(cf, 0, 'stockBasedCompensation', 0)
    m['dividends'] = abs(safe_get(cf, 0, 'dividendsPaid', 0))
    m['buybacks'] = abs(safe_get(cf, 0, 'commonStockRepurchased', 0))
    m['op_cf'] = safe_get(cf, 0, 'operatingCashFlow', 0)
    
    # Owner earnings (Buffett: net income + D&A - capex)
    m['da'] = safe_get(cf, 0, 'depreciationAndAmortization', 0)
    m['owner_earnings'] = m['net_income'] + m['da'] - m['capex']
    
    # Balance sheet
    m['total_equity'] = safe_get(bal, 0, 'totalStockholdersEquity', 0)
    m['total_debt'] = safe_get(bal, 0, 'totalDebt', 0)
    m['cash'] = safe_get(bal, 0, 'cashAndCashEquivalents', 0) + safe_get(bal, 0, 'shortTermInvestments', 0)
    m['total_assets'] = safe_get(bal, 0, 'totalAssets', 0)
    m['net_debt'] = m['total_debt'] - m['cash']
    
    # Invested capital
    m['ic'] = m['total_equity'] + m['total_debt'] - m['cash']
    if m['ic'] <= 0:
        m['ic'] = m['total_assets'] * 0.5  # fallback for NEQ
    
    # NOPAT
    m['nopat'] = m['ebit'] * (1 - m['tax_rate'])
    
    # ROIC
    m['roic'] = m['nopat'] / m['ic'] if m['ic'] > 0 else 0
    
    # EBITDA
    m['ebitda'] = m['ebit'] + m['da']
    
    # Per-share metrics
    if m['shares'] > 0:
        m['fcf_per_share'] = m['fcf'] / m['shares']
        m['eps'] = m['net_income'] / m['shares'] if m['eps'] == 0 else m['eps']
        m['oe_per_share'] = m['owner_earnings'] / m['shares']
    else:
        m['fcf_per_share'] = 0
        m['eps'] = 0
        m['oe_per_share'] = 0
    
    # Reinvestment rate
    m['reinvest_rate'] = (m['capex'] - m['da'] + safe_get(cf, 0, 'acquisitionsNet', 0)) / m['nopat'] if m['nopat'] > 0 else 0.3
    m['reinvest_rate'] = max(0, min(m['reinvest_rate'], 1.0))
    
    # Historical growth (5yr CAGRs)
    m['rev_5'] = safe_get(inc, 4, 'revenue', m['revenue'])
    m['ni_5'] = safe_get(inc, 4, 'netIncome', m['net_income'])
    m['fcf_5'] = safe_get(cf, 4, 'freeCashFlow', m['fcf'])
    m['shares_5'] = safe_get(inc, 4, 'weightedAverageShsOut', m['shares'])
    m['eps_5'] = safe_get(inc, 4, 'eps', m['eps'])
    
    def cagr(end, start, years=5):
        if start <= 0 or end <= 0:
            return 0
        return (end / start) ** (1 / years) - 1
    
    m['rev_cagr'] = cagr(m['revenue'], m['rev_5'])
    m['ni_cagr'] = cagr(m['net_income'], m['ni_5']) if m['ni_5'] > 0 and m['net_income'] > 0 else 0
    m['fcf_cagr'] = cagr(m['fcf'], m['fcf_5']) if m['fcf_5'] > 0 and m['fcf'] > 0 else 0
    m['eps_cagr'] = cagr(m['eps'], m['eps_5']) if m['eps_5'] > 0 and m['eps'] > 0 else 0
    
    # Per-share FCF growth (adjusting for buybacks)
    fcf_ps_now = m['fcf'] / m['shares'] if m['shares'] > 0 else 0
    fcf_ps_5 = m['fcf_5'] / m['shares_5'] if m['shares_5'] > 0 else 0
    m['fcf_ps_cagr'] = cagr(fcf_ps_now, fcf_ps_5) if fcf_ps_5 > 0 and fcf_ps_now > 0 else m['fcf_cagr']
    
    # Best growth estimate (conservative: median of available)
    growths = [g for g in [m['eps_cagr'], m['fcf_ps_cagr'], m['rev_cagr']] if g > 0]
    m['growth'] = sorted(growths)[len(growths)//2] if growths else 0.05
    
    # Cap extreme ROIC for model stability
    m['roic_capped'] = min(m['roic'], 0.50)
    
    # Metrics data — try multiple field names, then compute from fundamentals
    m['pe'] = safe_get(met, 0, 'peRatio') or safe_get(met, 0, 'priceEarningsRatio') or safe_get(met, 0, 'peRatioTTM')
    m['pfcf'] = safe_get(met, 0, 'priceToFreeCashFlowsRatio') or safe_get(met, 0, 'pfcfRatio') or safe_get(met, 0, 'priceToFreeCashFlowRatio')
    m['ev_ebitda'] = safe_get(met, 0, 'enterpriseValueOverEBITDA') or safe_get(met, 0, 'evToEbitda') or safe_get(met, 0, 'enterpriseValueMultiple')
    m['div_yield'] = safe_get(met, 0, 'dividendYield', 0)
    
    # Flag these to be recomputed from live price later
    m['pe_needs_calc'] = m['pe'] is None
    m['pfcf_needs_calc'] = m['pfcf'] is None
    
    # Market cap from profile
    if isinstance(prof, list) and len(prof) > 0:
        m['mcap'] = float(prof[0].get('mktCap', 0))
    elif isinstance(prof, dict):
        m['mcap'] = float(prof.get('mktCap', 0))
    else:
        m['mcap'] = 0
    
    return m


# ─── Quality-Adjusted Exit Multiple ──────────────────────────────

def compute_exit_pe(m):
    """Compute quality-adjusted exit P/E from fundamentals.
    Quality score (0-100) maps to exit PE (15-35x).
    Higher ROIC, growth, margins, FCF quality = higher justified multiple."""
    score = 0
    
    # 1. ROIC (0-25 pts)
    roic = m.get('roic', 0)
    if roic >= 0.50: score += 25
    elif roic >= 0.30: score += 20
    elif roic >= 0.20: score += 15
    elif roic >= 0.15: score += 10
    else: score += 5
    
    # 2. Growth (0-25 pts)
    g = m.get('growth', 0)
    if g >= 0.20: score += 25
    elif g >= 0.15: score += 20
    elif g >= 0.10: score += 15
    elif g >= 0.05: score += 10
    else: score += 5
    
    # 3. Gross Margin / Pricing Power (0-25 pts)
    gm = m.get('gross_margin', 0)
    if gm >= 0.70: score += 25
    elif gm >= 0.50: score += 20
    elif gm >= 0.35: score += 15
    elif gm >= 0.20: score += 10
    else: score += 5
    
    # 4. FCF Quality (0-25 pts)
    fcf_ni = m.get('fcf', 0) / m.get('net_income', 1) if m.get('net_income', 0) > 0 else 0.5
    if fcf_ni >= 1.0 and m.get('reinvest_rate', 1) < 0.3: score += 25
    elif fcf_ni >= 0.8: score += 20
    elif fcf_ni >= 0.6: score += 15
    elif fcf_ni >= 0.4: score += 10
    else: score += 5
    
    # Map score (20-100) to exit PE (15x-35x)
    exit_pe = 15 + (score - 20) * (20 / 80)
    exit_pe = max(15, min(exit_pe, 35))
    
    # Never assume expansion: cap at current PE
    current_pe = m.get('_current_pe', 50)
    exit_pe = min(exit_pe, current_pe)
    
    return exit_pe, score


# ─── 6 IRR Models ────────────────────────────────────────────────

def model_1_gemini_quick(m, price):
    """Gemini Quick: FCF Yield + (ROIC × Reinvest Rate) ± ΔMultiple"""
    if price <= 0 or m['fcf_per_share'] <= 0:
        return None
    fcf_yield = m['fcf_per_share'] / price
    roic = m['roic_capped']
    rr = m['reinvest_rate']
    growth_component = roic * rr
    
    # Quality-adjusted multiple reversion
    current_pfcf = price / m['fcf_per_share'] if m['fcf_per_share'] > 0 else 25
    exit_pe, _ = compute_exit_pe(m)
    target_pfcf = min(current_pfcf, exit_pe * 1.1)  # P/FCF slightly above P/E
    multiple_drag = ((target_pfcf / current_pfcf) ** (1/5) - 1) if current_pfcf > 0 else 0
    
    irr = fcf_yield + growth_component + multiple_drag
    return irr

def model_2_claude_eps_power(m, price):
    """Claude EPS Power: (Future EPS × Exit PE / Price)^(1/5) - 1"""
    if price <= 0 or m['eps'] <= 0:
        return None
    # Conservative growth: lower of historical EPS CAGR or 12%
    g = min(m['eps_cagr'], 0.12) if m['eps_cagr'] > 0 else min(m['growth'], 0.08)
    future_eps = m['eps'] * (1 + g) ** 5
    
    # Exit PE: quality-adjusted, never above forward PE (no expansion)
    current_pe = m.get('_forward_pe', price / m['eps'] if m['eps'] > 0 else 20)
    exit_pe, _ = compute_exit_pe(m)
    exit_pe = min(exit_pe, current_pe)
    
    future_price = future_eps * exit_pe
    if future_price <= 0:
        return None
    
    # Add dividends
    div_return = m['div_yield']
    
    irr = (future_price / price) ** (1/5) - 1 + div_return
    return irr

def model_3_copilot_scalable(m, price):
    """Copilot Scalable: Owner Earnings × (1+g)^5 × Terminal PE / Price"""
    if price <= 0 or m['oe_per_share'] <= 0:
        return None
    # Growth from ROIC-based reinvestment
    g = min(m['roic_capped'] * m['reinvest_rate'], 0.15)
    if g <= 0:
        g = min(m['growth'], 0.08)
    
    future_oe = m['oe_per_share'] * (1 + g) ** 5
    
    # Terminal multiple: quality-adjusted
    exit_pe, _ = compute_exit_pe(m)
    terminal_value = future_oe * exit_pe
    
    # Add cumulative dividends (simplified as lump sum)
    cum_divs = sum(m['oe_per_share'] * (1+g)**i * m['div_yield'] * (price / m['oe_per_share']) for i in range(5)) if m['oe_per_share'] > 0 else 0
    
    total_future = terminal_value + cum_divs
    if total_future <= 0:
        return None
    
    irr = (total_future / price) ** (1/5) - 1
    return irr

def model_4_grok_dcf(m, price):
    """Grok Full DCF: IRR that sets NPV of projected FCFs + terminal value = price"""
    if price <= 0 or m['fcf_per_share'] <= 0:
        return None
    
    g = min(m['fcf_ps_cagr'], 0.15) if m['fcf_ps_cagr'] > 0 else min(m['growth'], 0.08)
    terminal_growth = 0.03  # perpetuity growth
    
    # Project 5 years of FCF/share
    cfs = []
    for yr in range(1, 6):
        cfs.append(m['fcf_per_share'] * (1 + g) ** yr)
    
    # Terminal value at year 5: quality-adjusted exit multiple on FCF
    exit_pe, _ = compute_exit_pe(m)
    tv = cfs[-1] * exit_pe * 1.1  # P/FCF slightly above P/E
    
    # Solve for IRR using Newton's method
    def npv(r):
        if r <= -1:
            return float('inf')
        total = -price
        for i, cf in enumerate(cfs):
            total += cf / (1 + r) ** (i + 1)
        total += tv / (1 + r) ** 5
        return total
    
    # Binary search for IRR
    lo, hi = -0.5, 2.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    
    return (lo + hi) / 2

def model_5_deepseek_weighted(m, price):
    """DeepSeek Weighted: 60% DCF-based + 40% EPV + stress adjustment"""
    dcf_irr = model_4_grok_dcf(m, price)
    eps_irr = model_2_claude_eps_power(m, price)
    
    if dcf_irr is None and eps_irr is None:
        return None
    
    dcf_val = dcf_irr if dcf_irr is not None else 0
    eps_val = eps_irr if eps_irr is not None else 0
    
    if dcf_irr is not None and eps_irr is not None:
        blended = 0.6 * dcf_val + 0.4 * eps_val
    elif dcf_irr is not None:
        blended = dcf_val
    else:
        blended = eps_val
    
    # Stress adjustment: haircut for cyclicality/risk
    stress = -0.015  # 1.5% drag for general uncertainty
    
    return blended + stress

def model_6_perplexity_quick(m, price):
    """Perplexity Quick: FCF Yield + (ROIC_ex_cash × 0.35) - 1.5%"""
    if price <= 0 or m['fcf_per_share'] <= 0:
        return None
    
    fcf_yield = m['fcf_per_share'] / price
    
    # ROIC excluding excess cash
    ic_ex_cash = m['ic']
    roic_ex = m['nopat'] / ic_ex_cash if ic_ex_cash > 0 else 0
    roic_ex = min(roic_ex, 0.50)  # cap at 50%
    
    irr = fcf_yield + (roic_ex * 0.35) - 0.015
    return irr


# ─── Main Runner ─────────────────────────────────────────────────

def run_all():
    print("=" * 100)
    print("  GATE 5 IRR VALUATIONS — 30 Buffett Core Compounders")
    print("  6-Model Framework")
    print("=" * 100)
    print()
    
    # Check cache exists
    if not CACHE_DIR.exists():
        print(f"ERROR: Cache directory not found: {CACHE_DIR}")
        print("Run from ~/Documents/capital_compounders/")
        sys.exit(1)
    
    results = []
    errors = []
    
    # Diagnostic: show available metrics fields from first ticker
    test_d = load_ticker(TICKERS[0])
    if test_d and test_d['metrics']:
        met_sample = test_d['metrics'][0] if isinstance(test_d['metrics'], list) else test_d['metrics']
        pe_fields = [k for k in met_sample.keys() if 'pe' in k.lower() or 'earning' in k.lower() or 'price' in k.lower()]
        print(f"  [DEBUG] Metrics fields with PE/Price: {pe_fields}")
        print()
    
    for i, ticker in enumerate(sorted(TICKERS), 1):
        print(f"  [{i:2d}/{len(TICKERS)}] {ticker:6s} ... ", end="", flush=True)
        
        # Load cached data
        d = load_ticker(ticker)
        if d is None:
            print("❌ Missing cache data")
            errors.append(ticker)
            continue
        
        # Extract metrics
        m = extract_metrics(d)
        
        # Fetch live price
        price = fetch_live_price(ticker)
        if price is None or price <= 0:
            # Fallback to profile price
            prof = d['profile']
            if isinstance(prof, list) and len(prof) > 0:
                price = float(prof[0].get('price', 0))
            elif isinstance(prof, dict):
                price = float(prof.get('price', 0))
        
        if price is None or price <= 0:
            print("❌ No price available")
            errors.append(ticker)
            continue
        
        # Compute P/E and P/FCF from live price if metrics didn't have them
        if m.get('pe_needs_calc') or m['pe'] is None or m['pe'] == 0:
            m['pe'] = price / m['eps'] if m['eps'] > 0 else None
        if m.get('pfcf_needs_calc') or m['pfcf'] is None or m['pfcf'] == 0:
            m['pfcf'] = price / m['fcf_per_share'] if m['fcf_per_share'] > 0 else None
        if m['ev_ebitda'] is None or m['ev_ebitda'] == 0:
            ev = (m['mcap'] + m['net_debt']) if m['mcap'] > 0 else (price * m['shares'] + m['net_debt'])
            m['ev_ebitda'] = ev / m['ebitda'] if m['ebitda'] > 0 else None
        
        # Set current PE for quality-adjusted exit multiple
        # Use growth-adjusted trailing PE as proxy for forward PE
        trailing_pe = price / m['eps'] if m.get('eps') and m['eps'] > 0 else 30
        eps_g = m['eps_cagr'] if m['eps_cagr'] > 0 else m['growth']
        forward_pe = trailing_pe / (1 + eps_g) if eps_g > 0 else trailing_pe
        m['_current_pe'] = forward_pe
        m['_forward_pe'] = forward_pe
        m['_trailing_pe'] = trailing_pe
        exit_pe, q_score = compute_exit_pe(m)
        
        # Run all 6 models
        irrs = {}
        irrs['M1_Gemini'] = model_1_gemini_quick(m, price)
        irrs['M2_Claude'] = model_2_claude_eps_power(m, price)
        irrs['M3_Copilot'] = model_3_copilot_scalable(m, price)
        irrs['M4_Grok'] = model_4_grok_dcf(m, price)
        irrs['M5_DeepSeek'] = model_5_deepseek_weighted(m, price)
        irrs['M6_Perplexity'] = model_6_perplexity_quick(m, price)
        
        valid = [v for v in irrs.values() if v is not None]
        
        if not valid:
            print("❌ All models failed")
            errors.append(ticker)
            continue
        
        mean_irr = sum(valid) / len(valid)
        median_irr = sorted(valid)[len(valid) // 2]
        min_irr = min(valid)
        max_irr = max(valid)
        
        # Verdict
        if median_irr >= 0.20:
            verdict = "🟢 BUY"
        elif median_irr >= 0.12:
            verdict = "🟡 WATCH"
        elif median_irr >= 0.08:
            verdict = "⚪ HOLD"
        else:
            verdict = "🔴 EXPENSIVE"
        
        r = {
            'ticker': ticker,
            'price': price,
            'pe': m['pe'] if m['pe'] is not None else 0,
            'fwd_pe': forward_pe,
            'pfcf': m['pfcf'] if m['pfcf'] is not None else 0,
            'fcf_yield': (m['fcf_per_share'] / price * 100) if price > 0 and m['fcf_per_share'] > 0 else 0,
            'roic': m['roic'] * 100,
            'growth': m['growth'] * 100,
            'exit_pe': exit_pe,
            'q_score': q_score,
            'M1': irrs['M1_Gemini'],
            'M2': irrs['M2_Claude'],
            'M3': irrs['M3_Copilot'],
            'M4': irrs['M4_Grok'],
            'M5': irrs['M5_DeepSeek'],
            'M6': irrs['M6_Perplexity'],
            'mean_irr': mean_irr * 100,
            'median_irr': median_irr * 100,
            'min_irr': min_irr * 100,
            'max_irr': max_irr * 100,
            'verdict': verdict,
            'models_ok': len(valid),
        }
        results.append(r)
        
        print(f"${price:>8.2f}  FwdPE:{forward_pe:.1f}x  Exit:{exit_pe:.0f}x  Mean: {mean_irr*100:5.1f}%  Median: {median_irr*100:5.1f}%  {verdict}")
        time.sleep(0.3)  # API rate limit
    
    # ─── Summary Output ──────────────────────────────────────────
    print()
    print("=" * 100)
    print("  RESULTS SORTED BY MEDIAN IRR")
    print("=" * 100)
    print()
    print(f"  {'Sym':6s} {'Price':>8s} {'P/E':>6s} {'FwdPE':>6s} {'Exit':>5s} {'P/FCF':>6s} {'Yld%':>5s} {'ROIC%':>6s}  {'M1':>6s} {'M2':>6s} {'M3':>6s} {'M4':>6s} {'M5':>6s} {'M6':>6s}  {'Mean':>6s} {'Med':>6s}  Verdict")
    print("  " + "-" * 114)
    
    results.sort(key=lambda x: x['median_irr'], reverse=True)
    
    buys = watches = holds = expensive = 0
    for r in results:
        def f(v): return f"{v*100:5.1f}%" if v is not None else "  N/A"
        pe_str = f"{r['pe']:>6.1f}" if r['pe'] > 0 else "   N/A"
        pfcf_str = f"{r['pfcf']:>6.1f}" if r['pfcf'] > 0 else "   N/A"
        print(f"  {r['ticker']:6s} ${r['price']:>7.2f} {pe_str} {r['fwd_pe']:>5.1f}x {r['exit_pe']:>4.0f}x {pfcf_str} {r['fcf_yield']:>4.1f}% {r['roic']:>5.1f}%"
              f"  {f(r['M1'])} {f(r['M2'])} {f(r['M3'])} {f(r['M4'])} {f(r['M5'])} {f(r['M6'])}"
              f"  {r['mean_irr']:>5.1f}% {r['median_irr']:>5.1f}%  {r['verdict']}")
        if "BUY" in r['verdict']: buys += 1
        elif "WATCH" in r['verdict']: watches += 1
        elif "HOLD" in r['verdict']: holds += 1
        else: expensive += 1
    
    print()
    print(f"  🟢 BUY (≥20%): {buys}  |  🟡 WATCH (12-20%): {watches}  |  ⚪ HOLD (8-12%): {holds}  |  🔴 EXPENSIVE (<8%): {expensive}")
    if errors:
        print(f"  ❌ Errors: {len(errors)} — {', '.join(errors)}")
    print()
    
    # ─── CSV Export ───────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    
    with open(OUTPUT_CSV, 'w') as f:
        headers = ['Ticker', 'Price', 'P/E', 'P/FCF', 'FCF_Yield%', 'ROIC%', 'Growth%',
                   'M1_Gemini%', 'M2_Claude%', 'M3_Copilot%', 'M4_Grok%', 'M5_DeepSeek%', 'M6_Perplexity%',
                   'Mean_IRR%', 'Median_IRR%', 'Min_IRR%', 'Max_IRR%', 'Verdict']
        f.write(','.join(headers) + '\n')
        for r in results:
            def fv(v): return f"{v*100:.2f}" if v is not None else ""
            f.write(f"{r['ticker']},{r['price']:.2f},{r['pe']:.1f},{r['pfcf']:.1f},{r['fcf_yield']:.1f},{r['roic']:.1f},{r['growth']:.1f},"
                    f"{fv(r['M1'])},{fv(r['M2'])},{fv(r['M3'])},{fv(r['M4'])},{fv(r['M5'])},{fv(r['M6'])},"
                    f"{r['mean_irr']:.2f},{r['median_irr']:.2f},{r['min_irr']:.2f},{r['max_irr']:.2f},{r['verdict']}\n")
    
    print(f"  ✅ CSV exported: {OUTPUT_CSV}")
    
    # JSON export
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"  ✅ JSON exported: {OUTPUT_JSON}")
    print()

if __name__ == "__main__":
    run_all()
