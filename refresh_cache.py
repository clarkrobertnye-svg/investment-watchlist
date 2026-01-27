#!/usr/bin/env python3
"""
Capital Compounder Investment System - Nightly Cache Refresh
Run this script nightly (via cron) to pre-fetch data for all tracked tickers.

Usage:
    python refresh_cache.py                    # Refresh default universe
    python refresh_cache.py --tickers AAPL MSFT  # Refresh specific tickers
    python refresh_cache.py --file tickers.txt   # Refresh from file
    python refresh_cache.py --top 500            # Refresh top N by market cap

Cron example (run at 2am daily):
    0 2 * * * cd /path/to/capital_compounders && python refresh_cache.py >> logs/refresh.log 2>&1
"""

import argparse
import sys
import time
from datetime import datetime
from typing import List

from cache_manager import CachedFMPFetcher, CacheManager


# Default universe - top compounders to always keep fresh
DEFAULT_UNIVERSE = [
    # Your current portfolio (Top 13)
    'ASML', 'NVDA', 'MELI', 'DDOG', 'CRWD', 'FTNT', 'NOW', 
    'META', 'PANW', 'SNPS', 'MSFT', 'ADBE', 'MA',
    
    # Popular large caps (high request probability)
    'AAPL', 'GOOGL', 'GOOG', 'AMZN', 'TSLA', 'V', 'JPM', 'JNJ',
    'UNH', 'HD', 'PG', 'XOM', 'CVX', 'BAC', 'ABBV', 'KO', 'PEP',
    'MRK', 'LLY', 'TMO', 'COST', 'AVGO', 'WMT', 'MCD', 'DIS',
    'CSCO', 'ACN', 'VZ', 'CMCSA', 'NFLX', 'INTC', 'AMD', 'QCOM',
    'TXN', 'ORCL', 'IBM', 'CRM', 'INTU', 'AMAT', 'LRCX', 'KLAC',
    'CDNS', 'ANSS', 'WDAY', 'ZS', 'NET', 'SNOW', 'MDB', 'TEAM',
    
    # Quality compounders / watchlist candidates
    'SPGI', 'MCO', 'MSCI', 'ICE', 'CME', 'NDAQ', 'MKTX',  # Financials
    'ISRG', 'SYK', 'MDT', 'ABT', 'DHR', 'A', 'EW',         # Healthcare
    'DE', 'CAT', 'EMR', 'ROK', 'ITW', 'PH', 'GE',          # Industrials
    'NKE', 'LULU', 'DECK', 'ON', 'POOL', 'WSO',            # Consumer
    'TTD', 'PINS', 'SNAP', 'ROKU', 'SPOT', 'RBLX',         # Digital/Media
    
    # Multi-class shares (test special handling)
    'BRK-B', 'BRK-A', 'BF-B', 'BF-A',
]


def progress_bar(current: int, total: int, ticker: str, width: int = 40):
    """Display a progress bar."""
    pct = current / total
    filled = int(width * pct)
    bar = '█' * filled + '░' * (width - filled)
    print(f'\r  [{bar}] {current}/{total} ({pct*100:.1f}%) - {ticker:8}', end='', flush=True)


def refresh_cache(tickers: List[str], rate_limit_per_min: int = 300, use_ttm: bool = False):
    """
    Refresh cache for a list of tickers with rate limiting.
    
    Args:
        tickers: List of ticker symbols
        rate_limit_per_min: API calls per minute limit (default 300 for paid plan)
    """
    print("="*70)
    print("CAPITAL COMPOUNDERS - CACHE REFRESH")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Calculate delay between tickers (6 API calls per ticker)
    calls_per_ticker = 6
    tickers_per_minute = rate_limit_per_min / calls_per_ticker
    delay_between_tickers = 60 / tickers_per_minute  # seconds
    
    print(f"\nConfiguration:")
    print(f"  Tickers to refresh: {len(tickers)}")
    print(f"  API rate limit: {rate_limit_per_min}/min")
    print(f"  Delay between tickers: {delay_between_tickers:.2f}s")
    print(f"  Estimated time: {len(tickers) * delay_between_tickers / 60:.1f} minutes")
    
    # Initialize fetcher
    fetcher = CachedFMPFetcher()
    
    print(f"\nRefreshing...\n")
    
    stats = {
        'total': len(tickers),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'errors': [],
    }
    
    start_time = time.time()
    
    for i, ticker in enumerate(tickers):
        progress_bar(i + 1, len(tickers), ticker)
        
        try:
            result = fetcher.get_ticker_data(ticker, force_refresh=True, use_ttm=use_ttm)
            
            if result and result.get('data_quality') not in ['error', 'incomplete', None]:
                stats['success'] += 1
            elif result and result.get('data_quality') == 'incomplete':
                stats['skipped'] += 1
            else:
                stats['failed'] += 1
                error_msg = result.get('error', 'Unknown error') if result else 'No data returned'
                stats['errors'].append({'ticker': ticker, 'error': error_msg})
                
        except Exception as e:
            stats['failed'] += 1
            stats['errors'].append({'ticker': ticker, 'error': str(e)})
        
        # Rate limiting
        if i < len(tickers) - 1:  # Don't delay after last ticker
            time.sleep(delay_between_tickers)
    
    elapsed = time.time() - start_time
    
    # Mark refresh complete
    fetcher.cache.mark_refresh_complete()
    
    # Print summary
    print(f"\n\n{'='*70}")
    print("REFRESH COMPLETE")
    print("="*70)
    print(f"\nResults:")
    print(f"  ✓ Success:  {stats['success']}")
    print(f"  ⊘ Skipped:  {stats['skipped']} (incomplete data)")
    print(f"  ✗ Failed:   {stats['failed']}")
    print(f"  Total:      {stats['total']}")
    print(f"\nElapsed time: {elapsed/60:.1f} minutes ({elapsed:.0f}s)")
    
    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):")
        for err in stats['errors'][:10]:  # Show first 10 errors
            print(f"  - {err['ticker']}: {err['error']}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")
    
    # Cache stats
    cache_stats = fetcher.get_cache_stats()
    print(f"\nCache Statistics:")
    print(f"  Total tickers cached: {cache_stats['total_tickers_cached']}")
    print(f"  Cache hit rate: {cache_stats['hit_rate_pct']}%")
    print(f"  API calls saved (lifetime): {cache_stats['api_calls_saved']}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Refresh cache for capital compounders')
    parser.add_argument('--tickers', nargs='+', help='Specific tickers to refresh')
    parser.add_argument('--file', type=str, help='File with tickers (one per line)')
    parser.add_argument('--rate-limit', type=int, default=300, help='API calls per minute (default: 300)')
    parser.add_argument('--stats', action='store_true', help='Show cache stats only')
    parser.add_argument('--clear', action='store_true', help='Clear cache before refresh')
    parser.add_argument('--ttm', action='store_true', help='Use TTM (trailing twelve months) data from quarterly statements')
    
    args = parser.parse_args()
    
    # Show stats only
    if args.stats:
        cache = CacheManager()
        stats = cache.get_stats()
        print("\nCache Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        print(f"\nCached tickers: {', '.join(cache.list_cached_tickers()[:20])}")
        if len(cache.list_cached_tickers()) > 20:
            print(f"  ... and {len(cache.list_cached_tickers()) - 20} more")
        return
    
    # Clear cache if requested
    if args.clear:
        cache = CacheManager()
        cache.clear_all()
        print("Cache cleared.")
    
    # Determine tickers to refresh
    if args.tickers:
        tickers = args.tickers
    elif args.file:
        with open(args.file, 'r') as f:
            tickers = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        tickers = DEFAULT_UNIVERSE
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tickers = []
    for t in tickers:
        t_upper = t.upper()
        if t_upper not in seen:
            seen.add(t_upper)
            unique_tickers.append(t)
    
    # Run refresh
    refresh_cache(unique_tickers, rate_limit_per_min=args.rate_limit, use_ttm=args.ttm)


if __name__ == '__main__':
    main()
