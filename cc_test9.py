#!/usr/bin/env python3
"""
Capital Compounders v3 — Unified Total Value Creation
Gate 2: Total Value Creation Rate >= 20% (Power + Capital Return Yield on beginning IC)
Gate 3: NOPAT/sh or FCF/sh CAGR >= 15% (proof it shows up per-share)
"""

import json, csv, time, sys, os
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from datetime import datetime

API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"
BASE_URL = "https://financialmodelingprep.com/stable"
OUTPUT_DIR = os.path.expanduser("~/Documents/capital_compounders")
RATE_LIMIT_DELAY = 0.25

GATE1_GM = 0.15
GATE1_ROIC_AVG = 0.12
GATE1_ROIC_CURRENT = 0.18
GATE2_TVCR = 0.20
GATE3_PERSHARE_CAGR = 0.15
GATE4_FCF_NI = 0.70
GATE4_ND_EBITDA = 2.5
GATE4_ND_EBITDA_ESC = 3.0
ROIIC_CAP = 3.50
REINV_CAP = 2.00

api_calls = 0

def fetch_json(url):
    global api_calls
    time.sleep(RATE_LIMIT_DELAY)
    api_calls += 1
    try:
        req = Request(url, headers={"User-Agent": "CapitalCompounders/3.0"})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except (URLError, HTTPError, json.JSONDecodeError):
        return None

def get_income_statements(sym, limit=7):
    return fetch_json(f"{BASE_URL}/income-statement?symbol={sym}&limit={limit}&apikey={API_KEY}")

def get_balance_sheets(sym, limit=7):
    return fetch_json(f"{BASE_URL}/balance-sheet-statement?symbol={sym}&limit={limit}&apikey={API_KEY}")

def get_cash_flows(sym, limit=7):
    return fetch_json(f"{BASE_URL}/cash-flow-statement?symbol={sym}&limit={limit}&apikey={API_KEY}")

def get_profile(sym):
    data = fetch_json(f"{BASE_URL}/profile?symbol={sym}&apikey={API_KEY}")
    if data and isinstance(data, list) and len(data) > 0:
        return data[0]
    return data

def safe_div(a, b, default=None):
    if b is None or b == 0 or a is None: return default
    return a / b

def calc_nopat(inc):
    op_inc = inc.get("operatingIncome",0) or 0
    tax = inc.get("incomeTaxExpense",0) or 0
    pretax = inc.get("incomeBeforeTax",0) or 0
    eff_tax = tax/pretax if pretax > 0 and tax >= 0 else 0.21
    return op_inc * (1 - eff_tax)

def calc_ic(bs):
    equity = bs.get("totalStockholdersEquity",0) or 0
    total_debt = bs.get("totalDebt",0) or 0
    if total_debt == 0:
        total_debt = (bs.get("shortTermDebt",0) or 0) + (bs.get("longTermDebt",0) or 0)
    cash = bs.get("cashAndCashEquivalents",0) or 0
    sti = bs.get("shortTermInvestments",0) or 0
    leases = bs.get("capitalLeaseObligations",0) or 0
    ic = equity + total_debt + leases - cash - sti
    return ic if ic > 0 else None

def calc_fcf(cf):
    return (cf.get("operatingCashFlow",0) or 0) - abs(cf.get("capitalExpenditure",0) or 0)

def process_ticker(symbol):
    result = {"symbol": symbol, "error": None}
    inc_stmts = get_income_statements(symbol, 7)
    bal_sheets = get_balance_sheets(symbol, 7)
    cash_flows = get_cash_flows(symbol, 7)
    profile = get_profile(symbol)

    if not inc_stmts or not bal_sheets or not cash_flows:
        result["error"] = "Missing financial statements"; return result

    inc_stmts.sort(key=lambda x: x.get("date",""), reverse=True)
    bal_sheets.sort(key=lambda x: x.get("date",""), reverse=True)
    cash_flows.sort(key=lambda x: x.get("date",""), reverse=True)

    if len(inc_stmts) < 4 or len(bal_sheets) < 4:
        result["error"] = "Insufficient history"; return result

    if profile:
        result["mktCap"] = profile.get("mktCap",0) or 0
        result["sector"] = profile.get("sector","")
        result["industry"] = profile.get("industry","")
        result["companyName"] = profile.get("companyName", symbol)
    else:
        result["mktCap"] = 0; result["companyName"] = symbol
        result["sector"] = ""; result["industry"] = ""

    years = []
    n = min(len(inc_stmts), len(bal_sheets), len(cash_flows))
    for i in range(n):
        inc, bs, cf = inc_stmts[i], bal_sheets[i], cash_flows[i]
        nopat = calc_nopat(inc)
        ic = calc_ic(bs)
        fcf = calc_fcf(cf)
        revenue = inc.get("revenue",0) or 0
        gross_profit = inc.get("grossProfit",0) or 0
        net_income = inc.get("netIncome",0) or 0
        ebitda = inc.get("ebitda",0) or 0
        op_cf = cf.get("operatingCashFlow",0) or 0
        capex = abs(cf.get("capitalExpenditure",0) or 0)
        total_debt = (bs.get("totalDebt",0) or 0) or ((bs.get("shortTermDebt",0) or 0) + (bs.get("longTermDebt",0) or 0))
        cash = bs.get("cashAndCashEquivalents",0) or 0
        sti = bs.get("shortTermInvestments",0) or 0
        shares = inc.get("weightedAverageShsOutDil",0) or cf.get("weightedAverageShsOutDil",0) or 0
        buybacks = cf.get("commonStockRepurchased",0) or 0
        dividends = cf.get("dividendsPaid",0) or 0

        years.append({
            "date": inc.get("date","?"),
            "nopat": nopat, "ic": ic, "fcf": fcf, "revenue": revenue,
            "net_income": net_income, "ebitda": ebitda,
            "gross_margin": safe_div(gross_profit, revenue, 0),
            "roic": safe_div(nopat, ic) if ic and ic > 0 else None,
            "fcf_ni": safe_div(fcf, net_income) if net_income and net_income > 0 else None,
            "op_cf": op_cf, "capex": capex,
            "total_debt": total_debt, "cash": cash, "sti": sti,
            "net_debt": total_debt - cash - sti,
            "shares": shares, "buybacks": buybacks, "dividends": dividends,
            "nopat_per_share": safe_div(nopat, shares) if shares > 0 else None,
            "fcf_per_share": safe_div(fcf, shares) if shares > 0 else None,
        })

    result["grossMargin"] = years[0]["gross_margin"] if years else 0
    result["currentROIC"] = years[0]["roic"]

    roics = [y["roic"] for y in years[:3] if y["roic"] is not None]
    result["avg3yr_ROIC"] = sum(roics)/len(roics) if roics else None

    # 3yr cumulative ROIIC
    if len(years) >= 4 and years[0]["nopat"] and years[3]["nopat"] and years[0]["ic"] and years[3]["ic"]:
        d_nopat = years[0]["nopat"] - years[3]["nopat"]
        d_ic = years[0]["ic"] - years[3]["ic"]
        result["cum3yr_ROIIC"] = d_nopat / d_ic if d_ic > 0 else None
        result["ic_shrinking"] = d_ic < 0
    else:
        result["cum3yr_ROIIC"] = None; result["ic_shrinking"] = False

    # 3yr cumulative reinvestment rate
    if len(years) >= 4 and years[0]["ic"] and years[3]["ic"]:
        d_ic = years[0]["ic"] - years[3]["ic"]
        total_nopat = sum(y["nopat"] for y in years[:3] if y["nopat"])
        result["cum3yr_ReinvRate"] = d_ic / total_nopat if total_nopat > 0 else None
    else:
        result["cum3yr_ReinvRate"] = None

    # Power (capped)
    if result.get("cum3yr_ROIIC") is not None and result.get("cum3yr_ReinvRate") is not None:
        cr = min(result["cum3yr_ROIIC"], ROIIC_CAP)
        rr = min(result["cum3yr_ReinvRate"], REINV_CAP)
        result["cum3yr_Power"] = cr * rr if rr > 0 else 0
    else:
        result["cum3yr_Power"] = 0

    # Capital Return Yield on Beginning IC
    beginning_ic = years[3]["ic"] if len(years) >= 4 else None
    total_bb_3yr = sum(abs(y["buybacks"]) for y in years[:3])
    total_div_3yr = sum(abs(y["dividends"]) for y in years[:3])
    avg_annual_return = (total_bb_3yr + total_div_3yr) / 3

    result["total_buybacks_3yr"] = total_bb_3yr
    result["total_dividends_3yr"] = total_div_3yr
    result["avg_annual_capital_return"] = avg_annual_return
    result["beginning_ic"] = beginning_ic

    if beginning_ic and beginning_ic > 0:
        result["capital_return_yield"] = avg_annual_return / beginning_ic
    else:
        result["capital_return_yield"] = 0

    # Total Value Creation Rate
    power = result.get("cum3yr_Power", 0) or 0
    cr_yield = result.get("capital_return_yield", 0) or 0
    result["total_value_creation"] = power + cr_yield

    # Buyback intensity
    total_nopat_3yr = sum(y["nopat"] for y in years[:3] if y["nopat"])
    result["buyback_intensity"] = total_bb_3yr / total_nopat_3yr if total_nopat_3yr > 0 else 0

    # Shareholder yield (trailing, on mkt cap)
    if years and result.get("mktCap", 0) > 0:
        bb1 = abs(years[0]["buybacks"])
        div1 = abs(years[0]["dividends"])
        debt_paydown = max(0, years[1]["total_debt"] - years[0]["total_debt"]) if len(years) >= 2 else 0
        result["shareholder_yield"] = (bb1 + div1 + debt_paydown) / result["mktCap"]
    else:
        result["shareholder_yield"] = None

    # FCF Conversion
    total_capex = sum(y["capex"] for y in years[:3])
    total_ocf = sum(y["op_cf"] for y in years[:3])
    result["fcf_conversion"] = 1 - (total_capex / total_ocf) if total_ocf > 0 else None

    # 5yr NOPAT/Share CAGR
    if len(years) >= 6:
        a, b = years[0]["nopat_per_share"], years[5]["nopat_per_share"]
        result["nopat_share_cagr_5yr"] = (a/b)**(1/5)-1 if a and b and b > 0 and a > 0 else None
    elif len(years) >= 4:
        a, b = years[0]["nopat_per_share"], years[3]["nopat_per_share"]
        result["nopat_share_cagr_5yr"] = (a/b)**(1/3)-1 if a and b and b > 0 and a > 0 else None
        if result["nopat_share_cagr_5yr"]: result["nopat_cagr_note"] = "3yr"
    else:
        result["nopat_share_cagr_5yr"] = None

    # 5yr FCF/Share CAGR
    if len(years) >= 6:
        a, b = years[0]["fcf_per_share"], years[5]["fcf_per_share"]
        result["fcf_share_cagr_5yr"] = (a/b)**(1/5)-1 if a and b and b > 0 and a > 0 else None
    elif len(years) >= 4:
        a, b = years[0]["fcf_per_share"], years[3]["fcf_per_share"]
        result["fcf_share_cagr_5yr"] = (a/b)**(1/3)-1 if a and b and b > 0 and a > 0 else None
        if result["fcf_share_cagr_5yr"]: result["fcf_cagr_note"] = "3yr"
    else:
        result["fcf_share_cagr_5yr"] = None

    cagrs = [c for c in [result.get("nopat_share_cagr_5yr"), result.get("fcf_share_cagr_5yr")] if c is not None]
    result["best_pershare_cagr"] = max(cagrs) if cagrs else None

    fnis = [y["fcf_ni"] for y in years[:3] if y["fcf_ni"] is not None and y["fcf_ni"] > 0]
    result["avg3yr_FCF_NI"] = sum(fnis)/len(fnis) if fnis else None

    if years and years[0]["ebitda"] and years[0]["ebitda"] > 0:
        result["netDebt_EBITDA"] = years[0]["net_debt"] / years[0]["ebitda"]
    else:
        result["netDebt_EBITDA"] = None

    # Label mechanism
    if power > cr_yield:
        result["mechanism"] = "reinvestment"
    elif result["buyback_intensity"] > 0.50:
        result["mechanism"] = "buyback"
    elif cr_yield > 0:
        result["mechanism"] = "hybrid"
    else:
        result["mechanism"] = "unknown"

    return result


def apply_gates(stock):
    reasons = []

    # GATE 1: Quality
    gm = stock.get("grossMargin",0) or 0
    if gm <= GATE1_GM:
        reasons.append(f"GM {gm*100:.1f}% <= {GATE1_GM*100:.0f}%")
    avg_roic = stock.get("avg3yr_ROIC")
    curr_roic = stock.get("currentROIC")
    if not ((avg_roic and avg_roic >= GATE1_ROIC_AVG) or (curr_roic and curr_roic >= GATE1_ROIC_CURRENT)):
        r1 = f"3yr {avg_roic*100:.1f}%" if avg_roic else "N/A"
        r2 = f"curr {curr_roic*100:.1f}%" if curr_roic else "N/A"
        reasons.append(f"ROIC fail ({r1}, {r2})")
    if reasons: return False, "Gate 1", reasons

    # GATE 2: Total Value Creation Rate >= 20%
    tvcr = stock.get("total_value_creation", 0)
    power = stock.get("cum3yr_Power", 0) or 0
    cr_yield = stock.get("capital_return_yield", 0) or 0
    if tvcr < GATE2_TVCR:
        reasons.append(f"TVCR {tvcr*100:.1f}% < {GATE2_TVCR*100:.0f}% (Power {power*100:.1f}% + CapReturn {cr_yield*100:.1f}%)")
    if reasons: return False, "Gate 2", reasons

    # GATE 3: Per-share CAGR >= 15%
    best_cagr = stock.get("best_pershare_cagr")
    if best_cagr is None or best_cagr < GATE3_PERSHARE_CAGR:
        nps = stock.get("nopat_share_cagr_5yr")
        fps = stock.get("fcf_share_cagr_5yr")
        n_str = f"NOPAT/sh {nps*100:.1f}%" if nps else "NOPAT/sh N/A"
        f_str = f"FCF/sh {fps*100:.1f}%" if fps else "FCF/sh N/A"
        cagr_str = f"{best_cagr*100:.1f}%" if best_cagr else "N/A"
        reasons.append(f"Per-share CAGR {cagr_str} < {GATE3_PERSHARE_CAGR*100:.0f}% ({n_str}, {f_str})")
    if reasons: return False, "Gate 3", reasons

    # GATE 4: Financial Health
    fcf_ni = stock.get("avg3yr_FCF_NI")
    if fcf_ni is not None and fcf_ni < GATE4_FCF_NI:
        reasons.append(f"FCF/NI {fcf_ni*100:.1f}% < {GATE4_FCF_NI*100:.0f}%")
    elif fcf_ni is None:
        reasons.append("FCF/NI unavailable")
    nd = stock.get("netDebt_EBITDA")
    if nd is not None and nd > GATE4_ND_EBITDA:
        if nd <= GATE4_ND_EBITDA_ESC:
            reasons.append(f"ND/EBITDA {nd:.1f}x > {GATE4_ND_EBITDA}x (escape)")
        else:
            reasons.append(f"ND/EBITDA {nd:.1f}x > {GATE4_ND_EBITDA}x")
    if reasons: return False, "Gate 4", reasons

    return True, "PASS", []


def score_stocks(passers):
    tvcrs = [s.get("total_value_creation") for s in passers]
    roics = [s.get("avg3yr_ROIC") for s in passers]
    cagrs = [s.get("best_pershare_cagr") for s in passers]

    def pctrank(val, vals):
        valid = [v for v in vals if v is not None]
        if not valid or val is None: return 0.5
        return sum(1 for v in valid if v <= val) / len(valid)

    for s in passers:
        tvcr_pct = pctrank(s.get("total_value_creation"), tvcrs)
        roic_pct = pctrank(s.get("avg3yr_ROIC"), roics)
        cagr_pct = pctrank(s.get("best_pershare_cagr"), cagrs)
        nd = s.get("netDebt_EBITDA")
        bal = 1.0 if nd is None or nd < 0 else max(0, 1 - nd/5)
        s["composite_score"] = 0.30*tvcr_pct + 0.25*roic_pct + 0.30*cagr_pct + 0.15*bal


def main():
    global api_calls
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, "test9_log.txt")
    csv_path = os.path.join(OUTPUT_DIR, "test9_results.csv")
    all_data_path = os.path.join(OUTPUT_DIR, "test9_data.json")

    log = open(log_path, "w")
    def out(msg):
        print(msg); log.write(msg + "\n")

    out(f"Capital Compounders v3 — Unified Total Value Creation")
    out(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    TICKERS = ["NVDA", "AZO", "GOOGL", "MA", "ADP", "CLS", "MOD", "V", "AAPL"]
    out(f"TEST RUN: {len(TICKERS)} tickers")
    out(f"{'='*70}\n")

    all_stocks = []
    errors = []

    for i, ticker in enumerate(TICKERS):
        pct = (i+1)/len(TICKERS)*100
        print(f"\r[{pct:5.1f}%] Processing {ticker:<6} ({i+1}/{len(TICKERS)}) — {api_calls} API calls", end="", flush=True)
        result = process_ticker(ticker)
        if result.get("error"):
            errors.append((ticker, result["error"]))
        else:
            all_stocks.append(result)

    print()
    out(f"\nData pull complete: {len(all_stocks)} stocks, {len(errors)} errors, {api_calls} API calls")
    if errors:
        for t, e in errors: out(f"  x {t}: {e}")

    with open(all_data_path, "w") as f:
        json.dump(all_stocks, f, indent=2, default=str)

    # Detailed breakdown
    out(f"\n{'='*130}")
    out(f"DETAILED VALUE CREATION BREAKDOWN")
    out(f"{'='*130}\n")

    out(f"{'Sym':<6} {'3yr ROIC':>9} {'ROIIC':>8} {'Reinv':>7} {'Power':>7} {'BegIC':>9} "
        f"{'AvgBB/yr':>10} {'AvgDiv/yr':>10} {'CR Yield':>9} {'TVCR':>7} {'Mech':<12} "
        f"{'NOPAT/sh':>9} {'FCF/sh':>8}")
    out("-" * 130)

    for s in sorted(all_stocks, key=lambda x: x.get("total_value_creation",0), reverse=True):
        def p(v, f=".1f"): return f"{v*100:{f}}%" if v is not None else "---"
        def b(v): return f"${v/1e9:.1f}B" if v else "---"
        avg_div = s.get("total_dividends_3yr",0)/3

        out(f"{s['symbol']:<6} {p(s.get('avg3yr_ROIC')):>9} {p(s.get('cum3yr_ROIIC')):>8} "
            f"{p(s.get('cum3yr_ReinvRate')):>7} {p(s.get('cum3yr_Power')):>7} "
            f"{b(s.get('beginning_ic')):>9} "
            f"{b(s.get('avg_annual_capital_return')):>10} "
            f"{'$'+str(round(avg_div/1e9,1))+'B':>10} "
            f"{p(s.get('capital_return_yield')):>9} "
            f"{p(s.get('total_value_creation')):>7} "
            f"{s.get('mechanism','?'):<12} "
            f"{p(s.get('nopat_share_cagr_5yr')):>9} {p(s.get('fcf_share_cagr_5yr')):>8}")

    # Apply Gates
    out(f"\n{'='*70}")
    out(f"APPLYING GATES")
    out(f"{'='*70}\n")

    passers = []
    failures = {1:[], 2:[], 3:[], 4:[]}

    for stock in all_stocks:
        passed, gate, reasons = apply_gates(stock)
        if passed:
            passers.append(stock)
        else:
            gn = int(gate.split()[1][0])
            if gn in failures:
                failures[gn].append((stock["symbol"], reasons))

    out(f"Gate Results:")
    out(f"  Entered:       {len(all_stocks)}")
    out(f"  Failed Gate 1: {len(failures[1])} (Quality)")
    out(f"  Failed Gate 2: {len(failures[2])} (Value Creation < 20%)")
    out(f"  Failed Gate 3: {len(failures[3])} (Per-Share Proof < 15%)")
    out(f"  Failed Gate 4: {len(failures[4])} (Financial Health)")
    out(f"  PASSED ALL:    {len(passers)}")

    for gn, name in [(1,"Quality"),(2,"Value Creation"),(3,"Per-Share Proof"),(4,"Financial Health")]:
        if failures[gn]:
            out(f"\n  Gate {gn} failures ({name}):")
            for sym, reasons in sorted(failures[gn]):
                out(f"    {sym:<8} — {'; '.join(reasons)}")

    if passers:
        score_stocks(passers)
        passers.sort(key=lambda x: x.get("composite_score",0), reverse=True)

        out(f"\n{'='*140}")
        out(f"FINAL RANKED RESULTS: {len(passers)} Capital Compounders")
        out(f"{'='*140}\n")

        out(f"{'#':<3} {'Sym':<6} {'Name':<22} {'MktCap':>8} {'Mech':<13} "
            f"{'TVCR':>7} {'Power':>7} {'CRYld':>7} {'ROIC':>7} "
            f"{'NOPAT/sh':>9} {'FCF/sh':>8} {'FCF/NI':>7} {'ND/EB':>6} {'Score':>6}")
        out("-" * 140)

        for i, s in enumerate(passers):
            mc = s.get("mktCap",0)
            mc_s = f"${mc/1e12:.1f}T" if mc >= 1e12 else f"${mc/1e9:.0f}B" if mc >= 1e9 else f"${mc/1e6:.0f}M"
            def p(v,f=".1f"): return f"{v*100:{f}}%" if v is not None else "---"

            out(f"{i+1:<3} {s['symbol']:<6} {s.get('companyName','')[:21]:<22} {mc_s:>8} "
                f"{s.get('mechanism','?'):<13} "
                f"{p(s.get('total_value_creation')):>7} {p(s.get('cum3yr_Power')):>7} "
                f"{p(s.get('capital_return_yield')):>7} {p(s.get('avg3yr_ROIC')):>7} "
                f"{p(s.get('nopat_share_cagr_5yr')):>9} {p(s.get('fcf_share_cagr_5yr')):>8} "
                f"{p(s.get('avg3yr_FCF_NI'),'.0f'):>7} "
                f"{'%.1fx' % s['netDebt_EBITDA'] if s.get('netDebt_EBITDA') is not None else '---':>6} "
                f"{s.get('composite_score',0):.2f}")

        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Rank","Symbol","CompanyName","Sector","Industry","MktCap","Mechanism",
                        "TVCR%","Power%","CapReturnYield%","3yr_ROIC%","CurrentROIC%",
                        "ROIIC%","ReinvRate%","BuybackIntensity%",
                        "NOPAT_Share_CAGR%","FCF_Share_CAGR%","Best_CAGR%",
                        "FCF_NI%","NetDebt_EBITDA","FCF_Conversion","Score"])
            for i, s in enumerate(passers):
                def r(v, m=100): return round(v*m,2) if v is not None else ""
                w.writerow([i+1, s["symbol"], s.get("companyName",""),
                    s.get("sector",""), s.get("industry",""), s.get("mktCap",0),
                    s.get("mechanism",""),
                    r(s.get("total_value_creation")), r(s.get("cum3yr_Power")),
                    r(s.get("capital_return_yield")), r(s.get("avg3yr_ROIC")),
                    r(s.get("currentROIC")), r(s.get("cum3yr_ROIIC")),
                    r(s.get("cum3yr_ReinvRate")), r(s.get("buyback_intensity")),
                    r(s.get("nopat_share_cagr_5yr")), r(s.get("fcf_share_cagr_5yr")),
                    r(s.get("best_pershare_cagr")),
                    r(s.get("avg3yr_FCF_NI")),
                    round(s["netDebt_EBITDA"],2) if s.get("netDebt_EBITDA") is not None else "",
                    round(s["fcf_conversion"],2) if s.get("fcf_conversion") is not None else "",
                    round(s.get("composite_score",0),4)])
        out(f"\nResults: {csv_path}")
    else:
        out("\nNo stocks passed all gates.")

    out(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.close()
    print(f"\n{'='*70}")
    print(f"DONE — {len(passers)} compounders")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
