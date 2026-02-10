"""
Capital Compounder Investment System - Stage 1 Universe Screener
Filters initial universe to ~200-400 quality candidates for deep analysis.

STAGE 1 CRITERIA:
- Market Cap ≥ $1B
- Gross Margin ≥ 20%
- ROIC (ex-cash) ≥ 15%

OUTPUT: List of tickers to feed into fmp_data.py for full analysis

USAGE:
    python stage1_screener.py                    # Run screen, output to stage1_candidates.json
    python stage1_screener.py --preview          # Preview without saving
    python stage1_screener.py --min-mcap 5000    # $5B minimum market cap
"""

import requests
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# You'll need to create config.py with: FMP_API_KEY = "your_key_here"
try:
    from config import FMP_API_KEY
except ImportError:
    FMP_API_KEY = None
    print("⚠️  No config.py found. Set FMP_API_KEY environment variable or create config.py")


class Stage1Screener:
    """
    Stage 1: Universe Filter
    Quickly filters global equity universe to quality candidates.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or FMP_API_KEY
        if not self.api_key:
            raise ValueError("FMP API key required. Set in config.py or pass to constructor.")
        
        self.base_url = "https://financialmodelingprep.com/stable"
        self.stable_url = "https://financialmodelingprep.com/stable"
        self.request_delay = 0.2  # 300 calls/min = 5/sec, use 0.2s to be safe
        
        # Stage 1 thresholds
        self.MIN_MARKET_CAP = 1_000_000_000  # $1B
        self.MIN_GROSS_MARGIN = 0.20         # 20%
        self.MIN_ROIC = 0.15                 # 15%
        
        # Tracking
        self.api_calls = 0
        self.start_time = None
        
    def _make_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Make API request with rate limiting."""
        if params is None:
            params = {}
        params["apikey"] = self.api_key
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            self.api_calls += 1
            time.sleep(self.request_delay)
            return response.json()
        except Exception as e:
            print(f"  ⚠️ API error: {e}")
            return None
    
    def get_screener_results(self, min_mcap: int = None, min_gm: float = None) -> List[Dict]:
        """
        Use FMP stock screener to get initial universe.
        This is the most efficient way - single API call for bulk filtering.
        """
        min_mcap = min_mcap or self.MIN_MARKET_CAP
        min_gm = min_gm or self.MIN_GROSS_MARGIN
        
        print(f"📡 Calling FMP Stock Screener...")
        print(f"   Filters: Market Cap ≥ ${min_mcap/1e9:.1f}B, Gross Margin ≥ {min_gm*100:.0f}%")
        
        # FMP screener endpoint with filters
        url = f"{self.base_url}/stock-screener"
        params = {
            "marketCapMoreThan": min_mcap,
            "grossProfitMarginMoreThan": min_gm,
            "isEtf": "false",
            "isFund": "false",
            "isActivelyTrading": "true",
            "limit": 5000,  # Get all matches
        }
        
        results = self._make_request(url, params)
        
        if not results:
            print("   ❌ Screener returned no results")
            return []
        
        print(f"   ✓ Found {len(results)} companies passing market cap + gross margin filters")
        return results
    
    def calculate_roic_ex_cash(self, ticker: str) -> Tuple[Optional[float], Dict]:
        """
        Calculate ROIC excluding excess cash for a single ticker.
        
        ROIC ex-cash = NOPAT / (Invested Capital - Excess Cash)
        
        Where:
        - NOPAT = Operating Income × (1 - Tax Rate)
        - Invested Capital = Total Assets - Current Liabilities (non-interest bearing)
        - Excess Cash = Cash - (6 months operating expenses)
        """
        details = {"ticker": ticker}
        
        # Get income statement
        income_url = f"{self.stable_url}/income-statement"
        income = self._make_request(income_url, {"symbol": ticker, "period": "annual", "limit": 1})
        
        if not income or len(income) == 0:
            return None, details
        
        inc = income[0]
        
        # Get balance sheet
        balance_url = f"{self.stable_url}/balance-sheet-statement"
        balance = self._make_request(balance_url, {"symbol": ticker, "period": "annual", "limit": 1})
        
        if not balance or len(balance) == 0:
            return None, details
        
        bal = balance[0]
        
        # Calculate NOPAT
        operating_income = inc.get("operatingIncome", 0) or 0
        revenue = inc.get("revenue", 0) or 0
        
        # Estimate effective tax rate (use 21% if not calculable)
        income_tax = inc.get("incomeTaxExpense", 0) or 0
        pretax_income = inc.get("incomeBeforeTax", 0) or 0
        
        if pretax_income > 0:
            tax_rate = min(income_tax / pretax_income, 0.35)  # Cap at 35%
        else:
            tax_rate = 0.21
        
        nopat = operating_income * (1 - tax_rate)
        details["nopat"] = nopat
        details["operating_income"] = operating_income
        details["tax_rate"] = tax_rate
        
        # Calculate Invested Capital
        total_assets = bal.get("totalAssets", 0) or 0
        current_liabilities = bal.get("totalCurrentLiabilities", 0) or 0
        cash = bal.get("cashAndCashEquivalents", 0) or 0
        short_term_investments = bal.get("shortTermInvestments", 0) or 0
        
        # Invested Capital = Total Assets - Non-Debt Current Liabilities
        # Simplified: Total Assets - Current Liabilities (assumes most CL is non-debt)
        invested_capital = total_assets - current_liabilities
        details["invested_capital"] = invested_capital
        
        # Calculate Excess Cash
        # Excess Cash = Cash + ST Investments - (6 months of operating expenses)
        # Operating expenses ≈ Revenue - Operating Income (rough proxy)
        operating_expenses = revenue - operating_income if revenue > operating_income else revenue * 0.7
        six_months_opex = operating_expenses / 2
        
        total_cash = cash + short_term_investments
        excess_cash = max(0, total_cash - six_months_opex)
        details["cash_and_st_investments"] = total_cash
        details["excess_cash"] = excess_cash
        
        # Calculate ROIC ex-cash
        adjusted_ic = invested_capital - excess_cash
        details["invested_capital_ex_cash"] = adjusted_ic
        
        if adjusted_ic <= 0:
            return None, details
        
        roic_ex_cash = nopat / adjusted_ic
        details["roic_ex_cash"] = roic_ex_cash
        
        return roic_ex_cash, details
    
    def run_stage1_screen(self, 
                          min_mcap: int = None,
                          min_gm: float = None,
                          min_roic: float = None,
                          max_tickers: int = None,
                          preview: bool = False) -> Dict:
        """
        Run the complete Stage 1 screen.
        
        Args:
            min_mcap: Minimum market cap in dollars (default $1B)
            min_gm: Minimum gross margin as decimal (default 0.20)
            min_roic: Minimum ROIC ex-cash as decimal (default 0.15)
            max_tickers: Maximum tickers to process for ROIC (for testing)
            preview: If True, don't calculate ROIC for each ticker (fast preview)
        
        Returns:
            Dict with screening results and statistics
        """
        self.start_time = datetime.now()
        self.api_calls = 0
        
        min_mcap = min_mcap or self.MIN_MARKET_CAP
        min_gm = min_gm or self.MIN_GROSS_MARGIN
        min_roic = min_roic or self.MIN_ROIC
        
        print("=" * 70)
        print("STAGE 1: UNIVERSE FILTER")
        print("=" * 70)
        print(f"Criteria: MCap ≥ ${min_mcap/1e9:.1f}B | GM ≥ {min_gm*100:.0f}% | ROIC ex-cash ≥ {min_roic*100:.0f}%")
        print()
        
        # Step 1: Get initial universe from screener
        initial_universe = self.get_screener_results(min_mcap, min_gm)
        
        if not initial_universe:
            return {"error": "Screener returned no results", "candidates": []}
        
        # Step 2: Filter by ROIC ex-cash (requires per-ticker API calls)
        if preview:
            print(f"\n🔍 Preview mode - skipping ROIC calculation")
            print(f"   Would process {len(initial_universe)} tickers for ROIC filter")
            print(f"   Estimated API calls: {len(initial_universe) * 2} (income + balance per ticker)")
            print(f"   Estimated time: {len(initial_universe) * 2 * 0.2 / 60:.1f} minutes")
            
            return {
                "preview": True,
                "initial_count": len(initial_universe),
                "tickers_preview": [t.get("symbol") for t in initial_universe[:50]],
                "estimated_api_calls": len(initial_universe) * 2,
                "estimated_minutes": len(initial_universe) * 2 * 0.2 / 60,
            }
        
        print(f"\n🔬 Calculating ROIC ex-cash for {len(initial_universe)} tickers...")
        print(f"   Estimated time: {len(initial_universe) * 2 * 0.2 / 60:.1f} minutes")
        print()
        
        candidates = []
        rejected = []
        errors = []
        
        tickers_to_process = initial_universe
        if max_tickers:
            tickers_to_process = initial_universe[:max_tickers]
            print(f"   (Limited to {max_tickers} tickers for testing)")
        
        for i, stock in enumerate(tickers_to_process):
            ticker = stock.get("symbol", "")
            name = stock.get("companyName", "")[:30]
            mcap = stock.get("marketCap", 0) or 0
            gm = stock.get("grossProfitMargin", 0) or 0
            
            # Progress indicator
            if (i + 1) % 50 == 0 or i == 0:
                elapsed = (datetime.now() - self.start_time).total_seconds() / 60
                print(f"   Processing {i+1}/{len(tickers_to_process)} ({elapsed:.1f} min elapsed)...")
            
            # Calculate ROIC ex-cash
            roic_ex_cash, details = self.calculate_roic_ex_cash(ticker)
            
            if roic_ex_cash is None:
                errors.append({"ticker": ticker, "name": name, "reason": "Could not calculate ROIC"})
                continue
            
            # Check ROIC threshold
            if roic_ex_cash >= min_roic:
                candidates.append({
                    "ticker": ticker,
                    "company_name": name,
                    "market_cap": mcap,
                    "market_cap_b": mcap / 1e9,
                    "gross_margin": gm,
                    "roic_ex_cash": roic_ex_cash,
                    "nopat": details.get("nopat"),
                    "invested_capital_ex_cash": details.get("invested_capital_ex_cash"),
                    "excess_cash": details.get("excess_cash"),
                    "sector": stock.get("sector", ""),
                    "industry": stock.get("industry", ""),
                    "exchange": stock.get("exchangeShortName", ""),
                    "country": stock.get("country", ""),
                })
                print(f"   ✓ {ticker:8} ROIC: {roic_ex_cash*100:5.1f}% | GM: {gm*100:4.0f}% | MCap: ${mcap/1e9:6.1f}B | {name}")
            else:
                rejected.append({
                    "ticker": ticker,
                    "name": name,
                    "roic_ex_cash": roic_ex_cash,
                    "reason": f"ROIC {roic_ex_cash*100:.1f}% < {min_roic*100:.0f}%"
                })
        
        # Calculate statistics
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        results = {
            "screen_date": datetime.now().isoformat(),
            "criteria": {
                "min_market_cap": min_mcap,
                "min_gross_margin": min_gm,
                "min_roic_ex_cash": min_roic,
            },
            "statistics": {
                "initial_universe": len(initial_universe),
                "passed_roic": len(candidates),
                "rejected_roic": len(rejected),
                "errors": len(errors),
                "pass_rate": len(candidates) / len(tickers_to_process) * 100 if tickers_to_process else 0,
                "api_calls": self.api_calls,
                "elapsed_seconds": elapsed,
                "elapsed_minutes": elapsed / 60,
            },
            "candidates": sorted(candidates, key=lambda x: x.get("roic_ex_cash", 0), reverse=True),
            "rejected_sample": rejected[:20],  # First 20 rejected for review
            "errors": errors[:20],
        }
        
        # Summary
        print()
        print("=" * 70)
        print("STAGE 1 COMPLETE")
        print("=" * 70)
        print(f"Initial Universe:    {len(initial_universe):,} companies")
        print(f"Passed ROIC Filter:  {len(candidates):,} candidates ({results['statistics']['pass_rate']:.1f}%)")
        print(f"Rejected:            {len(rejected):,}")
        print(f"Errors:              {len(errors):,}")
        print(f"API Calls:           {self.api_calls:,}")
        print(f"Time Elapsed:        {elapsed/60:.1f} minutes")
        print()
        
        # Top 20 by ROIC
        print("TOP 20 BY ROIC EX-CASH:")
        print("-" * 70)
        for i, c in enumerate(results["candidates"][:20], 1):
            print(f"{i:2}. {c['ticker']:8} ROIC: {c['roic_ex_cash']*100:5.1f}% | GM: {c['gross_margin']*100:4.0f}% | MCap: ${c['market_cap_b']:6.1f}B")
        
        return results
    
    def export_ticker_list(self, results: Dict, output_path: str = "stage1_candidates.json"):
        """Export results to JSON for downstream processing."""
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: {output_path}")
        
        # Also export simple ticker list for easy feeding to fmp_data.py
        ticker_list_path = output_path.replace('.json', '_tickers.txt')
        with open(ticker_list_path, 'w') as f:
            for c in results.get("candidates", []):
                f.write(c["ticker"] + "\n")
        print(f"💾 Ticker list saved to: {ticker_list_path}")
        
        return output_path


def main():
    parser = argparse.ArgumentParser(description='Stage 1 Capital Compounder Screener')
    parser.add_argument('--preview', action='store_true', help='Preview mode - no ROIC calculation')
    parser.add_argument('--min-mcap', type=int, default=1000, help='Minimum market cap in millions (default: 1000 = $1B)')
    parser.add_argument('--min-gm', type=float, default=20, help='Minimum gross margin percent (default: 20)')
    parser.add_argument('--min-roic', type=float, default=15, help='Minimum ROIC ex-cash percent (default: 15)')
    parser.add_argument('--max-tickers', type=int, help='Max tickers to process (for testing)')
    parser.add_argument('--output', type=str, default='stage1_candidates.json', help='Output file path')
    parser.add_argument('--api-key', type=str, help='FMP API key (or set in config.py)')
    
    args = parser.parse_args()
    
    # Convert percentage inputs to decimals
    min_mcap = args.min_mcap * 1_000_000  # millions to dollars
    min_gm = args.min_gm / 100
    min_roic = args.min_roic / 100
    
    # Initialize screener
    api_key = args.api_key or FMP_API_KEY
    if not api_key:
        print("❌ Error: FMP API key required")
        print("   Set in config.py as FMP_API_KEY = 'your_key'")
        print("   Or pass via --api-key argument")
        return
    
    screener = Stage1Screener(api_key=api_key)
    
    # Run screen
    results = screener.run_stage1_screen(
        min_mcap=min_mcap,
        min_gm=min_gm,
        min_roic=min_roic,
        max_tickers=args.max_tickers,
        preview=args.preview,
    )
    
    # Export results (unless preview mode)
    if not args.preview and results.get("candidates"):
        screener.export_ticker_list(results, args.output)
        
        print(f"\n📋 NEXT STEPS:")
        print(f"   1. Review {args.output} for candidate quality")
        print(f"   2. Run: python run_batch.py --input stage1_candidates_tickers.txt")
        print(f"   3. Run: python generate_dashboard_v2.py")


if __name__ == "__main__":
    main()
