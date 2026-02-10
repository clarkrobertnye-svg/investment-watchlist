import os
import sys
import requests
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "private" / ".env")
API = os.getenv("FMP_API_KEY")

if not API:
    raise SystemExit("Add FMP_API_KEY to private/.env")

def fmp(url):
    r = requests.get(url + f"&apikey={API}")
    r.raise_for_status()
    return r.json()

def get_metrics(ticker):
    bs = fmp(f"https://financialmodelingprep.com/api/v3/balance-sheet-statement/{ticker}?limit=2")
    is_ = fmp(f"https://financialmodelingprep.com/api/v3/income-statement/{ticker}?limit=2")
    cf = fmp(f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{ticker}?limit=2")
    prof = fmp(f"https://financialmodelingprep.com/api/v3/profile/{ticker}")

    bs0 = bs[0]
    is0 = is_[0]
    cf0 = cf[0]

    tax = is0["incomeTaxExpense"] / max(is0["incomeBeforeTax"], 1)
    nopat = is0["operatingIncome"] * (1 - tax)

    cash = bs0["cashAndShortTermInvestments"]
    debt = bs0["totalDebt"]

    invested = bs0["totalAssets"] - bs0["totalCurrentLiabilities"]
    invested_x = invested - cash

    roic = nopat / invested
    roic_x = nopat / invested_x

    ocf = cf0["operatingCashFlow"]
    capex = abs(cf0["capitalExpenditures"])

    reinvest = capex / max(nopat, 1)

    beta = prof[0]["beta"]
    rf = 0.045
    erp = 0.055
    cost_equity = rf + beta * erp
    wacc = cost_equity   # simple no-debt assumption

    return {
        "Ticker": ticker,
        "ROIC": round(roic, 3),
        "ROIC ex-cash": round(roic_x, 3),
        "Reinvestment Rate": round(reinvest, 3),
        "WACC": round(wacc, 3)
    }

def main():
    tickers = sys.argv[1:]
    rows = [get_metrics(t) for t in tickers]
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

if __name__ == "__main__":
    main()


