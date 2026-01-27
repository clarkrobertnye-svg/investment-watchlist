# Capital Compounder Investment System

## Overview
Systematic screening system to identify high-quality capital compounders - companies that generate high returns on invested capital and can reinvest at attractive rates.

## Tier 1 Filter Criteria

| Filter | Threshold | Override |
|--------|-----------|----------|
| ROIC | ≥ 20% | OR ROIC ex-Goodwill ≥ 20% |
| Gross Margin | ≥ 60% | None |
| FCF Conversion | ≥ 80% | OR ≥ 60% if Inc ROIC ≥ 15% |
| Revenue Growth | ≥ 9% (3Y CAGR) | None |
| CapEx/Revenue | ≤ 7% | OR Inc ROIC ≥ 15% |
| Net Debt/EBITDA | ≤ 3.0x | None |
| Incremental ROIC | ≥ -5% | None |

### Key Innovations

1. **ROIC ex-Goodwill**: Handles serial acquirers (SPGI, AVGO, INTU) whose reported ROIC is artificially depressed by acquisition goodwill.

2. **Incremental ROIC Override**: Companies with high CapEx or low FCF conversion pass if their incremental investments earn ≥15% returns (META, MSFT, NVO).

3. **Mature Compounder Detection**: Companies with shrinking invested capital but growing profits (ADBE, V, MSCI) are recognized as efficient capital allocators.

4. **Currency Conversion**: International stocks (NVO, HESAY, RELX, etc.) have financials converted to USD for accurate FCF yield comparison.

## Current Results: 30 Capital Compounders

### By Valuation (FCF Yield)

**Attractive (>4%):** ADBE, CRM, ABNB, MORN, BKNG, RELX

**Fair (2.5-4%):** INTU, SPGI, NVO, V, MSCI, META, IDCC, MA, FTNT, LRLCY, PANW, KYCCF, ADSK, SYK

**Premium (<2.5%):** NOW, ANSS, ELF, MSFT, ANET, KLAC, AVGO, HESAY, NVDA, CDNS

## Files

- `config.py` - Filter thresholds and API configuration
- `fmp_data.py` - FMP API data fetcher with currency conversion
- `refresh_cache.py` - Cache refresh utility
- `screen_compounders.py` - Run the Tier 1 screen
- `capital_compounders_master.csv` - Universe of 204 tickers
- `cache/ticker_data/` - Cached financial data (JSON)

## Usage
```bash
# Refresh all data (~15 min)
cut -d',' -f2 capital_compounders_master.csv | tail -n +2 | tr '\n' ' ' | xargs python3 refresh_cache.py --tickers

# Run screen
python3 screen_compounders.py
```

## Last Updated
January 2026
