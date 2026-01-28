"""
Capital Compounder Investment System - Cache Manager
Handles caching of FMP API data to reduce API calls and improve performance.

Features:
- File-based JSON cache with TTL (time-to-live)
- Ticker normalization (BRK.B, BRK-B, BRKB all map to BRK-B)
- Nightly batch refresh capability
- Cache statistics and monitoring
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class TickerNormalizer:
    """
    Normalizes ticker symbols to handle different formats.
    FMP uses hyphen format: BRK-B, BF-B
    Users might enter: BRK.B, BRKB, brk-b, etc.
    """
    
    # Known multi-class tickers (expand as needed)
    MULTI_CLASS_TICKERS = {
        'BRK': ['A', 'B'],      # Berkshire Hathaway
        'BF': ['A', 'B'],       # Brown-Forman
        'MOG': ['A', 'B'],      # Moog Inc
        'LEN': ['A', 'B'],      # Lennar
        # 'GOOG': ['L'],        # REMOVED - GOOGL is the actual ticker, not GOOG class L
        'HEI': ['A'],           # HEICO
        'FOX': ['A'],           # Fox Corp
        'LBRDA': ['K'],         # Liberty Broadband
        'FWONA': ['K'],         # Liberty Formula One
    }
    
    @classmethod
    def normalize(cls, ticker: str) -> str:
        """
        Normalize ticker to FMP format (uppercase, hyphen for class).
        
        Examples:
            BRK.B -> BRK-B
            brk-b -> BRK-B
            BRKB  -> BRK-B (if recognized)
            AAPL  -> AAPL
        """
        if not ticker:
            return ""
        
        # Uppercase and strip whitespace
        ticker = ticker.upper().strip()
        
        # Replace dots with hyphens (BRK.B -> BRK-B)
        ticker = ticker.replace('.', '-')
        
        # Handle cases like "BRKB" -> "BRK-B"
        for base, classes in cls.MULTI_CLASS_TICKERS.items():
            for share_class in classes:
                # Match BRKB, BRKA patterns (no separator)
                if ticker == f"{base}{share_class}":
                    return f"{base}-{share_class}"
        
        return ticker
    
    @classmethod
    def validate(cls, ticker: str) -> Tuple[bool, str]:
        """
        Validate ticker format and return normalized version.
        Returns (is_valid, normalized_ticker_or_error_message)
        """
        if not ticker:
            return False, "Empty ticker"
        
        normalized = cls.normalize(ticker)
        
        # Basic validation: alphanumeric, hyphens, 1-10 chars
        if not re.match(r'^[A-Z0-9-]{1,10}$', normalized):
            return False, f"Invalid ticker format: {ticker}"
        
        return True, normalized
    
    @classmethod
    def get_display_format(cls, ticker: str) -> str:
        """
        Get display format (with dot) for UI.
        BRK-B -> BRK.B
        """
        normalized = cls.normalize(ticker)
        # For display, use dot format which is more familiar
        return normalized.replace('-', '.')


class CacheManager:
    """
    Manages file-based caching of FMP API data.
    
    Cache structure:
    cache/
        ticker_data/
            AAPL.json
            BRK-B.json
            ...
        metadata.json (cache stats, last refresh time)
    """
    
    DEFAULT_TTL_HOURS = 24  # Default cache TTL
    PRICE_TTL_HOURS = 1     # Price data refreshes more frequently
    
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            # Default to cache/ in the project directory
            cache_dir = os.path.join(os.path.dirname(__file__), 'cache')
        
        self.cache_dir = Path(cache_dir)
        self.ticker_cache_dir = self.cache_dir / 'ticker_data'
        self.metadata_file = self.cache_dir / 'metadata.json'
        
        # Create directories if they don't exist
        self.ticker_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize metadata
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load cache metadata or create default."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        return {
            'created': datetime.now().isoformat(),
            'last_refresh': None,
            'total_tickers': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'api_calls_saved': 0,
        }
    
    def _save_metadata(self):
        """Save cache metadata."""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def _get_cache_path(self, ticker: str) -> Path:
        """Get cache file path for a ticker."""
        normalized = TickerNormalizer.normalize(ticker)
        return self.ticker_cache_dir / f"{normalized}.json"
    
    def get(self, ticker: str, max_age_hours: float = None) -> Optional[Dict]:
        """
        Get cached data for a ticker if valid.
        
        Args:
            ticker: Ticker symbol (any format)
            max_age_hours: Maximum cache age in hours (default: DEFAULT_TTL_HOURS)
        
        Returns:
            Cached data dict or None if not found/expired
        """
        if max_age_hours is None:
            max_age_hours = self.DEFAULT_TTL_HOURS
        
        cache_path = self._get_cache_path(ticker)
        
        if not cache_path.exists():
            self.metadata['cache_misses'] = self.metadata.get('cache_misses', 0) + 1
            return None
        
        try:
            with open(cache_path, 'r') as f:
                cached = json.load(f)
            
            # Check if cache is still valid
            cached_time = datetime.fromisoformat(cached.get('_cached_at', '2000-01-01'))
            age = datetime.now() - cached_time
            
            if age > timedelta(hours=max_age_hours):
                self.metadata['cache_misses'] = self.metadata.get('cache_misses', 0) + 1
                return None
            
            # Cache hit!
            self.metadata['cache_hits'] = self.metadata.get('cache_hits', 0) + 1
            self.metadata['api_calls_saved'] = self.metadata.get('api_calls_saved', 0) + 6  # 6 calls per ticker
            
            return cached
            
        except (json.JSONDecodeError, IOError, KeyError):
            return None
    
    def set(self, ticker: str, data: Dict):
        """
        Cache data for a ticker.
        
        Args:
            ticker: Ticker symbol (any format)
            data: Data dict to cache
        """
        normalized = TickerNormalizer.normalize(ticker)
        cache_path = self._get_cache_path(ticker)
        
        # Add cache metadata
        data['_cached_at'] = datetime.now().isoformat()
        data['_ticker_normalized'] = normalized
        
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Update metadata
        self.metadata['total_tickers'] = len(list(self.ticker_cache_dir.glob('*.json')))
        self._save_metadata()
    
    def invalidate(self, ticker: str):
        """Remove cached data for a ticker."""
        cache_path = self._get_cache_path(ticker)
        if cache_path.exists():
            cache_path.unlink()
            self.metadata['total_tickers'] = len(list(self.ticker_cache_dir.glob('*.json')))
            self._save_metadata()
    
    def clear_all(self):
        """Clear entire cache."""
        for cache_file in self.ticker_cache_dir.glob('*.json'):
            cache_file.unlink()
        self.metadata = {
            'created': datetime.now().isoformat(),
            'last_refresh': None,
            'total_tickers': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'api_calls_saved': 0,
        }
        self._save_metadata()
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total_requests = self.metadata.get('cache_hits', 0) + self.metadata.get('cache_misses', 0)
        hit_rate = (self.metadata.get('cache_hits', 0) / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_tickers_cached': self.metadata.get('total_tickers', 0),
            'cache_hits': self.metadata.get('cache_hits', 0),
            'cache_misses': self.metadata.get('cache_misses', 0),
            'hit_rate_pct': round(hit_rate, 1),
            'api_calls_saved': self.metadata.get('api_calls_saved', 0),
            'last_refresh': self.metadata.get('last_refresh'),
        }
    
    def list_cached_tickers(self) -> List[str]:
        """Get list of all cached tickers."""
        tickers = []
        for cache_file in self.ticker_cache_dir.glob('*.json'):
            tickers.append(cache_file.stem)  # Filename without .json
        return sorted(tickers)
    
    def get_stale_tickers(self, max_age_hours: float = None) -> List[str]:
        """Get list of tickers with stale (expired) cache."""
        if max_age_hours is None:
            max_age_hours = self.DEFAULT_TTL_HOURS
        
        stale = []
        for cache_file in self.ticker_cache_dir.glob('*.json'):
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)
                cached_time = datetime.fromisoformat(cached.get('_cached_at', '2000-01-01'))
                if datetime.now() - cached_time > timedelta(hours=max_age_hours):
                    stale.append(cache_file.stem)
            except (json.JSONDecodeError, IOError):
                stale.append(cache_file.stem)
        
        return stale
    
    def mark_refresh_complete(self):
        """Mark that a batch refresh has completed."""
        self.metadata['last_refresh'] = datetime.now().isoformat()
        self._save_metadata()


class CachedFMPFetcher:
    """
    FMP data fetcher with caching layer.
    Wraps the existing FMPDataFetcher with cache lookup.
    """
    
    def __init__(self, cache_dir: str = None):
        self.cache = CacheManager(cache_dir)
        self._fetcher = None  # Lazy load FMP fetcher
    
    @property
    def fetcher(self):
        """Lazy load the FMP fetcher."""
        if self._fetcher is None:
            from fmp_data import FinancialDataProcessor
            self._fetcher = FinancialDataProcessor()
        return self._fetcher
    
    def get_ticker_data(self, ticker: str, force_refresh: bool = False, use_ttm: bool = False) -> Optional[Dict]:
        """
        Get all metrics for a ticker, using cache when available.
        
        Args:
            ticker: Ticker symbol (any format)
            force_refresh: If True, bypass cache and fetch fresh data
        
        Returns:
            Dict with all ticker metrics, or None if fetch failed
        """
        # Normalize ticker
        is_valid, normalized = TickerNormalizer.validate(ticker)
        if not is_valid:
            return {'error': normalized, 'ticker': ticker}
        
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached = self.cache.get(normalized)
            if cached:
                cached['_from_cache'] = True
                return cached
        
        # Cache miss - fetch from API
        try:
            data = self.fetcher.get_all_metrics(normalized, use_ttm=use_ttm)
            
            if data and data.get('data_quality') != 'error':
                data['_from_cache'] = False
                self.cache.set(normalized, data)
            
            return data
            
        except Exception as e:
            return {'error': str(e), 'ticker': normalized}
    
    def batch_refresh(self, tickers: List[str], progress_callback=None) -> Dict:
        """
        Refresh cache for a list of tickers.
        
        Args:
            tickers: List of ticker symbols
            progress_callback: Optional function(current, total, ticker) for progress updates
        
        Returns:
            Dict with refresh statistics
        """
        stats = {
            'total': len(tickers),
            'success': 0,
            'failed': 0,
            'errors': [],
        }
        
        for i, ticker in enumerate(tickers):
            if progress_callback:
                progress_callback(i + 1, len(tickers), ticker)
            
            result = self.get_ticker_data(ticker, force_refresh=True)
            
            if result and result.get('data_quality') not in ['error', 'incomplete']:
                stats['success'] += 1
            else:
                stats['failed'] += 1
                stats['errors'].append({
                    'ticker': ticker,
                    'error': result.get('error', 'Unknown error') if result else 'No data'
                })
        
        self.cache.mark_refresh_complete()
        return stats
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return self.cache.get_stats()


# Convenience functions
def normalize_ticker(ticker: str) -> str:
    """Normalize a ticker symbol."""
    return TickerNormalizer.normalize(ticker)


def validate_ticker(ticker: str) -> Tuple[bool, str]:
    """Validate and normalize a ticker symbol."""
    return TickerNormalizer.validate(ticker)


if __name__ == '__main__':
    # Test the cache manager
    print("="*60)
    print("CACHE MANAGER TEST")
    print("="*60)
    
    # Test ticker normalization
    print("\nTicker Normalization Tests:")
    test_cases = [
        ('BRK.B', 'BRK-B'),
        ('brk-b', 'BRK-B'),
        ('BRKB', 'BRK-B'),
        ('AAPL', 'AAPL'),
        ('bf.a', 'BF-A'),
        ('MSFT', 'MSFT'),
        ('  nvda  ', 'NVDA'),
    ]
    
    for input_ticker, expected in test_cases:
        result = TickerNormalizer.normalize(input_ticker)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {input_ticker:10} → {result:10} (expected: {expected})")
    
    # Test cache manager
    print("\nCache Manager Tests:")
    cache = CacheManager()
    
    # Clear and test
    cache.clear_all()
    print(f"  Cache cleared. Stats: {cache.get_stats()}")
    
    # Test set/get
    test_data = {'ticker': 'AAPL', 'price': 150.00, 'market_cap': 2500000000000}
    cache.set('AAPL', test_data)
    retrieved = cache.get('AAPL')
    print(f"  Set/Get test: {'✓ PASS' if retrieved and retrieved.get('price') == 150.00 else '✗ FAIL'}")
    
    # Test normalization in cache
    cache.set('BRK.B', {'ticker': 'BRK-B', 'price': 350.00})
    retrieved = cache.get('brkb')  # Different format
    print(f"  Normalization test: {'✓ PASS' if retrieved and retrieved.get('price') == 350.00 else '✗ FAIL'}")
    
    print(f"\n  Final stats: {cache.get_stats()}")
    print(f"  Cached tickers: {cache.list_cached_tickers()}")
