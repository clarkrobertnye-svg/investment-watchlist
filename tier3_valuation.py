"""
Capital Compounder Investment System - Tier 3: DCF Valuation & IRR Pricing
Calculates intrinsic value and target entry prices for ELITE+ companies.

DCF Methodology (per Charter v1.0):
- FCFF = NOPAT + D&A - CapEx - ΔNWC
- Growth: Lesser of Revenue CAGR or (Inc ROIC × Reinvestment Rate)
- Cap at 20% for exceptional growers, min 10% for ELITE
- 15-year projection: Years 1-5 at g_val, Years 6-15 fade to 6%
- Terminal: 3% perpetual (GDP ceiling)
- WACC: Risk-free (4%) + Adjusted Beta × ERP (6%)

Output: Three IRR-based entry prices:
- Buy@15%: High conviction (25%+ MOS)
- Buy@12%: Watch zone (fair price)
- Buy@10%: Market return
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from config import DCF_PARAMS, IRR_TARGETS, MOS_REQUIREMENTS


class DCFValuation:
    """Calculates intrinsic value using DCF methodology."""
    
    def __init__(self, params: Dict = None):
        self.params = params or DCF_PARAMS
    
    def value_company(self, row: pd.Series) -> Dict:
        """
        Calculate intrinsic value and IRR-based entry prices for a company.
        
        Returns dict with:
        - intrinsic_value: Per-share fair value
        - current_price: Current market price
        - upside_to_fair: Percentage upside to fair value
        - margin_of_safety: Current discount to fair value
        - buy_15_price: Price for 15% expected IRR
        - buy_12_price: Price for 12% expected IRR
        - buy_10_price: Price for 10% expected IRR
        - implied_irr: IRR at current price
        - action_signal: BUY/WATCH/TRIM/HOLD
        """
        result = {
            "ticker": row.get("ticker", ""),
            "company_name": row.get("company_name", ""),
            "valuation_date": datetime.now().isoformat(),
        }
        
        try:
            # Get required inputs
            fcf = row.get("fcf_current", 0) or 0
            revenue_growth = row.get("revenue_growth_3y", 0) or 0
            incremental_roic = row.get("incremental_roic", 0) or 0
            reinvestment_rate = row.get("reinvestment_rate", 0) or 0
            market_cap = row.get("market_cap", 0) or 0
            price = row.get("price", 0) or 0
            shares = row.get("shares_outstanding", 0) or 0
            beta = row.get("beta", 1.0) or 1.0
            net_debt = row.get("net_debt", 0) or 0
            tier_label = row.get("tier_label", "QUALITY")
            
            # Validate inputs
            if fcf <= 0 or market_cap <= 0 or shares <= 0:
                result["valuation_status"] = "insufficient_data"
                return result
            
            # Calculate WACC
            wacc = self._calculate_wacc(beta)
            
            # Calculate growth rate for valuation
            g_val = self._calculate_growth_rate(revenue_growth, incremental_roic, 
                                                  reinvestment_rate, tier_label)
            
            # Run DCF
            intrinsic_equity_value, dcf_components = self._run_dcf(
                fcf, g_val, wacc, net_debt
            )
            
            intrinsic_value_per_share = intrinsic_equity_value / shares
            
            # Calculate IRR-based entry prices
            buy_15_price = self._calculate_entry_price(
                fcf, g_val, wacc, net_debt, shares, target_irr=0.15
            )
            buy_12_price = self._calculate_entry_price(
                fcf, g_val, wacc, net_debt, shares, target_irr=0.12
            )
            buy_10_price = self._calculate_entry_price(
                fcf, g_val, wacc, net_debt, shares, target_irr=0.10
            )
            
            # Calculate implied IRR at current price
            implied_irr = self._calculate_implied_irr(
                price, intrinsic_value_per_share, g_val
            )
            
            # Calculate margins
            if intrinsic_value_per_share > price and price > 0:
                upside_to_fair = (intrinsic_value_per_share / price) - 1
                margin_of_safety = upside_to_fair  # MOS = how much below fair value
            elif price > 0:
                upside_to_fair = (intrinsic_value_per_share / price) - 1  # Will be negative
                margin_of_safety = 0  # No margin of safety if overvalued
            else:
                upside_to_fair = 0
                margin_of_safety = 0
            
            # Determine action signal
            action = self._determine_action(implied_irr, margin_of_safety, tier_label)
            
            # Check if capital returner adjustment was applied
            is_capital_returner = reinvestment_rate < self.params.get("capital_returner_reinv_threshold", 0.35)
            
            # Calculate analyst divergence (if consensus data available)
            from config import calculate_analyst_divergence
            ticker_symbol = row.get("ticker", "")
            divergence_data = calculate_analyst_divergence(ticker_symbol, intrinsic_value_per_share)
            
            result.update({
                "valuation_status": "complete",
                "wacc": wacc,
                "g_val": g_val,
                "fcf_base": fcf,
                "intrinsic_value": round(intrinsic_value_per_share, 2),
                "current_price": round(price, 2),
                "upside_to_fair": round(upside_to_fair * 100, 1),
                "margin_of_safety": round(margin_of_safety * 100, 1),
                "buy_15_price": round(buy_15_price, 2),
                "buy_12_price": round(buy_12_price, 2),
                "buy_10_price": round(buy_10_price, 2),
                "implied_irr": round(implied_irr * 100, 1),
                "action_signal": action,
                "enterprise_value": round(dcf_components.get("ev", 0) / 1e9, 2),
                "terminal_value_pct": round(dcf_components.get("tv_pct", 0) * 100, 1),
                "is_capital_returner": is_capital_returner,
                "growth_method": "revenue_growth" if is_capital_returner else "sustainable_growth",
                # Analyst divergence fields
                "analyst_divergence_flag": divergence_data.get("flag", "NO_DATA"),
                "analyst_divergence_pct": divergence_data.get("divergence_pct"),
                "analyst_target_avg": divergence_data.get("analyst_avg"),
                "analyst_target_range": divergence_data.get("analyst_range"),
            })
            
        except Exception as e:
            result["valuation_status"] = "error"
            result["error"] = str(e)
        
        return result
    
    def _calculate_wacc(self, beta: float) -> float:
        """
        Calculate WACC using CAPM with beta adjustment.
        Blume adjustment: 0.67 × Raw Beta + 0.33
        """
        rf = self.params["risk_free_rate"]
        erp = self.params["market_risk_premium"]
        
        # Blume beta adjustment (smooths toward 1.0)
        adjusted_beta = 0.67 * beta + 0.33
        
        # Further smooth toward 1.0 (prevents over-penalizing quality growers)
        smoothed_beta = 0.5 * adjusted_beta + 0.5 * 1.0
        
        wacc = rf + smoothed_beta * erp
        return wacc
    
    def _calculate_growth_rate(self, revenue_growth: float, inc_roic: float,
                                reinv_rate: float, tier_label: str) -> float:
        """
        Calculate growth rate for valuation.
        
        Three-part logic:
        1. CAPITAL RETURNERS (reinvestment < 35%): Use revenue growth directly
           - Companies like MSFT, MCO return capital via buybacks
           - Inc.ROIC × Reinv understates their growth potential
        
        2. HIGH REINVESTMENT (reinvestment >= 35%): Use sustainable growth formula
           - g = min(Revenue Growth, Inc.ROIC × Reinvestment)
           - Works well for DDOG, NOW, MA type companies
        
        3. CAP AT 30%: Even NVDA analysts only project 25-30%
           - Prevents unrealistic valuations from astronomical Inc.ROIC
        
        Floor at 8% for quality companies in universe.
        """
        g_floor = self.params.get("g_val_floor", 0.08)
        g_cap = self.params.get("g_val_cap", 0.30)
        capital_returner_threshold = self.params.get("capital_returner_reinv_threshold", 0.35)
        use_revenue_for_capital_returners = self.params.get("capital_returner_use_revenue_growth", True)
        
        # Check if this is a "capital returner" (low reinvestment company)
        is_capital_returner = reinv_rate < capital_returner_threshold
        
        if is_capital_returner and use_revenue_for_capital_returners:
            # For capital returners, use revenue growth directly
            # These companies grow through buybacks + modest reinvestment
            g_val = revenue_growth
        else:
            # For high-reinvestment companies, use sustainable growth formula
            sustainable_growth = inc_roic * reinv_rate if inc_roic > 0 and reinv_rate > 0 else 0
            
            # Use lesser of revenue growth or sustainable growth (conservative)
            if sustainable_growth > 0:
                g_val = min(revenue_growth, sustainable_growth)
            else:
                g_val = revenue_growth
        
        # Apply floor for quality companies
        g_val = max(g_val, g_floor)
        
        # Apply cap - even NVDA analysts only project 25-30%
        if g_cap:
            g_val = min(g_val, g_cap)
        
        return g_val
    
    def _run_dcf(self, fcf: float, g_val: float, wacc: float, 
                  net_debt: float) -> Tuple[float, Dict]:
        """
        Run 15-year DCF with realistic growth fade.
        
        Growth Schedule:
        - Years 1-5: Actual growth rate (g_val) - high growth phase
        - Years 6-15: Linear fade from g_val to mature rate (6%)
        - Terminal: 3% perpetual
        
        Returns (equity_value, components_dict)
        """
        years = self.params["projection_years"]  # 15
        high_growth_years = self.params.get("high_growth_years", 5)
        mature_rate = self.params.get("mature_growth_rate", 0.06)
        terminal_growth = self.params["terminal_growth_rate"]  # 3%
        
        projected_fcfs = []
        pv_fcfs = []
        growth_schedule = []
        
        current_fcf = fcf
        
        for year in range(1, years + 1):
            # Determine growth rate for this year
            if year <= high_growth_years:
                # High growth phase - use actual growth rate
                growth = g_val
            else:
                # Fade phase - linear interpolation from g_val to mature_rate
                fade_years = years - high_growth_years  # 10 years
                fade_progress = (year - high_growth_years) / fade_years
                growth = g_val - (g_val - mature_rate) * fade_progress
            
            growth_schedule.append(growth)
            
            # Project FCF
            current_fcf = current_fcf * (1 + growth)
            projected_fcfs.append(current_fcf)
            
            # Calculate PV
            discount_factor = (1 + wacc) ** year
            pv = current_fcf / discount_factor
            pv_fcfs.append(pv)
        
        # Terminal value (Gordon Growth)
        terminal_fcf = projected_fcfs[-1] * (1 + terminal_growth)
        
        # Ensure WACC > terminal growth
        wacc_for_terminal = max(wacc, terminal_growth + 0.02)
        terminal_value = terminal_fcf / (wacc_for_terminal - terminal_growth)
        pv_terminal = terminal_value / ((1 + wacc) ** years)
        
        # Sum up
        pv_fcf_total = sum(pv_fcfs)
        enterprise_value = pv_fcf_total + pv_terminal
        equity_value = enterprise_value - net_debt
        
        components = {
            "ev": enterprise_value,
            "pv_fcfs": pv_fcf_total,
            "pv_terminal": pv_terminal,
            "tv_pct": pv_terminal / enterprise_value if enterprise_value > 0 else 0,
            "terminal_value": terminal_value,
            "final_year_fcf": projected_fcfs[-1] if projected_fcfs else 0,
            "year1_growth": growth_schedule[0] if growth_schedule else 0,
            "year15_growth": growth_schedule[-1] if growth_schedule else 0,
        }
        
        return max(equity_value, 0), components
    
    def _calculate_entry_price(self, fcf: float, g_val: float, wacc: float,
                                net_debt: float, shares: float, 
                                target_irr: float) -> float:
        """
        Calculate price that would deliver target IRR.
        Uses iterative approach to find price where expected return = target.
        """
        # Simple approximation: IRR ≈ FCF Yield + Growth
        # Target Price = FCF / (target_irr - g_val × retention)
        
        # For a rough estimate, use:
        # Price = FCF × (1 + g_val) / (target_irr - g_val/2)
        
        effective_growth = g_val * 0.6  # Assume some multiple compression
        required_yield = target_irr - effective_growth
        
        if required_yield <= 0:
            required_yield = 0.02  # Floor at 2% yield
        
        implied_ev = fcf / required_yield
        implied_equity = implied_ev - net_debt
        implied_price = implied_equity / shares if shares > 0 else 0
        
        return max(implied_price, 0)
    
    def _calculate_implied_irr(self, current_price: float, 
                                 intrinsic_value: float, g_val: float) -> float:
        """
        Calculate implied IRR at current price.
        
        IRR components:
        1. FCF Yield (earnings yield proxy)
        2. Expected Growth
        3. Multiple Expansion/Compression over holding period
        
        Formula: IRR ≈ FCF Yield + Growth + Annualized Rerating
        """
        if current_price <= 0 or intrinsic_value <= 0:
            return 0
        
        # Calculate upside to fair value
        upside = (intrinsic_value / current_price) - 1
        
        # Annualize the rerating over 5-year holding period
        # If 50% undervalued, that's ~8.4% annual rerating contribution
        holding_years = 5
        if upside > 0:
            rerating_contribution = (1 + upside) ** (1/holding_years) - 1
        else:
            # If overvalued, rerating is a drag
            rerating_contribution = -((1 - abs(upside)) ** (1/holding_years) - 1)
        
        # Total IRR = Growth + Rerating
        # (In reality, also includes FCF yield, but growth captures reinvestment)
        implied_irr = g_val + rerating_contribution
        
        # Cap at reasonable bounds
        implied_irr = max(min(implied_irr, 0.50), -0.20)  # -20% to +50%
        
        return implied_irr
    
    def _determine_action(self, implied_irr: float, mos: float, 
                           tier_label: str) -> str:
        """
        Determine action signal based on IRR and MOS.
        
        Simplified Action Labels:
        - BUY:  High conviction, we're buying - IRR ≥15% AND MOS ≥10%
        - HOLD: We own it, maintaining position - IRR ≥10%
        - SELL: Overvalued, exiting - IRR <10% OR MOS < -20% (only via manual check)
        
        Note: IRR and MOS are passed in DECIMAL form (0.15 = 15%)
        """
        # SELL triggers (only shows via manual ticker check)
        if implied_irr < 0.10:
            return "SELL"
        if mos < -0.20:  # Stock is 20%+ overvalued
            return "SELL"
        
        # BUY: High conviction - IRR ≥15% AND MOS ≥10%
        if implied_irr >= 0.15 and mos >= 0.10:
            return "BUY"
        
        # Everything else we own is HOLD
        return "HOLD"


def run_tier3_valuation(input_file: str, output_file: str = "top20_buylist.csv",
                        min_score: int = 70) -> pd.DataFrame:
    """
    Run Tier 3 DCF valuation on ELITE+ companies.
    
    Args:
        input_file: CSV with Tier 2 scored companies
        output_file: Where to save valued companies
        min_score: Minimum score to value (default: 70 = ELITE+)
    
    Returns:
        DataFrame with valuations sorted by implied IRR
    """
    print(f"\n{'='*60}")
    print("TIER 3: DCF VALUATION")
    print(f"{'='*60}")
    
    print(f"\nLoading data from {input_file}...")
    df = pd.read_csv(input_file)
    
    # Filter to ELITE+ only
    elite_df = df[df["total_score"] >= min_score].copy()
    print(f"Valuing {len(elite_df)} ELITE+ companies...\n")
    
    valuator = DCFValuation()
    valuations = []
    
    for i, (idx, row) in enumerate(elite_df.iterrows(), 1):
        ticker = row.get("ticker", "N/A")
        print(f"  [{i}/{len(elite_df)}] Valuing {ticker}...", end=" ")
        
        val_result = valuator.value_company(row)
        
        # Merge with original row data
        merged = {**row.to_dict(), **val_result}
        valuations.append(merged)
        
        status = val_result.get("valuation_status", "unknown")
        if status == "complete":
            irr = val_result.get("implied_irr", 0)
            action = val_result.get("action_signal", "N/A")
            print(f"✓ IRR: {irr}% ({action})")
        else:
            print(f"⚠️ {status}")
    
    # Create results DataFrame
    results_df = pd.DataFrame(valuations)
    
    # Sort by implied IRR descending
    if "implied_irr" in results_df.columns:
        results_df = results_df.sort_values("implied_irr", ascending=False)
    
    # Save results
    results_df.to_csv(output_file, index=False)
    
    # Print summary
    _print_valuation_summary(results_df)
    
    print(f"\n✅ Valuations saved: {output_file}")
    
    return results_df


def _print_valuation_summary(df: pd.DataFrame):
    """Print valuation summary."""
    print(f"\n{'='*60}")
    print("VALUATION SUMMARY")
    print(f"{'='*60}")
    
    complete = df[df.get("valuation_status", "") == "complete"]
    
    if len(complete) == 0:
        print("No complete valuations.")
        return
    
    # Action distribution
    print("\nACTION SIGNALS:")
    print("-" * 40)
    for action in ["BUY", "WATCH", "HOLD", "TRIM"]:
        count = len(complete[complete["action_signal"] == action])
        print(f"  {action:8} {count:3} companies")
    
    # Top opportunities
    print(f"\nTOP 10 BY IMPLIED IRR:")
    print("-" * 70)
    print(f"{'Ticker':8} {'Score':>6} {'IRR':>7} {'MOS':>7} {'Price':>8} {'Buy@15%':>9} {'Action':>8}")
    print("-" * 70)
    
    for i, row in complete.head(10).iterrows():
        ticker = row.get("ticker", "N/A")
        score = row.get("total_score", 0)
        irr = row.get("implied_irr", 0)
        mos = row.get("margin_of_safety", 0)
        price = row.get("current_price", 0)
        buy15 = row.get("buy_15_price", 0)
        action = row.get("action_signal", "N/A")
        
        print(f"{ticker:8} {score:6.0f} {irr:6.1f}% {mos:6.1f}% ${price:7.2f} ${buy15:8.2f} {action:>8}")
    
    # Buy signals
    buys = complete[complete["action_signal"] == "BUY"]
    if len(buys) > 0:
        print(f"\n🎯 BUY SIGNALS ({len(buys)}):")
        print("-" * 60)
        for i, row in buys.iterrows():
            ticker = row.get("ticker", "")
            irr = row.get("implied_irr", 0)
            mos = row.get("margin_of_safety", 0)
            print(f"  {ticker}: IRR {irr}%, MOS {mos}%")
    else:
        print("\n✅ No BUY signals (this is expected most months per charter)")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "universe_tier2_scored.csv"
    
    run_tier3_valuation(input_file)
