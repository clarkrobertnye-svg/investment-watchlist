"""
Capital Compounder Investment System - Batch Runner
Feeds Stage 1 screener output to fmp_data.py for full analysis and caching.

This bridges:
  stage1_screener.py → run_batch.py → fmp_data.py → cache/*.json → generate_dashboard_v2.py

USAGE:
    # From Stage 1 output
    python run_batch.py --input stage1_candidates_tickers.txt
    
    # From manual list
    python run_batch.py --tickers NVDA,MSFT,AAPL,GOOG
    
    # Refresh existing cache
    python run_batch.py --refresh-stale
    
    # Test with small batch
    python run_batch.py --input stage1_candidates_tickers.txt --limit 10
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List

# Import your existing modules
try:
    from fmp_data import FinancialDataProcessor
    from cache_manager import CacheManager, CachedFMPFetcher
    HAS_CACHE_MANAGER = True
except ImportError:
    HAS_CACHE_MANAGER = False
    print("⚠️  cache_manager.py not found - using direct fmp_data.py")

try:
    from fmp_data import FinancialDataProcessor
    HAS_FMP = True
except ImportError:
    HAS_FMP = False
    print("❌ fmp_data.py not found - cannot run batch")


def load_tickers_from_file(filepath: str) -> List[str]:
    """Load ticker list from file (one per line or JSON)."""
    path = Path(filepath)
    
    if not path.exists():
        print(f"❌ File not found: {filepath}")
        return []
    
    if path.suffix == '.json':
        with open(path) as f:
            data = json.load(f)
        
        # Handle Stage 1 output format
        if isinstance(data, dict) and "candidates" in data:
            return [c["ticker"] for c in data["candidates"]]
        
        # Handle simple list
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                return [t.get("ticker", t.get("symbol", "")) for t in data]
            return data
    
    # Text file - one ticker per line
    with open(path) as f:
        tickers = [line.strip().upper() for line in f if line.strip() and not line.startswith('#')]
    
    return tickers


def run_batch(tickers: List[str], 
              use_cache: bool = True,
              force_refresh: bool = False,
              use_ttm: bool = False,
              delay: float = 0.0) -> dict:
    """
    Run full analysis for a list of tickers.
    
    Args:
        tickers: List of ticker symbols
        use_cache: Whether to use cache manager
        force_refresh: Force re-fetch even if cached
        use_ttm: Use TTM data instead of annual
        delay: Additional delay between tickers
    
    Returns:
        Dict with batch statistics
    """
    if not HAS_FMP:
        return {"error": "fmp_data.py not available"}
    
    stats = {
        "start_time": datetime.now().isoformat(),
        "total": len(tickers),
        "success": 0,
        "incomplete": 0,
        "error": 0,
        "skipped_cached": 0,
        "processed": [],
        "errors": [],
    }
    
    # Initialize processor
    if use_cache and HAS_CACHE_MANAGER:
        print("📦 Using cached fetcher")
        fetcher = CachedFMPFetcher()
    else:
        print("📡 Using direct FMP fetcher")
        processor = FinancialDataProcessor()
    
    cache_dir = Path("cache/ticker_data")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n🚀 Processing {len(tickers)} tickers...")
    print("=" * 60)
    
    start_time = datetime.now()
    
    for i, ticker in enumerate(tickers, 1):
        # Progress
        elapsed = (datetime.now() - start_time).total_seconds() / 60
        remaining = (elapsed / i * (len(tickers) - i)) if i > 0 else 0
        print(f"\n[{i}/{len(tickers)}] {ticker} (elapsed: {elapsed:.1f}m, remaining: ~{remaining:.1f}m)")
        
        # Check cache
        cache_file = cache_dir / f"{ticker}.json"
        if cache_file.exists() and not force_refresh:
            try:
                with open(cache_file) as f:
                    cached = json.load(f)
                if cached.get("data_quality") == "complete":
                    print(f"  ✓ Using cached data")
                    stats["skipped_cached"] += 1
                    stats["processed"].append(ticker)
                    continue
            except (json.JSONDecodeError, IOError):
                pass
        
        # Fetch data
        try:
            if use_cache and HAS_CACHE_MANAGER:
                data = fetcher.get_ticker_data(ticker, force_refresh=force_refresh, use_ttm=use_ttm)
            else:
                data = processor.get_all_metrics(ticker, use_ttm=use_ttm)
            
            if data:
                quality = data.get("data_quality", "unknown")
                
                if quality == "complete":
                    stats["success"] += 1
                    stats["processed"].append(ticker)
                    
                    # Save to cache if using direct processor
                    if not (use_cache and HAS_CACHE_MANAGER):
                        with open(cache_file, 'w') as f:
                            json.dump(data, f, indent=2)
                        print(f"  💾 Saved to cache")
                    
                elif quality == "incomplete":
                    stats["incomplete"] += 1
                    print(f"  ⚠️ Incomplete data")
                else:
                    stats["error"] += 1
                    stats["errors"].append({"ticker": ticker, "reason": quality})
            else:
                stats["error"] += 1
                stats["errors"].append({"ticker": ticker, "reason": "No data returned"})
        
        except Exception as e:
            stats["error"] += 1
            stats["errors"].append({"ticker": ticker, "reason": str(e)})
            print(f"  ❌ Error: {e}")
        
        # Additional delay if specified
        if delay > 0:
            time.sleep(delay)
    
    # Final stats
    stats["end_time"] = datetime.now().isoformat()
    total_time = (datetime.now() - start_time).total_seconds()
    stats["elapsed_seconds"] = total_time
    stats["elapsed_minutes"] = total_time / 60
    
    print("\n" + "=" * 60)
    print("BATCH COMPLETE")
    print("=" * 60)
    print(f"Total Tickers:     {stats['total']}")
    print(f"Success:           {stats['success']}")
    print(f"Incomplete:        {stats['incomplete']}")
    print(f"Errors:            {stats['error']}")
    print(f"Skipped (cached):  {stats['skipped_cached']}")
    print(f"Time Elapsed:      {stats['elapsed_minutes']:.1f} minutes")
    
    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):")
        for err in stats['errors'][:10]:
            print(f"  - {err['ticker']}: {err['reason']}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Batch runner for Capital Compounder analysis')
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--input', '-i', type=str, help='Input file (JSON or text, one ticker per line)')
    input_group.add_argument('--tickers', '-t', type=str, help='Comma-separated list of tickers')
    input_group.add_argument('--refresh-stale', action='store_true', help='Refresh stale cached tickers')
    
    # Processing options
    parser.add_argument('--limit', type=int, help='Limit number of tickers to process')
    parser.add_argument('--force', action='store_true', help='Force refresh even if cached')
    parser.add_argument('--no-cache', action='store_true', help='Skip cache manager, use direct FMP')
    parser.add_argument('--ttm', action='store_true', help='Use TTM data instead of annual')
    parser.add_argument('--delay', type=float, default=0, help='Additional delay between tickers (seconds)')
    parser.add_argument('--output', type=str, help='Output file for batch stats')
    
    args = parser.parse_args()
    
    # Get ticker list
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    elif args.input:
        tickers = load_tickers_from_file(args.input)
    elif args.refresh_stale:
        if HAS_CACHE_MANAGER:
            cache = CacheManager()
            tickers = cache.get_stale_tickers()
            print(f"Found {len(tickers)} stale tickers to refresh")
        else:
            print("❌ cache_manager.py required for --refresh-stale")
            return
    else:
        print("❌ No tickers specified")
        return
    
    if not tickers:
        print("❌ No tickers to process")
        return
    
    # Apply limit
    if args.limit:
        tickers = tickers[:args.limit]
        print(f"⚠️ Limited to {args.limit} tickers")
    
    print(f"\n📋 Tickers to process: {len(tickers)}")
    if len(tickers) <= 20:
        print(f"   {', '.join(tickers)}")
    else:
        print(f"   {', '.join(tickers[:10])}... and {len(tickers)-10} more")
    
    # Run batch
    stats = run_batch(
        tickers=tickers,
        use_cache=not args.no_cache,
        force_refresh=args.force,
        use_ttm=args.ttm,
        delay=args.delay,
    )
    
    # Save stats
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(stats, f, indent=2)
        print(f"\n💾 Stats saved to: {args.output}")
    
    # Next steps
    print(f"\n📋 NEXT STEPS:")
    print(f"   python generate_dashboard_v2.py")


if __name__ == "__main__":
    main()
