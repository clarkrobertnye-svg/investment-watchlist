#!/usr/bin/env python3
"""
Gate 5 IRR — 7-Model Comparison
30 Buffett Core Compounders

Models:
  M1  Claude      — Conservative anchor, asset-light EPS fallback, ROIC cap 50%, exit PE capped
  M2  ChatGPT     — Clean algebra, zero growth if reinvest≤0, tiered PE (25-28/20-22/15-18)
  M3  Gemini      — ln-based multiple drift, institutional tiering, 25-28x elite
  M4  Grok        — Forward consensus reinvestment proxy, PEG-based drift
  M5  DeepSeek    — 3-criteria tiers (ROIC+GM+OM), PE floor logic, 28/22/18/15x
  M6  Copilot     — Institutional tiers (22-28/18-22/14-18), ranking-aware
  M7  Consensus   — Best-of-all hybrid: Grok reinvest hierarchy + DeepSeek tiers + Claude fallback

Reads from: cache/raw/TICKER_*.json
Fetches live prices from FMP API
Outputs: terminal table + CSV
"""

import json, os, sys, time, math
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────
FMP_API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"  # ROTATE THIS
CACHE_DIR = Path("cache/raw")
OUTPUT_CSV = "cache/exports/gate5_irr_7models.csv"

TICKERS = [
    "AAPL", "ADBE", "ADP", "ANET", "APH", "ASML", "AXP", "BAH", "BKNG", "BMI",
    "BRC", "COKE", "CTAS", "HUBB", "IESC", "IT", "KLAC", "MA", "MSFT",
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
    d = {}
    for suffix in ['income', 'cashflow', 'balance', 'metrics', 'profile']:
        path = CACHE_DIR / f"{ticker}_{suffix}.json"
        data = load_json(path)
        if data is None:
            return None
        d[suffix] = data
    return d

def safe_get(data_list, index, key, default=None):
    try:
        if isinstance(data_list, list) and len(data_list) > index:
            v = data_list[index].get(key, default)
            return float(v) if v is not None else default
        return default
    except:
        return default

def fetch_live_price(ticker):
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
    except:
        pass
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


# ─── Metrics Extraction ─────────────────────────────────────────
def extract_metrics(d, price):
    inc = d['income'] if isinstance(d['income'], list) else []
    cf = d['cashflow'] if isinstance(d['cashflow'], list) else []
    bal = d['balance'] if isinstance(d['balance'], list) else []
    met = d['metrics'] if isinstance(d['metrics'], list) else []
    prof = d['profile'] if isinstance(d['profile'], list) else d['profile']

    m = {}

    # ── Income Statement ──
    m['revenue'] = safe_get(inc, 0, 'revenue', 0)
    m['ebit'] = safe_get(inc, 0, 'operatingIncome', 0)
    m['net_income'] = safe_get(inc, 0, 'netIncome', 0)
    m['eps'] = safe_get(inc, 0, 'eps', 0)
    m['shares'] = safe_get(inc, 0, 'weightedAverageShsOut', 0)
    m['shares_diluted'] = safe_get(inc, 0, 'weightedAverageShsOutDil', 0)
    m['gross_profit'] = safe_get(inc, 0, 'grossProfit', 0)
    m['gross_margin'] = safe_get(inc, 0, 'grossProfit', 0) / m['revenue'] if m['revenue'] > 0 else 0
    m['op_margin'] = safe_get(inc, 0, 'operatingIncome', 0) / m['revenue'] if m['revenue'] > 0 else 0
    m['tax_rate'] = safe_get(inc, 0, 'incomeTaxExpense', 0) / max(safe_get(inc, 0, 'incomeBeforeTax', 1), 1)

    # ── Cash Flow ──
    m['fcf'] = safe_get(cf, 0, 'freeCashFlow', 0)
    m['capex'] = abs(safe_get(cf, 0, 'capitalExpenditure', 0))
    m['sbc'] = safe_get(cf, 0, 'stockBasedCompensation', 0)
    m['da'] = safe_get(cf, 0, 'depreciationAndAmortization', 0)
    m['op_cf'] = safe_get(cf, 0, 'operatingCashFlow', 0)
    m['dividends'] = abs(safe_get(cf, 0, 'dividendsPaid', 0))
    m['buybacks'] = abs(safe_get(cf, 0, 'commonStockRepurchased', 0))
    m['acquisitions'] = safe_get(cf, 0, 'acquisitionsNet', 0)

    # Owner earnings
    m['owner_earnings'] = m['net_income'] + m['da'] - m['capex']

    # ── Balance Sheet ──
    m['total_equity'] = safe_get(bal, 0, 'totalStockholdersEquity', 0)
    m['total_debt'] = safe_get(bal, 0, 'totalDebt', 0)
    m['cash'] = safe_get(bal, 0, 'cashAndCashEquivalents', 0) + safe_get(bal, 0, 'shortTermInvestments', 0)
    m['total_assets'] = safe_get(bal, 0, 'totalAssets', 0)
    m['net_debt'] = m['total_debt'] - m['cash']

    # Invested capital
    m['ic'] = m['total_equity'] + m['total_debt'] - m['cash']
    if m['ic'] <= 0:
        m['ic'] = m['total_assets'] * 0.5

    # NOPAT & ROIC
    m['nopat'] = m['ebit'] * (1 - m['tax_rate'])
    m['roic'] = m['nopat'] / m['ic'] if m['ic'] > 0 else 0
    m['ebitda'] = m['ebit'] + m['da']

    # ── Per-share ──
    m['fcf_per_share'] = m['fcf'] / m['shares'] if m['shares'] > 0 else 0
    m['eps'] = m['net_income'] / m['shares'] if (m['eps'] == 0 and m['shares'] > 0) else m['eps']
    m['oe_per_share'] = m['owner_earnings'] / m['shares'] if m['shares'] > 0 else 0

    # SBC as % of FCF
    m['sbc_pct'] = m['sbc'] / m['fcf'] if m['fcf'] > 0 else 0
    m['sbc_pct'] = max(0, min(m['sbc_pct'], 1.0))

    # ── Reinvestment Rate (accounting-based) ──
    m['reinvest_rate_acct'] = (m['capex'] - m['da'] + abs(m['acquisitions'])) / m['nopat'] if m['nopat'] > 0 else 0
    # Don't clamp — let it go negative for asset-light

    # ── Dividend yield ──
    m['div_yield'] = m['dividends'] / (price * m['shares']) if (price > 0 and m['shares'] > 0) else 0

    # ── Historical Growth (5yr CAGRs) ──
    m['shares_5'] = safe_get(inc, 4, 'weightedAverageShsOut', m['shares'])
    m['eps_5'] = safe_get(inc, 4, 'eps', 0)
    m['fcf_5'] = safe_get(cf, 4, 'freeCashFlow', 0)
    m['rev_5'] = safe_get(inc, 4, 'revenue', m['revenue'])

    def cagr(end, start, years=5):
        if start <= 0 or end <= 0:
            return 0
        return (end / start) ** (1 / years) - 1

    m['eps_cagr'] = cagr(m['eps'], m['eps_5']) if m['eps_5'] > 0 and m['eps'] > 0 else 0
    m['rev_cagr'] = cagr(m['revenue'], m['rev_5'])
    m['fcf_cagr'] = cagr(m['fcf'], m['fcf_5']) if m['fcf_5'] > 0 and m['fcf'] > 0 else 0

    fcf_ps_now = m['fcf'] / m['shares'] if m['shares'] > 0 else 0
    fcf_ps_5 = m['fcf_5'] / m['shares_5'] if m['shares_5'] > 0 else 0
    m['fcf_ps_cagr'] = cagr(fcf_ps_now, fcf_ps_5) if fcf_ps_5 > 0 and fcf_ps_now > 0 else m['fcf_cagr']

    # Best historical growth (median of positives)
    growths = [g for g in [m['eps_cagr'], m['fcf_ps_cagr'], m['rev_cagr']] if g > 0]
    m['hist_growth'] = sorted(growths)[len(growths)//2] if growths else 0.05

    # ── Buyback yield (historical 5yr CAGR of share reduction) ──
    m['buyback_yield'] = (m['shares_5'] / m['shares']) ** 0.2 - 1 if (m['shares'] > 0 and m['shares_5'] > 0) else 0

    # ── P/E from live price ──
    m['pe'] = price / m['eps'] if m['eps'] > 0 else 0
    m['pfcf'] = price / m['fcf_per_share'] if m['fcf_per_share'] > 0 else 0

    # ── PEG estimate (using hist EPS growth as proxy for fwd) ──
    m['peg'] = m['pe'] / (m['eps_cagr'] * 100) if (m['pe'] > 0 and m['eps_cagr'] > 0.01) else 99

    # ── Market cap ──
    m['mcap'] = price * m['shares'] if m['shares'] > 0 else 0

    return m


# ─── Tier Assignment ─────────────────────────────────────────────

def tier_claude(m):
    """Claude: ROIC + GM only, conservative caps"""
    if m['roic'] >= 0.30 and m['gross_margin'] >= 0.50:
        return 'Elite', 30
    elif m['roic'] >= 0.20 and m['gross_margin'] >= 0.40:
        return 'High', 25
    else:
        return 'Solid', 20

def tier_chatgpt(m):
    """ChatGPT: ROIC-only tiers, midpoint of ranges"""
    if m['roic'] >= 0.30:
        return 'Elite', 26.5
    elif m['roic'] >= 0.20:
        return 'Quality', 21
    else:
        return 'Solid', 16.5

def tier_gemini(m):
    """Gemini: Same ranges as ChatGPT, slightly different labels"""
    if m['roic'] >= 0.30:
        return 'Elite', 26.5
    elif m['roic'] >= 0.20:
        return 'Quality', 21
    else:
        return 'Mature', 16.5

def tier_deepseek(m):
    """DeepSeek: 3-criteria (ROIC + GM + OM), 4 tiers"""
    if m['roic'] >= 0.30 and m['gross_margin'] >= 0.60 and m['op_margin'] >= 0.30:
        return 'Toll Road', 28
    elif m['roic'] >= 0.20 and m['gross_margin'] >= 0.45 and m['op_margin'] >= 0.20:
        return 'Strong', 22
    elif m['roic'] >= 0.15 and m['gross_margin'] >= 0.35 and m['op_margin'] >= 0.15:
        return 'Adequate', 18
    else:
        return 'Commodity', 15

def tier_copilot(m):
    """Copilot: A+/A/B tiers, midpoints"""
    if m['roic'] >= 0.40:
        return 'A+', 25
    elif m['roic'] >= 0.25:
        return 'A', 20
    elif m['roic'] >= 0.15:
        return 'B', 16
    else:
        return 'C', 12

def tier_consensus(m):
    """Consensus: DeepSeek 3-criteria with adjusted multiples from group median"""
    if m['roic'] >= 0.30 and m['gross_margin'] >= 0.50 and m['op_margin'] >= 0.25:
        return 'Elite', 28
    elif m['roic'] >= 0.20 and m['gross_margin'] >= 0.40:
        return 'High', 23
    elif m['roic'] >= 0.15:
        return 'Solid', 18
    else:
        return 'Value', 15


# ─── Common Components ───────────────────────────────────────────

def fcf_yield_adj(m, price):
    """SBC-adjusted FCF yield — universal across all models"""
    if price <= 0 or m['fcf_per_share'] <= 0:
        return 0
    return (m['fcf_per_share'] * (1 - m['sbc_pct'])) / price

def buyback_yield(m):
    """Historical 5yr buyback yield — universal"""
    return m['buyback_yield']

def div_yield(m):
    """Dividend yield — universal"""
    return m['div_yield']

def multiple_change(pe_now, pe_exit):
    """Arithmetic annualized multiple drift"""
    if pe_now <= 0 or pe_exit <= 0:
        return 0
    return (pe_exit / pe_now) ** 0.2 - 1

def multiple_change_ln(pe_now, pe_exit):
    """Log-based multiple drift (Gemini)"""
    if pe_now <= 0 or pe_exit <= 0:
        return 0
    return math.log(pe_exit / pe_now) / 5


# ─── 7 IRR Models ───────────────────────────────────────────────

def model_1_claude(m, price):
    """Claude: Conservative, asset-light EPS fallback, ROIC cap 50%, exit PE capped at current"""
    roic_cap = min(m['roic'], 0.50)
    rr = m['reinvest_rate_acct']

    # Growth engine with smart fallback
    acct_growth = roic_cap * max(rr, 0)
    if m['eps_cagr'] > 0 and acct_growth < m['eps_cagr'] * 0.5:
        growth = min(m['eps_cagr'], 0.30)  # Claude: slightly more conservative cap
    elif rr > 0:
        growth = acct_growth
    else:
        growth = min(m['hist_growth'], 0.20)

    # Exit PE: conservative but protect high-PE elite names
    _, tier_pe = tier_claude(m)
    if m['pe'] > 0 and m['pe'] > tier_pe * 2:
        exit_pe = max(tier_pe, m['pe'] * 0.80)  # accept 20% compression
    elif m['pe'] > 0:
        exit_pe = min(m['pe'], tier_pe)
    else:
        exit_pe = tier_pe

    fy = fcf_yield_adj(m, price)
    bb = buyback_yield(m)
    dy = div_yield(m)
    mc = multiple_change(m['pe'], exit_pe)

    return fy + growth + bb + dy + mc


def model_2_chatgpt(m, price):
    """ChatGPT: Clean algebra, zero growth if reinvest≤0, tiered PE"""
    rr = max(m['reinvest_rate_acct'], 0)
    growth = m['roic'] * rr  # No ROIC cap

    _, tier_pe = tier_chatgpt(m)
    exit_pe = tier_pe  # Straight tier assignment

    fy = fcf_yield_adj(m, price)
    bb = buyback_yield(m)
    dy = div_yield(m)
    mc = multiple_change(m['pe'], exit_pe)

    return fy + growth + bb + dy + mc


def model_3_gemini(m, price):
    """Gemini: ln-based drift, institutional tiering, base scenario"""
    rr = max(m['reinvest_rate_acct'], 0)
    growth = m['roic'] * rr

    _, tier_pe = tier_gemini(m)
    exit_pe = tier_pe

    fy = fcf_yield_adj(m, price)
    bb = buyback_yield(m)
    dy = div_yield(m)
    mc = multiple_change_ln(m['pe'], exit_pe)  # ln-based

    return fy + growth + bb + dy + mc


def model_4_grok(m, price):
    """Grok: Forward consensus reinvestment proxy, PEG-based drift"""
    # Reinvestment rate = hist_growth / ROIC (proxy for EPS Next 5Y / ROIC)
    # We use hist EPS growth as proxy since we don't have analyst consensus in cache
    if m['roic'] > 0 and m['eps_cagr'] > 0:
        implied_rr = min(m['eps_cagr'] / m['roic'], 1.0)
        growth = m['roic'] * implied_rr  # = eps_cagr, but mechanically grounded
    else:
        growth = max(m['hist_growth'], 0)

    # PEG-based multiple drift
    if m['peg'] < 1.0:
        drift = 0.02  # cheap on growth-adjusted basis → slight expansion
    elif m['peg'] < 1.5:
        drift = 0.0   # fair value
    elif m['peg'] < 2.5:
        drift = -0.02  # slightly rich
    else:
        drift = -0.04  # very expensive

    fy = fcf_yield_adj(m, price)
    bb = buyback_yield(m)
    dy = div_yield(m)

    raw = fy + growth + bb + dy + drift
    return min(raw, 0.40)  # cap at 40% to prevent median pollution


def model_5_deepseek(m, price):
    """DeepSeek: 3-criteria tiers, PE floor, zero growth if reinvest≤0"""
    rr = max(m['reinvest_rate_acct'], 0)
    growth = m['roic'] * rr

    _, tier_pe = tier_deepseek(m)
    # PE floor + high-PE protection
    if m['pe'] > 0 and m['pe'] < tier_pe:
        exit_pe = tier_pe
    elif m['pe'] > tier_pe * 2:
        exit_pe = max(tier_pe, m['pe'] * 0.75)
    else:
        exit_pe = tier_pe

    fy = fcf_yield_adj(m, price)
    bb = buyback_yield(m)
    dy = div_yield(m)
    mc = multiple_change(m['pe'], exit_pe)

    return fy + growth + bb + dy + mc


def model_6_copilot(m, price):
    """Copilot: Institutional tiers, explicit failure handling"""
    rr = max(m['reinvest_rate_acct'], 0)
    roic_cap = min(m['roic'], 0.50)
    growth = roic_cap * rr

    _, tier_pe = tier_copilot(m)
    exit_pe = tier_pe

    fy = fcf_yield_adj(m, price)
    bb = buyback_yield(m)
    dy = div_yield(m)
    mc = multiple_change(m['pe'], exit_pe)

    return fy + growth + bb + dy + mc


def model_7_consensus(m, price):
    """
    Consensus Hybrid — best of all models:
    - Grok's reinvestment hierarchy (forward → accounting → EPS fallback)
    - DeepSeek's 3-criteria tiering with PE floor
    - Claude's asset-light fallback + ROIC cap
    - Consensus exit PE (28/23/18)
    """
    roic_cap = min(m['roic'], 0.50)

    # Reinvestment hierarchy with smart override
    rr_acct = m['reinvest_rate_acct']
    acct_growth = roic_cap * max(rr_acct, 0)

    # If accounting growth is less than half of actual EPS growth,
    # the business grows through expensed R&D/SG&A (asset-light)
    # Use proven EPS CAGR directly — ROIC cap only applies to accounting path
    if m['eps_cagr'] > 0 and acct_growth < m['eps_cagr'] * 0.5:
        growth = min(m['eps_cagr'], 0.35)
    elif rr_acct > 0:
        growth = acct_growth
    elif m['eps_cagr'] > 0:
        growth = min(m['eps_cagr'], 0.35)
    else:
        growth = min(m['hist_growth'], 0.15)

    # Cap at 35% — prevents runaway estimates
    growth = min(growth, 0.35)

    # Tier assignment (DeepSeek 3-criteria + consensus multiples)
    tier_name, tier_pe = tier_consensus(m)

    # PE exit logic: cheap stocks expand to tier; expensive Elite stocks get partial compression
    if m['pe'] > 0 and m['pe'] < tier_pe:
        exit_pe = tier_pe  # cheap: expand to justified
    elif tier_name == 'Elite' and m['pe'] > tier_pe * 2:
        exit_pe = max(tier_pe, m['pe'] * 0.75)  # very expensive Elite: accept 25% compression, not collapse
    elif tier_name == 'High' and m['pe'] > tier_pe * 2:
        exit_pe = max(tier_pe, m['pe'] * 0.80)  # very expensive High: accept 20% compression
    else:
        exit_pe = tier_pe  # normal: compress to tier

    fy = fcf_yield_adj(m, price)
    bb = buyback_yield(m)
    dy = div_yield(m)
    mc = multiple_change(m['pe'], exit_pe)

    return fy + growth + bb + dy + mc


# ─── Main Runner ─────────────────────────────────────────────────

def run_all():
    print()
    print("=" * 130)
    print("  GATE 5 IRR — 7-MODEL COMPARISON")
    print("  30 Buffett Core Compounders")
    print("=" * 130)
    print()

    if not CACHE_DIR.exists():
        print(f"  ERROR: Cache directory not found: {CACHE_DIR}")
        print("  Run from ~/Documents/capital_compounders/")
        sys.exit(1)

    results = []
    errors = []

    for i, ticker in enumerate(sorted(TICKERS), 1):
        print(f"  [{i:2d}/30] {ticker:6s} ... ", end="", flush=True)

        d = load_ticker(ticker)
        if d is None:
            print("MISSING CACHE")
            errors.append(ticker)
            continue

        price = fetch_live_price(ticker)
        if price is None or price <= 0:
            prof = d['profile']
            if isinstance(prof, list) and len(prof) > 0:
                price = float(prof[0].get('price', 0))
            elif isinstance(prof, dict):
                price = float(prof.get('price', 0))

        if not price or price <= 0:
            print("NO PRICE")
            errors.append(ticker)
            continue

        m = extract_metrics(d, price)

        # Run all 7 models
        irrs = {
            'M1_Claude':    model_1_claude(m, price),
            'M2_ChatGPT':   model_2_chatgpt(m, price),
            'M3_Gemini':    model_3_gemini(m, price),
            'M4_Grok':      model_4_grok(m, price),
            'M5_DeepSeek':  model_5_deepseek(m, price),
            'M6_Copilot':   model_6_copilot(m, price),
            'M7_Consensus': model_7_consensus(m, price),
        }

        valid = [v for v in irrs.values() if v is not None]
        if not valid:
            print("ALL MODELS FAILED")
            errors.append(ticker)
            continue

        # Proper median (handles even counts)
        sv = sorted(valid)
        n = len(sv)
        median_irr = (sv[n//2 - 1] + sv[n//2]) / 2 if n % 2 == 0 else sv[n//2]

        consensus_irr = irrs['M7_Consensus']

        # Verdict based on consensus model
        if consensus_irr >= 0.15:
            verdict = "BUY"
        elif consensus_irr >= 0.12:
            verdict = "WATCH"
        elif consensus_irr >= 0.08:
            verdict = "HOLD"
        else:
            verdict = "EXPENSIVE"

        # Tier info
        tier_name, tier_pe = tier_consensus(m)

        r = {
            'ticker': ticker,
            'price': price,
            'pe': m['pe'],
            'roic': m['roic'],
            'gm': m['gross_margin'],
            'om': m['op_margin'],
            'sbc_pct': m['sbc_pct'],
            'rr_acct': m['reinvest_rate_acct'],
            'eps_cagr': m['eps_cagr'],
            'bb_yield': m['buyback_yield'],
            'div_yield': m['div_yield'],
            'tier': tier_name,
            'tier_pe': tier_pe,
            'M1': irrs['M1_Claude'],
            'M2': irrs['M2_ChatGPT'],
            'M3': irrs['M3_Gemini'],
            'M4': irrs['M4_Grok'],
            'M5': irrs['M5_DeepSeek'],
            'M6': irrs['M6_Copilot'],
            'M7': irrs['M7_Consensus'],
            'median': median_irr,
            'verdict': verdict,
        }
        results.append(r)

        print(f"${price:>8.2f}  ROIC:{m['roic']*100:5.1f}%  Tier:{tier_name:6s}  "
              f"M7:{consensus_irr*100:5.1f}%  {verdict}")
        time.sleep(0.3)

    # ─── Summary Table ────────────────────────────────────────────
    print()
    print("=" * 130)
    print("  RESULTS — SORTED BY CONSENSUS IRR (M7)")
    print("=" * 130)
    print()
    print(f"  {'Sym':6s} {'Price':>8s} {'P/E':>6s} {'ROIC':>6s} {'GM':>5s} {'OM':>5s} "
          f"{'SBC%':>5s} {'Tier':>6s}  "
          f"{'M1':>6s} {'M2':>6s} {'M3':>6s} {'M4':>6s} {'M5':>6s} {'M6':>6s}  "
          f"{'M7':>6s} {'Med':>6s}  Verdict")
    print("  " + "-" * 124)

    results.sort(key=lambda x: x['M7'], reverse=True)

    counts = {'BUY': 0, 'WATCH': 0, 'HOLD': 0, 'EXPENSIVE': 0}
    for r in results:
        def f(v): return f"{v*100:5.1f}%" if v is not None else "  N/A"
        pe_str = f"{r['pe']:>6.1f}" if r['pe'] > 0 else "   N/A"
        print(f"  {r['ticker']:6s} ${r['price']:>7.2f} {pe_str} {r['roic']*100:>5.1f}% "
              f"{r['gm']*100:>4.0f}% {r['om']*100:>4.0f}% "
              f"{r['sbc_pct']*100:>4.0f}% {r['tier']:>6s}  "
              f"{f(r['M1'])} {f(r['M2'])} {f(r['M3'])} {f(r['M4'])} {f(r['M5'])} {f(r['M6'])}  "
              f"{f(r['M7'])} {f(r['median'])}  {r['verdict']}")
        counts[r['verdict']] = counts.get(r['verdict'], 0) + 1

    print()
    print(f"  BUY (>=15%): {counts['BUY']}  |  WATCH (12-15%): {counts['WATCH']}  |  "
          f"HOLD (8-12%): {counts['HOLD']}  |  EXPENSIVE (<8%): {counts['EXPENSIVE']}")
    if errors:
        print(f"  ERRORS: {len(errors)} — {', '.join(errors)}")
    print()

    # ─── Component Decomposition for Top 10 ──────────────────────
    print("=" * 130)
    print("  IRR DECOMPOSITION — TOP 10 BY CONSENSUS")
    print("=" * 130)
    print()
    print(f"  {'Sym':6s} {'FCF Yld':>7s} {'Growth':>7s} {'Buyback':>7s} {'Divid':>7s} {'Multi':>7s}  {'= IRR':>7s}  {'Tier':>6s} {'TierPE':>6s} {'CurrPE':>6s}")
    print("  " + "-" * 90)

    for r in results[:10]:
        m_data = extract_metrics(load_ticker(r['ticker']), r['price'])
        roic_cap = min(m_data['roic'], 0.50)
        rr = m_data['reinvest_rate_acct']
        acct_growth = roic_cap * max(rr, 0)

        fy = fcf_yield_adj(m_data, r['price'])
        # Same logic as model_7_consensus
        if m_data['eps_cagr'] > 0 and acct_growth < m_data['eps_cagr'] * 0.5:
            g = min(m_data['eps_cagr'], 0.35)
        elif rr > 0:
            g = acct_growth
        elif m_data['eps_cagr'] > 0:
            g = min(m_data['eps_cagr'], 0.35)
        else:
            g = min(m_data['hist_growth'], 0.15)
        g = min(g, 0.35)

        bb = m_data['buyback_yield']
        dy = m_data['div_yield']
        tier_name, t_pe = tier_consensus(m_data)
        # Same exit PE logic as model_7
        if m_data['pe'] > 0 and m_data['pe'] < t_pe:
            exit_pe = t_pe
        elif tier_name == 'Elite' and m_data['pe'] > t_pe * 2:
            exit_pe = max(t_pe, m_data['pe'] * 0.75)
        elif tier_name == 'High' and m_data['pe'] > t_pe * 2:
            exit_pe = max(t_pe, m_data['pe'] * 0.80)
        else:
            exit_pe = t_pe
        mc = multiple_change(m_data['pe'], exit_pe) if m_data['pe'] > 0 else 0

        total = fy + g + bb + dy + mc
        print(f"  {r['ticker']:6s} {fy*100:>6.1f}% {g*100:>6.1f}% {bb*100:>6.1f}% "
              f"{dy*100:>6.1f}% {mc*100:>6.1f}%  {total*100:>6.1f}%  "
              f"{r['tier']:>6s} {t_pe:>5.0f}x {m_data['pe']:>5.1f}x")

    print()

    # ─── CSV Export ───────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    with open(OUTPUT_CSV, 'w') as f:
        headers = ['Ticker', 'Price', 'P/E', 'ROIC%', 'GM%', 'OM%', 'SBC%',
                   'RR_acct', 'EPS_CAGR%', 'BB_Yield%', 'Div_Yield%', 'Tier', 'Tier_PE',
                   'M1_Claude%', 'M2_ChatGPT%', 'M3_Gemini%', 'M4_Grok%',
                   'M5_DeepSeek%', 'M6_Copilot%', 'M7_Consensus%', 'Median%', 'Verdict']
        f.write(','.join(headers) + '\n')
        for r in results:
            def fv(v): return f"{v*100:.2f}" if v is not None else ""
            f.write(f"{r['ticker']},{r['price']:.2f},{r['pe']:.1f},"
                    f"{r['roic']*100:.1f},{r['gm']*100:.1f},{r['om']*100:.1f},{r['sbc_pct']*100:.1f},"
                    f"{r['rr_acct']:.3f},{r['eps_cagr']*100:.1f},{r['bb_yield']*100:.2f},{r['div_yield']*100:.2f},"
                    f"{r['tier']},{r['tier_pe']},"
                    f"{fv(r['M1'])},{fv(r['M2'])},{fv(r['M3'])},{fv(r['M4'])},"
                    f"{fv(r['M5'])},{fv(r['M6'])},{fv(r['M7'])},{fv(r['median'])},"
                    f"{r['verdict']}\n")

    print(f"  CSV exported: {OUTPUT_CSV}")
    print()


if __name__ == "__main__":
    run_all()
