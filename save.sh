#!/bin/bash
cd ~/Documents/capital_compounders
git add -A
git status
read -p "Commit message: " msg
git commit -m "$msg"
git push
echo "✅ Saved to GitHub"
