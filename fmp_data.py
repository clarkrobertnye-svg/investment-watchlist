"""
Capital Compounder Investment System - FMP API Data Fetcher
Uses FMP stable API endpoints with currency conversion
"""

import requests
from typing import Dict, List, Optional
import time
from datetime import datetime
from config import FMP_API_KEY

# Exchange rates to USD (update periodically)
EXCHANGE_RATES_TO_USD = {
    "USD": 1.0,
    "DKK": 0.14,    # Danish Krone
    "EUR": 1.04,    # Euro
    "GBP": 1.25,    # British Pound
    "JPY": 0.0064,  # Japanese Yen
    "CHF": 1.11,    # Swiss Franc
    "CAD": 0.70,    # Canadian Dollar
    "SEK": 0.092,   # Swedish Krona
    "NOK": 0.089,   # Norwegian Krone
    "AUD": 0.62,    # Australian Dollar
    "HKD": 0.13,    # Hong Kong Dollar
    "CNY": 0.14,    # Chinese Yuan
    "KRW": 0.00070, # Korean Won
    "TWD": 0.031,   # Taiwan Dollar
    "INR": 0.012,   # Indian Rupee
    "BRL": 0.17,    # Brazilian Real
    "MXN": 0.049,   # Mexican Peso
}

def convert_to_usd(value, currency):
    """Convert a value from given currency to USD."""
    if value is None:
        return None
    rate = EXCHANGE_RATES_TO_USD.get(currency, 1.0)
    return value * rate


class FMPDataFetcher:
    def __init__(self, api_key: str = FMP_API_KEY):
        self.api_key = api_key
        self.base_url = "https://financialmodelingprep.com/stable"
        self.request_delay = 0.15
        
    def _make_request(self, endpoint: str, params: Dict = None):
        if params is None:
            params = {}
        params["apikey"] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            time.sleep(self.request_delay)
            return response.json()
        except Exception as e:
            print(f"  API error for {endpoint}: {e}")
            return None
    
    def get_company_profile(self, ticker):
        data = self._make_request("profile", {"symbol": ticker})
        return data[0] if data and len(data) > 0 else None
    
    def get_income_statement(self, ticker, period="annual", limit=5):
        return self._make_request("income-statement", {"symbol": ticker, "period": period, "limit": limit})
    
    def get_balance_sheet(self, ticker, period="annual", limit=5):
        return self._make_request("balance-sheet-statement", {"symbol": ticker, "period": period, "limit": limit})
    
    def get_cash_flow(self, ticker, period="annual", limit=5):
        return self._make_request("cash-flow-statement", {"symbol": ticker, "period": period, "limit": limit})
    
    def get_key_metrics(self, ticker, period="annual", limit=5):
        return self._make_request("key-metrics", {"symbol": ticker, "period": period, "limit": limit})
    
    def get_income_statement_quarterly(self, ticker, limit=4):
        return self._make_request("income-statement", {"symbol": ticker, "period": "quarter", "limit": limit})
    
    def get_balance_sheet_quarterly(self, ticker, limit=1):
        return self._make_request("balance-sheet-statement", {"symbol": ticker, "period": "quarter", "limit": limit})
    
    def get_income_statement_quarterly(self, ticker, limit=4):
        return self._make_request("income-statement", {"symbol": ticker, "period": "quarter", "limit": limit})
    
    def get_balance_sheet_quarterly(self, ticker, limit=1):
        return self._make_request("balance-sheet-statement", {"symbol": ticker, "period": "quarter", "limit": limit})
    
    def get_cash_flow_quarterly(self, ticker, limit=4):
        return self._make_request("cash-flow-statement", {"symbol": ticker, "period": "quarter", "limit": limit})
    
    def get_income_statement_quarterly(self, ticker, limit=4):
        return self._make_request("income-statement", {"symbol": ticker, "period": "quarter", "limit": limit})
    
    def get_balance_sheet_quarterly(self, ticker, limit=4):
        return self._make_request("balance-sheet-statement", {"symbol": ticker, "period": "quarter", "limit": limit})
    
    def get_cash_flow_quarterly(self, ticker, limit=4):
        return self._make_request("cash-flow-statement", {"symbol": ticker, "period": "quarter", "limit": limit})
    
    def get_income_statement_quarterly(self, ticker, limit=4):
        return self._make_request("income-statement", {"symbol": ticker, "period": "quarter", "limit": limit})
    
    def get_balance_sheet_quarterly(self, ticker, limit=4):
        return self._make_request("balance-sheet-statement", {"symbol": ticker, "period": "quarter", "limit": limit})
    
    def get_cash_flow_quarterly(self, ticker, limit=4):
        return self._make_request("cash-flow-statement", {"symbol": ticker, "period": "quarter", "limit": limit})
    
    def get_insider_ownership(self, ticker):
        """Get insider ownership percentage - uses v4 endpoint"""
        url = f"{self.base_url}/v4/institutional-ownership/symbol-ownership?symbol={ticker}&apikey={self.api_key}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return []
    
    def get_insider_trading(self, ticker, limit=100):
        """Get recent insider transactions"""
        url = f"{self.base_url}/v4/insider-trading?symbol={ticker}&limit={limit}&apikey={self.api_key}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return []


class FinancialDataProcessor:
    def __init__(self):
        self.fetcher = FMPDataFetcher()
    
    def get_all_metrics(self, ticker, use_ttm=False):
        ttm_label = " (TTM)" if use_ttm else ""
        print(f"  Fetching data for {ticker}{ttm_label}...", end=" ")
        metrics = {"ticker": ticker, "fetch_date": datetime.now().isoformat(), "data_quality": "complete"}
        
        try:
            profile = self.fetcher.get_company_profile(ticker)
            income_stmts = self.fetcher.get_income_statement(ticker, limit=4)
            balance_sheets = self.fetcher.get_balance_sheet(ticker, limit=4)
            cash_flows = self.fetcher.get_cash_flow(ticker, limit=4)
            key_metrics = self.fetcher.get_key_metrics(ticker, limit=4)
            
            # Insider data for alignment score
            insider_trading = self.fetcher.get_insider_trading(ticker, limit=100)
            
            if not all([profile, income_stmts, balance_sheets, cash_flows, key_metrics]):
                print("Missing data")
                metrics["data_quality"] = "incomplete"
                return metrics
            
            # Get reporting currency for conversion
            reporting_currency = income_stmts[0].get("reportedCurrency", "USD") if income_stmts else "USD"
            fx_rate = EXCHANGE_RATES_TO_USD.get(reporting_currency, 1.0)
            metrics["reporting_currency"] = reporting_currency
            metrics["fx_rate_to_usd"] = fx_rate
            
            # Profile data (already in USD for US-listed ADRs)
            metrics["company_name"] = profile.get("companyName", "")
            metrics["sector"] = profile.get("sector", "")
            metrics["industry"] = profile.get("industry", "")
            metrics["market_cap"] = profile.get("marketCap", 0)  # Already USD
            metrics["price"] = profile.get("price", 0)  # Already USD
            metrics["beta"] = profile.get("beta", 1.0)
            
            # Revenue growth (currency-neutral ratio)
            if len(income_stmts) >= 4:
                rev_now = income_stmts[0].get("revenue", 0)
                rev_old = income_stmts[3].get("revenue", 0)
                if rev_old > 0:
                    metrics["revenue_growth_3y"] = (rev_now / rev_old) ** (1/3) - 1
            
            # Gross margin (currency-neutral ratio)
            if income_stmts:
                gp = income_stmts[0].get("grossProfit", 0)
                rev = income_stmts[0].get("revenue", 1)
                metrics["gross_margin"] = gp / rev if rev > 0 else 0
            
            # FCF with currency conversion
            if cash_flows and income_stmts:
                ocf = cash_flows[0].get("operatingCashFlow", 0)
                capex = abs(cash_flows[0].get("capitalExpenditure", 0))
                fcf = ocf - capex
                ni = income_stmts[0].get("netIncome", 1)
                rev = income_stmts[0].get("revenue", 1)
                
                # Convert to USD for absolute values
                metrics["fcf_current"] = fcf * fx_rate
                metrics["fcf_conversion"] = fcf / ni if ni > 0 else 0  # Ratio, no conversion needed
                metrics["capex_to_revenue"] = capex / rev if rev > 0 else 0  # Ratio
                
                # Stock-Based Compensation (for alignment score)
                sbc = cash_flows[0].get("stockBasedCompensation", 0) or 0
                metrics["sbc"] = sbc * fx_rate
                metrics["sbc_to_fcf"] = sbc / fcf if fcf > 0 else 0  # SBC as % of FCF
                metrics["sbc_to_revenue"] = sbc / rev if rev > 0 else 0  # SBC as % of revenue
            
            # ROIC - Calculate ourselves using Analyst Method (Equity + Debt, no cash deduction)
            # This matches analyst consensus better than FMP's returnOnInvestedCapital field
            if balance_sheets and income_stmts:
                total_equity = balance_sheets[0].get("totalStockholdersEquity") or 0
                total_debt = balance_sheets[0].get("totalDebt") or 0
                op_income_curr = income_stmts[0].get("operatingIncome") or 0
                
                # Use actual effective tax rate, with sanity bounds
                effective_tax = income_stmts[0].get("incomeTaxExpense", 0)
                pre_tax_income = income_stmts[0].get("incomeBeforeTax", 1)
                if pre_tax_income > 0:
                    actual_tax_rate = effective_tax / pre_tax_income
                else:
                    actual_tax_rate = 0.21
                
                # Sanity check: if rate is >30% (one-time charges) or <0% (credits), use 21%
                if actual_tax_rate > 0.30 or actual_tax_rate < 0:
                    tax_rate = 0.21
                else:
                    tax_rate = actual_tax_rate
                
                metrics["effective_tax_rate"] = tax_rate
                nopat_curr = op_income_curr * (1 - tax_rate)
                # === HYBRID: Claude + Gemini + DeepSeek Excess Cash Method ===
                # Excess cash = Cash & ST Investments - (1% of Revenue for operations)
                revenue_curr = income_stmts[0].get("revenue") or 0
                cash_and_st = (balance_sheets[0].get("cashAndCashEquivalents") or 0) + \
                              (balance_sheets[0].get("shortTermInvestments") or 0)
                required_cash = revenue_curr * 0.01  # 1% of revenue for operations
                excess_cash = max(0, cash_and_st - required_cash)
                
                # Store raw values for transparency
                metrics["revenue_annual"] = revenue_curr * fx_rate
                metrics["cash_and_st_investments"] = cash_and_st * fx_rate
                metrics["required_operating_cash"] = required_cash * fx_rate
                metrics["excess_cash"] = excess_cash * fx_rate
                metrics["cash_to_revenue_pct"] = (cash_and_st / revenue_curr * 100) if revenue_curr > 0 else 0
                
                # Original IC (for comparison)
                ic_original = total_equity + total_debt
                metrics["invested_capital_original"] = ic_original * fx_rate
                
                # Adjusted IC (with excess cash removed)
                ic_curr = total_equity + total_debt - excess_cash
                metrics["invested_capital_adjusted"] = ic_curr * fx_rate
                
                # Adjustment impact percentage
                if ic_original > 0:
                    metrics["ic_adjustment_pct"] = ((ic_original - ic_curr) / ic_original) * 100
                else:
                    metrics["ic_adjustment_pct"] = 0
                
                # Dual ROIC (DeepSeek method: show both for transparency)
                metrics["roic_current"] = nopat_curr / ic_curr if ic_curr > 0 else 0  # Adjusted ROIC
                metrics["roic_original"] = nopat_curr / ic_original if ic_original > 0 else 0  # Original ROIC
                
                # ROIC improvement from cash adjustment
                if metrics["roic_original"] > 0:
                    metrics["roic_improvement_pct"] = ((metrics["roic_current"] - metrics["roic_original"]) / metrics["roic_original"]) * 100
                else:
                    metrics["roic_improvement_pct"] = 0
                
                # Hidden Compounder Flag (DeepSeek logic)
                # Flagged if: Adjusted ROIC > 20% AND improvement > 10%
                metrics["hidden_compounder"] = (metrics["roic_current"] > 0.20 and metrics["roic_improvement_pct"] > 10)
                
                # 3Y average ROIC
                if len(balance_sheets) >= 3 and len(income_stmts) >= 3:
                    roics = []
                    for i in range(3):
                        eq = balance_sheets[i].get("totalStockholdersEquity") or 0
                        debt = balance_sheets[i].get("totalDebt") or 0
                        op_inc = income_stmts[i].get("operatingIncome") or 0
                        ic = eq + debt
                        if ic > 0:
                            roics.append((op_inc * (1 - tax_rate)) / ic)
                    if roics:
                        metrics["roic_3y_avg"] = sum(roics) / len(roics)
                
                # Enterprise Yield = (Dividends + Buybacks + Debt Paydown) / EV
                # More accurate than using Market Cap since debt paydown benefits debt holders
                if cash_flows and balance_sheets:
                    mcap = metrics.get("market_cap") or 0  # Already in USD
                    total_debt = (balance_sheets[0].get("totalDebt") or 0) * fx_rate
                    cash = (balance_sheets[0].get("cashAndCashEquivalents") or 0) * fx_rate
                    ev = mcap + total_debt - cash
                    
                    if ev > 0 and mcap > 0:
                        # Get cash flow items (use most recent year) - APPLY FX CONVERSION
                        cf = cash_flows[0]
                        # FMP field names (values are negative for outflows)
                        dividends = abs(cf.get("commonDividendsPaid") or cf.get("netDividendsPaid") or 0) * fx_rate
                        
                        # Net buybacks (negative = net repurchase)
                        net_stock = (cf.get("netCommonStockIssuance") or cf.get("netStockIssuance") or 0) * fx_rate
                        net_buybacks = abs(net_stock) if net_stock < 0 else 0
                        
                        # Net debt paydown (negative = paying down debt)
                        net_debt_chg = (cf.get("netDebtIssuance") or cf.get("longTermNetDebtIssuance") or 0) * fx_rate
                        net_debt_paydown = abs(net_debt_chg) if net_debt_chg < 0 else 0
                        
                        # Enterprise Yield
                        enterprise_yield = (dividends + net_buybacks + net_debt_paydown) / ev
                        metrics["enterprise_yield"] = enterprise_yield
                        metrics["dividend_yield"] = dividends / mcap
                        metrics["buyback_yield"] = net_buybacks / mcap
                        metrics["debt_paydown_yield"] = net_debt_paydown / ev
                        
                        # Net Shareholder Yield (buybacks minus dilution from issuance)
                        # Positive = returning capital, Negative = diluting shareholders
                        metrics["net_stock_issuance"] = net_stock  # Raw value (negative = buyback)
                        net_shareholder_yield = -net_stock / mcap if mcap > 0 else 0  # Flip sign: positive = good
                        metrics["net_shareholder_yield"] = net_shareholder_yield
                
                # Value Creation Ratio = ROIC / WACC (Dynamic calculation)
                if metrics.get("roic_current"):
                    # Cost of Equity (CAPM with current rates)
                    risk_free_rate = 0.043  # 10Y Treasury Jan 2026
                    equity_risk_premium = 0.052
                    
                    beta = profile.get("beta") or 1.0 if profile else 1.0
                    beta = max(0.8, min(beta, 1.4))  # Tighter clamp
                    
                    cost_of_equity = risk_free_rate + (beta * equity_risk_premium)
                    
                    # Cost of Debt (after-tax)
                    total_debt = balance_sheets[0].get("totalDebt") or 0
                    interest_exp = abs(income_stmts[0].get("interestExpense") or 0)
                    tax_rate = metrics.get("effective_tax_rate", 0.21)
                    
                    if total_debt > 0 and interest_exp > 0:
                        cod_pretax = min(interest_exp / total_debt, 0.15)
                        cost_of_debt = cod_pretax * (1 - tax_rate)
                    else:
                        cost_of_debt = 0
                    
                    # Capital weights from EV
                    mcap = metrics.get("market_cap") or 0
                    cash = balance_sheets[0].get("cashAndCashEquivalents") or 0
                    ev = mcap + total_debt - cash
                    
                    if ev > 0 and mcap > 0:
                        eq_wt = min(mcap / ev, 1.5)  # Allow >100% for net cash
                        debt_wt = max(total_debt / ev, 0)
                        total_wt = eq_wt + debt_wt
                        eq_wt = eq_wt / total_wt if total_wt > 0 else 1.0
                        debt_wt = 1 - eq_wt
                    else:
                        eq_wt, debt_wt = 1.0, 0.0
                    
                    # Final WACC with bounds
                    wacc = (eq_wt * cost_of_equity) + (debt_wt * cost_of_debt)
                    wacc = max(0.06, min(wacc, 0.14))
                    
                    metrics["wacc"] = wacc
                    metrics["cost_of_equity"] = cost_of_equity
                    metrics["cost_of_debt"] = cost_of_debt
                    # VCR uses CURRENT ROIC (reflects today's value creation)
                    metrics["value_creation_ratio"] = metrics["roic_current"] / wacc if wacc > 0 else 0
                    
                    # ROIC Trend: Is ROIC improving? (Current vs 3Y Avg)
                    roic_curr = metrics.get("roic_current") or 0
                    roic_3y = metrics.get("roic_3y_avg") or roic_curr
                    if roic_3y > 0:
                        metrics["roic_trend"] = (roic_curr - roic_3y) / roic_3y  # % change
                    else:
                        metrics["roic_trend"] = 0
                    
                    # TTM ROIC (optional - for fast-moving situations)
                    if use_ttm:
                        try:
                            income_q = self.fetcher.get_income_statement_quarterly(ticker, limit=4)
                            bs_q = self.fetcher.get_balance_sheet_quarterly(ticker, limit=1)
                            
                            if income_q and len(income_q) >= 4 and bs_q:
                                ttm_op_income = sum(q.get("operatingIncome", 0) for q in income_q)
                                eq_q = bs_q[0].get("totalStockholdersEquity") or 0
                                debt_q = bs_q[0].get("totalDebt") or 0
                                ic_q = eq_q + debt_q
                                
                                if ic_q > 0:
                                    nopat_ttm = ttm_op_income * 0.75
                                    metrics["roic_ttm"] = nopat_ttm / ic_q
                                    if metrics.get("wacc"):
                                        metrics["vcr_ttm"] = metrics["roic_ttm"] / metrics["wacc"]
                                    ttm_rev = sum(q.get("revenue", 0) for q in income_q)
                                    metrics["revenue_ttm"] = ttm_rev * fx_rate
                                metrics["ttm_data_available"] = True
                        except:
                            metrics["ttm_data_available"] = False
                
                # ROIC ex-Goodwill
                invested_cap = key_metrics[0].get("investedCapital") or 0
                goodwill = balance_sheets[0].get("goodwill") or 0
                op_income = income_stmts[0].get("operatingIncome") or 0
                
                metrics["goodwill"] = goodwill * fx_rate
                metrics["invested_capital"] = invested_cap * fx_rate
                metrics["goodwill_pct"] = goodwill / invested_cap if invested_cap > 0 else 0
                
                adj_ic = invested_cap - goodwill
                if adj_ic > 0:
                    metrics["roic_ex_goodwill"] = (op_income * (1 - tax_rate)) / adj_ic
                else:
                    metrics["roic_ex_goodwill"] = 0
                
                # 3Y avg ROIC ex-Goodwill
                if len(key_metrics) >= 3 and len(balance_sheets) >= 3 and len(income_stmts) >= 3:
                    roics_ex_gw = []
                    for i in range(3):
                        ic = key_metrics[i].get("investedCapital") or 0
                        gw = balance_sheets[i].get("goodwill") or 0
                        op_inc = income_stmts[i].get("operatingIncome") or 0
                        adj = ic - gw
                        if adj > 0:
                            roics_ex_gw.append((op_inc * (1 - tax_rate)) / adj)
                    if roics_ex_gw:
                        metrics["roic_ex_goodwill_3y_avg"] = sum(roics_ex_gw) / len(roics_ex_gw)
            
            # Incremental ROIC (ratio, no conversion needed)
            if balance_sheets and len(balance_sheets) >= 2 and income_stmts and len(income_stmts) >= 2:
                ic_now = balance_sheets[0].get("totalAssets", 0) - balance_sheets[0].get("totalCurrentLiabilities", 0)
                ic_old = balance_sheets[1].get("totalAssets", 0) - balance_sheets[1].get("totalCurrentLiabilities", 0)
                # Use consistent tax rate for incremental ROIC
                tax_rate_inc = metrics.get("effective_tax_rate", 0.21)
                nopat_now = income_stmts[0].get("operatingIncome", 0) * (1 - tax_rate_inc)
                nopat_old = income_stmts[1].get("operatingIncome", 0) * (1 - tax_rate_inc)
                d_ic = ic_now - ic_old
                d_nopat = nopat_now - nopat_old
                metrics["incremental_roic"] = d_nopat / d_ic if d_ic > 0 else 0
            
            # Leverage (ratio, no conversion needed)
            if balance_sheets and income_stmts:
                debt = balance_sheets[0].get("totalDebt", 0)
                cash = balance_sheets[0].get("cashAndCashEquivalents", 0)
                net_debt = debt - cash
                ebitda = income_stmts[0].get("ebitda", 1)
                metrics["net_debt"] = net_debt * fx_rate
                metrics["net_debt_ebitda"] = net_debt / ebitda if ebitda > 0 else 0
                metrics["is_net_cash"] = net_debt < 0
            
            if metrics.get("roic_current"):
                metrics["roic_wacc_spread"] = metrics["roic_current"] - 0.10
            
            # FCF Yield (need both in same currency - market cap is USD, fcf now USD)
            if metrics.get("fcf_current") and metrics.get("market_cap"):
                metrics["fcf_yield"] = metrics["fcf_current"] / metrics["market_cap"]
            
            # ============================================================
            # MANAGEMENT ALIGNMENT INDICATOR (MAI) - 0-100 Scale
            # 5 Pillars: Skin in Game (30%) + Capital Allocation (30%) + 
            #            Compensation (20%) + Retention (10%) + Shareholder Friendly (10%)
            # ============================================================
            alignment_flags = []
            pillar_scores = {}
            
            # -----------------------------------------------------------
            # PILLAR 1: SKIN IN THE GAME (30% weight, 0-100 raw score)
            # Insider ownership and trading patterns
            # -----------------------------------------------------------
            skin_score = 50  # Base score
            
            # 1a. Recent Insider Buying/Selling (0-30 points)
            net_insider_buys = 0
            insider_buy_value = 0
            insider_sell_value = 0
            
            if insider_trading:
                for txn in insider_trading:
                    txn_type = txn.get("transactionType", "")
                    value = abs(txn.get("securitiesTransacted", 0) * txn.get("price", 0))
                    if txn_type in ["P-Purchase", "A-Award"]:
                        insider_buy_value += value
                    elif txn_type in ["S-Sale", "S-Sale+OE"]:
                        insider_sell_value += value
                
                net_insider_activity = insider_buy_value - insider_sell_value
                metrics["insider_buy_value_12mo"] = insider_buy_value
                metrics["insider_sell_value_12mo"] = insider_sell_value
                metrics["net_insider_value_12mo"] = net_insider_activity
                
                # Score based on dollar value of net activity
                if net_insider_activity > 1_000_000:  # $1M+ net buying
                    skin_score += 30
                    alignment_flags.append("Heavy insider buying ($1M+)")
                elif net_insider_activity > 500_000:
                    skin_score += 25
                    alignment_flags.append("Strong insider buying")
                elif net_insider_activity > 100_000:
                    skin_score += 15
                elif net_insider_activity > 0:
                    skin_score += 10
                elif net_insider_activity > -500_000:
                    skin_score += 0  # Modest selling, neutral
                elif net_insider_activity > -1_000_000:
                    skin_score -= 10
                else:  # $1M+ net selling
                    skin_score -= 20
                    alignment_flags.append("⚠️ Heavy insider selling")
            
            # 1b. Bonus for consistent buybacks (proxy for management confidence)
            net_sh_yield = metrics.get("net_shareholder_yield", 0) or 0
            if net_sh_yield >= 0.05:
                skin_score += 20
            elif net_sh_yield >= 0.03:
                skin_score += 15
            elif net_sh_yield >= 0.01:
                skin_score += 10
            elif net_sh_yield < -0.02:  # Heavy dilution
                skin_score -= 10
                alignment_flags.append("⚠️ Share dilution")
            
            skin_score = max(0, min(100, skin_score))
            pillar_scores["skin_in_game"] = skin_score
            metrics["skin_in_game_score"] = skin_score
            
            # -----------------------------------------------------------
            # PILLAR 2: CAPITAL ALLOCATION HISTORY (30% weight, 0-100 raw score)
            # How management uses cash flow
            # -----------------------------------------------------------
            capalloc_score = 50  # Base score
            
            # 2a. Buyback Effectiveness (0-30 points)
            # Are they buying back stock when cheap?
            buyback_yield = metrics.get("buyback_yield", 0) or 0
            fcf_yield = metrics.get("fcf_yield", 0) or 0
            # Use FCF yield as proxy for "cheapness" (higher = cheaper)
            
            if buyback_yield > 0.05:  # 5%+ annual buyback
                if fcf_yield > 0.08:  # Buying when FCF yield is high (cheap)
                    capalloc_score += 30
                    alignment_flags.append("Smart buybacks (cheap)")
                elif fcf_yield > 0.05:
                    capalloc_score += 20
                else:  # Buying when expensive
                    capalloc_score += 10
            elif buyback_yield > 0.02:
                capalloc_score += 15
            elif buyback_yield > 0:
                capalloc_score += 5
            
            # 2b. Dividend Policy (0-20 points)
            div_yield = metrics.get("dividend_yield", 0) or 0
            # FCF payout ratio
            fcf_payout = div_yield / fcf_yield if fcf_yield > 0 else 0
            
            if 0 < div_yield < 0.06:  # Reasonable yield
                if fcf_payout < 0.50:  # Well-covered
                    capalloc_score += 20
                elif fcf_payout < 0.70:
                    capalloc_score += 15
                elif fcf_payout < 0.90:
                    capalloc_score += 10
                else:
                    capalloc_score += 0  # Stretched
            elif div_yield >= 0.06:  # High yield, possibly unsustainable
                if fcf_payout > 1.0:
                    alignment_flags.append("⚠️ Dividend exceeds FCF")
                    capalloc_score -= 10
            elif div_yield == 0:
                capalloc_score += 10  # Growth company reinvesting, neutral-positive
            
            # 2c. M&A Track Record / Incremental ROIC (0-30 points)
            inc_roic = metrics.get("incremental_roic", 0) or 0
            goodwill_pct = metrics.get("goodwill_pct", 0) or 0
            wacc = metrics.get("wacc", 0.10) or 0.10
            
            if inc_roic > 0.20:  # Exceptional returns on deployed capital
                capalloc_score += 30
                alignment_flags.append("Elite capital deployer")
            elif inc_roic > 0.15:
                capalloc_score += 25
            elif inc_roic > wacc:  # Above cost of capital
                capalloc_score += 15
            elif inc_roic > 0:
                capalloc_score += 5
            else:  # Negative incremental ROIC
                capalloc_score -= 10
            
            # Penalty for high goodwill (possible overpayment for acquisitions)
            if goodwill_pct > 0.40:
                capalloc_score -= 10
                alignment_flags.append("⚠️ High goodwill (M&A risk)")
            elif goodwill_pct > 0.30:
                capalloc_score -= 5
            
            capalloc_score = max(0, min(100, capalloc_score))
            pillar_scores["capital_allocation"] = capalloc_score
            metrics["capital_allocation_score"] = capalloc_score
            
            # -----------------------------------------------------------
            # PILLAR 3: COMPENSATION ALIGNMENT (20% weight, 0-100 raw score)
            # Is executive pay tied to performance?
            # -----------------------------------------------------------
            comp_score = 50  # Base score
            
            # 3a. SBC as % of FCF (0-40 points)
            # Lower SBC = less dilution = better alignment
            sbc_to_fcf = metrics.get("sbc_to_fcf", 0) or 0
            sbc_to_rev = metrics.get("sbc_to_revenue", 0) or 0
            
            if sbc_to_fcf <= 0.05:
                comp_score += 40
                alignment_flags.append("Minimal SBC dilution")
            elif sbc_to_fcf <= 0.10:
                comp_score += 30
            elif sbc_to_fcf <= 0.15:
                comp_score += 20
            elif sbc_to_fcf <= 0.25:
                comp_score += 10
            elif sbc_to_fcf <= 0.40:
                comp_score += 0
            else:  # >40% of FCF going to SBC
                comp_score -= 20
                alignment_flags.append("⚠️ Excessive SBC (>40% FCF)")
            
            # 3b. SBC relative to revenue (catches high-margin tech)
            if sbc_to_rev > 0.15:
                comp_score -= 15
            elif sbc_to_rev > 0.10:
                comp_score -= 10
            elif sbc_to_rev < 0.03:
                comp_score += 10
            
            comp_score = max(0, min(100, comp_score))
            pillar_scores["compensation_alignment"] = comp_score
            metrics["compensation_score"] = comp_score
            
            # -----------------------------------------------------------
            # PILLAR 4: EXECUTIVE RETENTION (10% weight, 0-100 raw score)
            # Stability and continuity of leadership
            # Proxied by ROIC trend stability (consistent leadership = consistent results)
            # -----------------------------------------------------------
            retention_score = 50  # Base score
            
            roic_trend = metrics.get("roic_trend", 0) or 0
            roic_current = metrics.get("roic_current", 0) or 0
            roic_3y = metrics.get("roic_3y_avg", 0) or 0
            
            # Stable/improving ROIC suggests good leadership retention
            if roic_trend >= 0.10:  # Improving
                retention_score += 30
            elif roic_trend >= 0:  # Stable
                retention_score += 20
            elif roic_trend >= -0.10:  # Modest decline
                retention_score += 10
            else:  # Significant decline
                retention_score -= 20
            
            # Consistency bonus: if both current and 3Y avg are strong
            if roic_current > 0.20 and roic_3y > 0.18:
                retention_score += 20
                alignment_flags.append("Consistent leadership")
            elif roic_current > 0.15 and roic_3y > 0.12:
                retention_score += 10
            
            retention_score = max(0, min(100, retention_score))
            pillar_scores["executive_retention"] = retention_score
            metrics["retention_score"] = retention_score
            
            # -----------------------------------------------------------
            # PILLAR 5: SHAREHOLDER FRIENDLY (10% weight, 0-100 raw score)
            # Policies and financial health
            # -----------------------------------------------------------
            friendly_score = 50  # Base score
            
            # 5a. Conservative leverage
            net_debt_ebitda = metrics.get("net_debt_ebitda", 0) or 0
            if net_debt_ebitda < 0:  # Net cash position
                friendly_score += 25
                alignment_flags.append("Net cash position")
            elif net_debt_ebitda <= 1.0:
                friendly_score += 15
            elif net_debt_ebitda <= 2.0:
                friendly_score += 5
            elif net_debt_ebitda > 3.0:
                friendly_score -= 20
                alignment_flags.append("⚠️ High leverage")
            
            # 5b. FCF Conversion quality (earnings quality)
            fcf_conversion = metrics.get("fcf_conversion", 0) or 0
            if fcf_conversion >= 1.2:
                friendly_score += 25
                alignment_flags.append("Excellent FCF conversion")
            elif fcf_conversion >= 1.0:
                friendly_score += 15
            elif fcf_conversion >= 0.8:
                friendly_score += 10
            elif fcf_conversion < 0.5:
                friendly_score -= 10
            
            friendly_score = max(0, min(100, friendly_score))
            pillar_scores["shareholder_friendly"] = friendly_score
            metrics["shareholder_friendly_score"] = friendly_score
            
            # -----------------------------------------------------------
            # COMPOSITE MAI SCORE (Weighted)
            # Skin (30%) + CapAlloc (30%) + Comp (20%) + Retention (10%) + Friendly (10%)
            # -----------------------------------------------------------
            mai_score = (
                pillar_scores["skin_in_game"] * 0.30 +
                pillar_scores["capital_allocation"] * 0.30 +
                pillar_scores["compensation_alignment"] * 0.20 +
                pillar_scores["executive_retention"] * 0.10 +
                pillar_scores["shareholder_friendly"] * 0.10
            )
            
            metrics["alignment_score"] = round(mai_score, 1)
            metrics["alignment_flags"] = alignment_flags
            metrics["pillar_scores"] = pillar_scores
            
            # Alignment tier with emoji
            if mai_score >= 80:
                metrics["alignment_tier"] = "A"
                metrics["alignment_emoji"] = "🟢"
                metrics["mgmt_aligned"] = True
            elif mai_score >= 70:
                metrics["alignment_tier"] = "B+"
                metrics["alignment_emoji"] = "🟢"
                metrics["mgmt_aligned"] = True
            elif mai_score >= 60:
                metrics["alignment_tier"] = "B"
                metrics["alignment_emoji"] = "🟡"
                metrics["mgmt_aligned"] = True
            elif mai_score >= 50:
                metrics["alignment_tier"] = "C"
                metrics["alignment_emoji"] = "⚪"
                metrics["mgmt_aligned"] = False
            elif mai_score >= 40:
                metrics["alignment_tier"] = "D"
                metrics["alignment_emoji"] = "🟠"
                metrics["mgmt_aligned"] = False
            else:
                metrics["alignment_tier"] = "F"
                metrics["alignment_emoji"] = "🔴"
                metrics["mgmt_aligned"] = False
            
            print("OK")
            
        except Exception as e:
            print(f"Error: {e}")
            metrics["data_quality"] = "error"
        
        return metrics
