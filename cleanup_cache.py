#!/usr/bin/env python3
"""
Cleanup script to remove bad/stale/dead tickers from cache.
Run this before regenerating the dashboard.

Usage:
    python3 cleanup_cache.py           # Preview what will be removed
    python3 cleanup_cache.py --delete  # Actually delete the files
"""

import argparse
from pathlib import Path

# Tickers to remove and why
REMOVE_TICKERS = {
    # Acquired / No longer exists
    "AEL": "Acquired by Brookfield Reinsurance (May 2024)",
    
    # Bonds / Debt instruments (not equity)
    "RZB": "Bond/debt instrument, not common stock",
    
    # Stale ticker symbols (company rebranded)
    "ANTM": "Rebranded to ELV (Elevance Health)",
    
    # Value Traps (VCR < 1.2 + declining ROIC trend)
    "UNH": "Value trap: VCR 1.1x, -37% trend, DOJ probe",
    "NKE": "Value trap: VCR 1.0x, -26% trend, negative growth",
    "EW": "Value trap: VCR 1.0x, -34% trend, stagnant",
    "CSX": "Value trap: VCR 1.0x, -12% trend, negative growth",
    "NTDOY": "Value trap: VCR 1.1x, -41% trend, cyclical decline",
    "CCI": "Value destroyer: VCR -0.8x, -927% trend",
    "WOLWF": "Value destroyer: VCR -0.5x, -168% trend",
    "SSDOY": "Value trap: VCR 0.1x, -75% trend, negative growth",
    
    # Pure Insurers (ROIC meaningless, 100% GM data artifact)
    "PNGAY": "Pure insurer: 100% GM, 0.6x VCR, ROIC not applicable",
    "QBEIF": "Pure insurer: 100% GM, 125% ROIC is data noise",
    
    # Managed Care (fails ROIC gate)
    "ELV": "Managed care: 6.4% ROIC fails 20% Stage 2 gate",
}

def main():
    parser = argparse.ArgumentParser(description='Clean bad tickers from cache')
    parser.add_argument('--delete', action='store_true', help='Actually delete files (default is preview)')
    parser.add_argument('--cache-dir', default='cache/ticker_data', help='Cache directory path')
    args = parser.parse_args()
    
    cache_dir = Path(args.cache_dir)
    
    if not cache_dir.exists():
        print(f"❌ Cache directory not found: {cache_dir}")
        return
    
    print("=" * 60)
    print("CACHE CLEANUP" + (" (PREVIEW MODE)" if not args.delete else " (DELETE MODE)"))
    print("=" * 60)
    
    removed = 0
    not_found = 0
    
    for ticker, reason in REMOVE_TICKERS.items():
        cache_file = cache_dir / f"{ticker}.json"
        
        if cache_file.exists():
            if args.delete:
                cache_file.unlink()
                print(f"  🗑️  DELETED: {ticker}.json - {reason}")
            else:
                print(f"  ⚠️  FOUND:   {ticker}.json - {reason}")
            removed += 1
        else:
            print(f"  ✓  Not in cache: {ticker}")
            not_found += 1
    
    print("-" * 60)
    print(f"Summary: {removed} to remove, {not_found} not in cache")
    
    if not args.delete and removed > 0:
        print("\n👉 Run with --delete to actually remove these files:")
        print(f"   python3 cleanup_cache.py --delete")


if __name__ == '__main__':
    main()
