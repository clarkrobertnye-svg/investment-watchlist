"""Deduplicate watchlist - keep primary listing only"""
import json

with open("stage2_master_watchlist.json") as f:
    data = json.load(f)

watchlist = data["watchlist"]

# Group by company name (normalized)
from collections import defaultdict
by_company = defaultdict(list)

for t in watchlist:
    name = t["name"].lower().strip()
    # Remove common suffixes
    for suffix in [" inc", " ltd", " plc", " corp", " sa", " ag", " se", " nv", " ab", " asa", " limited", " group"]:
        name = name.replace(suffix, "")
    name = name.strip()
    by_company[name].append(t)

# Pick best listing per company
def score(t):
    ticker = t["ticker"]
    s = 0
    # Prefer shorter tickers (usually primary)
    s -= len(ticker)
    # Penalize OTC (ends in F or Y, 5 chars)
    if len(ticker) == 5 and ticker[-1] in "FY":
        s -= 100
    # Prefer higher market cap
    s += t["mcap_b"] / 100
    # Prefer higher VCR
    s += t["vcr"]
    return s

deduped = []
removed = []

for name, listings in by_company.items():
    if len(listings) == 1:
        deduped.append(listings[0])
    else:
        listings.sort(key=score, reverse=True)
        deduped.append(listings[0])
        for dup in listings[1:]:
            removed.append(f"{dup['ticker']} (dup of {listings[0]['ticker']})")

deduped.sort(key=lambda x: x["vcr"], reverse=True)

print(f"Original: {len(watchlist)} | Deduped: {len(deduped)} | Removed: {len(removed)}")
print()
print("Removed duplicates:")
for r in removed[:20]:
    print(f"  {r}")
if len(removed) > 20:
    print(f"  ... +{len(removed)-20} more")

print()
print(f"{'Ticker':<8} {'Name':<22} {'ROIC':>6} {'VCR':>5} {'Sprd':>5} {'GM':>5} {'FCFYld':>6} {'Grwth':>6} {'MCap':>7}")
print("-" * 75)
for t in deduped[:50]:
    print(f"{t['ticker']:<8} {t['name']:<22} {t['roic']*100:5.1f}% {t['vcr']:5.2f} {t['spread']*100:4.1f}% {t['gm']*100:4.0f}% {t['fcf_yield']*100:5.1f}% {t['growth']*100:5.1f}% ${t['mcap_b']:6.1f}B")
if len(deduped) > 50:
    print(f"... +{len(deduped)-50} more")

# Save
with open("stage2_watchlist_tickers.txt", "w") as f:
    f.write("\n".join(t["ticker"] for t in deduped))

data["watchlist"] = deduped
data["passed"] = len(deduped)
data["removed_duplicates"] = removed
with open("stage2_master_watchlist.json", "w") as f:
    json.dump(data, f, indent=2)

print(f"\n💾 stage2_master_watchlist.json ({len(deduped)} tickers)")
