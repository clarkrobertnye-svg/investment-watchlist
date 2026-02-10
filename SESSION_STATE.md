# SESSION_STATE.md — Capital Compounders Project
**Last Updated:** 2026-02-10 (Session 15-16)
**Project Directory:** `~/Documents/capital_compounders/`

---

## Current Status
- **Unified Portfolio:** 24 investable compounders (9 large-cap + 15 small-cap) from 2,430 stocks screened
- **6-Model IRR Comparison Tool:** Built and tested across all 24 stocks
- **Final Deliverable:** `Capital_Compounders_Unified_Shortlist.docx` — landscape format with full thesis per position

---

## Universe & Screening

### Large-Cap ($10B+): 994 stocks → 9 investable
AXP, LULU, DDS, DECK, PYPL, BAH, BLD, ADBE, CSL

### Small-Cap ($800M–$10B): 1,444 stocks → 15 investable
CROX, LRN, PRI, ALRM, PRDO, PAYC, ETSY, IPAR, POOL, HALO, IDCC, ASO, NEU, MORN, SKY

### Watchlist (Marginal 12–15% IRR)
Large-cap: MA, ADP, WSO, RMD, CAT
Small-cap: SKY, EAT, IBP, XPEL, FDS

### CBT was in the small-cap 15 but is a cyclical-at-peak concern

---

## 5-Gate Screening Methodology (v4.1)

| Gate | Test | Threshold |
|------|------|-----------|
| 1. Quality | Gross Margin, ROIC | GM > 15%, 3yr avg or current ROIC >= 12% or >= 18% |
| 2. Engine | TVCR (Power + Capital Return Yield) | >= 20% |
| 3. Proof | Best of NOPAT/sh or FCF/sh CAGR | >= 15% |
| 4. Health | FCF/NI, Leverage | FCF/NI >= 70%, ND/EBITDA <= 2.5x (3.0x escape) |
| 5. IRR | Base-case IRR from DCF model | >= 15% pass, 12-15% marginal |

### Tier Classification
- **Tier 1 Machine:** Passes all gates, flags <= 2
- **Tier 2 Cash Cow:** Passes gates but SBC/FCF > 25% or IC < $1B instability
- **Tier 3 Special Situation:** Passes with 3+ flags
- **Tier 4 Exclude:** Fails any gate

### Key Metrics (v3 methodology)
- **IC** = Total Debt + Total Equity + Capital Lease Obligations - Cash
- **NOPAT** = Operating Income x (1 - Effective Tax Rate)
- **ROIIC** = deltaNOPAT / deltaIC (cumulative, 3yr or 5yr)
- **Reinvestment Rate** = deltaIC / Cumulative NOPAT (capped at 200%)
- **Power** = ROIIC (capped 350%) x Reinvestment Rate
- **Capital Return Yield** = (Avg Buybacks + Avg Dividends) / Beginning IC
- **TVCR** = Power + Capital Return Yield
- **Per-Share CAGRs:** NOPAT/sh, FCF/sh, SBC-adj FCF/sh, Revenue/sh, EPS (5yr, fallback 3yr)

---

## 7 IRR Models (from 7 AI Partners)

All have been pitched and 6 are implemented in irr_6_models_compare.py. ChatGPT Model 7 was pitched but not yet coded into the comparison tool.

| # | Model | Creator | Type | Formula |
|---|-------|---------|------|---------|
| 1 | Gemini Quick | Gemini | Additive | FCF Yield + (ROIIC x Reinvest Rate) + SH Yield; SBC invalidation >40% |
| 2 | Claude EPS Power | Claude | Additive-DCF | (Future EPS x Exit PE / Price)^(1/5) - 1 |
| 3 | Copilot Scalable | Copilot | Additive | TVCR + Owner Earnings Yield + Multiple Change |
| 4 | Grok Full DCF | Grok | DCF solve | Sum FCF_t/(1+r)^t + TV/(1+r)^N = Price; fade ROIIC to WACC |
| 5 | DeepSeek Weighted | DeepSeek | Blended | 60% DCF + 40% EPV + Stress Tests |
| 6 | Perplexity Quick | Perplexity | Additive | FCF Yield + (ROIC_ex_cash x 0.35) - 1.5% |
| 7 | ChatGPT Intrinsic | ChatGPT | Additive | (ROIIC x Reinvest) + CR Yield +/- Valuation Effect via ln(Exit/Entry)/N |

### Model Type Split
- **Additive (5 models):** ChatGPT, Gemini, Copilot, DeepSeek, Perplexity — IRR = yield + growth + adjustment
- **DCF solve-for-rate (2 models):** Grok, Claude — find discount rate where PV of projected CFs = price
- These are fundamentally different approaches: additive is faster/transparent, DCF is more rigorous but sensitive to projection assumptions

### Current Gate 5 Implementation (in screener)
Uses a DCF solve-for-rate with SBC-adjusted FCF/share as starting point. Growth = historical SBC-adj FCF/sh CAGR, capped at 30%. Three scenarios (bear/base/bull). 10-year horizon: 5yr growth + 5yr fade to 3%.

### Known Issues from 24-Stock Comparison Run
1. **Model 1 (Gemini) breaks on buyback machines** — ADBE 1.2%, DECK -11.9%, AXP 6.9%, DDS 4.0%, IDCC 7.8%. Negative reinvest rate zeroes out growth engine. Needs capital return term.
2. **Model 6 (Perplexity) systematically conservative** — sole holdout on 11/24 stocks. 0.35 ROIC multiplier caps upside. Good floor, bad signal.
3. **Model 2 (Claude EPS) breaks on volatile EPS** — PYPL shows 7% despite 14% FCF yield. Exit PE cap at 25 inflates cheap stocks.
4. **Model 4 (Grok DCF) consistently highest** — 20x terminal multiple is aggressive. Always most optimistic.
5. **Model 5 (DeepSeek) best balanced** — 60/40 blend anchors against overpaying for growth.
6. **30% growth cap flattens genuinely different profiles** — CROX shows identical IRR across all 5 growth inputs because all >30%. Same for LRN, DECK, ALRM.
7. **HALO data problem** — all per-share CAGRs N/A except revenue. Only 2 of 6 models ran.

### 24-Stock 6-Model Consensus Results
| Ticker | Verdict | Models >= 15% | Median IRR |
|--------|---------|---------------|------------|
| CROX | HIGH | 6/6 | 58.1% |
| LULU | HIGH | 6/6 | 31.3% |
| LRN | HIGH | 5/6 | 36.1% |
| PAYC | HIGH | 5/6 | 30.0% |
| DDS | HIGH | 4/6 | 29.7% |
| AXP | HIGH | 4/6 | 30.8% |
| ALRM | HIGH | 5/6 | 30.0% |
| DECK | HIGH | 5/6 | 30.0% |
| CBT | HIGH | 5/6 | 29.3% |
| ETSY | HIGH | 5/6 | 26.3% |
| BAH | HIGH | 5/6 | 24.3% |
| BLD | HIGH | 5/6 | 26.9% |
| PYPL | HIGH | 4/6 | 27.0% |
| PRI | HIGH | 4/6 | 27.3% |
| IDCC | HIGH | 4/6 | 28.6% |
| PRDO | HIGH | 5/6 | 25.5% |
| IPAR | HIGH | 5/6 | 23.5% |
| ADBE | HIGH | 5/6 | 20.9% |
| NEU | HIGH | 4/6 | 21.2% |
| POOL | HIGH | 5/6 | 20.1% |
| MORN | HIGH | 4/6 | 17.1% |
| CSL | MIXED | 3/6 | 16.9% |
| ASO | MIXED | 3/6 | 22.2% |
| HALO | WEAK | 1/2 | 30.6% |

---

## Growth Rates & Caps

### Per-Share Growth Inputs (used by growth-dependent models)
5 independent growth rates calculated for each stock:
1. SBC-adjusted FCF/share CAGR (primary)
2. FCF/share CAGR
3. NOPAT/share CAGR
4. Revenue/share CAGR
5. EPS CAGR

### Current Cap: Hard 30% on all growth rates
- 29 of 55 tested stocks (53%) hit the cap
- All capped stocks project at identical 22.5% base growth (30% x 0.75 base multiplier)
- Phase 1 growth floor at 3% (even if historical x multiplier is tiny/negative)
- Data years capped at 6

### Other Caps in System
- ROIIC capped at 100% in screener (for scoring/Power calc)
- Maintenance capex capped at depreciation
- Reinvestment Rate capped at 200%

### Proposed Tiered Cap (not yet implemented)
| Hist Growth | Cap | Base (x0.75) | Rationale |
|-------------|-----|-------------|-----------|
| >100% | 30% | 22.5% | Clearly cyclical/unsustainable |
| 50-100% | 40% | 30.0% | Hyper-growth, some fade expected |
| 30-50% | Actual | 22.5-37.5% | Structural compounders, use real rate |
| <30% | Actual | Actual x 0.75 | Already conservative |

---

## SBC/FCF Benchmarks
| Ticker | SBC/FCF | Category |
|--------|---------|----------|
| MA | 3.5% | Negligible |
| ADP | 5.6% | Negligible |
| NVDA | 7.8% | Modest |
| MSFT | 16.7% | Moderate |
| ADBE | 19.7% | Moderate |
| CVLT | 55.6% | Majority phantom — excluded |

CVLT Gate 5 result: 12.1% base IRR (marginal) at 43.9x SBC-adjusted P/FCF. Business is elite (171% ROIC) but shareholders get <45 cents per dollar of reported FCF.

---

## Red Flag Categories (used for filtering Gate 5 passers)
1. **Model artifacts** (0.0x P/FCF): SFB, DFH, AN, TBBK, USLM, TCBK, NIC, TREX, RH, BOOT
2. **Financial sector** (FCF model unreliable): OZK, AX, NMIH, OFG, CASH, MBWM, KNSL, PLMR, RLI, HGTY
3. **Cyclicals at peak**: CALM, MATX, CBT, LPX
4. **Extreme flags**: CCB (6F), PLMR (5F), CASH (5F), LQDT (5F), CPRX (4F)
5. **N/A historical growth** -> 22.5% default assumed
6. **High SBC**: DBX (39.8%), ETSY (38.3%), PIPR (34.7%), CARG (34.5%), DAVE (29.9%)

---

## Key Files

### Scripts
| File | Purpose |
|------|---------|
| capital_compounders_v41_screener.py | Gates 1-4 screener. Supports --tickers-file and --export-tag |
| capital_compounders_gate5_irr.py | Gate 5 DCF IRR. Supports --from-screener, --export-tag, --live |
| irr_6_models_compare.py | NEW — Runs all 6 IRR models x 5 growth inputs per stock |
| capital_intensity_v4.py | FMP data fetcher, populates cache/raw/ |
| fetch_smallcap_universe.py | Small-cap universe builder ($800M-$10B) |

### Data
| File | Contents |
|------|----------|
| cache/raw/ | FMP API responses per ticker (profile, income, cashflow, balance, metrics) |
| cache/exports/v41_screener_smallcap.csv | 112 small-cap Gate 1-4 passers |
| cache/exports/gate5_irr_smallcap_LIVE.csv | 59 small-cap Gate 5 passers |
| smallcap_universe.json | 1,444 filtered $800M-$10B stocks |
| smallcap_tickers.txt | 1,444 ticker list |
| irr_6models_full24.txt | Full 24-stock x 6-model comparison output |

### Deliverables
| File | Contents |
|------|----------|
| Capital_Compounders_Unified_Shortlist.docx | 24-stock portfolio, conviction tiers, sector analysis |

---

## Dashboard
https://clarkrobertnye-svg.github.io/investment-watchlist/dashboard49.html

---

## Next Steps / Open Items
1. **Each AI partner to refine their IRR model** based on 24-stock comparison critique and full results in irr_6models_full24.txt
2. **Add ChatGPT Model 7** to irr_6_models_compare.py
3. **Tiered growth cap** — implement to differentiate genuine compounders from cyclicals
4. **Fix Model 1 (Gemini)** — add capital return term for buyback machines
5. **Fix HALO data** — per-share CAGRs returning N/A, only revenue works
6. **Position sizing** based on conviction tiers (overweight pristine, underweight speculative)
7. **Weekly watchlist monitoring** for 5-15% pullbacks
8. **Forward estimate verification** for N/A historical growth stocks
9. **Sector concentration limits** (Consumer 7/24, Technology 5/24)
10. Cancel PayPal — Adobe software keeps billing

---

## Key Findings

### Quality Premium Paradox
Stocks with 1-2 flags (Tier 1 Flagged) outperform pristine zero-flag stocks on investability. The flags often signal market mispricing — the market overreacts to surface blemishes, creating better entry points. Pristine machines tend to be fully priced.

### Small-Cap Richer Than Large-Cap
- Small-cap hit rate: 1.04% (15/1,444) vs large-cap 0.90% (9/994)
- Small-cap median IRR higher despite cheaper valuations
- Market systematically underprices quality in less-covered names

### Conviction Tiers
- **Pristine (11):** LULU, BAH, BLD, ADBE, CSL, LRN, POOL, NEU, MORN + others
- **Flagged (11):** AXP, DDS, DECK, PYPL, CROX, PRI, ALRM, PRDO, PAYC, ETSY, IPAR
- **Speculative (2):** IDCC, ASO
