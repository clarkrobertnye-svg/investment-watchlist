#!/usr/bin/env python3
"""
Capital Compounder - Top 13 BUY Signals Test Run
================================================
Run this locally to test the model with live FMP data.

Usage:
    python run_top13.py

Requirements:
    pip install pandas requests

The 13 tickers are the BUY signals from our calibrated model.
"""

import os
import sys
import json
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import FMP_API_KEY, calculate_analyst_divergence
from fmp_data import FMPDataFetcher, FinancialDataProcessor
from tier1_filter import Tier1Filter
from tier2_scorer import Tier2Scorer
from tier3_valuation import DCFValuation
from dashboard_generator import generate_dashboard

# The 13 BUY signals from our calibrated model
TOP_13_TICKERS = [
    'ASML',  # Semiconductor equipment - 42.5% IRR
    'NVDA',  # AI chips - 40.1% IRR
    'MELI',  # LatAm e-commerce - 39.8% IRR
    'DDOG',  # Observability SaaS - 34.6% IRR
    'CRWD',  # Cybersecurity - 33.6% IRR
    'FTNT',  # Network security - 26.8% IRR
    'NOW',   # Workflow SaaS - 26.0% IRR
    'META',  # Social/AI - 23.5% IRR
    'PANW',  # Cybersecurity - 21.3% IRR
    'SNPS',  # EDA software - 18.1% IRR
    'MSFT',  # Cloud/AI - 17.9% IRR
    'ADBE',  # Creative software - 17.4% IRR
    'MA',    # Payments - 16.3% IRR
]


def run_top13_analysis():
    """Run full analysis on top 13 tickers with live data."""
    
    print("="*70)
    print("CAPITAL COMPOUNDER - TOP 13 LIVE ANALYSIS")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    
    # Create output directory
    os.makedirs('output', exist_ok=True)
    
    # Step 1: Fetch live data from FMP
    print("\n📊 STEP 1: Fetching live data from FMP API...")
    print("-"*50)
    
    fetcher = FMPDataFetcher(FMP_API_KEY)
    processor = FinancialDataProcessor()
    
    all_data = []
    for i, ticker in enumerate(TOP_13_TICKERS):
        print(f"  [{i+1}/{len(TOP_13_TICKERS)}] {ticker}...", end=" ")
        
        try:
            # Fetch all required data
            profile = fetcher.get_company_profile(ticker)
            financials = fetcher.get_financial_statements(ticker, limit=4)
            ratios = fetcher.get_financial_ratios(ticker)
            metrics = fetcher.get_key_metrics(ticker)
            quote = fetcher.get_stock_quote(ticker)
            
            if profile and financials:
                # Process into our format
                processed = processor.process_company_data(
                    ticker, profile, financials, ratios, metrics, quote
                )
                all_data.append(processed)
                print(f"✓ ${processed.get('price', 0):.2f}")
            else:
                print("⚠️ Missing data")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    if not all_data:
        print("\n❌ No data fetched. Check your API key and connection.")
        return
    
    # Convert to DataFrame
    import pandas as pd
    df = pd.DataFrame(all_data)
    df.to_csv('output/top13_raw_data.csv', index=False)
    print(f"\n✅ Fetched data for {len(df)} companies")
    
    # Step 2: Run Tier 1 Filters (light filtering for this focused run)
    print("\n📋 STEP 2: Quality checks...")
    print("-"*50)
    
    # For this focused run, we skip Tier 1 since these are pre-selected
    # But we'll flag any data quality issues
    for _, row in df.iterrows():
        issues = []
        if row.get('fcf_current', 0) <= 0:
            issues.append("negative FCF")
        if row.get('incremental_roic', 0) < 0.15:
            issues.append(f"low Inc.ROIC ({row.get('incremental_roic', 0)*100:.0f}%)")
        if issues:
            print(f"  ⚠️ {row['ticker']}: {', '.join(issues)}")
    
    # Step 3: Run Tier 2 Scoring
    print("\n🎯 STEP 3: Quality scoring...")
    print("-"*50)
    
    scorer = Tier2Scorer()
    scored_data = []
    
    for _, row in df.iterrows():
        score_result = scorer.score_company(row)
        scored_row = {**row.to_dict(), **score_result}
        scored_data.append(scored_row)
        print(f"  {row['ticker']:<6} Score: {score_result['total_score']:>3} ({score_result['tier_label']})")
    
    scored_df = pd.DataFrame(scored_data)
    scored_df.to_csv('output/top13_scored.csv', index=False)
    
    # Step 4: Run Tier 3 Valuations
    print("\n💰 STEP 4: DCF Valuations...")
    print("-"*50)
    
    valuator = DCFValuation()
    valued_data = []
    
    print(f"\n{'Ticker':<6} {'Price':>8} {'IV':>8} {'IRR':>7} {'MOS':>7} {'Diverg':>8} {'Action':>8}")
    print("-"*70)
    
    for _, row in scored_df.iterrows():
        result = valuator.value_company(row)
        
        if result.get('valuation_status') == 'complete':
            valued_row = {**row.to_dict(), **result}
            valued_data.append(valued_row)
            
            # Get divergence flag
            div_flag = result.get('analyst_divergence_flag', 'N/A')
            div_pct = result.get('analyst_divergence_pct', 0) or 0
            flag_symbol = {'ALIGNED': '✅', 'MODERATE': '🔶', 'HIGH': '🔶', 'MAJOR': '⚠️'}.get(div_flag, '—')
            
            print(f"{row['ticker']:<6} ${result['current_price']:>6.0f} ${result['intrinsic_value']:>6.0f} "
                  f"{result['implied_irr']:>5.1f}% {result['margin_of_safety']:>5.1f}% "
                  f"{div_pct:>+6.0f}%{flag_symbol} {result['action_signal']:>8}")
        else:
            print(f"{row['ticker']:<6} ❌ Error: {result.get('error', 'unknown')}")
    
    valued_df = pd.DataFrame(valued_data)
    valued_df.to_csv('output/top13_valuations.csv', index=False)
    
    # Step 5: Generate Dashboard
    print("\n📈 STEP 5: Generating dashboard...")
    print("-"*50)
    
    # Create summary
    summary = {
        'input_universe': len(TOP_13_TICKERS),
        'tier1_passed': len(df),
        'tier2_exceptional': len(scored_df[scored_df['tier_label'] == 'EXCEPTIONAL']),
        'tier2_elite': len(scored_df[scored_df['tier_label'] == 'ELITE']),
        'buy_signals': len(valued_df[valued_df['action_signal'] == 'BUY']),
        'watch_signals': len(valued_df[valued_df['action_signal'] == 'WATCH']),
    }
    
    # Create dashboard JSON
    dashboard_data = {
        'generated_at': datetime.now().isoformat(),
        'summary': summary,
        'companies': valued_df.to_dict('records'),
    }
    
    with open('output/top13_dashboard.json', 'w') as f:
        json.dump(dashboard_data, f, indent=2)
    
    generate_dashboard('output/top13_dashboard.json', 'output/top13_dashboard.html')
    
    # Final Summary
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    
    buy_signals = valued_df[valued_df['action_signal'] == 'BUY'].sort_values('implied_irr', ascending=False)
    watch_signals = valued_df[valued_df['action_signal'] == 'WATCH']
    
    print(f"\n🎯 BUY SIGNALS: {len(buy_signals)}")
    for _, row in buy_signals.iterrows():
        print(f"   {row['ticker']:<6} IRR: {row['implied_irr']:>5.1f}%  MOS: {row['margin_of_safety']:>5.1f}%  "
              f"Buy@15%: ${row['buy_15_price']:.0f}")
    
    print(f"\n👀 WATCH SIGNALS: {len(watch_signals)}")
    for _, row in watch_signals.iterrows():
        print(f"   {row['ticker']:<6} IRR: {row['implied_irr']:>5.1f}%  MOS: {row['margin_of_safety']:>5.1f}%")
    
    print(f"\n✅ Dashboard saved: output/top13_dashboard.html")
    print(f"✅ Data saved: output/top13_valuations.csv")
    print("="*70)


if __name__ == "__main__":
    run_top13_analysis()
