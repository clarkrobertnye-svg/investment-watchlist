#!/usr/bin/env python3
"""
Capital Compounder Investment System - Main Pipeline
Orchestrates the complete three-tier screening process.

Usage:
    python main.py                    # Run full pipeline with default universe
    python main.py --tickers AAPL MSFT # Run for specific tickers
    python main.py --input universe.csv # Run from CSV with ticker column
    
Owner: Rob (clarkrobertnye@gmail.com)
Based on Investment Charter v1.0 (January 26, 2026)
"""

import argparse
import pandas as pd
import json
from datetime import datetime
from pathlib import Path

from config import OUTPUT_CONFIG
from fmp_data import fetch_universe_data, FinancialDataProcessor
from tier1_filter import run_tier1_filter, Tier1Filter
from tier2_scorer import run_tier2_scoring, Tier2Scorer
from tier3_valuation import run_tier3_valuation, DCFValuation


def load_universe(source: str) -> list:
    """Load ticker universe from CSV file."""
    df = pd.read_csv(source)
    
    # Find ticker column
    ticker_cols = ["Ticker", "ticker", "Symbol", "symbol", "TICKER"]
    for col in ticker_cols:
        if col in df.columns:
            tickers = df[col].dropna().tolist()
            # Clean tickers (remove .TO, .V suffixes for FMP)
            tickers = [t.split(".")[0] if "." in t else t for t in tickers]
            return tickers
    
    raise ValueError(f"No ticker column found. Expected one of: {ticker_cols}")


def run_full_pipeline(tickers: list, output_dir: str = ".") -> dict:
    """
    Run the complete three-tier pipeline.
    
    Args:
        tickers: List of ticker symbols to screen
        output_dir: Directory to save output files
    
    Returns:
        Dict with summary statistics
    """
    start_time = datetime.now()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*70}")
    print("CAPITAL COMPOUNDER INVESTMENT SYSTEM")
    print("Three-Tier Screening Pipeline")
    print(f"{'='*70}")
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Universe: {len(tickers)} tickers")
    print(f"Output: {output_path.absolute()}")
    print(f"{'='*70}")
    
    results = {
        "run_date": start_time.isoformat(),
        "input_universe": len(tickers),
    }
    
    # =========================================================================
    # STAGE 1: Fetch Financial Data
    # =========================================================================
    print("\n" + "="*70)
    print("STAGE 1: FETCHING FINANCIAL DATA")
    print("="*70)
    
    data_file = output_path / "universe_data.csv"
    raw_df = fetch_universe_data(tickers, str(data_file))
    
    results["data_fetched"] = len(raw_df)
    results["data_complete"] = len(raw_df[raw_df["data_quality"] == "complete"])
    
    # =========================================================================
    # STAGE 2: Tier 1 Hard Filters
    # =========================================================================
    tier1_passed_file = output_path / OUTPUT_CONFIG["universe_file"]
    tier1_failed_file = output_path / "universe_tier1_failed.csv"
    
    passed_df, failed_df = run_tier1_filter(
        str(data_file),
        str(tier1_passed_file),
        str(tier1_failed_file)
    )
    
    results["tier1_passed"] = len(passed_df)
    results["tier1_failed"] = len(failed_df)
    
    # =========================================================================
    # STAGE 3: Tier 2 Quality Scoring
    # =========================================================================
    tier2_file = output_path / OUTPUT_CONFIG["scored_file"]
    
    if len(passed_df) > 0:
        scored_df = run_tier2_scoring(str(tier1_passed_file), str(tier2_file))
        
        results["tier2_exceptional"] = len(scored_df[scored_df["tier_label"] == "EXCEPTIONAL"])
        results["tier2_elite"] = len(scored_df[scored_df["tier_label"] == "ELITE"])
        results["tier2_quality"] = len(scored_df[scored_df["tier_label"] == "QUALITY"])
    else:
        print("\n⚠️ No companies passed Tier 1 - skipping Tier 2 & 3")
        scored_df = pd.DataFrame()
        results["tier2_exceptional"] = 0
        results["tier2_elite"] = 0
        results["tier2_quality"] = 0
    
    # =========================================================================
    # STAGE 4: Tier 3 DCF Valuation
    # =========================================================================
    top20_file = output_path / OUTPUT_CONFIG["top20_file"]
    
    elite_plus = results["tier2_exceptional"] + results["tier2_elite"]
    if elite_plus > 0:
        valued_df = run_tier3_valuation(str(tier2_file), str(top20_file))
        
        complete_vals = valued_df[valued_df.get("valuation_status", "") == "complete"]
        results["valuations_complete"] = len(complete_vals)
        results["buy_signals"] = len(complete_vals[complete_vals["action_signal"] == "BUY"])
        results["watch_signals"] = len(complete_vals[complete_vals["action_signal"] == "WATCH"])
    else:
        print("\n⚠️ No ELITE+ companies - skipping Tier 3 valuation")
        valued_df = pd.DataFrame()
        results["valuations_complete"] = 0
        results["buy_signals"] = 0
        results["watch_signals"] = 0
    
    # =========================================================================
    # STAGE 5: Generate Dashboard Data
    # =========================================================================
    print("\n" + "="*70)
    print("STAGE 5: GENERATING DASHBOARD DATA")
    print("="*70)
    
    # Create JSON for dashboard
    dashboard_data = create_dashboard_json(
        valued_df if elite_plus > 0 else pd.DataFrame(),
        results
    )
    
    json_file = output_path / OUTPUT_CONFIG["watchlist_json"]
    with open(json_file, "w") as f:
        json.dump(dashboard_data, f, indent=2, default=str)
    print(f"✅ Dashboard JSON: {json_file}")
    
    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    results["duration_seconds"] = duration
    
    print(f"\n{'='*70}")
    print("PIPELINE COMPLETE")
    print(f"{'='*70}")
    print(f"Duration: {duration:.1f} seconds")
    print(f"\nFUNNEL SUMMARY:")
    print(f"  Input Universe:     {results['input_universe']:>4} tickers")
    print(f"  Data Complete:      {results['data_complete']:>4} ({results['data_complete']/results['input_universe']*100:.0f}%)")
    print(f"  Tier 1 Passed:      {results['tier1_passed']:>4} ({results['tier1_passed']/results['input_universe']*100:.0f}%)")
    print(f"  EXCEPTIONAL:        {results['tier2_exceptional']:>4}")
    print(f"  ELITE:              {results['tier2_elite']:>4}")
    print(f"  Valuations:         {results.get('valuations_complete', 0):>4}")
    print(f"  BUY Signals:        {results.get('buy_signals', 0):>4}")
    print(f"  WATCH Signals:      {results.get('watch_signals', 0):>4}")
    
    # Health check
    print(f"\n{'='*70}")
    print("SYSTEM HEALTH CHECK")
    print(f"{'='*70}")
    
    universe_size = results["tier1_passed"]
    if 30 <= universe_size <= 50:
        print(f"✅ Universe size: {universe_size} (target: 30-50)")
    elif universe_size > 100:
        print(f"⚠️ Universe too large: {universe_size} (filters may be too loose)")
    elif universe_size < 20:
        print(f"⚠️ Universe too small: {universe_size} (filters may be too strict)")
    else:
        print(f"📊 Universe size: {universe_size}")
    
    elite_count = results["tier2_exceptional"] + results["tier2_elite"]
    if 15 <= elite_count <= 25:
        print(f"✅ ELITE+ count: {elite_count} (target: 15-25)")
    elif elite_count > 40:
        print(f"⚠️ ELITE+ too many: {elite_count} (scoring may be too lenient)")
    else:
        print(f"📊 ELITE+ count: {elite_count}")
    
    buy_count = results.get("buy_signals", 0)
    if buy_count <= 2:
        print(f"✅ BUY signals: {buy_count} (target: 0-2 per month)")
    elif buy_count > 5:
        print(f"⚠️ Too many BUY signals: {buy_count} (standards may be too low)")
    else:
        print(f"📊 BUY signals: {buy_count}")
    
    return results


def create_dashboard_json(valued_df: pd.DataFrame, summary: dict) -> dict:
    """Create JSON structure for interactive dashboard."""
    
    dashboard = {
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "companies": [],
    }
    
    if len(valued_df) == 0:
        return dashboard
    
    # Only include companies with complete valuations
    if "valuation_status" in valued_df.columns:
        complete = valued_df[valued_df["valuation_status"] == "complete"].copy()
    else:
        complete = valued_df.copy()
    
    for _, row in complete.iterrows():
        company = {
            "ticker": row.get("ticker", ""),
            "name": row.get("company_name", ""),
            "sector": row.get("sector", ""),
            "tier_label": row.get("tier_label", ""),
            "total_score": int(row.get("total_score", 0)) if pd.notna(row.get("total_score")) else 0,
            "metrics": {
                "incremental_roic": _safe_float(row.get("incremental_roic")),
                "roic_current": _safe_float(row.get("roic_current")),
                "revenue_growth_3y": _safe_float(row.get("revenue_growth_3y")),
                "fcf_conversion": _safe_float(row.get("fcf_conversion")),
                "gross_margin": _safe_float(row.get("gross_margin")),
                "gross_margin_trend": row.get("gross_margin_trend", "unknown"),
                "net_debt_ebitda": _safe_float(row.get("net_debt_ebitda")),
            },
            "valuation": {
                "current_price": _safe_float(row.get("current_price")),
                "intrinsic_value": _safe_float(row.get("intrinsic_value")),
                "implied_irr": _safe_float(row.get("implied_irr")),
                "margin_of_safety": _safe_float(row.get("margin_of_safety")),
                "buy_15_price": _safe_float(row.get("buy_15_price")),
                "buy_12_price": _safe_float(row.get("buy_12_price")),
                "buy_10_price": _safe_float(row.get("buy_10_price")),
                "action_signal": row.get("action_signal", "HOLD"),
            },
            "scores": {
                "incremental_roic": int(row.get("score_incremental_roic", 0)) if pd.notna(row.get("score_incremental_roic")) else 0,
                "reinvestment_runway": int(row.get("score_reinvestment_runway", 0)) if pd.notna(row.get("score_reinvestment_runway")) else 0,
                "revenue_growth": int(row.get("score_revenue_growth", 0)) if pd.notna(row.get("score_revenue_growth")) else 0,
                "fcf_conversion": int(row.get("score_fcf_conversion", 0)) if pd.notna(row.get("score_fcf_conversion")) else 0,
                "gross_margin_trend": int(row.get("score_gross_margin_trend", 0)) if pd.notna(row.get("score_gross_margin_trend")) else 0,
                "capex_efficiency": int(row.get("score_capex_efficiency", 0)) if pd.notna(row.get("score_capex_efficiency")) else 0,
            },
        }
        dashboard["companies"].append(company)
    
    # Sort by implied IRR
    dashboard["companies"].sort(key=lambda x: x["valuation"]["implied_irr"] or 0, reverse=True)
    
    return dashboard


def _safe_float(val):
    """Convert value to float, handling None/NaN."""
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    try:
        return round(float(val), 4)
    except (ValueError, TypeError):
        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Capital Compounder Investment Screening System"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        help="CSV file with ticker universe (must have Ticker column)"
    )
    parser.add_argument(
        "--tickers", "-t",
        nargs="+",
        help="Specific tickers to screen (space-separated)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./output",
        help="Output directory (default: ./output)"
    )
    
    args = parser.parse_args()
    
    # Determine ticker source
    if args.tickers:
        tickers = args.tickers
    elif args.input:
        tickers = load_universe(args.input)
    else:
        # Default: use the master universe
        default_file = "/mnt/user-data/uploads/capital_compounders_master.csv"
        if Path(default_file).exists():
            tickers = load_universe(default_file)
        else:
            print("Error: No ticker source specified. Use --input or --tickers")
            return
    
    # Run pipeline
    results = run_full_pipeline(tickers, args.output)
    
    # Save results summary
    summary_file = Path(args.output) / "pipeline_summary.json"
    with open(summary_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n📊 Summary saved: {summary_file}")


if __name__ == "__main__":
    main()
