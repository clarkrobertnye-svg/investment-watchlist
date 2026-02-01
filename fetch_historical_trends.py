"""
Fetch 5-Year Historical Data for Trends & Incremental ROIC
"""

import json
import time
import requests
import argparse
from datetime import datetime
from pathlib import Path

try:
    from config import FMP_API_KEY
except ImportError:
    FMP_API_KEY = "TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU"

UNIVERSE_FILE = "capital_compounders_universe.json"
OUTPUT_FILE = "capital_compounders_universe.json"
BACKUP_FILE = f"capital_compounders_universe_backup_hist_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
PROGRESS_FILE = "historical_trends_progress.json"

CALLS_PER_MINUTE = 280
DELAY = 60 / CALLS_PER_MINUTE
BASE_URL = "https://financialmodelingprep.com/stable"


def fetch_json(endpoint, symbol, limit=5):
    url = f"{BASE_URL}/{endpoint}?symbol={symbol}&period=annual&limit={limit}&apikey={FMP_API_KEY}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("Error Message"):
            return None
        return data
    except Exception as e:
        print(f"  ⚠️  {symbol} {endpoint}: {e}")
        return None


def calc_nopat(inc):
    op_income = inc.get("operatingIncome", 0) or 0
    tax_expense = inc.get("incomeTaxExpense", 0) or 0
    pretax_income = inc.get("incomeBeforeTax", 0) or 0
    if pretax_income and pretax_income > 0:
        eff_tax_rate = max(0, min(tax_expense / pretax_income, 0.50))
    else:
        eff_tax_rate = 0.21
    return op_income * (1 - eff_tax_rate)


def calc_invested_capital(bs):
    total_equity = bs.get("totalStockholdersEquity", 0) or bs.get("totalEquity", 0) or 0
    total_debt = bs.get("totalDebt", 0) or 0
    if not total_debt:
        short_debt = bs.get("shortTermDebt", 0) or 0
        long_debt = bs.get("longTermDebt", 0) or 0
        total_debt = short_debt + long_debt
    return total_equity + total_debt


def calc_invested_capital_ex_cash(bs):
    ic = calc_invested_capital(bs)
    cash = bs.get("cashAndCashEquivalents", 0) or bs.get("cashAndShortTermInvestments", 0) or 0
    return ic + cash


def determine_trend(values, threshold=0.02):
    if not values or len(values) < 2:
        return 'unknown'
    newest = values[0]
    oldest = values[-1]
    if oldest == 0 or oldest is None:
        return 'unknown'
    change_pct = (newest - oldest) / abs(oldest)
    if change_pct > threshold:
        return 'improving'
    elif change_pct < -threshold:
        return 'declining'
    else:
        return 'stable'


def safe_cagr(newest, oldest, years):
    """Calculate CAGR safely, avoiding complex numbers from negative values."""
    if oldest is None or oldest <= 0 or newest is None or newest <= 0 or years <= 0:
        return None
    try:
        return (newest / oldest) ** (1 / years) - 1
    except:
        return None


def calc_historical_metrics(inc_data, bs_data):
    if not inc_data or not bs_data:
        return None
    
    years_data = []
    for i in range(min(len(inc_data), len(bs_data))):
        inc = inc_data[i]
        bs = bs_data[i]
        year = inc.get("calendarYear") or inc.get("date", "")[:4]
        revenue = inc.get("revenue", 0) or 0
        gross_profit = inc.get("grossProfit", 0) or 0
        gm = gross_profit / revenue if revenue > 0 else 0
        nopat = calc_nopat(inc)
        ic = calc_invested_capital(bs)
        ic_ex_cash = calc_invested_capital_ex_cash(bs)
        roic = nopat / ic if ic > 0 else 0
        roic_ex_cash = nopat / ic_ex_cash if ic_ex_cash > 0 else 0
        years_data.append({
            "year": year, "revenue": revenue, "gross_margin": gm,
            "nopat": nopat, "invested_capital": ic,
            "invested_capital_ex_cash": ic_ex_cash,
            "roic": roic, "roic_ex_cash": roic_ex_cash,
        })
    
    if len(years_data) < 2:
        return None
    
    roic_history = [y["roic"] for y in years_data]
    roic_ex_cash_history = [y["roic_ex_cash"] for y in years_data]
    gm_history = [y["gross_margin"] for y in years_data]
    nopat_history = [y["nopat"] for y in years_data]
    ic_history = [y["invested_capital"] for y in years_data]
    years = [y["year"] for y in years_data]
    
    roic_trend = determine_trend(roic_history)
    gm_trend_raw = determine_trend(gm_history, threshold=0.01)
    gm_trend = gm_trend_raw.replace('improving', 'expanding').replace('declining', 'contracting')
    
    # Safe CAGR calculation
    if len(roic_history) >= 5:
        roic_5y_cagr = safe_cagr(roic_history[0], roic_history[-1], len(roic_history) - 1)
    elif len(roic_history) >= 3:
        roic_5y_cagr = safe_cagr(roic_history[0], roic_history[-1], len(roic_history) - 1)
    else:
        roic_5y_cagr = None
    
    gm_5y_change = gm_history[0] - gm_history[-1] if len(gm_history) >= 2 else None
    
    if len(nopat_history) >= 3 and len(ic_history) >= 3:
        delta_nopat_3y = nopat_history[0] - nopat_history[2]
        delta_ic_3y = ic_history[0] - ic_history[2]
        incremental_roic_3y = delta_nopat_3y / delta_ic_3y if delta_ic_3y > 0 else None
    else:
        incremental_roic_3y = None
    
    if len(nopat_history) >= 5 and len(ic_history) >= 5:
        delta_nopat_5y = nopat_history[0] - nopat_history[4]
        delta_ic_5y = ic_history[0] - ic_history[4]
        incremental_roic_5y = delta_nopat_5y / delta_ic_5y if delta_ic_5y > 0 else None
    elif len(nopat_history) >= 3:
        delta_nopat = nopat_history[0] - nopat_history[-1]
        delta_ic = ic_history[0] - ic_history[-1]
        incremental_roic_5y = delta_nopat / delta_ic if delta_ic > 0 else None
    else:
        incremental_roic_5y = None
    
    current_roic = roic_history[0] if roic_history else 0
    if incremental_roic_5y is not None and current_roic > 0:
        ratio = incremental_roic_5y / current_roic
        if ratio > 1.1:
            incremental_vs_current = 'above'
        elif ratio < 0.9:
            incremental_vs_current = 'below'
        else:
            incremental_vs_current = 'similar'
    else:
        incremental_vs_current = 'unknown'
    
    return {
        "roic_history": roic_history, "roic_ex_cash_history": roic_ex_cash_history,
        "roic_5y_cagr": roic_5y_cagr, "roic_trend": roic_trend,
        "gm_history": gm_history, "gm_5y_change": gm_5y_change, "gm_trend": gm_trend,
        "nopat_history": nopat_history, "ic_history": ic_history, "years": years,
        "incremental_roic_3y": incremental_roic_3y, "incremental_roic_5y": incremental_roic_5y,
        "incremental_vs_current": incremental_vs_current, "data_years": len(years_data),
    }


def load_progress():
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed": {}, "errors": []}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--test", type=str)
    args = parser.parse_args()

    if args.test:
        print(f"Testing {args.test}...")
        inc = fetch_json("income-statement", args.test, limit=5)
        time.sleep(DELAY)
        bs = fetch_json("balance-sheet-statement", args.test, limit=5)
        result = calc_historical_metrics(inc, bs)
        if result:
            print(f"\n{'='*60}")
            print(f"  {args.test} Historical Trends ({result['data_years']} years)")
            print(f"{'='*60}")
            print(f"  Years: {' -> '.join(result['years'])}")
            print(f"\n  ROIC History:")
            for i, (yr, roic) in enumerate(zip(result['years'], result['roic_history'])):
                marker = "<- newest" if i == 0 else ""
                print(f"    {yr}: {roic*100:5.1f}%  {marker}")
            print(f"  ROIC Trend: {result['roic_trend'].upper()}")
            print(f"\n  GM History:")
            for i, (yr, gm) in enumerate(zip(result['years'], result['gm_history'])):
                marker = "<- newest" if i == 0 else ""
                print(f"    {yr}: {gm*100:5.1f}%  {marker}")
            print(f"  GM Trend: {result['gm_trend'].upper()}")
            print(f"\n  Incremental ROIC:")
            if result['incremental_roic_3y']:
                print(f"    3-Year: {result['incremental_roic_3y']*100:5.1f}%")
            if result['incremental_roic_5y']:
                print(f"    5-Year: {result['incremental_roic_5y']*100:5.1f}%")
            print(f"    vs Current: {result['incremental_vs_current'].upper()}")
            current_roic = result['roic_history'][0]
            inc_roic = result['incremental_roic_5y']
            if inc_roic and current_roic:
                print(f"\n  Current ROIC: {current_roic*100:.1f}%  |  Incremental: {inc_roic*100:.1f}%")
                if inc_roic > current_roic:
                    print(f"  ✅ Moat WIDENING")
                elif inc_roic < current_roic * 0.8:
                    print(f"  ⚠️ Moat NARROWING")
                else:
                    print(f"  ➡️ Moat STABLE")
        else:
            print("  ❌ Could not calculate")
        return

    if not Path(UNIVERSE_FILE).exists():
        print(f"❌ {UNIVERSE_FILE} not found")
        return

    with open(UNIVERSE_FILE) as f:
        universe = json.load(f)

    tickers = universe["tickers"]
    total = len(tickers)

    if args.status:
        progress = load_progress()
        print(f"Progress: {len(progress['completed'])}/{total}")
        return

    progress = load_progress() if args.resume else {"completed": {}, "errors": []}

    if not args.resume:
        print(f"📋 Backing up to {BACKUP_FILE}...")
        with open(BACKUP_FILE, "w") as f:
            json.dump(universe, f)

    already_done = len(progress["completed"])
    remaining = total - already_done

    print(f"{'='*60}")
    print(f"  Historical Trends Fetch (ROIC, GM, Incremental ROIC)")
    print(f"{'='*60}")
    print(f"  Universe: {total} | Remaining: {remaining}")
    print(f"  Est. time: {(remaining * 2) / CALLS_PER_MINUTE:.0f} minutes")
    print(f"{'='*60}\n")

    start_time = time.time()
    processed = 0
    api_calls = 0

    for ticker_data in tickers:
        ticker = ticker_data["ticker"]
        if ticker in progress["completed"]:
            continue

        inc = fetch_json("income-statement", ticker, limit=5)
        api_calls += 1
        time.sleep(DELAY)

        bs = fetch_json("balance-sheet-statement", ticker, limit=5)
        api_calls += 1
        time.sleep(DELAY)

        result = calc_historical_metrics(inc, bs)

        if result:
            progress["completed"][ticker] = result
            trend_str = result['roic_trend'][:3].upper()
            inc_str = f"{result['incremental_roic_5y']*100:.0f}%" if result['incremental_roic_5y'] else "N/A"
            status = "✅"
        else:
            progress["completed"][ticker] = None
            progress["errors"].append(ticker)
            trend_str = "ERR"
            inc_str = "ERR"
            status = "❌"

        processed += 1
        done_total = already_done + processed

        if processed % 25 == 0 or processed <= 3:
            elapsed = time.time() - start_time
            rate = processed / (elapsed / 60) if elapsed > 0 else 0
            eta = (remaining - processed) / rate if rate > 0 else 0
            print(f"  [{done_total}/{total}] {ticker:<6} Trend: {trend_str}  IncROIC: {inc_str:>5}  {status}  ({rate:.0f}/min, ETA: {eta:.0f}min)")

        if processed % 50 == 0:
            save_progress(progress)

    save_progress(progress)
    print(f"\n📊 Merging results...")

    success = 0
    improving = 0
    declining = 0
    moat_widening = 0

    for ticker_data in tickers:
        ticker = ticker_data["ticker"]
        result = progress["completed"].get(ticker)
        if result:
            ticker_data["roic_history"] = result["roic_history"]
            ticker_data["roic_ex_cash_history"] = result["roic_ex_cash_history"]
            ticker_data["roic_5y_cagr"] = result["roic_5y_cagr"]
            ticker_data["roic_trend"] = result["roic_trend"]
            ticker_data["gm_history"] = result["gm_history"]
            ticker_data["gm_5y_change"] = result["gm_5y_change"]
            ticker_data["gm_trend"] = result["gm_trend"]
            ticker_data["nopat_history"] = result["nopat_history"]
            ticker_data["ic_history"] = result["ic_history"]
            ticker_data["incremental_roic_3y"] = result["incremental_roic_3y"]
            ticker_data["incremental_roic_5y"] = result["incremental_roic_5y"]
            ticker_data["incremental_vs_current"] = result["incremental_vs_current"]
            ticker_data["trend_years"] = result["data_years"]
            success += 1
            if result["roic_trend"] == "improving":
                improving += 1
            elif result["roic_trend"] == "declining":
                declining += 1
            if result["incremental_vs_current"] == "above":
                moat_widening += 1
        else:
            ticker_data["roic_history"] = None
            ticker_data["roic_ex_cash_history"] = None
            ticker_data["roic_5y_cagr"] = None
            ticker_data["roic_trend"] = None
            ticker_data["gm_history"] = None
            ticker_data["gm_5y_change"] = None
            ticker_data["gm_trend"] = None
            ticker_data["nopat_history"] = None
            ticker_data["ic_history"] = None
            ticker_data["incremental_roic_3y"] = None
            ticker_data["incremental_roic_5y"] = None
            ticker_data["incremental_vs_current"] = None
            ticker_data["trend_years"] = None

    universe["historical_trends_added"] = datetime.now().isoformat()
    with open(OUTPUT_FILE, "w") as f:
        json.dump(universe, f, indent=2)

    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"  ✅ COMPLETE")
    print(f"{'='*60}")
    print(f"  Processed: {processed} in {elapsed/60:.1f} min")
    print(f"  ROIC Improving: {improving} | Declining: {declining} | Stable: {success - improving - declining}")
    print(f"  Moat Widening: {moat_widening}")
    print(f"{'='*60}")

    Path(PROGRESS_FILE).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
