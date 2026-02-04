# Capital Compounders Session State
**Last Updated:** February 3, 2026  
**Dashboard URL:** https://clarkrobertnye-svg.github.io/investment-watchlist/dashboard49.html  
**Repo:** https://github.com/clarkrobertnye-svg/investment-watchlist

---

## Working Files Inventory

| File | Location | Status |
|------|----------|--------|
| dashboard49.html | repo root | ✅ WORKING - 49 stocks + VCR* column |
| cache_lookup.json | repo root | ✅ 451 tickers with roicAdj |
| capital_compounders_dashboard.html | repo root | Reference (435KB, 200+ stocks) |
| universe_49_final.json | repo root | 49 ticker list |

---

## Features Checklist

### dashboard49.html HAS:
- [x] 49 curated stocks (machines + cows)
- [x] 19 metrics columns including Power*, VCR*, and Moat
- [x] Key Metrics Reference section with formulas
- [x] Column header tooltips (hover for explanation)
- [x] Ticker links to Yahoo Finance
- [x] Working analyze box with 3-tier lookup
- [x] ROIC* (Hidden Compounder) column
- [x] VCR* column (ROIC* ÷ WACC)
- [x] Power* column (ROIIC* × Reinv Rate)
- [x] Moat Trend column (↑/→/↓)
- [x] Complete Key Metrics Reference for all 19 columns
- [x] FMP /stable/ endpoints (NOT /api/v3/)

### Analyze Box 3-Tier Lookup:
1. **49 main stocks** → Full metrics display
2. **451 cached tickers** → Partial metrics from cache_lookup.json
3. **FMP live fetch** → TTM data via /stable/ endpoints

---

## Column Headers (in order)
```
Ticker | 3yr Rev | ROIIC | Rate | Power | Power* | ROIC | ROIC* | Moat | VCR | VCR* | GM | GM Δ3yr | OCF/NI | FCF/Debt | FCF/NI | SH Yield | OCF/CapEx | 3yr ROIIC
```

### Shortened Names:
- "Rate" = Reinvestment Rate
- "Power" = Compounding Power (ROIIC × Reinv Rate)
- "Power*" = Compounding Power* (ROIIC* × Reinv Rate)
- "Moat" = Moat Trend (↑ widening / → stable / ↓ narrowing)

---

## Key Formulas

| Metric | Formula | Target |
|--------|---------|--------|
| ROIC | NOPAT ÷ Invested Capital | ≥20% |
| ROIC* | NOPAT ÷ (IC - Excess Cash) | ≥30% |
| VCR | ROIC ÷ WACC (10%) | ≥1.5x |
| VCR* | ROIC* ÷ WACC (10%) | ≥3x |
| Compounding Power | ROIIC × Reinv Rate | ≥20% |
| Compounding Power* | ROIIC* × Reinv Rate | ≥25% |
| Moat Trend | ROIC* now vs ROIC* 5yr ago | ↑ (>5% improvement) |

### WACC Analysis (Feb 3, 2026)
Universe WACC range: 6.0% - 14.8%
- Min: LNTH 6.0% (β=-0.09)
- Median: 10.0%
- Max: NVDA 14.8% (β=2.31)
- **10% assumption validated** - right at median

**Hidden Compounder:** When ROIC* >> ROIC (excess cash depresses standard ROIC)
- Example: ADP 24% ROIC → 463% ROIC* ($7.8B cash on $8.3B IC)

---

## DO NOT (already working):
- ❌ Recreate the 49-stock list
- ❌ Recreate metrics reference section
- ❌ Recreate column tooltips
- ❌ Change targets (ROIC 20%, GM 30%)
- ❌ Use /api/v3/ FMP endpoints (deprecated, returns 403)

---

## API Keys
- **FMP:** `TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU`

---

## FMP Endpoint Reference (WORKING)
```javascript
// Profile
https://financialmodelingprep.com/stable/profile?symbol=MSFT&apikey=KEY

// Key Metrics TTM (has ROIC, VCR data)
https://financialmodelingprep.com/stable/key-metrics-ttm?symbol=MSFT&apikey=KEY

// Ratios TTM (often empty - don't rely on)
https://financialmodelingprep.com/stable/ratios-ttm?symbol=MSFT&apikey=KEY
```

**Key fields from key-metrics-ttm:**
- `returnOnInvestedCapitalTTM` → ROIC
- `incomeQualityTTM` → OCF/NI
- `capexToOperatingCashFlowTTM` → inverse = OCF/CapEx
- `freeCashFlowYieldTTM` → FCF Yield

---

## Deployment Commands
```bash
cd ~/Documents/capital_compounders
git add .
git commit -m "description"
git push
# Wait 1-2 min for GitHub Pages to update
```

---

## Session History

### Feb 3, 2026
- Fixed analyze box (FMP /api/v3/ → /stable/ migration)
- Added ROIC* column (hidden compounder)
- Added VCR* column (ROIC* ÷ WACC)
- Rebuilt cache_lookup.json with roicAdj field
- Shortened "Comp Power" → "Power", "Reinv Rate" → "Rate"
- **Added Moat Trend column** (↑/→/↓) based on ROIC* 5yr trajectory
  - 39 stocks widening, 3 stable, 1 narrowing (FTNT)
  - Proper apples-to-apples comparison (ROIC* now vs ROIC* 5yr ago)
- Fetched fresh ROIC/ROIC* data from FMP for all 45 stocks
- WACC analysis: universe range 6-15%, median 10% (validates assumption)
- Added VCR* and Moat Trend to Key Metrics Reference
- **Added Power* column** (ROIIC* × Reinv Rate) - true compounding ex-cash
  - Hidden compounders: ADP 120%→490%, COKE 39%→222%, NVDA 18%→33%
  - Overstated: VITL 156%→31%, GWW 29%→16%
- Now 19 columns total, all documented in Key Metrics Reference

### Previous
- Built 49-stock dashboard from 451 universe
- Created metrics reference with formulas
- Added column tooltips
- Integrated Yahoo Finance links

---

## Next Steps / Ideas
- [ ] Fetch remaining 43 of 49 stocks into cache
- [ ] Add sector filter buttons
- [ ] Export to CSV feature
- [ ] Sort persistence across page refresh
