# Capital Compounder Screening Results
## Date: February 2, 2026

### Screening Summary
- **Total Securities Screened:** 36,333
- **API Calls:** 65,729
- **Time:** ~19 hours
- **Final Universe:** 166 quality stocks

### Thresholds Applied
| Filter | Threshold |
|--------|-----------|
| Market Cap | > $500M |
| Gross Margin | > 25% |
| ROIC (ex-cash) | > 15% |
| VCR | > 1.5x |
| FCF/NI | > 70% |
| FCF/Debt | > 25% |
| ROIIC | > 20% |
| ROIIC >= ROIC | Yes |

### Results
- **Compounding Machines:** 51 stocks (CompPower ≥ 20%)
- **Cash Cows:** 115 stocks (High ROIIC, lower reinvestment)

### Top 20 Compounding Machines
| Ticker | ROIIC | Reinv | CompPower | ROIC | GM | VCR |
|--------|-------|-------|-----------|------|-----|-----|
| VITL | 269% | 58% | 156% | 37% | 38% | 3.7x |
| ITT | 86% | 149% | 129% | 17% | 34% | 1.7x |
| ADP | 244% | 49% | 120% | 46% | 51% | 4.6x |
| YELP | 73% | 139% | 102% | 19% | 91% | 1.9x |
| BBW | 167% | 57% | 95% | 27% | 55% | 2.7x |
| ANF | 461% | 19% | 88% | 39% | 61% | 3.9x |
| CVLT | 61% | 130% | 80% | 21% | 82% | 2.1x |
| PSIX | 309% | 25% | 78% | 135% | 30% | 13.5x |
| PTRN | 259% | 26% | 66% | 28% | 44% | 2.8x |
| PAYO | 71% | 93% | 66% | 37% | 84% | 3.7x |
| CPNG | 43% | 146% | 63% | 19% | 29% | 1.9x |
| MLI | 50% | 122% | 61% | 31% | 28% | 3.1x |
| LNTH | 295% | 19% | 57% | 41% | 64% | 4.1x |
| SEAS | 230% | 24% | 56% | 17% | 92% | 1.7x |
| ULTA | 116% | 47% | 55% | 34% | 39% | 3.4x |
| HMY | 94% | 56% | 53% | 29% | 40% | 2.9x |
| PLAB | 52% | 92% | 48% | 17% | 35% | 1.7x |
| SHOO | 125% | 33% | 41% | 21% | 41% | 2.1x |
| CNQ | 61% | 66% | 40% | 17% | 49% | 1.7x |
| BMI | 33% | 120% | 40% | 23% | 42% | 2.3x |

### Files Included
- `compounders_clean.json` - Final cleaned results
- `s4_final.json` - Raw Stage 4 output
- `fresh_screener.py` - The screening script
- `config.py` - API configuration
