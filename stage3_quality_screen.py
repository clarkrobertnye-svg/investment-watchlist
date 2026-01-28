"""
FMP Universe Screener - Stage 3: Quality Filter
Fetches key-metrics + ratios for MCap > $1B stocks
Filters for: ROIC > 15%, Gross Margin > 50%

Usage:
    python3 stage3_quality_screen.py              # Run/resume
    python3 stage3_quality_screen.py --status     # Check progress
    python3 stage3_quality_screen.py --reset      # Start over
"""

import json
import time
import requests
from datetime import datetime
from pathlib import Path
from config import FMP_API_KEY

# Configuration
MIN_ROIC = 0.15          # 15%
MIN_GROSS_MARGIN = 0.50  # 50%
CALLS_PER_MINUTE = 145   # 2 calls per ticker, stay under 300/min
DELAY = 60 / CALLS_PER_MINUTE

# Files
STAGE2_RESULTS = 'screening_results.json'
EXISTING_UNIVERSE = 'capital_compounders_master.csv'
PROGRESS_FILE = 'stage3_progress.json'
RESULTS_FILE = 'stage3_quality_passed.json'

def load_progress():
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
    progress['last_update'] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)

def fetch_metrics(symbol):
    """Fetch key-metrics and ratios for quality screening."""
    base = 'https://financialmodelingprep.com/stable'
    metrics = {}
    
    try:
        # Key metrics (has ROIC, ROE)
        r1 = requests.get(f'{base}/key-metrics?symbol={symbol}&limit=1&apikey={FMP_API_KEY}', timeout=10)
        if r1.status_code == 200 and r1.json():
            km = r1.json()[0]
            metrics['roic'] = km.get('roic') or km.get('returnOnCapitalEmployed') or 0
            metrics['roe'] = km.get('returnOnEquity') or 0
            metrics['marketCap'] = km.get('marketCap') or 0
        
        time.sleep(DELAY)
        
        # Ratios (has gross margin)
        r2 = requests.get(f'{base}/ratios?symbol={symbol}&limit=1&apikey={FMP_API_KEY}', timeout=10)
        if r2.status_code == 200 and r2.json():
            ratios = r2.json()[0]
            metrics['grossMargin'] = ratios.get('grossProfitMargin') or 0
            metrics['operatingMargin'] = ratios.get('operatingProfitMargin') or 0
            metrics['netMargin'] = ratios.get('netProfitMargin') or 0
        
        return metrics
    except Exception as e:
        return {'error': str(e)}

def run_screening():
    # Load Stage 2 results
    with open(STAGE2_RESULTS) as f:
        stage2 = json.load(f)
    
    # Load existing universe to exclude
    existing = set()
    if Path(EXISTING_UNIVERSE).exists():
        with open(EXISTING_UNIVERSE) as f:
            existing = set(line.split(',')[1].strip() for line in f.readlines()[1:])
    
    # Get new candidates only
    candidates = [s for s in stage2 if s['symbol'] not in existing]
    symbols = [c['symbol'] for c in candidates]
    
    # Create lookup for Stage 2 data
    stage2_lookup = {s['symbol']: s for s in stage2}
    
    # Load progress
    progress = load_progress()
    completed = set(progress['completed'])
    remaining = [s for s in symbols if s not in completed]
    
    print("="*60)
    print("STAGE 3: Quality Screen (ROIC > 15%, GM > 50%)")
    print("="*60)
    print(f"New candidates (not in universe): {len(symbols)}")
    print(f"Already completed: {len(completed)}")
    print(f"Remaining: {len(remaining)}")
    print(f"Passed so far: {len(progress['passed'])}")
    print(f"Rate: ~{CALLS_PER_MINUTE/2:.0f} tickers/min (2 calls each)")
    print(f"ETA: {len(remaining) * 2 * DELAY / 60:.1f} minutes")
    print("="*60)
    
    if not remaining:
        print("\n✓ Stage 3 complete!")
        return
    
    print(f"\nStarting in 3 seconds... (Ctrl+C to pause)")
    time.sleep(3)
    
    start_time = time.time()
    
    for i, symbol in enumerate(remaining):
        total_done = len(completed) + i + 1
        pct = total_done / len(symbols) * 100
        passed_cnt = len(progress['passed'])
        
        print(f"\r[{total_done}/{len(symbols)}] {pct:.1f}% | Passed: {passed_cnt} | {symbol:<6}", end='', flush=True)
        
        metrics = fetch_metrics(symbol)
        
        if 'error' not in metrics:
            roic = metrics.get('roic', 0) or 0
            gm = metrics.get('grossMargin', 0) or 0
            
            if roic >= MIN_ROIC and gm >= MIN_GROSS_MARGIN:
                # Get Stage 2 data
                s2 = stage2_lookup.get(symbol, {})
                progress['passed'].append({
                    'symbol': symbol,
                    'name': s2.get('name', ''),
                    'marketCap': s2.get('marketCap', 0),
                    'price': s2.get('price', 0),
                    'roic': roic,
                    'grossMargin': gm,
                    'roe': metrics.get('roe', 0),
                    'operatingMargin': metrics.get('operatingMargin', 0),
                })
            else:
                progress['failed'].append({
                    'symbol': symbol,
                    'roic': roic,
                    'grossMargin': gm
                })
        else:
            progress['errors'].append(symbol)
        
        progress['completed'].append(symbol)
        
        if (i + 1) % 50 == 0:
            save_progress(progress)
        
        time.sleep(DELAY)
    
    save_progress(progress)
    
    # Save final results
    with open(RESULTS_FILE, 'w') as f:
        json.dump(progress['passed'], f, indent=2)
    
    elapsed = time.time() - start_time
    print(f"\n\n{'='*60}")
    print("STAGE 3 COMPLETE")
    print("="*60)
    print(f"Screened: {len(progress['completed'])}")
    print(f"Passed (ROIC>15%, GM>50%): {len(progress['passed'])}")
    print(f"Failed: {len(progress['failed'])}")
    print(f"Errors: {len(progress['errors'])}")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"\nResults saved to: {RESULTS_FILE}")

def show_status():
    if not Path(PROGRESS_FILE).exists():
        print("No Stage 3 screening in progress.")
        return
    
    progress = load_progress()
    
    print("="*60)
    print("STAGE 3 STATUS")
    print("="*60)
    print(f"Started: {progress.get('started', 'Unknown')}")
    print(f"Last update: {progress.get('last_update', 'Unknown')}")
    print(f"Completed: {len(progress['completed'])}")
    print(f"Passed: {len(progress['passed'])}")
    print(f"Failed: {len(progress['failed'])}")
    print(f"Errors: {len(progress['errors'])}")
    
    if progress['passed']:
        print(f"\nTop 10 Quality Stocks Found:")
        top = sorted(progress['passed'], key=lambda x: x.get('roic', 0), reverse=True)[:10]
        for s in top:
            roic = s.get('roic', 0) * 100
            gm = s.get('grossMargin', 0) * 100
            mcap = s.get('marketCap', 0) / 1e9
            print(f"  {s['symbol']:<6} ROIC:{roic:>5.0f}% GM:{gm:>5.0f}% ${mcap:>6.1f}B")

def reset_screening():
    for f in [PROGRESS_FILE, RESULTS_FILE]:
        if Path(f).exists():
            Path(f).unlink()
            print(f"Deleted: {f}")
    print("Stage 3 reset.")

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
