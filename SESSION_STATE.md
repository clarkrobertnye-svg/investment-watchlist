# SESSION STATE — Capital Compounders Dashboard
## Last Updated: 2026-02-11 (Session 3)

---

## CURRENT STATUS

### Universe: 29 Buffett Core Compounders (IPAR removed — fashion/taste risk)
### Dashboard: Live at GitHub Pages
- **Repo:** https://github.com/clarkrobertnye-svg/investment-watchlist
- **Live URL:** https://clarkrobertnye-svg.github.io/investment-watchlist/capital_compounders_dashboard.html

### Gate 5: 7-Model IRR Comparison — Operational
- Single consensus formula replaces old 6-model ensemble
- All 7 models agree on same 5-component identity
- Smart asset-light growth fallback solves V/MA/NVDA understatement
- Script: gate5_irr_7models.py

### Pipeline History: 126 → 63 (Buffett Filter) → 36 (7-model consensus) → 30 (final cuts) → 29 (IPAR removed)

---

## 29 BUFFETT CORE COMPOUNDERS (alphabetical)
AAPL, ADBE, ADP, ANET, APH, ASML, AXP, BAH, BKNG, BMI, BRC, COKE, CTAS, HUBB, IESC, IT, KLAC, MA, MSFT, NEU, NSSC, NVDA, NVR, QCOM, RMD, ROL, TT, V, VRSK

### Gate 5 IRR Results — M7 Consensus (sorted by IRR)
| Ticker | Price | M7 IRR | Verdict | Tier |
|--------|-------|--------|---------|------|
| BKNG | $4312 | 46.6% | BUY | Elite |
| NEU | $698 | 39.6% | BUY | Solid |
| BAH | $80 | 36.1% | BUY | High |
| ADBE | $257 | 32.9% | BUY | Elite |
| NVDA | $190 | 30.7% | BUY | Elite |
| COKE | $159 | 30.4% | BUY | Solid |
| BMI | $157 | 30.1% | BUY | High |
| ANET | $141 | 29.9% | BUY | Elite |
| IESC | $514 | 26.0% | BUY | Solid |
| RMD | $260 | 24.5% | BUY | High |
| ADP | $218 | 21.4% | BUY | Elite |
| IT | $162 | 21.3% | BUY | High |
| AXP | $354 | 18.8% | BUY | High |
| VRSK | $174 | 16.9% | BUY | Elite |
| NSSC | $43 | 16.4% | BUY | Elite |
| NVR | $8108 | 16.2% | BUY | Solid |
| MA | $537 | 16.0% | BUY | Elite |
| V | $329 | 15.0% | BUY | Elite |
| MSFT | $404 | 13.0% | WATCH | Elite |
| KLAC | $1480 | 12.1% | WATCH | Elite |
| BRC | $95 | 10.6% | HOLD | Solid |
| ROL | $66 | 9.9% | HOLD | High |
| HUBB | $516 | 9.1% | HOLD | Solid |
| APH | $144 | 9.1% | HOLD | Solid |
| TT | $473 | 8.0% | HOLD | Solid |
| ASML | $1436 | 7.1% | EXPENSIVE | Elite |
| QCOM | $141 | 4.7% | EXPENSIVE | High |
| CTAS | $200 | 1.6% | EXPENSIVE | High |
| AAPL | $276 | 1.1% | EXPENSIVE | High |

**Distribution: 18 BUY, 2 WATCH, 5 HOLD, 4 EXPENSIVE**

---

## SESSION 3 WORK COMPLETED (2026-02-11)

### 1. IRR Formula Audit — Complete
- Audited original gate5_irr_30.py, identified 9 issues ranked by severity
- Critical bugs: no SBC adjustment, M5 not independent, M6 structurally bullish
- Moderate: asset-light reinvestment = 0, arbitrary exit PEs, wrong median calc

### 2. 6-AI Consensus Research — Complete
- Queried Claude, ChatGPT, Gemini, Grok, DeepSeek, Copilot for IRR formulas
- All 6 converged on identical 5-component identity
- Key disagreements: exit PE tiers (25-45x elite), asset-light handling, ROIC caps
- Created IRR_Formula_Comparison.pdf (2-page summary)

### 3. 7-Model IRR Script Built — gate5_irr_7models.py
**7 Models:**
| Model | Name | Unique Feature |
|-------|------|---------------|
| M1 | Claude | Conservative anchor, exit PE capped at current, 20% compression for expensive High-PE |
| M2 | ChatGPT | Clean algebra, zero growth if reinvest≤0, tiered PE midpoints |
| M3 | Gemini | ln-based multiple drift, same tiers as ChatGPT |
| M4 | Grok | PEG-based drift, eps_cagr/ROIC reinvestment proxy, capped at 40% |
| M5 | DeepSeek | 3-criteria tiers (ROIC+GM+OM), PE floor logic |
| M6 | Copilot | Strictest tiers (ROIC≥40% for 25x), institutional framework |
| M7 | Consensus | Best-of-all hybrid (see below) |

### 4. Consensus Formula (M7) — Final Design

```
IRR = SBC-Adjusted FCF Yield
    + Growth Engine
    + Buyback Yield
    + Dividend Yield
    + Multiple Change
```

**Component Details:**
- **FCF Yield:** (FCF_ps × (1 - SBC%)) / Price
- **Growth Engine (3-tier hierarchy):**
  1. If accounting RR > 0 AND produces growth ≥ 50% of EPS CAGR → use ROIC_cap × RR
  2. If EPS CAGR available → use min(EPS_CAGR, 35%) directly (no ROIC cap penalty)
  3. Fallback → min(hist_growth, 15%)
- **Buyback Yield:** (Shares_5yr_ago / Shares_now)^(1/5) - 1
- **Dividend Yield:** Annual dividend / (Price × Shares)
- **Multiple Change:** (Exit_PE / Current_PE)^(1/5) - 1

**Exit PE Tiers (3-criteria):**
| Tier | Criteria | Exit P/E |
|------|----------|----------|
| Elite | ROIC ≥30%, GM ≥50%, OM ≥25% | 28x |
| High | ROIC ≥20%, GM ≥40% | 23x |
| Solid | ROIC ≥15% | 18x |

**High-PE Protection:**
- Elite stocks trading >2x tier PE: exit = max(28, current × 0.75)
- High stocks trading >2x tier PE: exit = max(23, current × 0.80)
- Cheap stocks (PE < tier): exit = tier PE (model expansion)

### 5. Iterative Bug Fixes Applied
1. Gross margin / op margin computed from dollars (not missing ratio fields)
2. Growth cap set at 35% (was uncapped, then 25%)
3. Grok M4 capped at 40% to prevent median pollution
4. EPS fallback uses eps_cagr directly (ROIC cap only on accounting path)
5. Decomposition table mirrors M7 logic exactly
6. High-PE Elite/High stocks get partial compression, not collapse

### 6. IPAR Removed — Fashion/taste risk
Same category as LULU, ULTA, DECK removed in Round 2.

---

## NOTABLE DESIGN DECISIONS

1. **ROIC cap (50%) only applies to accounting reinvestment path.** When using EPS CAGR fallback, proven growth is used directly (capped at 35%). This prevents double-penalizing ultra-high-ROIC asset-light businesses (MA, V, NVDA).

2. **Smart asset-light trigger:** If accounting_growth < 50% of EPS CAGR, the business grows via expensed R&D/SG&A. Fallback to proven EPS growth.

3. **High-PE protection prevents "false EXPENSIVE."** NVDA at 64x forced to 28x = -15% annual drag. With 75% compression floor: exit = 48x, drag = -5.6%. Still conservative but not fictional.

4. **Grok M4 capped at 40%** — uncapped it produces 78% IRR for NVDA. PEG-based drift + no ROIC cap = garbage for extreme-ROIC names.

5. **Gate 5 is still an overlay.** All 126 Quality Universe stocks preserved. Failed tickers not deleted.

---

## STOCKS UNDER REVIEW

- **COKE** (Coca-Cola Consolidated): 30% growth likely non-recurring. 40% GM, 13% OM. Bottler, not Coca-Cola.
- **IESC** (IES Holdings): Electrical contractor, 25% GM, 11% OM. Cyclical infrastructure.
- **NEU** (NewMarket): Petroleum additives. 32% GM, 21% OM. Niche moat but commodity-adjacent.
- **BKNG**: 100% gross margin is FMP data error (real ~80-85%). Doesn't affect tier but is dirty data.

---

## PENDING / NEXT STEPS

- [ ] Decide on COKE, IESC, NEU — keep or cut?
- [ ] Haircut EPS CAGR fallback to 80% of historical? (reduces BUY inflation)
- [ ] Add analyst consensus EPS Next 5Y as cross-check growth input
- [ ] Integrate IRR results into dashboard (new columns: M7 IRR, Verdict, Tier)
- [ ] Monthly refresh cycle implementation
- [ ] Rotate FMP API key (exposed in scripts)
- [ ] Cancel PayPal - Adobe software keeps billing
- [ ] Fix BKNG 100% gross margin data

---

## KEY FILES

### On Mac (~/Documents/capital_compounders/)
- `capital_compounders_dashboard.html` — main dashboard
- `gate5_irr_7models.py` — 7-model IRR script (current)
- `gate5_irr_30.py` — old 6-model script (deprecated)
- `cache/raw/` — FMP financial data per ticker
- `cache/exports/gate5_irr_7models.csv` — IRR results
- `IRR_Formula_Comparison.pdf` — 2-page model comparison
- `SESSION_STATE.md` — this file

### On GitHub (clarkrobertnye-svg/investment-watchlist)
- `capital_compounders_dashboard.html` — deployed dashboard
- `SESSION_STATE.md` — project state doc

### IRR Models Reference
| Model | Name | Formula Type |
|-------|------|-------------|
| M1 | Claude | Conservative, exit PE capped, 30% EPS cap |
| M2 | ChatGPT | Clean algebra, zero growth if RR≤0 |
| M3 | Gemini | ln-based drift, institutional tiers |
| M4 | Grok | PEG-based drift, capped at 40% |
| M5 | DeepSeek | 3-criteria tiers, PE floor |
| M6 | Copilot | Strictest tiers, institutional framework |
| M7 | Consensus | Hybrid: smart growth hierarchy + 3-criteria tiers + high-PE protection |

## DASHBOARD KNOWN FEATURES
- 3yr ROIIC displays ">500%" in green for infinity values
- All columns sortable with click headers
- Dark theme with color-coded metrics
- Tickers link to Yahoo Finance
- No tier/flags columns (removed Session 2)
