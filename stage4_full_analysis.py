"""
FMP Universe Screener - Stage 4: Full Analysis
Runs your complete Capital Compounders model on Stage 3 winners.
Applies all quality filters + calculates IRR.

Usage:
    python3 stage4_full_analysis.py              # Run/resume
    python3 stage4_full_analysis.py --status     # Check progress
    python3 stage4_full_analysis.py --reset      # Start over
"""

import json
import time
from datetime import datetime
from pathlib import Path
from fmp_data import FinancialDataProcessor
from config import FMP_API_KEY

# Files
STAGE3_RESULTS = 'stage3_quality_passed.json'
EXISTING_UNIVERSE = 'capital_compounders_master.csv'
PROGRESS_FILE = 'stage4_progress.json'
RESULTS_FILE = 'stage4_new_opportunities.json'

# Rate limiting (6 calls per ticker)
CALLS_PER_MINUTE = 290
CALLS_PER_TICKER = 6
DELAY = 60 / (CALLS_PER_MINUTE / CALLS_PER_TICKER)  # ~1.2 sec per ticker

def load_progress():
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {
        'completed': [],
        'buy': [],
        'hold': [],
        'filtered': [],
        'errors': [],
        'started': datetime.now().isoformat(),
        'last_update': None
    }

def save_progress(progress):
    progress['last_update'] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)

def passes_filters(t):
    """Apply all quality filters."""
    roic = t.get("roic_3y_avg") or t.get("roic_current") or 0
    roic_ex_gw = t.get("roic_ex_goodwill_3y_avg") or t.get("roic_ex_goodwill") or 0
    inc_roic = t.get("incremental_roic", 0)
    gm = t.get("gross_margin", 0)
    fcf = t.get("fcf_conversion", 0)
    growth = t.get("revenue_growth_3y", 0)
    capex = t.get("capex_to_revenue", 0)
    leverage = t.get("net_debt_ebitda", 0)
    vcr = t.get("value_creation_ratio", 0)
    
    roic_pass = (roic >= 0.20) or (roic_ex_gw >= 0.20)
    capex_pass = (capex <= 0.07) or (inc_roic >= 0.15)
    fcf_pass = (fcf >= 0.80) or (fcf >= 0.60 and inc_roic >= 0.15)
    inc_roic_pass = inc_roic >= -0.05
    vcr_pass = vcr >= 1.0
    
    return roic_pass and gm >= 0.60 and fcf_pass and growth >= 0.09 and capex_pass and leverage <= 3.0 and inc_roic_pass and vcr_pass

def get_filter_failures(t):
    """Get list of failed filters."""
    failures = []
    roic = t.get("roic_3y_avg") or t.get("roic_current") or 0
    roic_ex_gw = t.get("roic_ex_goodwill_3y_avg") or t.get("roic_ex_goodwill") or 0
    inc_roic = t.get("incremental_roic", 0)
    gm = t.get("gross_margin", 0)
    fcf = t.get("fcf_conversion", 0)
    growth = t.get("revenue_growth_3y", 0)
    capex = t.get("capex_to_revenue", 0)
    leverage = t.get("net_debt_ebitda", 0)
    vcr = t.get("value_creation_ratio", 0)
    
    if not ((roic >= 0.20) or (roic_ex_gw >= 0.20)):
        failures.append(f"ROIC {max(roic, roic_ex_gw)*100:.0f}%<20%")
    if gm < 0.60:
        failures.append(f"GM {gm*100:.0f}%<60%")
    if not ((fcf >= 0.80) or (fcf >= 0.60 and inc_roic >= 0.15)):
        failures.append(f"FCF {fcf*100:.0f}%<80%")
    if growth < 0.09:
        failures.append(f"Growth {growth*100:.1f}%<9%")
    if not ((capex <= 0.07) or (inc_roic >= 0.15)):
        failures.append(f"CapEx {capex*100:.1f}%>7%")
    if leverage > 3.0:
        failures.append(f"Debt {leverage:.1f}x>3x")
    if inc_roic < -0.05:
        failures.append(f"IncROIC {inc_roic*100:.0f}%<-5%")
    if vcr < 1.0:
        failures.append(f"VCR {vcr:.1f}x<1.0")
    
    return failures

def select_best_model(t):
    """Select valuation model and calculate IRR."""
    fcf_yield = t.get("fcf_yield") or 0
    ent_yield = t.get("enterprise_yield") or 0
    base_yield = max(fcf_yield, ent_yield)
    
    roic = t.get("roic_3y_avg") or t.get("roic_current") or 0
    roic_ex_gw = t.get("roic_ex_goodwill_3y_avg") or t.get("roic_ex_goodwill") or 0
    growth = t.get("revenue_growth_3y", 0)
    inc_roic = t.get("incremental_roic", 0)
    gm = t.get("gross_margin", 0)
    capex = t.get("capex_to_revenue", 0)
    goodwill_pct = t.get("goodwill_pct", 0)
    
    if inc_roic == 0 or inc_roic < 0.05:
        model = "Mature"
        irr = base_yield + min(growth, 0.10)
    elif growth > 0.25 and roic < 0.15:
        model = "DCF-Fade"
        irr = base_yield + min(growth, 0.15) * 0.70
    elif gm > 0.80 and capex < 0.03:
        model = "Platform"
        irr = base_yield + min(growth, 0.20)
    elif goodwill_pct > 0.30 and roic_ex_gw > roic * 1.5:
        model = "Ex-Goodwill"
        capped_roic_ex_gw = min(roic_ex_gw, 0.30)
        blended_roic = (roic + capped_roic_ex_gw) / 2
        sustainable_g = min(growth, blended_roic * 0.8)
        irr = base_yield + sustainable_g
    elif roic > 0.25 and growth > 0.10:
        model = "Compounder"
        sustainable_g = min(growth, roic * 0.6)
        irr = base_yield + sustainable_g
    else:
        model = "Standard"
        irr = base_yield + min(growth, 0.15)
    
    return model, irr

def run_analysis():
    # Load Stage 3 results
    with open(STAGE3_RESULTS) as f:
        stage3 = json.load(f)
    
    # Load existing universe to exclude
    existing = set()
    if Path(EXISTING_UNIVERSE).exists():
        with open(EXISTING_UNIVERSE) as f:
            existing = set(line.split(',')[1].strip() for line in f.readlines()[1:])
    
    # Get new candidates only
    candidates = [s for s in stage3 if s['symbol'] not in existing]
    symbols = [c['symbol'] for c in candidates]
    
    # Load progress
    progress = load_progress()
    completed = set(progress['completed'])
    remaining = [s for s in symbols if s not in completed]
    
    print("="*60)
    print("STAGE 4: Full Analysis (All Quality Filters + IRR)")
    print("="*60)
    print(f"Stage 3 winners (new): {len(symbols)}")
    print(f"Already completed: {len(completed)}")
    print(f"Remaining: {len(remaining)}")
    print(f"BUY found so far: {len(progress['buy'])}")
    print(f"HOLD found so far: {len(progress['hold'])}")
    print(f"Rate: ~{CALLS_PER_MINUTE/CALLS_PER_TICKER:.0f} tickers/min")
    print(f"ETA: {len(remaining) * DELAY / 60:.1f} minutes")
    print("="*60)
    
    if not remaining:
        print("\n✓ Stage 4 complete!")
        return
    
    print(f"\nStarting in 3 seconds... (Ctrl+C to pause)")
    time.sleep(3)
    
    processor = FinancialDataProcessor()
    start_time = time.time()
    
    for i, symbol in enumerate(remaining):
        total_done = len(completed) + i + 1
        pct = total_done / len(symbols) * 100
        buy_cnt = len(progress['buy'])
        hold_cnt = len(progress['hold'])
        
        print(f"\r[{total_done}/{len(symbols)}] {pct:.1f}% | BUY:{buy_cnt} HOLD:{hold_cnt} | {symbol:<6}", end='', flush=True)
        
        try:
            # Fetch full metrics
            data = processor.get_all_metrics(symbol)
            
            if data and data.get('data_quality') == 'complete':
                # Check filters
                if passes_filters(data):
                    model, irr = select_best_model(data)
                    
                    result = {
                        'symbol': symbol,
                        'name': data.get('company_name', ''),
                        'model': model,
                        'irr': irr,
                        'roic': data.get('roic_current', 0),
                        'roic_3y': data.get('roic_3y_avg', 0),
                        'vcr': data.get('value_creation_ratio', 0),
                        'grossMargin': data.get('gross_margin', 0),
                        'growth': data.get('revenue_growth_3y', 0),
                        'fcfConversion': data.get('fcf_conversion', 0),
                        'marketCap': data.get('market_cap', 0),
                        'price': data.get('price', 0),
                    }
                    
                    if irr >= 0.20:
                        progress['buy'].append(result)
                    elif irr >= 0.12:
                        progress['hold'].append(result)
                    else:
                        progress['filtered'].append({'symbol': symbol, 'reason': f'IRR {irr*100:.0f}%<12%'})
                else:
                    failures = get_filter_failures(data)
                    progress['filtered'].append({'symbol': symbol, 'reason': ', '.join(failures)})
            else:
                progress['errors'].append(symbol)
                
        except Exception as e:
            progress['errors'].append(symbol)
        
        progress['completed'].append(symbol)
        
        if (i + 1) % 20 == 0:
            save_progress(progress)
        
        time.sleep(DELAY)
    
    save_progress(progress)
    
    # Save final results
    results = {
        'buy': sorted(progress['buy'], key=lambda x: x['irr'], reverse=True),
        'hold': sorted(progress['hold'], key=lambda x: x['irr'], reverse=True),
        'summary': {
            'total_screened': len(progress['completed']),
            'buy_count': len(progress['buy']),
            'hold_count': len(progress['hold']),
            'filtered_count': len(progress['filtered']),
            'error_count': len(progress['errors']),
        }
    }
    
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    elapsed = time.time() - start_time
    print(f"\n\n{'='*60}")
    print("STAGE 4 COMPLETE - NEW OPPORTUNITIES FOUND!")
    print("="*60)
    print(f"Analyzed: {len(progress['completed'])}")
    print(f"🟢 BUY: {len(progress['buy'])}")
    print(f"🟡 HOLD: {len(progress['hold'])}")
    print(f"⚪ Filtered: {len(progress['filtered'])}")
    print(f"❌ Errors: {len(progress['errors'])}")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"\nResults saved to: {RESULTS_FILE}")
    
    if progress['buy']:
        print(f"\n🟢 NEW BUY OPPORTUNITIES:")
        print(f"{'Symbol':<8} {'Model':<12} {'IRR':>6} {'VCR':>6} {'ROIC':>6} {'Name':<25}")
        print("-"*70)
        for s in sorted(progress['buy'], key=lambda x: x['irr'], reverse=True)[:15]:
            print(f"{s['symbol']:<8} {s['model']:<12} {s['irr']*100:>5.0f}% {s['vcr']:>5.1f}x {s['roic']*100:>5.0f}% {s['name'][:25]}")

def show_status():
    if not Path(PROGRESS_FILE).exists():
        print("No Stage 4 analysis in progress.")
        return
    
    progress = load_progress()
    
    print("="*60)
    print("STAGE 4 STATUS")
    print("="*60)
    print(f"Started: {progress.get('started', 'Unknown')}")
    print(f"Last update: {progress.get('last_update', 'Unknown')}")
    print(f"Completed: {len(progress['completed'])}")
    print(f"🟢 BUY: {len(progress['buy'])}")
    print(f"🟡 HOLD: {len(progress['hold'])}")
    print(f"⚪ Filtered: {len(progress['filtered'])}")
    print(f"❌ Errors: {len(progress['errors'])}")
    
    if progress['buy']:
        print(f"\nBUY opportunities found:")
        for s in sorted(progress['buy'], key=lambda x: x['irr'], reverse=True)[:10]:
            print(f"  {s['symbol']:<8} IRR:{s['irr']*100:>5.0f}% VCR:{s['vcr']:>4.1f}x {s['name'][:25]}")

def reset_analysis():
    for f in [PROGRESS_FILE, RESULTS_FILE]:
        if Path(f).exists():
            Path(f).unlink()
            print(f"Deleted: {f}")
    print("Stage 4 reset.")

if __name__ == '__main__':
    import sys
    
    if '--status' in sys.argv:
        show_status()
    elif '--reset' in sys.argv:
        reset_analysis()
    else:
        try:
            run_analysis()
        except KeyboardInterrupt:
            print("\n\nPaused. Progress saved. Run again to resume.")
