#!/bin/bash
SRC=~/Documents/capital_compounders
GDRIVE=$(ls -d ~/Library/CloudStorage/GoogleDrive-*/My\ Drive 2>/dev/null | head -1)
ICLOUD=~/Library/Mobile\ Documents/com~apple~CloudDocs/capital_compounders
mkdir -p "$ICLOUD/exports" 2>/dev/null
[ -n "$GDRIVE" ] && mkdir -p "$GDRIVE/capital_compounders/exports" 2>/dev/null
for f in *.py *.md *.docx; do
    [ -f "$SRC/$f" ] || continue
    cp "$SRC/$f" "$ICLOUD/" 2>/dev/null
    [ -n "$GDRIVE" ] && cp "$SRC/$f" "$GDRIVE/capital_compounders/" 2>/dev/null
done
cp "$SRC"/cache/exports/*.csv "$ICLOUD/exports/" 2>/dev/null
[ -n "$GDRIVE" ] && cp "$SRC"/cache/exports/*.csv "$GDRIVE/capital_compounders/exports/" 2>/dev/null
echo "✅ Synced to:"
echo "   📁 iMac:    $SRC"
echo "   ☁️  iCloud:  $ICLOUD"
[ -n "$GDRIVE" ] && echo "   📎 GDrive:  $GDRIVE/capital_compounders/" || echo "   ⚠️  No GDrive"
echo "   🕐 $(date '+%Y-%m-%d %H:%M:%S')"
