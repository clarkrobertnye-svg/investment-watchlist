# SESSION STATE — Capital Compounders Dashboard
## Last Updated: 2026-02-11 (Session 2 — Final)

---

## CURRENT STATUS

### Universe: 30 Buffett Core Compounders
### Dashboard: Live at GitHub Pages
- **Repo:** https://github.com/clarkrobertnye-svg/investment-watchlist
- **Live URL:** https://clarkrobertnye-svg.github.io/investment-watchlist/capital_compounders_dashboard.html
- **Dashboard subtitle:** "Buffett Core — 30 Compounders"

### Gate 5: Valuation (6-model IRR) — v3 complete
- All 30 tickers valued with live prices (Feb 11, 2026)
- Quality-adjusted exit multiples (15-35x based on ROIC/growth/margins/FCF)
- Growth-capped forward PE proxy (25% max adjustment)
- Results: 1 BUY, 11 WATCH, 3 HOLD, 15 EXPENSIVE

### Pipeline: 126 → 63 (Buffett Filter) → 36 (7-model consensus) → 30 (final cuts)

---

## 30 BUFFETT CORE COMPOUNDERS
AAPL, ADBE, ADP, ANET, APH, ASML, AXP, BAH, BKNG, BMI, BRC, COKE, CTAS, HUBB, IESC, IPAR, IT, KLAC, MA, MSFT, NEU, NSSC, NVDA, NVR, QCOM, RMD, ROL, TT, V, VRSK

### Gate 5 IRR Results (sorted by median IRR)
| Ticker | Price | Trailing PE | Fwd PE | Exit PE | Median IRR | Verdict |
|--------|-------|------------|--------|---------|-----------|---------|
| IT | $162 | 16.7x | 16.6x | 17x | 22.0% | BUY |
| AXP | $354 | 23.0x | 21.1x | 21x | 17.4% | WATCH |
| ADBE | $257 | 15.4x | 13.9x | 14x | 17.4% | WATCH |
| ADP | $218 | 21.7x | 19.7x | 20x | 15.8% | WATCH |
| QCOM | $141 | 27.9x | 25.6x | 24x | 14.3% | WATCH |
| MA | $537 | 32.5x | 28.6x | 28x | 14.2% | WATCH |
| IPAR | $101 | 19.7x | 15.7x | 16x | 14.0% | WATCH |
| NSSC | $43 | 35.8x | 30.4x | 29x | 13.2% | WATCH |
| BAH | $80 | 11.0x | 9.9x | 10x | 13.0% | WATCH |
| NVR | $8108 | 17.5x | 16.6x | 17x | 12.5% | WATCH |
| NEU | $698 | 14.5x | 12.7x | 13x | 12.1% | WATCH |
| BMI | $157 | 32.6x | 27.5x | 26x | 12.1% | WATCH |
| BKNG | $4312 | 24.6x | 19.7x | 20x | 11.7% | HOLD |
| RMD | $260 | 27.2x | 21.9x | 22x | 11.6% | HOLD |
| V | $329 | 32.2x | 28.6x | 26x | 9.6% | HOLD |
| Others | — | — | — | — | <8% | EXPENSIVE |

### Known Issue: Forward PE Accuracy
Our growth-adjusted trailing PE overshoots for high-growth names:
- NVDA: our 51.2x vs real ~24.5x forward
- ASML: our 55x vs real ~32x
- ANET: our 49.6x vs real ~42x
- FMP free plan lacks analyst estimates endpoint
- Need: upgrade FMP, scrape alternative source, or use ratios-ttm more aggressively

---

## PENDING / NEXT STEPS
- [ ] Forward PE fix (real analyst estimates)
- [ ] Add IRR% column to dashboard (clean number, color-coded, no verdict)
- [ ] Growth regimes: AI-era vs legacy compounders
- [ ] FMP ratios-ttm integration for fresher TTM EPS/FCF
- [ ] Monthly refresh cycle
- [ ] Rotate FMP API key (exposed)
- [ ] Cancel PayPal - Adobe billing

---

## KEY FILES (~/Documents/capital_compounders/)
- capital_compounders_dashboard.html — dashboard (30 Buffett Core)
- gate5_irr_30.py — 6-model IRR script v3
- cache/raw/ — FMP financial data per ticker
- cache/exports/gate5_irr_30.csv — IRR results
- cache/exports/gate5_irr_30.json — IRR results JSON
- SESSION_STATE.md — this file

## IRR MODELS
| # | Name | Formula | Type |
|---|------|---------|------|
| M1 | Gemini Quick | FCF Yield + (ROIC x RR) +/- Multiple | Fundamental |
| M2 | Claude EPS | (Future EPS x Exit PE / Price)^(1/5) - 1 | Earnings |
| M3 | Copilot Scalable | OE x (1+g)^5 x Terminal PE / Price | Reinvestment |
| M4 | Grok DCF | IRR solving NPV of FCFs + TV = Price | Cash Flow |
| M5 | DeepSeek Weighted | 60% DCF + 40% EPV + Stress | Blended |
| M6 | Perplexity Quick | FCF Yield + (ROIC x 0.35) - 1.5% | Quick Check |

## QUALITY-ADJUSTED EXIT PE
Score (0-100): ROIC(25) + Growth(25) + GM(25) + FCF Quality(25)
Maps 15x (score 20) to 35x (score 100). Capped at forward PE (no expansion).

## DASHBOARD FEATURES
- 30 Buffett Core, dark theme, sortable columns
- Tickers link to Yahoo Finance
- 3yr ROIIC displays ">500%" for infinity values
