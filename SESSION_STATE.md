# SESSION STATE — Capital Compounders Dashboard
## Last Updated: 2026-02-11

---

## CURRENT STATUS

### Universe: 72 Buffett Compounders (filtered from 126 via Gate 5 Buffett Filter)
### Dashboard: Live at GitHub Pages
- **Repo:** https://github.com/clarkrobertnye-svg/investment-watchlist
- **Live URL:** https://clarkrobertnye-svg.github.io/investment-watchlist/capital_compounders_dashboard.html
- **Dashboard subtitle:** "Buffett-Filtered Universe — Gate 5 Ready"

### Gate 5: Valuation (multi-model IRR) — In progress
- NVDA 6-model framework completed (8.0% mean IRR, HOLD verdict)
- Remaining 71 Buffett Compounders pending IRR valuation

### Pipeline: 126 universe → Buffett Filter (72 survive) → IRR on 72 only
- 54 non-Buffett names removed from dashboard display
- 68 Tier 1, 4 Tier 2 (AXP, GMAB, QCOM, SYF)

---

## SESSION WORK COMPLETED (2026-02-11)

### 1. ROE Column Integration — DONE (126/126)
- Added two sortable columns: ROE (Current) and ROE (5yr Avg)
- Color thresholds: green ≥20%, white ≥10%, red <10%, dark red negative
- NEQ badge (amber "NEQ") for negative-equity companies with tooltip
- Data source: FMP stable API (https://financialmodelingprep.com/stable)
- **fetch_roe_data.py (v2):** Initial fetch, 114 tickers → cache/exports/roe_data.json
- **fetch_roe_supplemental.py:** 101 missing universe tickers fetched and merged
- Final: 215 total tickers in roe_data.json (114 original + 101 supplemental)
- NEQ companies in universe (7): HGTY, BKNG, EAT, LYV, BLBD, LII, APP
- API key used: TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU (ROTATE THIS)

### 2. Buffett Compounder Analysis — DONE
- 7-model consensus PDF analyzed (uploaded as __Xbuffet.pdf)
- Cross-referenced all model opinions to find tickers mentioned 4+ times as "non-Buffett"
- **10 Consensus Non-Buffett Tickers (4+ model mentions):**
  - DAVE (6/7), HGTY (5/7), HRMY (5/7), EAT (5/7)
  - YETI (4/7), LQDT (4/7), BLBD (4/7), APP (4/7), BKNG (4/7), LYV (4/7)

### 3. Gate 5 Buffett Filter — DESIGNED AND TESTED
Rather than brute-force removing consensus names, built a reproducible rules-based filter using existing dashboard data.

#### Gate 5 Sub-Gates:
| Sub-Gate | Rule | Failure Rate |
|----------|------|-------------|
| **5a: ROIC/ROE History** | ROIC avg ≥ 15% AND ROE 5yr ≥ 15% (NEQ: ROIC avg ≥ 20%) | 28% (35/126) |
| **5b: FCF Quality** | FCF/NI ≥ 70% | 1% (1/126) |
| **5c: Leverage** | ND/EBITDA ≤ 2.5x | 0% (0/126) |
| **5d: SBC/Dilution** | SBC/FCF ≤ 25% AND Share CAGR ≤ 2% | 20% (25/126) |
| **5e: Flag Health** | Flags ≤ 3 | 14% (18/126) |

#### Results:
- **72 Buffett Compounders** (57%) — passed all 5 sub-gates
  - 68 Tier 1, 4 Tier 2 (AXP, GMAB, QCOM, SYF)
- **54 Failed** (43%)
- Caught 9/10 consensus non-Buffett names
- BKNG passed via NEQ escape valve (ROIC avg 46.3% ≥ 20% threshold) — correct behavior

#### 72 Buffett Compounders (alphabetical):
AAPL, ADBE, ADP, AMG, ANET, APH, ASML, ASO, AX, AXP, BAH, BKNG, BLD, BMI, BRC, CAT, COCO, COKE, CROX, CRUS, CSL, CTAS, CVCO, DDS, DECK, EME, ERIE, FIX, GMAB, HALO, HUBB, IBP, IDCC, IDT, IESC, IPAR, IT, ITT, KLAC, LII, LOGI, LULU, MA, MATX, MEDP, MSFT, NEU, NSSC, NTES, NVDA, NVMI, NVR, NVS, POOL, POWL, PRDO, PRI, QCOM, RLI, RMD, ROL, SKY, SYF, TT, UFPI, ULTA, V, VRSK, WSM, WSO, WTS, XPEL

#### 54 Failed Buffett Filter:
**3 sub-gate failures:** CCB, CELH, FBK, PIPR, PLMR
**2 sub-gate failures:** APP, ATEN, CARG, CPRX, DAVE, EAT, EBAY, ESQ, EXLS, GOOGL, HGTY, HLNE, IRMD, LMB, NMIH
**1 sub-gate failure:** ACGL, ALRM, AMPH, ASIC, AVGO, BLBD, BX, CASH, CDNS, CSW, FELE, FFIV, FSS, GOLF, HIG, HRMY, HWKN, KAI, KFY, KNSL, LQDT, LRN, LYV, MANH, MNR, MORN, MSA, MWA, NYT, OFG, OZK, PH, TXRH, YETI

### 4. PDF Export — DONE
- Tabloid landscape (11×17) dark-theme PDF with all 126 stocks, 23 columns
- File: capital_compounders_dashboard.pdf

### 5. Dashboard Filtered to 72 Buffett Compounders — DONE
- Removed 54 non-Buffett tickers from dashboard HTML
- Updated subtitle: "Buffett-Filtered Universe — Gate 5 Ready"
- Updated stock count references: 126 → 72
- Dashboard pushed to GitHub Pages via git
- **54 Removed:** ACGL, ALRM, AMPH, APP, ASIC, ATEN, AVGO, BLBD, BX, CARG, CASH, CCB, CDNS, CELH, CPRX, CSW, DAVE, EAT, EBAY, ESQ, EXLS, FBK, FELE, FFIV, FSS, GOLF, GOOGL, HGTY, HIG, HLNE, HRMY, HWKN, IRMD, KAI, KFY, KNSL, LMB, LQDT, LRN, LYV, MANH, MNR, MORN, MSA, MWA, NMIH, NYT, OFG, OZK, PH, PIPR, PLMR, TXRH, YETI

---

## NOTABLE DESIGN DECISIONS

1. **Gate 5 Buffett Filter is an OVERLAY, not a removal.** Failed tickers stay in the 126 universe — they just don't get the "Buffett Compounder" badge. This preserves the pipeline.

2. **NEQ escape valve:** Negative equity companies can still pass if ROIC avg ≥ 20%. This correctly saves BKNG (46.3% ROIC) and LII (30.2% ROIC) while catching EAT (9.6%) and BLBD (38.8% but fails 5d on dilution).

3. **5b (FCF quality) and 5c (leverage) are near-zero filters** because Gates 1-4 already cleaned these. The Buffett filter's real teeth are 5a (ROIC/ROE consistency) and 5d (SBC/dilution).

4. **GOOGL fails on 5b (FCF/NI 65.8%) and 5d (SBC).** This is arguably correct — Buffett himself said he "missed" Google but the SBC culture is genuinely anti-Buffett.

---

## PENDING / NEXT STEPS

- [x] **DECIDED:** Buffett filter stays behind the scenes — no dashboard badge column
- [x] **DECIDED:** Non-Buffett names removed from dashboard display entirely
- [x] **DONE:** Dashboard filtered from 126 → 72 Buffett Compounders
- [ ] **Gate 5 pipeline: 72 Buffett Compounders → multi-model IRR valuations**
- [ ] Gate 5 IRR valuations for 71 remaining Buffett Compounders (NVDA already done)
- [ ] Monthly refresh cycle implementation
- [ ] Rotate FMP API key (TtvF1nFuyMJk23iOeTklWpU0XEYcCvQU exposed in session)
- [ ] Cancel PayPal - Adobe software keeps billing
- [ ] Known issue: large-cap data gap blocking exclusion reasons for ~900 tickers

---

## KEY FILES (User's Mac)
- `cache/exports/roe_data.json` — 215 tickers ROE data
- `capital_compounders_dashboard.html` — main dashboard (needs push to repo)
- `fetch_roe_data.py` (v2) — primary ROE fetch script
- `fetch_roe_supplemental.py` — supplemental ROE fetch for 101 missing tickers

## KEY FILES (This Session Outputs)
- `/mnt/user-data/outputs/capital_compounders_dashboard.html` — dashboard with ROE columns
- `/mnt/user-data/outputs/capital_compounders_dashboard.pdf` — tabloid PDF export
- `/mnt/user-data/outputs/fetch_roe_supplemental.py` — supplemental fetch script
- `/mnt/user-data/outputs/SESSION_STATE.md` — this file

## DASHBOARD KNOWN FEATURES
- 3yr ROIIC displays ">500%" in green for infinity values (when invested capital shrinks while NOPAT grows)
- Table min-width 1600px (increased from 1400px for ROE columns)
- All columns sortable with click headers
- Dark theme with color-coded metrics
