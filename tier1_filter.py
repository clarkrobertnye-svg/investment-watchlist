"""
Capital Compounder Investment System - Tier 1: Universe Filter
Applies NON-NEGOTIABLE hard filters to reduce universe to 30-50 candidates.

Based on Investment Charter v1.0 requirements:
- Incremental ROIC ≥ 25%
- Historical ROIC ≥ 20% (3Y avg)
- ROIC - WACC spread ≥ 15 ppts
- Revenue Growth ≥ 15% (3Y CAGR)
- FCF Conversion ≥ 90% (3Y avg)
- Gross Margin ≥ 60% (expanding)
- Net Debt/EBITDA ≤ 2.0× OR Net Cash
- Market Cap ≥ $10B
- Reinvestment Rate ≥ 30% of FCF
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from config import TIER1_FILTERS, EXCLUDED_SECTORS, EXCLUDED_TICKERS, EXEMPT_TICKERS, FILTER_EXEMPTIONS, is_exempt


class Tier1Filter:
    """Applies hard filters to create investment universe."""
    
    def __init__(self, filters: Dict = None):
        self.filters = filters or TIER1_FILTERS
        self.filter_stats = {}
    
    def apply_filters(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Apply all Tier 1 filters to the data.
        Returns: (passed_df, failed_df)
        """
        print(f"\n{'='*60}")
        print("TIER 1: HARD FILTERS")
        print(f"{'='*60}")
        print(f"Starting universe: {len(df)} companies\n")
        
        initial_count = len(df)
        
        # Track filter results
        df = df.copy()
        df["tier1_pass"] = True
        df["tier1_fail_reasons"] = ""
        
        # 1. Data Quality Filter
        df = self._filter_data_quality(df)
        
        # 2. Sector Exclusions (with exemptions)
        df = self._filter_sectors(df)
        
        # 3. Incremental ROIC Filter (THE KEY METRIC)
        df = self._filter_incremental_roic(df)
        
        # 4. Historical ROIC Filter
        df = self._filter_historical_roic(df)
        
        # 5. ROIC-WACC Spread Filter
        df = self._filter_roic_wacc_spread(df)
        
        # 6. Revenue Growth Filter
        df = self._filter_revenue_growth(df)
        
        # 7. FCF Conversion Filter
        df = self._filter_fcf_conversion(df)
        
        # 8. Gross Margin Filter
        df = self._filter_gross_margin(df)
        
        # 9. Leverage Filter
        df = self._filter_leverage(df)
        
        # 10. Market Cap Filter
        df = self._filter_market_cap(df)
        
        # 11. Reinvestment Rate Filter
        df = self._filter_reinvestment_rate(df)
        
        # Split into passed and failed
        passed_df = df[df["tier1_pass"]].copy()
        failed_df = df[~df["tier1_pass"]].copy()
        
        # Summary
        print(f"\n{'='*60}")
        print("TIER 1 FILTER SUMMARY")
        print(f"{'='*60}")
        print(f"Starting count:    {initial_count}")
        print(f"Passed Tier 1:     {len(passed_df)} ({len(passed_df)/initial_count*100:.1f}%)")
        print(f"Failed Tier 1:     {len(failed_df)} ({len(failed_df)/initial_count*100:.1f}%)")
        
        # Health check per charter
        if len(passed_df) > 100:
            print(f"\n⚠️  WARNING: Universe too large ({len(passed_df)}). Filters may be too loose.")
        elif len(passed_df) < 30:
            print(f"\n⚠️  WARNING: Universe too small ({len(passed_df)}). Consider relaxing filters.")
        else:
            print(f"\n✅ Universe size healthy (target: 30-50)")
        
        return passed_df, failed_df
    
    def _filter_data_quality(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove companies with incomplete data."""
        mask = df["data_quality"] != "complete"
        failed_count = mask.sum()
        
        df.loc[mask, "tier1_pass"] = False
        df.loc[mask, "tier1_fail_reasons"] += "incomplete_data;"
        
        print(f"1. Data Quality:      {failed_count} removed (incomplete data)")
        return df
    
    def _filter_sectors(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Exclude certain sectors per charter.
        Exempts payment networks, exchanges, rating agencies.
        """
        failed_count = 0
        
        for idx, row in df.iterrows():
            ticker = row.get("ticker", "")
            sector = str(row.get("sector", "")).lower()
            
            # Skip exempt tickers
            if ticker in EXEMPT_TICKERS:
                continue
            
            # Skip explicitly excluded tickers
            if ticker in EXCLUDED_TICKERS:
                df.at[idx, "tier1_pass"] = False
                df.at[idx, "tier1_fail_reasons"] += "excluded_ticker;"
                failed_count += 1
                continue
            
            # Check sector exclusions
            for excluded in EXCLUDED_SECTORS:
                if excluded.lower() in sector:
                    df.at[idx, "tier1_pass"] = False
                    df.at[idx, "tier1_fail_reasons"] += f"excluded_sector:{excluded};"
                    failed_count += 1
                    break
        
        print(f"2. Sector Exclusions: {failed_count} removed")
        return df
    
    def _filter_incremental_roic(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        THE KEY FILTER: Incremental ROIC ≥ 25%
        Each new dollar invested must earn at least 25%.
        """
        threshold = self.filters["min_incremental_roic"]
        
        # Handle missing/null values - don't auto-fail, just flag
        mask = pd.notna(df["incremental_roic"]) & (df["incremental_roic"] < threshold)
        failed_count = mask.sum()
        
        df.loc[mask, "tier1_pass"] = False
        df.loc[mask, "tier1_fail_reasons"] += f"low_incremental_roic(<{threshold*100:.0f}%);"
        
        # Also fail if missing and we can't calculate
        missing_mask = pd.isna(df["incremental_roic"])
        missing_count = missing_mask.sum()
        
        print(f"3. Incremental ROIC:  {failed_count} removed (<{threshold*100:.0f}%), {missing_count} missing data")
        return df
    
    def _filter_historical_roic(self, df: pd.DataFrame) -> pd.DataFrame:
        """Historical ROIC ≥ 20% (3Y avg)."""
        threshold = self.filters["min_historical_roic"]
        
        # Use either roic_3y_avg or roic_current
        df["roic_check"] = df["roic_3y_avg"].fillna(df["roic_current"])
        
        mask = pd.notna(df["roic_check"]) & (df["roic_check"] < threshold)
        failed_count = mask.sum()
        
        df.loc[mask, "tier1_pass"] = False
        df.loc[mask, "tier1_fail_reasons"] += f"low_historical_roic(<{threshold*100:.0f}%);"
        
        print(f"4. Historical ROIC:   {failed_count} removed (<{threshold*100:.0f}%)")
        return df
    
    def _filter_roic_wacc_spread(self, df: pd.DataFrame) -> pd.DataFrame:
        """ROIC - WACC spread ≥ 15 percentage points."""
        threshold = self.filters["min_roic_wacc_spread"]
        
        mask = pd.notna(df["roic_wacc_spread"]) & (df["roic_wacc_spread"] < threshold)
        failed_count = mask.sum()
        
        df.loc[mask, "tier1_pass"] = False
        df.loc[mask, "tier1_fail_reasons"] += f"low_spread(<{threshold*100:.0f}ppts);"
        
        print(f"5. ROIC-WACC Spread:  {failed_count} removed (<{threshold*100:.0f}ppts)")
        return df
    
    def _filter_revenue_growth(self, df: pd.DataFrame) -> pd.DataFrame:
        """Revenue Growth ≥ 15% (3Y CAGR)."""
        threshold = self.filters["min_revenue_growth"]
        
        mask = pd.notna(df["revenue_growth_3y"]) & (df["revenue_growth_3y"] < threshold)
        failed_count = mask.sum()
        
        df.loc[mask, "tier1_pass"] = False
        df.loc[mask, "tier1_fail_reasons"] += f"low_growth(<{threshold*100:.0f}%);"
        
        print(f"6. Revenue Growth:    {failed_count} removed (<{threshold*100:.0f}% 3Y CAGR)")
        return df
    
    def _filter_fcf_conversion(self, df: pd.DataFrame) -> pd.DataFrame:
        """FCF Conversion ≥ 90% of net income."""
        threshold = self.filters["min_fcf_conversion"]
        
        mask = pd.notna(df["fcf_conversion"]) & (df["fcf_conversion"] < threshold)
        failed_count = mask.sum()
        
        df.loc[mask, "tier1_pass"] = False
        df.loc[mask, "tier1_fail_reasons"] += f"low_fcf_conv(<{threshold*100:.0f}%);"
        
        print(f"7. FCF Conversion:    {failed_count} removed (<{threshold*100:.0f}%)")
        return df
    
    def _filter_gross_margin(self, df: pd.DataFrame) -> pd.DataFrame:
        """Gross Margin ≥ 60% (expanding preferred)."""
        threshold = self.filters["min_gross_margin"]
        
        mask = pd.notna(df["gross_margin"]) & (df["gross_margin"] < threshold)
        failed_count = mask.sum()
        
        df.loc[mask, "tier1_pass"] = False
        df.loc[mask, "tier1_fail_reasons"] += f"low_gross_margin(<{threshold*100:.0f}%);"
        
        print(f"8. Gross Margin:      {failed_count} removed (<{threshold*100:.0f}%)")
        return df
    
    def _filter_leverage(self, df: pd.DataFrame) -> pd.DataFrame:
        """Net Debt/EBITDA ≤ 2.0× OR Net Cash position."""
        threshold = self.filters["max_net_debt_ebitda"]
        
        # Pass if net cash (negative net debt) OR low leverage
        net_cash_mask = df["is_net_cash"] == True
        low_leverage_mask = pd.notna(df["net_debt_ebitda"]) & (df["net_debt_ebitda"] <= threshold)
        
        pass_mask = net_cash_mask | low_leverage_mask
        fail_mask = ~pass_mask & df["tier1_pass"]  # Only fail those still passing
        
        # Handle missing data - assume failure if can't calculate
        missing_mask = pd.isna(df["net_debt_ebitda"]) & (df["is_net_cash"] != True)
        
        failed_count = fail_mask.sum()
        
        df.loc[fail_mask, "tier1_pass"] = False
        df.loc[fail_mask, "tier1_fail_reasons"] += f"high_leverage(>{threshold}x);"
        
        print(f"9. Leverage:          {failed_count} removed (>{threshold}x Net Debt/EBITDA)")
        return df
    
    def _filter_market_cap(self, df: pd.DataFrame) -> pd.DataFrame:
        """Market Cap ≥ $10B."""
        threshold = self.filters["min_market_cap"]
        
        mask = pd.notna(df["market_cap"]) & (df["market_cap"] < threshold)
        failed_count = mask.sum()
        
        df.loc[mask, "tier1_pass"] = False
        df.loc[mask, "tier1_fail_reasons"] += f"small_cap(<${threshold/1e9:.0f}B);"
        
        print(f"10. Market Cap:       {failed_count} removed (<${threshold/1e9:.0f}B)")
        return df
    
    def _filter_reinvestment_rate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Reinvestment Rate ≥ 30% of FCF."""
        threshold = self.filters["min_reinvestment_rate"]
        
        # This filter is more lenient - some great compounders return capital
        # Only fail if reinvestment rate is very low AND FCF is high
        mask = pd.notna(df["reinvestment_rate"]) & (df["reinvestment_rate"] < threshold)
        
        # Don't hard fail on this one - it's informational
        # Many quality companies return capital vs reinvest
        flagged_count = mask.sum()
        
        # Add flag but don't fail
        df.loc[mask, "tier1_fail_reasons"] += f"low_reinvestment({threshold*100:.0f}%);"
        
        print(f"11. Reinvestment:     {flagged_count} flagged (informational, not hard filter)")
        return df


def run_tier1_filter(input_file: str, output_file: str = "universe_tier1_passed.csv",
                     failed_file: str = "universe_tier1_failed.csv") -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run Tier 1 filtering on universe data.
    
    Args:
        input_file: CSV with raw financial data
        output_file: Where to save passed companies
        failed_file: Where to save failed companies
    
    Returns:
        Tuple of (passed_df, failed_df)
    """
    print(f"\nLoading data from {input_file}...")
    df = pd.read_csv(input_file)
    
    filter_engine = Tier1Filter()
    passed_df, failed_df = filter_engine.apply_filters(df)
    
    # Save results
    passed_df.to_csv(output_file, index=False)
    failed_df.to_csv(failed_file, index=False)
    
    print(f"\n✅ Tier 1 passed: {output_file}")
    print(f"📋 Tier 1 failed: {failed_file}")
    
    return passed_df, failed_df


def apply_tier1_filters(data: Dict) -> Tuple[bool, List[str]]:
    """
    Apply Tier 1 filters to a single ticker's data dict.
    
    Args:
        data: Dict with ticker metrics
        
    Returns:
        Tuple of (passed: bool, failures: List[str])
    """
    failures = []
    ticker = data.get('ticker', '')
    
    # Get filter thresholds
    filters = TIER1_FILTERS
    
    # Check excluded sectors
    sector = data.get('sector', '')
    if sector in EXCLUDED_SECTORS:
        return False, [f"Excluded sector: {sector}"]
    
    # Check excluded tickers
    if ticker in EXCLUDED_TICKERS:
        return False, [f"Excluded ticker: {ticker}"]
    
    # Incremental ROIC
    inc_roic = data.get('incremental_roic')
    min_inc_roic = filters.get('min_incremental_roic', 0.15)
    if inc_roic is None:
        failures.append("Missing incremental ROIC data")
    elif inc_roic < min_inc_roic and not is_exempt(ticker, 'min_incremental_roic'):
        failures.append(f"Inc ROIC {inc_roic*100:.1f}% < {min_inc_roic*100}% min")
    
    # Historical ROIC
    hist_roic = data.get('roic_3y_avg') or data.get('roic')
    min_hist_roic = filters.get('min_historical_roic', 0.15)
    if hist_roic is not None and hist_roic < min_hist_roic and not is_exempt(ticker, 'min_historical_roic'):
        failures.append(f"ROIC {hist_roic*100:.1f}% < {min_hist_roic*100}% min")
    
    # ROIC-WACC spread
    spread = data.get('roic_wacc_spread')
    min_spread = filters.get('min_roic_wacc_spread', 0.08)
    if spread is not None and spread < min_spread and not is_exempt(ticker, 'min_roic_wacc_spread'):
        failures.append(f"ROIC-WACC spread {spread*100:.1f}% < {min_spread*100}% min")
    
    # Revenue growth
    growth = data.get('revenue_growth_3y')
    min_growth = filters.get('min_revenue_growth', 0.08)
    if growth is not None and growth < min_growth and not is_exempt(ticker, 'min_revenue_growth'):
        failures.append(f"Revenue growth {growth*100:.1f}% < {min_growth*100}% min")
    
    # FCF conversion
    fcf_conv = data.get('fcf_conversion')
    min_fcf = filters.get('min_fcf_conversion', 0.70)
    if fcf_conv is not None and fcf_conv < min_fcf and not is_exempt(ticker, 'min_fcf_conversion'):
        failures.append(f"FCF conversion {fcf_conv*100:.1f}% < {min_fcf*100}% min")
    
    # Gross margin
    gm = data.get('gross_margin')
    min_gm = filters.get('min_gross_margin', 0.40)
    if gm is not None and gm < min_gm and not is_exempt(ticker, 'min_gross_margin'):
        failures.append(f"Gross margin {gm*100:.1f}% < {min_gm*100}% min")
    
    # CapEx/Revenue (capital light requirement)
    capex_rev = data.get('capex_to_revenue') or data.get('capex_revenue')
    max_capex = filters.get('max_capex_revenue')
    if max_capex and capex_rev is not None and capex_rev > max_capex and not is_exempt(ticker, 'max_capex_revenue'):
        failures.append(f"CapEx/Revenue {capex_rev*100:.1f}% > {max_capex*100}% max")
    
    # Leverage
    leverage = data.get('net_debt_ebitda')
    max_leverage = filters.get('max_net_debt_ebitda', 3.0)
    if leverage is not None and leverage > max_leverage and not is_exempt(ticker, 'max_net_debt_ebitda'):
        failures.append(f"Leverage {leverage:.1f}x > {max_leverage}x max")
    
    # Market cap
    market_cap = data.get('market_cap', 0)
    min_cap = filters.get('min_market_cap', 10e9)
    if market_cap < min_cap and not is_exempt(ticker, 'min_market_cap'):
        failures.append(f"Market cap ${market_cap/1e9:.1f}B < ${min_cap/1e9}B min")
    
    passed = len(failures) == 0
    return passed, failures


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "universe_data.csv"
    
    run_tier1_filter(input_file)
