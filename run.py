#!/usr/bin/env python3
"""
Capital Compounder Investment System - Quick Run Script

This script runs the complete three-tier screening system.

USAGE:
    # With live FMP API data (requires internet access to financialmodelingprep.com):
    python run.py --live --input your_universe.csv

    # With sample data (for testing/demonstration):
    python run.py --sample

    # With specific tickers:
    python run.py --live --tickers NVDA MSFT AAPL GOOGL META

REQUIREMENTS:
    pip install pandas numpy requests

API KEY:
    Set your FMP API key in config.py or pass via --api-key argument.

Owner: Rob (clarkrobertnye@gmail.com)
Based on Investment Charter v1.0 (January 26, 2026)
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime


def run_with_sample_data(output_dir: str = "output"):
    """Run the system with sample data for demonstration."""
    from sample_data import generate_sample_data
    from tier1_filter import run_tier1_filter
    from tier2_scorer import run_tier2_scoring
    from tier3_valuation import run_tier3_valuation
    from dashboard_generator import generate_dashboard
    from main import create_dashboard_json
    import json
    
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "="*70)
    print("CAPITAL COMPOUNDER SYSTEM - SAMPLE DATA MODE")
    print("="*70)
    
    # Generate sample data
    df = generate_sample_data(f'{output_dir}/universe_data.csv')
    
    # Run pipeline
    passed, failed = run_tier1_filter(
        f'{output_dir}/universe_data.csv',
        f'{output_dir}/universe_tier1_passed.csv',
        f'{output_dir}/universe_tier1_failed.csv'
    )
    
    if len(passed) == 0:
        print("\n⚠️ No companies passed Tier 1 filters!")
        return
    
    scored = run_tier2_scoring(
        f'{output_dir}/universe_tier1_passed.csv',
        f'{output_dir}/universe_tier2_scored.csv'
    )
    
    elite_count = len(scored[scored['tier_label'].isin(['EXCEPTIONAL', 'ELITE'])])
    if elite_count == 0:
        print("\n⚠️ No ELITE+ companies found!")
        return
    
    valued = run_tier3_valuation(
        f'{output_dir}/universe_tier2_scored.csv',
        f'{output_dir}/top20_buylist.csv'
    )
    
    # Generate dashboard
    summary = {
        'input_universe': len(df),
        'tier1_passed': len(passed),
        'tier2_exceptional': len(scored[scored['tier_label'] == 'EXCEPTIONAL']),
        'tier2_elite': len(scored[scored['tier_label'] == 'ELITE']),
        'buy_signals': len(valued[valued.get('action_signal', '') == 'BUY']) if 'action_signal' in valued.columns else 0,
        'watch_signals': len(valued[valued.get('action_signal', '') == 'WATCH']) if 'action_signal' in valued.columns else 0,
    }
    
    dashboard_data = create_dashboard_json(valued, summary)
    with open(f'{output_dir}/watchlist_dashboard.json', 'w') as f:
        json.dump(dashboard_data, f, indent=2)
    
    generate_dashboard(f'{output_dir}/watchlist_dashboard.json', 
                       f'{output_dir}/capital_compounders_dashboard.html')
    
    print("\n" + "="*70)
    print("COMPLETE! Output files in:", output_dir)
    print("="*70)
    print(f"\nOpen the dashboard: file://{os.path.abspath(output_dir)}/capital_compounders_dashboard.html")


def run_with_live_data(tickers: list = None, input_file: str = None, 
                       output_dir: str = "output", api_key: str = None):
    """Run the system with live FMP API data."""
    from fmp_data import fetch_universe_data
    from tier1_filter import run_tier1_filter
    from tier2_scorer import run_tier2_scoring
    from tier3_valuation import run_tier3_valuation
    from dashboard_generator import generate_dashboard
    from main import create_dashboard_json, load_universe
    import json
    
    # Update API key if provided
    if api_key:
        import config
        config.FMP_API_KEY = api_key
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Get tickers
    if tickers:
        ticker_list = tickers
    elif input_file:
        ticker_list = load_universe(input_file)
    else:
        print("Error: Must provide either --tickers or --input")
        return
    
    print("\n" + "="*70)
    print("CAPITAL COMPOUNDER SYSTEM - LIVE DATA MODE")
    print("="*70)
    print(f"Processing {len(ticker_list)} tickers...")
    
    # Fetch data
    df = fetch_universe_data(ticker_list, f'{output_dir}/universe_data.csv')
    
    complete_count = len(df[df['data_quality'] == 'complete'])
    if complete_count == 0:
        print("\n❌ No data retrieved! Check API key and internet connection.")
        return
    
    print(f"✅ Data retrieved for {complete_count}/{len(ticker_list)} tickers")
    
    # Run pipeline
    passed, failed = run_tier1_filter(
        f'{output_dir}/universe_data.csv',
        f'{output_dir}/universe_tier1_passed.csv',
        f'{output_dir}/universe_tier1_failed.csv'
    )
    
    if len(passed) == 0:
        print("\n⚠️ No companies passed Tier 1 filters!")
        print("Check failed companies in:", f'{output_dir}/universe_tier1_failed.csv')
        return
    
    scored = run_tier2_scoring(
        f'{output_dir}/universe_tier1_passed.csv',
        f'{output_dir}/universe_tier2_scored.csv'
    )
    
    elite_count = len(scored[scored['tier_label'].isin(['EXCEPTIONAL', 'ELITE'])])
    if elite_count == 0:
        print("\n⚠️ No ELITE+ companies found!")
        return
    
    valued = run_tier3_valuation(
        f'{output_dir}/universe_tier2_scored.csv',
        f'{output_dir}/top20_buylist.csv'
    )
    
    # Generate dashboard
    summary = {
        'input_universe': len(ticker_list),
        'data_complete': complete_count,
        'tier1_passed': len(passed),
        'tier2_exceptional': len(scored[scored['tier_label'] == 'EXCEPTIONAL']),
        'tier2_elite': len(scored[scored['tier_label'] == 'ELITE']),
        'buy_signals': len(valued[valued.get('action_signal', '') == 'BUY']) if 'action_signal' in valued.columns else 0,
        'watch_signals': len(valued[valued.get('action_signal', '') == 'WATCH']) if 'action_signal' in valued.columns else 0,
    }
    
    dashboard_data = create_dashboard_json(valued, summary)
    with open(f'{output_dir}/watchlist_dashboard.json', 'w') as f:
        json.dump(dashboard_data, f, indent=2)
    
    generate_dashboard(f'{output_dir}/watchlist_dashboard.json', 
                       f'{output_dir}/capital_compounders_dashboard.html')
    
    print("\n" + "="*70)
    print("COMPLETE! Output files in:", output_dir)
    print("="*70)
    print(f"\nOpen the dashboard: file://{os.path.abspath(output_dir)}/capital_compounders_dashboard.html")


def main():
    parser = argparse.ArgumentParser(
        description="Capital Compounder Investment Screening System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run.py --sample                           # Run with sample data
    python run.py --live --input universe.csv        # Run with CSV file
    python run.py --live --tickers NVDA MSFT AAPL   # Run with specific tickers
        """
    )
    
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--sample', action='store_true',
                           help='Run with sample data (no API needed)')
    mode_group.add_argument('--live', action='store_true',
                           help='Run with live FMP API data')
    
    parser.add_argument('--input', '-i', type=str,
                       help='CSV file with Ticker column')
    parser.add_argument('--tickers', '-t', nargs='+',
                       help='Specific tickers to screen')
    parser.add_argument('--output', '-o', type=str, default='output',
                       help='Output directory (default: output)')
    parser.add_argument('--api-key', type=str,
                       help='FMP API key (overrides config.py)')
    
    args = parser.parse_args()
    
    if args.sample:
        run_with_sample_data(args.output)
    elif args.live:
        if not args.input and not args.tickers:
            print("Error: --live mode requires either --input or --tickers")
            sys.exit(1)
        run_with_live_data(
            tickers=args.tickers,
            input_file=args.input,
            output_dir=args.output,
            api_key=args.api_key
        )


if __name__ == "__main__":
    main()
