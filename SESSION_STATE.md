# Capital Compounders - Session State

**Last Updated:** February 3, 2026

## ⚠️ READ THIS FIRST
Before making ANY changes, check what already exists. DO NOT rebuild features that work.

---

## Working Files

| File | Purpose | Status |
|------|---------|--------|
| `dashboard49.html` | Main dashboard (49 stocks) | ✅ Deployed to GitHub Pages |
| `capital_compounders_dashboard.html` | Full dashboard with working analyze box | ✅ Working locally |
| `cache_lookup.json` | 451 ticker cache for analyze | ✅ On GitHub |
| `cache/ticker_data/` | 451 individual ticker JSON files | ✅ Local only |

---

## Features Inventory

### dashboard49.html HAS:
- [x] 49 curated high-conviction stocks
- [x] 14 metrics columns (3yr Rev, ROIIC, Reinv Rate, Comp Power, ROIC, VCR, GM, GM Δ3yr, OCF/NI, FCF/Debt, FCF/NI, SH Yield, OCF/CapEx, 3yr ROIIC)
- [x] Key Metrics Reference section with formulas
- [x] Column header tooltips (data-tooltip with formulas)
- [x] Ticker links to Yahoo Finance
- [x] Updated targets: ROIC ≥20%, GM ≥30%, no target on SH Yield
- [x] Sortable columns
- [x] Search/filter box
- [ ] Working analyze box with FMP fallback ❌ BROKEN

### capital_compounders_dashboard.html HAS:
- [x] Working analyze box (cache → FMP fallback)
- [x] FMP /stable/ endpoints
- [x] 200+ stocks
- [ ] Latest metrics reference section ❌ OUTDATED
- [ ] 49 curated stocks ❌ HAS MORE

---

## What NEEDS to be merged:

**FROM capital_compounders_dashboard.html:**
- `analyzeTicker()` function
- FMP API integration with /stable/ endpoints
- Cache lookup logic

**INTO dashboard49.html:**
- Keep all existing features
- Add working analyze box

---

## Key Files & Locations

```
~/Documents/capital_compounders/
├── dashboard49.html              # Current main (needs analyze fix)
├── capital_compounders_dashboard.html  # Has working analyze
├── cache_lookup.json             # 451 tickers for quick lookup
├── cache/
│   ├── ticker_data/              # 451 individual JSONs
│   └── metadata.json
└── SESSION_STATE.md              # THIS FILE
```

**GitHub Pages:** https://clarkrobertnye-svg.github.io/investment-watchlist/dashboard49.html

---

## API Keys

- **FMP:** TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU

---

## DO NOT:
- ❌ Recreate the 49-stock list
- ❌ Recreate the metrics reference section
- ❌ Recreate column tooltips
- ❌ Change targets (ROIC 20%, GM 30%)
- ❌ Remove Yahoo Finance links from tickers

---

## Deployment Checklist

1. Edit files in `~/Documents/capital_compounders/`
2. Test locally: `open dashboard49.html`
3. Push to GitHub:
   ```bash
   cd ~/Documents/capital_compounders
   git add .
   git commit -m "description"
   git push
   ```
4. Wait 1-2 min for GitHub Pages
5. Test: https://clarkrobertnye-svg.github.io/investment-watchlist/dashboard49.html

---

## Next Steps (as of Feb 3)

1. [ ] Merge working analyze box into dashboard49.html
2. [ ] Test all features work together
3. [ ] Push to GitHub
4. [ ] Share with friends/family for feedback
