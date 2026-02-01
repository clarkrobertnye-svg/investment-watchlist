"""
Fetch Reinvestment Rate for Capital Compounders Universe
Adds reinvestment_rate to each ticker in capital_compounders_universe.json

Formula: (Net CapEx + ΔWorking Capital + Acquisitions) / NOPAT
  - Net CapEx = |CapEx| - D&A
  - NOPAT = Operating Income × (1 - Effective Tax Rate)
  - Target: 40-80% (depending on maturity)

API Calls: 2 per ticker (cash-flow-statement + income-statement)
Time: ~6 minutes for 857 tickers at 290 calls/min

Usage:
    cd ~/Documents/capital_compounders
    python3 fetch_reinvestment_rate.py
    python3 fetch_reinvestment_rate.py --resume     # Resume interrupted run
    python3 fetch_reinvestment_rate.py --status      # Check progress
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
BACKUP_FILE = f"capital_compounders_universe_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
PROGRESS_FILE = "reinvestment_progress.json"

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


def calc_reinvestment_rate(cf_data, inc_data):
    if not cf_data or not inc_data:
        return None

    results = []

    for i in range(min(len(cf_data), len(inc_data), 3)):
        cf = cf_data[i]
        inc = inc_data[i]

        op_income = inc.get("operatingIncome", 0) or 0
        tax_expense = inc.get("incomeTaxExpense", 0) or 0
        pretax_income = inc.get("incomeBeforeTax", 0) or 0

        if pretax_income and pretax_income > 0:
            eff_tax_rate = max(0, min(tax_expense / pretax_income, 0.50))
        else:
            eff_tax_rate = 0.21

        nopat = op_income * (1 - eff_tax_rate)

        capex = abs(cf.get("capitalExpenditure", 0) or 0)
        da = abs(cf.get("depreciationAndAmortization", 0) or 0)
        net_capex = capex - da

        dwc_raw = cf.get("changeInWorkingCapital", 0) or 0
        dwc = -dwc_raw

        acquisitions = abs(cf.get("acquisitionsNet", 0) or 0)

        total_reinvestment = net_capex + dwc + acquisitions

        if nopat > 0:
            reinv_rate = total_reinvestment / nopat
        else:
            reinv_rate = None

        results.append({
            "year": cf.get("calendarYear") or cf.get("date", "")[:4],
            "nopat": nopat,
            "capex": capex,
            "da": da,
            "net_capex": net_capex,
            "dwc": dwc,
            "acquisitions": acquisitions,
            "total_reinvestment": total_reinvestment,
            "reinvestment_rate": reinv_rate,
            "eff_tax_rate": eff_tax_rate,
        })

    if not results:
        return None

    latest = results[0]

    valid_rates = [r["reinvestment_rate"] for r in results if r["reinvestment_rate"] is not None]
    avg_rate = sum(valid_rates) / len(valid_rates) if valid_rates else None

    if latest["nopat"] > 0:
        organic_rate = (latest["net_capex"] + latest["dwc"]) / latest["nopat"]
    else:
        organic_rate = None

    return {
        "reinvestment_rate": latest["reinvestment_rate"],
        "reinvestment_rate_3y_avg": avg_rate,
        "reinvestment_rate_organic": organic_rate,
        "nopat": latest["nopat"],
        "net_capex": latest["net_capex"],
        "delta_working_capital": latest["dwc"],
        "acquisitions": latest["acquisitions"],
        "total_reinvestment": latest["total_reinvestment"],
        "eff_tax_rate": latest["eff_tax_rate"],
        "reinvestment_years": len(results),
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
    parser = argparse.ArgumentParser(description="Fetch reinvestment rate for all universe tickers")
    parser.add_argument("--resume", action="store_true", help="Resume interrupted run")
    parser.add_argument("--status", action="store_true", help="Check progress")
    parser.add_argument("--test", type=str, help="Test single ticker")
    args = parser.parse_args()

    if args.test:
        print(f"Testing {args.test}...")
        cf = fetch_json("cash-flow-statement", args.test)
        time.sleep(DELAY)
        inc = fetch_json("income-statement", args.test)

        result = calc_reinvestment_rate(cf, inc)
        if result:
            print(f"\n{'='*50}")
            print(f"  {args.test} Reinvestment Rate")
            print(f"{'='*50}")
            print(f"  NOPAT:              ${result['nopat']/1e6:>10,.0f}M")
            print(f"  Net CapEx:          ${result['net_capex']/1e6:>10,.0f}M")
            print(f"  ΔWorking Capital:   ${result['delta_working_capital']/1e6:>10,.0f}M")
            print(f"  Acquisitions:       ${result['acquisitions']/1e6:>10,.0f}M")
            print(f"  ---------------------------------")
            print(f"  Total Reinvestment: ${result['total_reinvestment']/1e6:>10,.0f}M")
            print(f"  Reinvestment Rate:  {result['reinvestment_rate']*100:>10.0f}%")
            if result['reinvestment_rate_3y_avg'] is not None:
                print(f"  3Y Avg Rate:        {result['reinvestment_rate_3y_avg']*100:>10.0f}%")
            if result['reinvestment_rate_organic'] is not None:
                print(f"  Organic Rate:       {result['reinvestment_rate_organic']*100:>10.0f}%")
            print(f"  Eff Tax Rate:       {result['eff_tax_rate']*100:>10.0f}%")
            target = "✅ IN RANGE" if 0.4 <= (result['reinvestment_rate'] or 0) <= 0.8 else "⚠️ OUTSIDE 40-80%"
            print(f"  Target (40-80%):    {target}")
        else:
            print("  ❌ Could not calculate")
        return

    if not Path(UNIVERSE_FILE).exists():
        print(f"❌ {UNIVERSE_FILE} not found. Run from ~/Documents/capital_compounders/")
        return

    with open(UNIVERSE_FILE) as f:
        universe = json.load(f)

    tickers = universe["tickers"]
    total = len(tickers)

    if args.status:
        progress = load_progress()
        done = len(progress["completed"])
        errors = len(progress["errors"])
        print(f"Progress: {done}/{total} completed, {errors} errors")
        print(f"Remaining: {total - done}")
        remaining_calls = (total - done) * 2
        remaining_min = remaining_calls / CALLS_PER_MINUTE
        print(f"Est. time remaining: {remaining_min:.0f} minutes")
        return

    progress = load_progress() if args.resume else {"completed": {}, "errors": []}

    if not args.resume:
        print(f"📋 Backing up to {BACKUP_FILE}...")
        with open(BACKUP_FILE, "w") as f:
            json.dump(universe, f)

    already_done = len(progress["completed"])
    remaining = total - already_done
    est_minutes = (remaining * 2) / CALLS_PER_MINUTE

    print(f"{'='*60}")
    print(f"  Capital Compounders - Reinvestment Rate Fetch")
    print(f"{'='*60}")
    print(f"  Universe: {total} tickers")
    print(f"  Already done: {already_done}")
    print(f"  Remaining: {remaining}")
    print(f"  API calls: {remaining * 2}")
    print(f"  Est. time: {est_minutes:.0f} minutes")
    print(f"{'='*60}")
    print()

    start_time = time.time()
    processed = 0
    api_calls = 0

    for i, ticker_data in enumerate(tickers):
        ticker = ticker_data["ticker"]

        if ticker in progress["completed"]:
            continue

        cf = fetch_json("cash-flow-statement", ticker)
        api_calls += 1
        time.sleep(DELAY)

        inc = fetch_json("income-statement", ticker)
        api_calls += 1
        time.sleep(DELAY)

        result = calc_reinvestment_rate(cf, inc)

        if result:
            progress["completed"][ticker] = result
            rate_str = f"{result['reinvestment_rate']*100:.0f}%" if result['reinvestment_rate'] is not None else "N/A"
            status = "✅"
        else:
            progress["completed"][ticker] = None
            progress["errors"].append(ticker)
            rate_str = "ERR"
            status = "❌"

        processed += 1
        done_total = already_done + processed

        if processed % 25 == 0 or processed <= 3:
            elapsed = time.time() - start_time
            rate = processed / (elapsed / 60) if elapsed > 0 else 0
            eta = (remaining - processed) / rate if rate > 0 else 0
            print(f"  [{done_total}/{total}] {ticker:<6} Reinv: {rate_str:>6}  {status}  ({rate:.0f}/min, ETA: {eta:.0f}min)")

        if processed % 50 == 0:
            save_progress(progress)

    save_progress(progress)

    print(f"\n📊 Merging results into {OUTPUT_FILE}...")

    success = 0
    in_range = 0
    above_range = 0
    below_range = 0

    for ticker_data in tickers:
        ticker = ticker_data["ticker"]
        result = progress["completed"].get(ticker)

        if result:
            ticker_data["reinvestment_rate"] = result["reinvestment_rate"]
            ticker_data["reinvestment_rate_3y_avg"] = result["reinvestment_rate_3y_avg"]
            ticker_data["reinvestment_rate_organic"] = result["reinvestment_rate_organic"]
            ticker_data["nopat"] = result["nopat"]
            ticker_data["net_capex"] = result["net_capex"]
            ticker_data["delta_working_capital"] = result["delta_working_capital"]
            ticker_data["acquisitions"] = result["acquisitions"]
            ticker_data["total_reinvestment"] = result["total_reinvestment"]
            success += 1

            rr = result["reinvestment_rate"]
            if rr is not None:
                if 0.4 <= rr <= 0.8:
                    in_range += 1
                elif rr > 0.8:
                    above_range += 1
                else:
                    below_range += 1
        else:
            ticker_data["reinvestment_rate"] = None
            ticker_data["reinvestment_rate_3y_avg"] = None
            ticker_data["reinvestment_rate_organic"] = None
            ticker_data["nopat"] = None
            ticker_data["net_capex"] = None
            ticker_data["delta_working_capital"] = None
            ticker_data["acquisitions"] = None
            ticker_data["total_reinvestment"] = None

    universe["reinvestment_rate_added"] = datetime.now().isoformat()
    with open(OUTPUT_FILE, "w") as f:
        json.dump(universe, f, indent=2)

    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"  ✅ COMPLETE")
    print(f"{'='*60}")
    print(f"  Processed: {processed} tickers in {elapsed/60:.1f} minutes")
    print(f"  Success: {success} | Errors: {len(progress['errors'])}")
    print(f"  API calls: {api_calls}")
    print(f"")
    print(f"  Reinvestment Rate Distribution:")
    print(f"    🎯 In range (40-80%):  {in_range}")
    print(f"    🔺 Above 80%:          {above_range}")
    print(f"    🔻 Below 40%:          {below_range}")
    print(f"")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Backup: {BACKUP_FILE}")
    print(f"{'='*60}")

    Path(PROGRESS_FILE).unlink(missing_ok=True)

    if progress["errors"]:
        print(f"\n  Errors ({len(progress['errors'])}): {', '.join(progress['errors'][:20])}")


if __name__ == "__main__":
    main()
