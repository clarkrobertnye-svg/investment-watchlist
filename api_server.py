"""
Capital Compounder Investment System - API Server
Flask API for serving cached ticker data to the dashboard.

Endpoints:
    GET /api/analyze/<ticker>  - Get analysis for a ticker
    GET /api/portfolio         - Get current portfolio data
    GET /api/cache/stats       - Get cache statistics
    POST /api/cache/refresh    - Trigger cache refresh (admin only)

Run with:
    python api_server.py                  # Development mode
    gunicorn api_server:app -w 4          # Production mode
"""

import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime

from cache_manager import CachedFMPFetcher, CacheManager, TickerNormalizer
from tier1_filter import apply_tier1_filters
from tier2_scorer import calculate_tier2_score
from tier3_valuation import DCFValuation

app = Flask(__name__)
CORS(app)  # Enable CORS for dashboard

# Initialize components
cache_fetcher = CachedFMPFetcher()
valuator = DCFValuation()

# Excluded sectors (per investment charter)
EXCLUDED_SECTORS = {
    'Financial Services': 'Banks/financials excluded - difficult to analyze ROIC',
    'Energy': 'Energy sector excluded - commodity-driven, unpredictable FCF',
    'Utilities': 'Utilities excluded - regulated returns, limited compounding',
    'Real Estate': 'REITs excluded - different capital structure',
}


def analyze_ticker(ticker: str) -> dict:
    """
    Run full analysis pipeline on a ticker.
    Returns analysis results including tier classification and valuation.
    """
    # Normalize ticker
    is_valid, normalized = TickerNormalizer.validate(ticker)
    if not is_valid:
        return {
            'error': True,
            'message': f'Invalid ticker format: {ticker}',
            'ticker': ticker,
        }
    
    ticker = normalized
    display_ticker = TickerNormalizer.get_display_format(ticker)
    
    # Fetch data (from cache or API)
    data = cache_fetcher.get_ticker_data(ticker)
    
    if not data:
        return {
            'error': True,
            'message': f'Unable to fetch data for {display_ticker}',
            'ticker': display_ticker,
        }
    
    if data.get('error'):
        return {
            'error': True,
            'message': data.get('error'),
            'ticker': display_ticker,
        }
    
    if data.get('data_quality') == 'incomplete':
        return {
            'error': True,
            'message': f'Incomplete data available for {display_ticker}',
            'ticker': display_ticker,
        }
    
    # Check for excluded sectors
    sector = data.get('sector', '')
    if sector in EXCLUDED_SECTORS:
        return {
            'ticker': display_ticker,
            'name': data.get('company_name', ''),
            'sector': sector,
            'action': 'EXCLUDED',
            'excluded': True,
            'exclusion_reason': EXCLUDED_SECTORS[sector],
            'price': data.get('price', 0),
            'market_cap': data.get('market_cap', 0),
            'from_cache': data.get('_from_cache', False),
        }
    
    # Run Tier 1 filters
    tier1_pass, tier1_failures = apply_tier1_filters(data)
    
    if not tier1_pass:
        return {
            'ticker': display_ticker,
            'name': data.get('company_name', ''),
            'sector': sector,
            'action': 'REVIEW',
            'tier': 'FAILED',
            'tier1_pass': False,
            'tier1_failures': tier1_failures,
            'price': data.get('price', 0),
            'market_cap': data.get('market_cap', 0),
            'incremental_roic': data.get('incremental_roic'),
            'revenue_growth_3y': data.get('revenue_growth_3y'),
            'from_cache': data.get('_from_cache', False),
        }
    
    # Run Tier 2 scoring
    tier2_result = calculate_tier2_score(data)
    tier_label = tier2_result.get('tier_label', 'REVIEW')
    total_score = tier2_result.get('total_score', 0)
    
    # Run Tier 3 valuation (only for ELITE+)
    valuation = {}
    if tier_label in ['EXCEPTIONAL', 'ELITE']:
        import pandas as pd
        row = pd.Series({**data, **tier2_result})
        valuation = valuator.value_company(row)
    
    # Determine action signal
    irr = valuation.get('implied_irr', 0)
    mos = valuation.get('margin_of_safety', 0)
    
    if tier_label not in ['EXCEPTIONAL', 'ELITE']:
        action = 'REVIEW'
    elif irr >= 15 and mos >= 10:
        action = 'BUY'
    elif irr >= 10:
        action = 'HOLD'
    elif irr < 10 or mos < -20:
        action = 'SELL'
    else:
        action = 'HOLD'
    
    return {
        'ticker': display_ticker,
        'name': data.get('company_name', ''),
        'sector': sector,
        'industry': data.get('industry', ''),
        'price': data.get('price', 0),
        'market_cap': data.get('market_cap', 0),
        
        # Tier 1
        'tier1_pass': True,
        
        # Tier 2
        'tier': tier_label,
        'score': total_score,
        
        # Key metrics
        'incremental_roic': data.get('incremental_roic'),
        'revenue_growth_3y': data.get('revenue_growth_3y'),
        'fcf_conversion': data.get('fcf_conversion'),
        'gross_margin': data.get('gross_margin'),
        'roic_wacc_spread': data.get('roic_wacc_spread'),
        
        # Valuation
        'intrinsic_value': valuation.get('intrinsic_value'),
        'irr': irr,
        'mos': mos,
        'buy_below': valuation.get('buy_15_price'),
        'action': action,
        
        # Meta
        'from_cache': data.get('_from_cache', False),
        'analyzed_at': datetime.now().isoformat(),
    }


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.route('/api/analyze/<ticker>', methods=['GET'])
def api_analyze(ticker):
    """Analyze a single ticker."""
    try:
        result = analyze_ticker(ticker)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'error': True,
            'message': str(e),
            'ticker': ticker,
        }), 500


@app.route('/api/portfolio', methods=['GET'])
def api_portfolio():
    """Get current portfolio data (from latest dashboard JSON)."""
    try:
        import json
        dashboard_file = os.path.join(os.path.dirname(__file__), 'output', 'top13_dashboard.json')
        
        if os.path.exists(dashboard_file):
            with open(dashboard_file, 'r') as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({'error': True, 'message': 'Portfolio data not found'}), 404
            
    except Exception as e:
        return jsonify({'error': True, 'message': str(e)}), 500


@app.route('/api/cache/stats', methods=['GET'])
def api_cache_stats():
    """Get cache statistics."""
    try:
        stats = cache_fetcher.get_cache_stats()
        stats['cached_tickers'] = cache_fetcher.cache.list_cached_tickers()[:50]  # First 50
        stats['total_cached'] = len(cache_fetcher.cache.list_cached_tickers())
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': True, 'message': str(e)}), 500


@app.route('/api/cache/check/<ticker>', methods=['GET'])
def api_cache_check(ticker):
    """Check if a ticker is in cache."""
    try:
        normalized = TickerNormalizer.normalize(ticker)
        cached = cache_fetcher.cache.get(normalized)
        return jsonify({
            'ticker': ticker,
            'normalized': normalized,
            'in_cache': cached is not None,
            'cached_at': cached.get('_cached_at') if cached else None,
        })
    except Exception as e:
        return jsonify({'error': True, 'message': str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
    })


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    # Development server
    print("="*60)
    print("CAPITAL COMPOUNDERS API SERVER")
    print("="*60)
    print("\nEndpoints:")
    print("  GET  /api/analyze/<ticker>  - Analyze a ticker")
    print("  GET  /api/portfolio         - Get portfolio data")
    print("  GET  /api/cache/stats       - Cache statistics")
    print("  GET  /api/cache/check/<ticker> - Check if ticker is cached")
    print("  GET  /health                - Health check")
    print("\nStarting development server on http://localhost:5000")
    print("-"*60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
