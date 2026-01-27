"""
Capital Compounder Investment System - Tier 2: Quality Scoring
Ranks Tier 1 survivors by compounding potential using 100-point system.

Scoring Weights (per Charter v1.0):
- Incremental ROIC:      30 pts (>40%=30, 30-40%=20, 25-30%=10)
- Reinvestment Runway:   20 pts (>$10B=20, $5-10B=15, $1-5B=10)
- Revenue Growth (3Y):   20 pts (>20%=20, 15-20%=15, 10-15%=10)
- FCF Conversion:        15 pts (>100%=15, 95-100%=10, 90-95%=5)
- Gross Margin Trend:    10 pts (Expanding=10, Stable=5, Declining=0)
- CapEx Efficiency:       5 pts (<3%=5, 3-5%=3, >5%=0)

Tier Labels:
- EXCEPTIONAL: ≥80 pts → Auto-advance to Tier 3
- ELITE: 70-79 pts → Advance to Tier 3
- QUALITY: 60-69 pts → Watch list only
- REVIEW: <60 pts → Ignore
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from config import TIER2_WEIGHTS, TIER2_SCORING, TIER_LABELS


class Tier2Scorer:
    """Scores companies on compounding quality using 100-point system."""
    
    def __init__(self):
        self.weights = TIER2_WEIGHTS
        self.scoring = TIER2_SCORING
        self.tier_labels = TIER_LABELS
    
    def score_universe(self, df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
        """
        Score all companies in the DataFrame.
        Returns DataFrame with scores and tier labels.
        """
        if verbose:
            print(f"\n{'='*60}")
            print("TIER 2: QUALITY SCORING")
            print(f"{'='*60}")
            print(f"Scoring {len(df)} companies...\n")
        
        df = df.copy()
        
        # Calculate individual component scores
        df["score_incremental_roic"] = df.apply(self._score_incremental_roic, axis=1)
        df["score_reinvestment_runway"] = df.apply(self._score_reinvestment_runway, axis=1)
        df["score_revenue_growth"] = df.apply(self._score_revenue_growth, axis=1)
        df["score_fcf_conversion"] = df.apply(self._score_fcf_conversion, axis=1)
        df["score_gross_margin_trend"] = df.apply(self._score_gross_margin_trend, axis=1)
        df["score_capex_efficiency"] = df.apply(self._score_capex_efficiency, axis=1)
        
        # Calculate total score
        score_columns = [
            "score_incremental_roic",
            "score_reinvestment_runway",
            "score_revenue_growth",
            "score_fcf_conversion",
            "score_gross_margin_trend",
            "score_capex_efficiency"
        ]
        df["total_score"] = df[score_columns].sum(axis=1)
        
        # Assign tier labels
        df["tier_label"] = df["total_score"].apply(self._assign_tier_label)
        
        # Sort by total score descending
        df = df.sort_values("total_score", ascending=False)
        
        # Print summary (unless verbose=False)
        if verbose:
            self._print_summary(df)
        
        return df
    
    def _score_incremental_roic(self, row) -> int:
        """
        Score Incremental ROIC (30 pts max).
        >40% = 30, 30-40% = 20, 25-30% = 10, <25% = 0
        """
        val = row.get("incremental_roic")
        if pd.isna(val):
            return 0
        
        if val > 0.40:
            return 30
        elif val > 0.30:
            return 20
        elif val >= 0.25:
            return 10
        else:
            return 0
    
    def _score_reinvestment_runway(self, row) -> int:
        """
        Score Reinvestment Runway (20 pts max).
        Based on market cap as proxy for addressable opportunity.
        >$100B cap = 20 (likely >$10B runway)
        $50-100B = 15
        $10-50B = 10
        <$10B = 5
        """
        market_cap = row.get("market_cap", 0)
        growth_rate = row.get("revenue_growth_3y", 0) or 0
        
        # Estimate runway based on market cap and growth trajectory
        # Companies with large caps AND high growth have proven runways
        if pd.isna(market_cap):
            return 0
        
        # Adjust for growth rate - high growth suggests runway exists
        growth_mult = 1.0
        if growth_rate > 0.25:
            growth_mult = 1.3
        elif growth_rate > 0.20:
            growth_mult = 1.2
        elif growth_rate > 0.15:
            growth_mult = 1.1
        
        effective_cap = market_cap * growth_mult
        
        if effective_cap > 100_000_000_000:  # $100B+
            return 20
        elif effective_cap > 50_000_000_000:  # $50-100B
            return 15
        elif effective_cap > 10_000_000_000:  # $10-50B
            return 10
        else:
            return 5
    
    def _score_revenue_growth(self, row) -> int:
        """
        Score Revenue Growth (20 pts max).
        >20% = 20, 15-20% = 15, 10-15% = 10, <10% = 0
        """
        val = row.get("revenue_growth_3y")
        if pd.isna(val):
            return 0
        
        if val > 0.20:
            return 20
        elif val > 0.15:
            return 15
        elif val > 0.10:
            return 10
        else:
            return 0
    
    def _score_fcf_conversion(self, row) -> int:
        """
        Score FCF Conversion (15 pts max).
        >100% = 15, 95-100% = 10, 90-95% = 5, <90% = 0
        """
        val = row.get("fcf_conversion")
        if pd.isna(val):
            return 0
        
        if val > 1.00:
            return 15
        elif val > 0.95:
            return 10
        elif val >= 0.90:
            return 5
        else:
            return 0
    
    def _score_gross_margin_trend(self, row) -> int:
        """
        Score Gross Margin Trend (10 pts max).
        Expanding 100bps+ = 10, Stable = 5, Declining = 0
        """
        trend = row.get("gross_margin_trend", "unknown")
        
        if trend == "expanding":
            return 10
        elif trend == "stable":
            return 5
        else:  # declining or unknown
            return 0
    
    def _score_capex_efficiency(self, row) -> int:
        """
        Score CapEx Efficiency (5 pts max).
        <3% of revenue = 5, 3-5% = 3, >5% = 0
        Note: Context-dependent - some industries require higher CapEx
        """
        val = row.get("capex_to_revenue")
        if pd.isna(val):
            return 3  # Neutral if missing
        
        if val < 0.03:
            return 5
        elif val < 0.05:
            return 3
        else:
            return 0
    
    def _assign_tier_label(self, score: float) -> str:
        """Assign tier label based on total score."""
        if score >= self.tier_labels["exceptional"]:
            return "EXCEPTIONAL"
        elif score >= self.tier_labels["elite"]:
            return "ELITE"
        elif score >= self.tier_labels["quality"]:
            return "QUALITY"
        else:
            return "REVIEW"
    
    def _print_summary(self, df: pd.DataFrame):
        """Print scoring summary."""
        print("SCORING DISTRIBUTION:")
        print("-" * 40)
        
        for label in ["EXCEPTIONAL", "ELITE", "QUALITY", "REVIEW"]:
            count = len(df[df["tier_label"] == label])
            pct = count / len(df) * 100 if len(df) > 0 else 0
            bar = "█" * int(pct / 2)
            print(f"  {label:12} {count:3} ({pct:5.1f}%) {bar}")
        
        print("-" * 40)
        
        # Top 10 preview
        print(f"\nTOP 10 BY SCORE:")
        print("-" * 60)
        for i, row in df.head(10).iterrows():
            ticker = row.get("ticker", "N/A")
            score = row.get("total_score", 0)
            tier = row.get("tier_label", "N/A")
            inc_roic = row.get("incremental_roic", 0)
            inc_roic_str = f"{inc_roic*100:.1f}%" if pd.notna(inc_roic) else "N/A"
            print(f"  {ticker:8} Score: {score:3.0f} ({tier:12}) Inc.ROIC: {inc_roic_str}")
        
        # Health check
        elite_plus = len(df[df["tier_label"].isin(["EXCEPTIONAL", "ELITE"])])
        if elite_plus > 40:
            print(f"\n⚠️  WARNING: {elite_plus} ELITE+ companies. Scoring may be too lenient.")
        elif elite_plus < 15:
            print(f"\n⚠️  WARNING: Only {elite_plus} ELITE+ companies. Review scoring thresholds.")
        else:
            print(f"\n✅ ELITE+ count healthy: {elite_plus} (target: 15-25)")


def run_tier2_scoring(input_file: str, output_file: str = "universe_tier2_scored.csv",
                      min_score: int = 70) -> pd.DataFrame:
    """
    Run Tier 2 scoring on Tier 1 passed companies.
    
    Args:
        input_file: CSV with Tier 1 passed companies
        output_file: Where to save scored companies
        min_score: Minimum score to include in output (default: 70 = ELITE)
    
    Returns:
        DataFrame with all scored companies
    """
    print(f"\nLoading data from {input_file}...")
    df = pd.read_csv(input_file)
    
    scorer = Tier2Scorer()
    scored_df = scorer.score_universe(df)
    
    # Save all scored companies
    scored_df.to_csv(output_file, index=False)
    print(f"\n✅ Scored universe saved: {output_file}")
    
    # Also save ELITE+ for Tier 3
    elite_df = scored_df[scored_df["total_score"] >= min_score]
    elite_file = output_file.replace(".csv", "_elite.csv")
    elite_df.to_csv(elite_file, index=False)
    print(f"✅ ELITE+ companies ({len(elite_df)}): {elite_file}")
    
    return scored_df


def calculate_tier2_score(data: Dict) -> Dict:
    """
    Calculate Tier 2 quality score for a single ticker's data dict.
    
    Args:
        data: Dict with ticker metrics
        
    Returns:
        Dict with score breakdown and tier label
    """
    scorer = Tier2Scorer()
    
    # Create a single-row DataFrame
    import pandas as pd
    df = pd.DataFrame([data])
    
    # Score it
    scored_df = scorer.score_universe(df, verbose=False)
    
    if len(scored_df) == 0:
        return {
            'total_score': 0,
            'tier_label': 'REVIEW',
        }
    
    row = scored_df.iloc[0]
    
    return {
        'total_score': row.get('total_score', 0),
        'tier_label': row.get('tier_label', 'REVIEW'),
        'score_roic': row.get('score_roic', 0),
        'score_growth': row.get('score_growth', 0),
        'score_fcf': row.get('score_fcf', 0),
        'score_margin': row.get('score_margin', 0),
        'score_reinvest': row.get('score_reinvest', 0),
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "universe_tier1_passed.csv"
    
    run_tier2_scoring(input_file)
