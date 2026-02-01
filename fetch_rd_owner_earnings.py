"""
Fetch R&D and Owner Earnings for Capital Compounders Universe
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
BACKUP_FILE = f"capital_compounders_universe_backup_rd_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
PROGRESS_FILE = "rd_owner_earnings_progress.json"

CALLS_PER_MINUTE = 280
DELAY = 60 / CALLS_PER_MINUTE
BASE_URL = "https://financialmodelingprep.com/stable"


def fetch_json(endpoint, symbol):
    url = f"{BASE_URL}/{endpoint}?symbol={symbol}&period=annual&limit=3&apikey={FMP_API_KEY}"
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


def calc_rd_owner_earnings(inc_data, cf_data, existing_data):
    if not inc_data or not cf_data:
        return None

    results = []
    for i in range(min(len(inc_data), len(cf_data), 3)):
        inc = inc_data[i]
        cf = cf_data[i]
        
        r_and_d = inc.get("researchAndDevelopmentExpenses", 0) or 0
        revenue = inc.get("revenue", 0) or 0
        r_and_d_revenue = r_and_d / revenue if revenue > 0 else 0
        
        depreciation = abs(cf.get("depreciationAndAmortization", 0) or 0)
        ocf = cf.get("operatingCashFlow", 0) or 0
        owner_earnings = ocf - depreciation
        
        results.append({
            "year": cf.get("calendarYear") or cf.get("date", "")[:4],
            "r_and_d": r_and_d,
            "revenue": revenue,
            "r_and_d_revenue": r_and_d_revenue,
            "depreciation": depreciation,
            "ocf": ocf,
            "owner_earnings": owner_earnings,
        })
    
    if not results:
        return None
    
    latest = results[0]
    valid_rd = [r["r_and_d_revenue"] for r in results if r["r_and_d_revenue"] > 0]
    avg_rd_revenue = sum(valid_rd) / len(valid_rd) if valid_rd else 0
    valid_oe = [r["owner_earnings"] for r in results]
    avg_owner_earnings = sum(valid_oe) / len(valid_oe) if valid_oe else 0
    
    market_cap = existing_data.get("market_cap", 0) or 0
    oe_yield = latest["owner_earnings"] / market_cap if market_cap > 0 and latest["owner_earnings"] else None
    
    return {
        "r_and_d": latest["r_and_d"],
        "r_and_d_revenue": latest["r_and_d_revenue"],
        "r_and_d_revenue_3y_avg": avg_rd_revenue,
        "depreciation": latest["depreciation"],
        "owner_earnings": latest["owner_earnings"],
        "owner_earnings_3y_avg": avg_owner_earnings,
        "owner_earnings_yield": oe_yield,
        "data_years": len(results),
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
        inc = fetch_json("income-statement", args.test)
        time.sleep(DELAY)
        cf = fetch_json("cash-flow-statement", args.test)
        existing = {"market_cap": 3000000000000}
        result = calc_rd_owner_earnings(inc, cf, existing)
        if result:
            print(f"\n{'='*50}")
            print(f"  {args.test} R&D & Owner Earnings")
            print(f"{'='*50}")
            print(f"  R&D Expense:        ${result['r_and_d']/1e9:>10,.1f}B")
            print(f"  R&D / Revenue:      {result['r_and_d_revenue']*100:>10.1f}%")
            print(f"  Depreciation:       ${result['depreciation']/1e9:>10,.1f}B")
            print(f"  Owner Earnings:     ${result['owner_earnings']/1e9:>10,.1f}B")
            if result['owner_earnings_yield']:
                print(f"  OE Yield:           {result['owner_earnings_yield']*100:>10.1f}%")
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
    print(f"  R&D & Owner Earnings Fetch")
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

        inc = fetch_json("income-statement", ticker)
        api_calls += 1
        time.sleep(DELAY)

        cf = fetch_json("cash-flow-statement", ticker)
        api_calls += 1
        time.sleep(DELAY)

        result = calc_rd_owner_earnings(inc, cf, ticker_data)

        if result:
            progress["completed"][ticker] = result
            rd_str = f"{result['r_and_d_revenue']*100:.0f}%"
            status = "✅"
        else:
            progress["completed"][ticker] = None
            progress["errors"].append(ticker)
            rd_str = "ERR"
            status = "❌"

        processed += 1
        done_total = already_done + processed

        if processed % 25 == 0 or processed <= 3:
            elapsed = time.time() - start_time
            rate = processed / (elapsed / 60) if elapsed > 0 else 0
            eta = (remaining - processed) / rate if rate > 0 else 0
            print(f"  [{done_total}/{total}] {ticker:<6} R&D: {rd_str:>4}  {status}  ({rate:.0f}/min, ETA: {eta:.0f}min)")

        if processed % 50 == 0:
            save_progress(progress)

    save_progress(progress)
    print(f"\n📊 Merging results...")

    success = 0
    has_rd = 0

    for ticker_data in tickers:
        ticker = ticker_data["ticker"]
        result = progress["completed"].get(ticker)
        if result:
            ticker_data["r_and_d"] = result["r_and_d"]
            ticker_data["r_and_d_revenue"] = result["r_and_d_revenue"]
            ticker_data["r_and_d_revenue_3y_avg"] = result["r_and_d_revenue_3y_avg"]
            ticker_data["depreciation"] = result["depreciation"]
            ticker_data["owner_earnings"] = result["owner_earnings"]
            ticker_data["owner_earnings_3y_avg"] = result["owner_earnings_3y_avg"]
            ticker_data["owner_earnings_yield"] = result["owner_earnings_yield"]
            success += 1
            if result["r_and_d"] and result["r_and_d"] > 0:
                has_rd += 1
        else:
            ticker_data["r_and_d"] = None
            ticker_data["r_and_d_revenue"] = None
            ticker_data["r_and_d_revenue_3y_avg"] = None
            ticker_data["depreciation"] = None
            ticker_data["owner_earnings"] = None
            ticker_data["owner_earnings_3y_avg"] = None
            ticker_data["owner_earnings_yield"] = None

    universe["rd_owner_earnings_added"] = datetime.now().isoformat()
    with open(OUTPUT_FILE, "w") as f:
        json.dump(universe, f, indent=2)

    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"  ✅ COMPLETE")
    print(f"{'='*60}")
    print(f"  Processed: {processed} in {elapsed/60:.1f} min")
    print(f"  With R&D: {has_rd} | No R&D: {success - has_rd}")
    print(f"{'='*60}")

    Path(PROGRESS_FILE).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
