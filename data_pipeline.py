"""
Capital Compounder Investment System - Efficient Data Pipeline
Minimizes API costs through smart caching and pre-filtering.

ARCHITECTURE:
=============

QUARTERLY FULL REFRESH (200 tickers × 4/year = 800 FMP calls)
├── Pull complete financials for universe
├── Run Tier 1 + Tier 2 scoring
├── Cache results locally
└── Identify ELITE+ watchlist (~30-50 names)

WEEKLY PRICE UPDATE (50 tickers × 52/year = 2,600 cheap calls)
├── Pull prices only for ELITE+ companies
├── Recalculate IRR and action signals
└── Generate alerts for BUY zone entries

PRE-FILTER WITH FREE/CHEAP LLMs (Optional - cuts FMP calls 50-70%)
├── Use DeepSeek, Gemini, or local LLM to screen for ROIC hurdles
├── Only send likely candidates to FMP
└── Leverage free tiers of alternative data sources

Owner: Rob (clarkrobertnye@gmail.com)
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd


class DataPipelineManager:
    """Manages efficient data fetching with caching and pre-filtering."""
    
    def __init__(self, cache_dir: str = "./data_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache file paths
        self.universe_cache = self.cache_dir / "universe_full.csv"
        self.elite_cache = self.cache_dir / "elite_watchlist.csv"
        self.prices_cache = self.cache_dir / "prices_latest.csv"
        self.metadata_file = self.cache_dir / "cache_metadata.json"
    
    def needs_quarterly_refresh(self) -> bool:
        """Check if quarterly full refresh is needed."""
        metadata = self._load_metadata()
        last_full = metadata.get("last_full_refresh")
        
        if not last_full:
            return True
        
        last_date = datetime.fromisoformat(last_full)
        days_since = (datetime.now() - last_date).days
        
        return days_since >= 90  # 90 days = quarterly
    
    def needs_weekly_refresh(self) -> bool:
        """Check if weekly price refresh is needed."""
        metadata = self._load_metadata()
        last_price = metadata.get("last_price_refresh")
        
        if not last_price:
            return True
        
        last_date = datetime.fromisoformat(last_price)
        days_since = (datetime.now() - last_date).days
        
        return days_since >= 7
    
    def run_quarterly_refresh(self, tickers: List[str], fmp_api_key: str):
        """
        Full quarterly refresh of all financials.
        Expensive but comprehensive.
        """
        from fmp_data import fetch_universe_data
        from tier1_filter import run_tier1_filter
        from tier2_scorer import run_tier2_scoring
        
        print("\n" + "="*60)
        print("QUARTERLY FULL REFRESH")
        print(f"Processing {len(tickers)} tickers...")
        print("="*60)
        
        # Fetch all data (expensive)
        df = fetch_universe_data(tickers, str(self.universe_cache))
        
        # Run Tier 1 filtering
        passed, _ = run_tier1_filter(
            str(self.universe_cache),
            str(self.cache_dir / "tier1_passed.csv"),
            str(self.cache_dir / "tier1_failed.csv")
        )
        
        # Run Tier 2 scoring
        scored = run_tier2_scoring(
            str(self.cache_dir / "tier1_passed.csv"),
            str(self.cache_dir / "tier2_scored.csv")
        )
        
        # Save ELITE+ watchlist
        elite = scored[scored["tier_label"].isin(["EXCEPTIONAL", "ELITE"])]
        elite.to_csv(self.elite_cache, index=False)
        
        # Update metadata
        self._update_metadata({
            "last_full_refresh": datetime.now().isoformat(),
            "universe_count": len(tickers),
            "tier1_passed": len(passed),
            "elite_count": len(elite),
        })
        
        print(f"\n✅ Quarterly refresh complete")
        print(f"   ELITE+ watchlist: {len(elite)} companies")
        
        return elite
    
    def run_weekly_price_update(self, fmp_api_key: str) -> pd.DataFrame:
        """
        Weekly price update for ELITE+ companies only.
        Cheap - just price quotes.
        """
        from fmp_data import FMPDataFetcher
        from tier3_valuation import run_tier3_valuation
        
        print("\n" + "="*60)
        print("WEEKLY PRICE UPDATE")
        print("="*60)
        
        # Load ELITE+ watchlist
        if not self.elite_cache.exists():
            print("❌ No ELITE+ cache found. Run quarterly refresh first.")
            return pd.DataFrame()
        
        elite_df = pd.read_csv(self.elite_cache)
        tickers = elite_df["ticker"].tolist()
        
        print(f"Updating prices for {len(tickers)} ELITE+ companies...")
        
        # Fetch just prices (cheap)
        fetcher = FMPDataFetcher(fmp_api_key)
        prices = {}
        
        for ticker in tickers:
            price = fetcher.get_stock_price(ticker)
            if price:
                prices[ticker] = price
                print(f"  {ticker}: ${price:.2f}")
        
        # Update prices in elite dataframe
        elite_df["price"] = elite_df["ticker"].map(prices)
        elite_df["price_date"] = datetime.now().isoformat()
        
        # Save updated prices
        elite_df.to_csv(self.prices_cache, index=False)
        
        # Re-run valuations with new prices
        valued = run_tier3_valuation(
            str(self.prices_cache),
            str(self.cache_dir / "weekly_valuations.csv")
        )
        
        # Update metadata
        self._update_metadata({
            "last_price_refresh": datetime.now().isoformat(),
            "prices_updated": len(prices),
        })
        
        return valued
    
    def get_cached_elite(self) -> Optional[pd.DataFrame]:
        """Get cached ELITE+ companies without API call."""
        if self.elite_cache.exists():
            return pd.read_csv(self.elite_cache)
        return None
    
    def get_cached_valuations(self) -> Optional[pd.DataFrame]:
        """Get cached valuations without API call."""
        val_file = self.cache_dir / "weekly_valuations.csv"
        if val_file.exists():
            return pd.read_csv(val_file)
        return None
    
    def _load_metadata(self) -> Dict:
        """Load cache metadata."""
        if self.metadata_file.exists():
            with open(self.metadata_file, "r") as f:
                return json.load(f)
        return {}
    
    def _update_metadata(self, updates: Dict):
        """Update cache metadata."""
        metadata = self._load_metadata()
        metadata.update(updates)
        metadata["last_updated"] = datetime.now().isoformat()
        
        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)


class PreFilterWithLLM:
    """
    Pre-filter universe using free/cheap LLMs before expensive FMP calls.
    
    Supported providers:
    - DeepSeek (very cheap, good at financial analysis)
    - Google Gemini (free tier available)
    - Local LLMs via Ollama (free, private)
    """
    
    def __init__(self, provider: str = "deepseek"):
        self.provider = provider
    
    def screen_for_roic_hurdle(self, tickers: List[str], 
                                min_roic: float = 0.15) -> List[str]:
        """
        Use LLM to quickly screen for companies likely to meet ROIC hurdle.
        Returns list of tickers that pass the pre-screen.
        
        This is a heuristic filter - not perfect, but cuts API costs.
        """
        # Prompt template for ROIC screening
        prompt = f"""
        For each company ticker, assess whether it likely has:
        - Return on Invested Capital (ROIC) > {min_roic*100}%
        - Strong competitive moat
        - Pricing power (gross margins > 40%)
        
        Respond with ONLY the tickers that likely meet ALL criteria.
        
        Tickers to evaluate: {', '.join(tickers[:50])}  # Batch of 50
        
        Response format: Just list the passing tickers, comma-separated.
        """
        
        # Call appropriate LLM
        if self.provider == "deepseek":
            return self._call_deepseek(prompt)
        elif self.provider == "gemini":
            return self._call_gemini(prompt)
        else:
            # Default: return all (no pre-filtering)
            return tickers
    
    def _call_deepseek(self, prompt: str) -> List[str]:
        """Call DeepSeek API for pre-screening."""
        # DeepSeek API implementation
        # Cost: ~$0.001 per 1K tokens (very cheap)
        
        import requests
        
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            print("⚠️ No DEEPSEEK_API_KEY found, skipping pre-filter")
            return []
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            }
        )
        
        if response.ok:
            content = response.json()["choices"][0]["message"]["content"]
            # Parse comma-separated tickers
            tickers = [t.strip().upper() for t in content.split(",")]
            return [t for t in tickers if t.isalpha()]
        
        return []
    
    def _call_gemini(self, prompt: str) -> List[str]:
        """Call Google Gemini API for pre-screening."""
        # Gemini API implementation
        # Free tier: 60 requests/minute
        
        import requests
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("⚠️ No GEMINI_API_KEY found, skipping pre-filter")
            return []
        
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1},
            }
        )
        
        if response.ok:
            content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            tickers = [t.strip().upper() for t in content.split(",")]
            return [t for t in tickers if t.isalpha()]
        
        return []


def run_smart_pipeline(tickers: List[str], fmp_api_key: str,
                       use_prefilter: bool = False,
                       prefilter_provider: str = "deepseek"):
    """
    Run the efficient data pipeline.
    
    Args:
        tickers: Full universe of tickers
        fmp_api_key: FMP API key
        use_prefilter: Whether to use LLM pre-filtering
        prefilter_provider: Which LLM to use for pre-filtering
    """
    manager = DataPipelineManager()
    
    # Check what needs updating
    needs_quarterly = manager.needs_quarterly_refresh()
    needs_weekly = manager.needs_weekly_refresh()
    
    print("\n" + "="*60)
    print("SMART DATA PIPELINE")
    print("="*60)
    print(f"Quarterly refresh needed: {needs_quarterly}")
    print(f"Weekly refresh needed: {needs_weekly}")
    
    if needs_quarterly:
        # Optional: Pre-filter to reduce FMP calls
        if use_prefilter:
            prefilter = PreFilterWithLLM(prefilter_provider)
            print(f"\nPre-filtering {len(tickers)} tickers with {prefilter_provider}...")
            tickers = prefilter.screen_for_roic_hurdle(tickers)
            print(f"Pre-filter passed: {len(tickers)} tickers")
        
        manager.run_quarterly_refresh(tickers, fmp_api_key)
    
    elif needs_weekly:
        manager.run_weekly_price_update(fmp_api_key)
    
    else:
        print("\n✅ Cache is fresh. Using cached data.")
    
    # Return current valuations
    return manager.get_cached_valuations()


# =============================================================================
# ALTERNATIVE DATA SOURCES (Free/Cheap)
# =============================================================================

ALTERNATIVE_DATA_SOURCES = """
FREE DATA SOURCES FOR PRE-SCREENING:
=====================================

1. Yahoo Finance (yfinance library)
   - Free, no API key needed
   - Good for: Prices, basic financials, market cap
   - Limitations: Rate limited, some data gaps
   
2. EDGAR / SEC Filings
   - Free, official source
   - Good for: 10-K, 10-Q financials
   - Limitations: Requires parsing, quarterly lag

3. Macrotrends (scraping)
   - Free data, requires scraping
   - Good for: Historical ROIC, margins, growth
   - Limitations: ToS concerns

4. Finviz (free tier)
   - Free screener
   - Good for: Pre-filtering by P/E, growth, margins
   - Limitations: Limited API access

CHEAP API ALTERNATIVES:
=======================

1. Alpha Vantage
   - Free tier: 5 calls/min, 500/day
   - Good for: Fundamentals, prices
   - Cost: $50/mo for premium

2. Polygon.io
   - Free tier: 5 calls/min
   - Good for: Real-time prices
   - Cost: $29/mo for starter

3. Tiingo
   - Free tier: 500 calls/day
   - Good for: Fundamentals, news
   - Cost: $10/mo for starter

4. IEX Cloud
   - Pay-as-you-go
   - Good for: Real-time data
   - Cost: ~$0.0001 per API call

RECOMMENDED STACK:
==================
- Pre-filter: DeepSeek ($0.001/1K tokens) or Gemini (free)
- Fundamentals: FMP (quarterly refresh only)
- Prices: Yahoo Finance (free) or IEX (cheap)
- Total cost: ~$10-20/month for full system
"""


if __name__ == "__main__":
    print(ALTERNATIVE_DATA_SOURCES)
    
    # Example usage
    from config import FMP_API_KEY
    
    tickers = ["NVDA", "MSFT", "AAPL", "GOOGL", "META"]  # Example
    
    valuations = run_smart_pipeline(
        tickers=tickers,
        fmp_api_key=FMP_API_KEY,
        use_prefilter=False,  # Set to True if you have DeepSeek/Gemini API key
    )
    
    if valuations is not None:
        print("\nCurrent Valuations:")
        print(valuations[["ticker", "total_score", "implied_irr", "action_signal"]].head(10))
