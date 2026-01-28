"""
FMP Universe Screener - Stage 2: Filter by Market Cap
Fetches quotes for all candidates, filters to MCap > $1B
Saves progress and can resume if interrupted.

Usage:
    python3 universe_screener.py              # Run/resume screening
    python3 universe_screener.py --status     # Check progress
    python3 universe_screener.py --reset      # Start over
"""

import json
import time
import requests
from datetime import datetime
from pathlib import Path
from config import FMP_API_KEY

# Configuration
MIN_MARKET_CAP = 1_000_000_000  # $1B
CALLS_PER_MINUTE = 290  # Stay under 300 limit
DELAY = 60 / CALLS_PER_MINUTE  # ~0.2 seconds

# Files
CANDIDATES_FILE = 'fmp_stock_candidates.json'
PROGRESS_FILE = 'screening_progress.json'
RESULTS_FILE = 'screening_results.json'

def load_progress():
    """Load progress from file or initialize."""
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {
        'completed': [],
        'passed': [],
        'failed': [],
        'errors': [],
        'started': datetime.now().isoformat(),
        'last_update': None
    }

def save_progress(progress):
    """Save progress to file."""
    progress['last_update'] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)

def fetch_quote(symbol):
    """Fetch quote for a single symbol."""
    url = f'https://financialmodelingprep.com/stable/quote?symbol={symbol}&apikey={FMP_API_KEY}'
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                return data[0]
        return None
    except Exception as e:
        return {'error': str(e)}

def run_screening():
    """Run the market cap screening."""
    # Load candidates
    with open(CANDIDATES_FILE) as f:
        candidates = json.load(f)
    
    symbols = [c['symbol'] for c in candidates]
    
    # Load progress
    progress = load_progress()
    completed = set(progress['completed'])
    
    # Find remaining
    remaining = [s for s in symbols if s not in completed]
    
    print("="*60)
    print("FMP UNIVERSE SCREENER - Stage 2: Market Cap Filter")
    print("="*60)
    print(f"Total candidates: {len(symbols)}")
    print(f"Already completed: {len(completed)}")
    print(f"Remaining: {len(remaining)}")
    print(f"Passed so far: {len(progress['passed'])} (MCap > ${MIN_MARKET_CAP/1e9:.0f}B)")
    print(f"Rate: {CALLS_PER_MINUTE}/min")
    print(f"ETA: {len(remaining) * DELAY / 60:.1f} minutes")
    print("="*60)
    
    if not remaining:
        print("\n✓ Screening complete!")
        return
    
    print(f"\nStarting in 3 seconds... (Ctrl+C to pause)")
    time.sleep(3)
    
    start_time = time.time()
    
    for i, symbol in enumerate(remaining):
        # Progress bar
        total_done = len(completed) + i + 1
        pct = total_done / len(symbols) * 100
        passed_cnt = len(progress['passed'])
        
        print(f"\r[{total_done}/{len(symbols)}] {pct:.1f}% | Passed: {passed_cnt} | Current: {symbol:<6}", end='', flush=True)
        
        # Fetch quote
        quote = fetch_quote(symbol)
        
        if quote and 'error' not in quote:
            mcap = quote.get('marketCap', 0) or 0
            if mcap >= MIN_MARKET_CAP:
                progress['passed'].append({
                    'symbol': symbol,
                    'name': quote.get('name', ''),
                    'marketCap': mcap,
                    'price': quote.get('price', 0),
                    'exchange': quote.get('exchange', '')
                })
            else:
                progress['failed'].append(symbol)
        else:
            progress['errors'].append(symbol)
        
        progress['completed'].append(symbol)
        
        # Save progress every 100 symbols
        if (i + 1) % 100 == 0:
            save_progress(progress)
        
        # Rate limiting
        time.sleep(DELAY)
    
    # Final save
    save_progress(progress)
    
    # Save results
    with open(RESULTS_FILE, 'w') as f:
        json.dump(progress['passed'], f, indent=2)
    
    elapsed = time.time() - start_time
    print(f"\n\n{'='*60}")
    print("SCREENING COMPLETE")
    print("="*60)
    print(f"Total screened: {len(progress['completed'])}")
    print(f"Passed (MCap > $1B): {len(progress['passed'])}")
    print(f"Failed: {len(progress['failed'])}")
    print(f"Errors: {len(progress['errors'])}")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"\nResults saved to: {RESULTS_FILE}")

def show_status():
    """Show current screening status."""
    if not Path(PROGRESS_FILE).exists():
        print("No screening in progress.")
        return
    
    progress = load_progress()
    with open(CANDIDATES_FILE) as f:
        candidates = json.load(f)
    
    print("="*60)
    print("SCREENING STATUS")
    print("="*60)
    print(f"Started: {progress.get('started', 'Unknown')}")
    print(f"Last update: {progress.get('last_update', 'Unknown')}")
    print(f"Total candidates: {len(candidates)}")
    print(f"Completed: {len(progress['completed'])}")
    print(f"Remaining: {len(candidates) - len(progress['completed'])}")
    print(f"Passed: {len(progress['passed'])}")
    print(f"Failed: {len(progress['failed'])}")
    print(f"Errors: {len(progress['errors'])}")
    
    if progress['passed']:
        print(f"\nTop 10 by Market Cap:")
        top = sorted(progress['passed'], key=lambda x: x.get('marketCap', 0), reverse=True)[:10]
        for s in top:
            print(f"  {s['symbol']:<6} ${s['marketCap']/1e9:>7.1f}B  {s.get('name', '')[:30]}")

def reset_screening():
    """Reset screening progress."""
    for f in [PROGRESS_FILE, RESULTS_FILE]:
        if Path(f).exists():
            Path(f).unlink()
            print(f"Deleted: {f}")
    print("Screening reset. Run again to start fresh.")

if __name__ == '__main__':
    import sys
    
    if '--status' in sys.argv:
        show_status()
    elif '--reset' in sys.argv:
        reset_screening()
    else:
        try:
            run_screening()
        except KeyboardInterrupt:
            print("\n\nPaused. Run again to resume.")
