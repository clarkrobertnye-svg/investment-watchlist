"""
Capital Compounder System - Sample Data Generator
Creates realistic sample data for demonstration when API is unavailable.
Based on publicly available financial data from web sources.
"""

import pandas as pd
import numpy as np
from datetime import datetime

# Sample data based on real metrics from web research
# This allows the system to run without live API access
SAMPLE_DATA = [
    # Exceptional Compounders (High Incremental ROIC)
    {
        "ticker": "NVDA", "company_name": "NVIDIA Corporation", "sector": "Technology",
        "market_cap": 3200000000000, "price": 140.0, "shares_outstanding": 24521000000, "beta": 1.65,
        "incremental_roic": 1.45, "roic_current": 1.13, "roic_3y_avg": 0.90, "roic_wacc_spread": 1.03,
        "revenue_growth_3y": 0.43, "revenue_growth_1y": 0.43, "revenue_current": 130000000000,
        "fcf_conversion": 1.05, "fcf_current": 65000000000, "fcf_3y_avg": 35000000000,
        "gross_margin": 0.75, "gross_margin_3y_avg": 0.72, "gross_margin_trend": "expanding",
        "margin_change_bps": 300, "operating_margin": 0.62, "net_margin": 0.55,
        "capex_to_revenue": 0.02, "net_debt": -35000000000, "net_debt_ebitda": -0.5,
        "is_net_cash": True, "reinvestment_rate": 0.60, "data_quality": "complete"
    },
    {
        "ticker": "ASML", "company_name": "ASML Holding NV", "sector": "Technology",
        "market_cap": 280000000000, "price": 750.0, "shares_outstanding": 390000000, "beta": 1.25,
        "incremental_roic": 0.55, "roic_current": 0.42, "roic_3y_avg": 0.38, "roic_wacc_spread": 0.32,
        "revenue_growth_3y": 0.22, "revenue_growth_1y": 0.18, "revenue_current": 32000000000,
        "fcf_conversion": 1.15, "fcf_current": 9500000000, "fcf_3y_avg": 7500000000,
        "gross_margin": 0.51, "gross_margin_3y_avg": 0.50, "gross_margin_trend": "expanding",
        "margin_change_bps": 150, "operating_margin": 0.35, "net_margin": 0.28,
        "capex_to_revenue": 0.08, "net_debt": -8000000000, "net_debt_ebitda": -0.6,
        "is_net_cash": True, "reinvestment_rate": 0.45, "data_quality": "complete"
    },
    {
        "ticker": "MSFT", "company_name": "Microsoft Corporation", "sector": "Technology",
        "market_cap": 3100000000000, "price": 455.0, "shares_outstanding": 7470000000, "beta": 0.90,
        "incremental_roic": 0.38, "roic_current": 0.32, "roic_3y_avg": 0.30, "roic_wacc_spread": 0.22,
        "revenue_growth_3y": 0.14, "revenue_growth_1y": 0.16, "revenue_current": 260000000000,
        "fcf_conversion": 1.25, "fcf_current": 85000000000, "fcf_3y_avg": 70000000000,
        "gross_margin": 0.70, "gross_margin_3y_avg": 0.69, "gross_margin_trend": "stable",
        "margin_change_bps": 50, "operating_margin": 0.45, "net_margin": 0.36,
        "capex_to_revenue": 0.05, "net_debt": -45000000000, "net_debt_ebitda": -0.4,
        "is_net_cash": True, "reinvestment_rate": 0.30, "data_quality": "complete"
    },
    {
        "ticker": "V", "company_name": "Visa Inc", "sector": "Financial Services",
        "market_cap": 600000000000, "price": 310.00, "shares_outstanding": 1935000000, "beta": 0.95,
        "incremental_roic": 0.45, "roic_current": 0.35, "roic_3y_avg": 0.33, "roic_wacc_spread": 0.25,
        "revenue_growth_3y": 0.11, "revenue_growth_1y": 0.10, "revenue_current": 36000000000,
        "fcf_conversion": 1.10, "fcf_current": 20000000000, "fcf_3y_avg": 18000000000,
        "gross_margin": 0.82, "gross_margin_3y_avg": 0.81, "gross_margin_trend": "stable",
        "margin_change_bps": 80, "operating_margin": 0.68, "net_margin": 0.54,
        "capex_to_revenue": 0.025, "net_debt": 15000000000, "net_debt_ebitda": 0.5,
        "is_net_cash": False, "reinvestment_rate": 0.20, "data_quality": "complete"
    },
    {
        "ticker": "MA", "company_name": "Mastercard Inc", "sector": "Financial Services",
        "market_cap": 480000000000, "price": 540.0, "shares_outstanding": 923000000, "beta": 1.05,
        "incremental_roic": 0.50, "roic_current": 0.45, "roic_3y_avg": 0.42, "roic_wacc_spread": 0.35,
        "revenue_growth_3y": 0.13, "revenue_growth_1y": 0.12, "revenue_current": 28000000000,
        "fcf_conversion": 1.08, "fcf_current": 14000000000, "fcf_3y_avg": 12000000000,
        "gross_margin": 0.80, "gross_margin_3y_avg": 0.79, "gross_margin_trend": "expanding",
        "margin_change_bps": 120, "operating_margin": 0.58, "net_margin": 0.46,
        "capex_to_revenue": 0.03, "net_debt": 12000000000, "net_debt_ebitda": 0.6,
        "is_net_cash": False, "reinvestment_rate": 0.25, "data_quality": "complete"
    },
    {
        "ticker": "FICO", "company_name": "Fair Isaac Corporation", "sector": "Technology",
        "market_cap": 55000000000, "price": 2200.00, "shares_outstanding": 25000000, "beta": 1.35,
        "incremental_roic": 0.85, "roic_current": 0.65, "roic_3y_avg": 0.55, "roic_wacc_spread": 0.55,
        "revenue_growth_3y": 0.12, "revenue_growth_1y": 0.14, "revenue_current": 1700000000,
        "fcf_conversion": 1.30, "fcf_current": 700000000, "fcf_3y_avg": 550000000,
        "gross_margin": 0.82, "gross_margin_3y_avg": 0.80, "gross_margin_trend": "expanding",
        "margin_change_bps": 200, "operating_margin": 0.45, "net_margin": 0.32,
        "capex_to_revenue": 0.02, "net_debt": 2500000000, "net_debt_ebitda": 2.5,
        "is_net_cash": False, "reinvestment_rate": 0.15, "data_quality": "complete"
    },
    {
        "ticker": "SPGI", "company_name": "S&P Global Inc", "sector": "Financial Services",
        "market_cap": 155000000000, "price": 500.00, "shares_outstanding": 310000000, "beta": 1.10,
        "incremental_roic": 0.35, "roic_current": 0.28, "roic_3y_avg": 0.26, "roic_wacc_spread": 0.18,
        "revenue_growth_3y": 0.09, "revenue_growth_1y": 0.11, "revenue_current": 14500000000,
        "fcf_conversion": 1.05, "fcf_current": 5500000000, "fcf_3y_avg": 4800000000,
        "gross_margin": 0.68, "gross_margin_3y_avg": 0.67, "gross_margin_trend": "stable",
        "margin_change_bps": 60, "operating_margin": 0.47, "net_margin": 0.32,
        "capex_to_revenue": 0.025, "net_debt": 8000000000, "net_debt_ebitda": 1.1,
        "is_net_cash": False, "reinvestment_rate": 0.30, "data_quality": "complete"
    },
    {
        "ticker": "CDNS", "company_name": "Cadence Design Systems", "sector": "Technology",
        "market_cap": 85000000000, "price": 310.00, "shares_outstanding": 274000000, "beta": 1.20,
        "incremental_roic": 0.42, "roic_current": 0.32, "roic_3y_avg": 0.30, "roic_wacc_spread": 0.22,
        "revenue_growth_3y": 0.15, "revenue_growth_1y": 0.13, "revenue_current": 4500000000,
        "fcf_conversion": 1.15, "fcf_current": 1600000000, "fcf_3y_avg": 1300000000,
        "gross_margin": 0.89, "gross_margin_3y_avg": 0.88, "gross_margin_trend": "expanding",
        "margin_change_bps": 100, "operating_margin": 0.32, "net_margin": 0.28,
        "capex_to_revenue": 0.015, "net_debt": -2000000000, "net_debt_ebitda": -1.0,
        "is_net_cash": True, "reinvestment_rate": 0.35, "data_quality": "complete"
    },
    {
        "ticker": "SNPS", "company_name": "Synopsys Inc", "sector": "Technology",
        "market_cap": 80000000000, "price": 530.0, "shares_outstanding": 154000000, "beta": 1.15,
        "incremental_roic": 0.38, "roic_current": 0.28, "roic_3y_avg": 0.26, "roic_wacc_spread": 0.18,
        "revenue_growth_3y": 0.14, "revenue_growth_1y": 0.15, "revenue_current": 6500000000,
        "fcf_conversion": 1.20, "fcf_current": 2200000000, "fcf_3y_avg": 1800000000,
        "gross_margin": 0.80, "gross_margin_3y_avg": 0.79, "gross_margin_trend": "stable",
        "margin_change_bps": 70, "operating_margin": 0.28, "net_margin": 0.24,
        "capex_to_revenue": 0.02, "net_debt": -3500000000, "net_debt_ebitda": -1.5,
        "is_net_cash": True, "reinvestment_rate": 0.40, "data_quality": "complete"
    },
    {
        "ticker": "ADBE", "company_name": "Adobe Inc", "sector": "Technology",
        "market_cap": 200000000000, "price": 485.0, "shares_outstanding": 444000000, "beta": 1.25,
        "incremental_roic": 0.32, "roic_current": 0.28, "roic_3y_avg": 0.27, "roic_wacc_spread": 0.18,
        "revenue_growth_3y": 0.11, "revenue_growth_1y": 0.10, "revenue_current": 21000000000,
        "fcf_conversion": 1.35, "fcf_current": 8000000000, "fcf_3y_avg": 7000000000,
        "gross_margin": 0.88, "gross_margin_3y_avg": 0.88, "gross_margin_trend": "stable",
        "margin_change_bps": 30, "operating_margin": 0.36, "net_margin": 0.28,
        "capex_to_revenue": 0.015, "net_debt": -6000000000, "net_debt_ebitda": -0.7,
        "is_net_cash": True, "reinvestment_rate": 0.25, "data_quality": "complete"
    },
    {
        "ticker": "NOW", "company_name": "ServiceNow Inc", "sector": "Technology",
        "market_cap": 220000000000, "price": 1100.0, "shares_outstanding": 210000000, "beta": 1.05,
        "incremental_roic": 0.48, "roic_current": 0.35, "roic_3y_avg": 0.30, "roic_wacc_spread": 0.25,
        "revenue_growth_3y": 0.24, "revenue_growth_1y": 0.22, "revenue_current": 11000000000,
        "fcf_conversion": 1.40, "fcf_current": 3500000000, "fcf_3y_avg": 2500000000,
        "gross_margin": 0.79, "gross_margin_3y_avg": 0.78, "gross_margin_trend": "expanding",
        "margin_change_bps": 120, "operating_margin": 0.27, "net_margin": 0.22,
        "capex_to_revenue": 0.02, "net_debt": -4000000000, "net_debt_ebitda": -1.0,
        "is_net_cash": True, "reinvestment_rate": 0.45, "data_quality": "complete"
    },
    {
        "ticker": "CRWD", "company_name": "CrowdStrike Holdings", "sector": "Technology",
        "market_cap": 95000000000, "price": 395.0, "shares_outstanding": 243000000, "beta": 1.40,
        "incremental_roic": 0.55, "roic_current": 0.22, "roic_3y_avg": 0.15, "roic_wacc_spread": 0.12,
        "revenue_growth_3y": 0.35, "revenue_growth_1y": 0.32, "revenue_current": 4000000000,
        "fcf_conversion": 1.50, "fcf_current": 1200000000, "fcf_3y_avg": 700000000,
        "gross_margin": 0.75, "gross_margin_3y_avg": 0.74, "gross_margin_trend": "expanding",
        "margin_change_bps": 150, "operating_margin": 0.22, "net_margin": 0.18,
        "capex_to_revenue": 0.025, "net_debt": -3500000000, "net_debt_ebitda": -2.5,
        "is_net_cash": True, "reinvestment_rate": 0.50, "data_quality": "complete"
    },
    {
        "ticker": "MELI", "company_name": "MercadoLibre Inc", "sector": "Consumer Cyclical",
        "market_cap": 105000000000, "price": 2050.0, "shares_outstanding": 50000000, "beta": 1.55,
        "incremental_roic": 0.42, "roic_current": 0.25, "roic_3y_avg": 0.20, "roic_wacc_spread": 0.15,
        "revenue_growth_3y": 0.32, "revenue_growth_1y": 0.28, "revenue_current": 18000000000,
        "fcf_conversion": 0.95, "fcf_current": 2500000000, "fcf_3y_avg": 1500000000,
        "gross_margin": 0.52, "gross_margin_3y_avg": 0.48, "gross_margin_trend": "expanding",
        "margin_change_bps": 400, "operating_margin": 0.18, "net_margin": 0.12,
        "capex_to_revenue": 0.04, "net_debt": 2000000000, "net_debt_ebitda": 0.5,
        "is_net_cash": False, "reinvestment_rate": 0.60, "data_quality": "complete"
    },
    {
        "ticker": "ISRG", "company_name": "Intuitive Surgical", "sector": "Healthcare",
        "market_cap": 185000000000, "price": 520.00, "shares_outstanding": 356000000, "beta": 1.05,
        "incremental_roic": 0.28, "roic_current": 0.22, "roic_3y_avg": 0.21, "roic_wacc_spread": 0.12,
        "revenue_growth_3y": 0.15, "revenue_growth_1y": 0.17, "revenue_current": 8500000000,
        "fcf_conversion": 1.10, "fcf_current": 2800000000, "fcf_3y_avg": 2300000000,
        "gross_margin": 0.68, "gross_margin_3y_avg": 0.67, "gross_margin_trend": "stable",
        "margin_change_bps": 80, "operating_margin": 0.32, "net_margin": 0.28,
        "capex_to_revenue": 0.035, "net_debt": -8000000000, "net_debt_ebitda": -2.5,
        "is_net_cash": True, "reinvestment_rate": 0.35, "data_quality": "complete"
    },
    {
        "ticker": "COST", "company_name": "Costco Wholesale", "sector": "Consumer Defensive",
        "market_cap": 420000000000, "price": 950.00, "shares_outstanding": 442000000, "beta": 0.75,
        "incremental_roic": 0.22, "roic_current": 0.25, "roic_3y_avg": 0.24, "roic_wacc_spread": 0.15,
        "revenue_growth_3y": 0.10, "revenue_growth_1y": 0.08, "revenue_current": 260000000000,
        "fcf_conversion": 0.85, "fcf_current": 7500000000, "fcf_3y_avg": 6500000000,
        "gross_margin": 0.13, "gross_margin_3y_avg": 0.13, "gross_margin_trend": "stable",
        "margin_change_bps": 10, "operating_margin": 0.035, "net_margin": 0.028,
        "capex_to_revenue": 0.015, "net_debt": -12000000000, "net_debt_ebitda": -1.2,
        "is_net_cash": True, "reinvestment_rate": 0.40, "data_quality": "complete"
    },
    # More companies with various characteristics
    {
        "ticker": "GOOGL", "company_name": "Alphabet Inc", "sector": "Communication Services",
        "market_cap": 2100000000000, "price": 198.00, "shares_outstanding": 12000000000, "beta": 1.05,
        "incremental_roic": 0.25, "roic_current": 0.22, "roic_3y_avg": 0.21, "roic_wacc_spread": 0.12,
        "revenue_growth_3y": 0.12, "revenue_growth_1y": 0.14, "revenue_current": 350000000000,
        "fcf_conversion": 1.10, "fcf_current": 75000000000, "fcf_3y_avg": 65000000000,
        "gross_margin": 0.57, "gross_margin_3y_avg": 0.56, "gross_margin_trend": "stable",
        "margin_change_bps": 60, "operating_margin": 0.28, "net_margin": 0.24,
        "capex_to_revenue": 0.08, "net_debt": -95000000000, "net_debt_ebitda": -0.8,
        "is_net_cash": True, "reinvestment_rate": 0.35, "data_quality": "complete"
    },
    {
        "ticker": "META", "company_name": "Meta Platforms Inc", "sector": "Communication Services",
        "market_cap": 1500000000000, "price": 620.0, "shares_outstanding": 2540000000, "beta": 1.30,
        "incremental_roic": 0.35, "roic_current": 0.28, "roic_3y_avg": 0.25, "roic_wacc_spread": 0.18,
        "revenue_growth_3y": 0.15, "revenue_growth_1y": 0.22, "revenue_current": 165000000000,
        "fcf_conversion": 1.05, "fcf_current": 50000000000, "fcf_3y_avg": 35000000000,
        "gross_margin": 0.81, "gross_margin_3y_avg": 0.80, "gross_margin_trend": "expanding",
        "margin_change_bps": 150, "operating_margin": 0.40, "net_margin": 0.34,
        "capex_to_revenue": 0.18, "net_debt": -55000000000, "net_debt_ebitda": -0.7,
        "is_net_cash": True, "reinvestment_rate": 0.45, "data_quality": "complete"
    },
    {
        "ticker": "AAPL", "company_name": "Apple Inc", "sector": "Technology",
        "market_cap": 3400000000000, "price": 225.00, "shares_outstanding": 15100000000, "beta": 1.25,
        "incremental_roic": 0.30, "roic_current": 0.58, "roic_3y_avg": 0.55, "roic_wacc_spread": 0.48,
        "revenue_growth_3y": 0.04, "revenue_growth_1y": 0.05, "revenue_current": 400000000000,
        "fcf_conversion": 1.05, "fcf_current": 110000000000, "fcf_3y_avg": 100000000000,
        "gross_margin": 0.46, "gross_margin_3y_avg": 0.44, "gross_margin_trend": "expanding",
        "margin_change_bps": 200, "operating_margin": 0.30, "net_margin": 0.26,
        "capex_to_revenue": 0.025, "net_debt": 60000000000, "net_debt_ebitda": 0.5,
        "is_net_cash": False, "reinvestment_rate": 0.10, "data_quality": "complete"
    },
    {
        "ticker": "AMZN", "company_name": "Amazon.com Inc", "sector": "Consumer Cyclical",
        "market_cap": 2200000000000, "price": 210.00, "shares_outstanding": 10476000000, "beta": 1.15,
        "incremental_roic": 0.18, "roic_current": 0.12, "roic_3y_avg": 0.10, "roic_wacc_spread": 0.02,
        "revenue_growth_3y": 0.11, "revenue_growth_1y": 0.12, "revenue_current": 640000000000,
        "fcf_conversion": 0.75, "fcf_current": 45000000000, "fcf_3y_avg": 25000000000,
        "gross_margin": 0.48, "gross_margin_3y_avg": 0.45, "gross_margin_trend": "expanding",
        "margin_change_bps": 300, "operating_margin": 0.10, "net_margin": 0.07,
        "capex_to_revenue": 0.08, "net_debt": 40000000000, "net_debt_ebitda": 0.4,
        "is_net_cash": False, "reinvestment_rate": 0.55, "data_quality": "complete"
    },
    {
        "ticker": "TDG", "company_name": "TransDigm Group", "sector": "Industrials",
        "market_cap": 75000000000, "price": 1350.00, "shares_outstanding": 56000000, "beta": 1.35,
        "incremental_roic": 0.42, "roic_current": 0.35, "roic_3y_avg": 0.32, "roic_wacc_spread": 0.25,
        "revenue_growth_3y": 0.18, "revenue_growth_1y": 0.20, "revenue_current": 8000000000,
        "fcf_conversion": 1.20, "fcf_current": 2200000000, "fcf_3y_avg": 1800000000,
        "gross_margin": 0.60, "gross_margin_3y_avg": 0.58, "gross_margin_trend": "expanding",
        "margin_change_bps": 200, "operating_margin": 0.48, "net_margin": 0.28,
        "capex_to_revenue": 0.015, "net_debt": 22000000000, "net_debt_ebitda": 5.5,
        "is_net_cash": False, "reinvestment_rate": 0.30, "data_quality": "complete"
    },
    # Additional companies for realistic screening results
    {
        "ticker": "AXON", "company_name": "Axon Enterprise", "sector": "Industrials",
        "market_cap": 45000000000, "price": 580.00, "shares_outstanding": 78000000, "beta": 1.25,
        "incremental_roic": 0.38, "roic_current": 0.22, "roic_3y_avg": 0.20, "roic_wacc_spread": 0.12,
        "revenue_growth_3y": 0.28, "revenue_growth_1y": 0.32, "revenue_current": 2000000000,
        "fcf_conversion": 1.10, "fcf_current": 450000000, "fcf_3y_avg": 300000000,
        "gross_margin": 0.62, "gross_margin_3y_avg": 0.60, "gross_margin_trend": "expanding",
        "margin_change_bps": 200, "operating_margin": 0.18, "net_margin": 0.14,
        "capex_to_revenue": 0.03, "net_debt": -800000000, "net_debt_ebitda": -1.5,
        "is_net_cash": True, "reinvestment_rate": 0.45, "data_quality": "complete"
    },
    {
        "ticker": "DDOG", "company_name": "Datadog Inc", "sector": "Technology",
        "market_cap": 55000000000, "price": 155.0, "shares_outstanding": 344000000, "beta": 1.35,
        "incremental_roic": 0.52, "roic_current": 0.18, "roic_3y_avg": 0.15, "roic_wacc_spread": 0.08,
        "revenue_growth_3y": 0.35, "revenue_growth_1y": 0.28, "revenue_current": 2800000000,
        "fcf_conversion": 1.45, "fcf_current": 850000000, "fcf_3y_avg": 500000000,
        "gross_margin": 0.81, "gross_margin_3y_avg": 0.79, "gross_margin_trend": "expanding",
        "margin_change_bps": 180, "operating_margin": 0.22, "net_margin": 0.18,
        "capex_to_revenue": 0.02, "net_debt": -2500000000, "net_debt_ebitda": -2.5,
        "is_net_cash": True, "reinvestment_rate": 0.50, "data_quality": "complete"
    },
    {
        "ticker": "PANW", "company_name": "Palo Alto Networks", "sector": "Technology",
        "market_cap": 120000000000, "price": 395.0, "shares_outstanding": 316000000, "beta": 1.20,
        "incremental_roic": 0.45, "roic_current": 0.25, "roic_3y_avg": 0.20, "roic_wacc_spread": 0.15,
        "revenue_growth_3y": 0.22, "revenue_growth_1y": 0.18, "revenue_current": 8500000000,
        "fcf_conversion": 1.55, "fcf_current": 3200000000, "fcf_3y_avg": 2200000000,
        "gross_margin": 0.74, "gross_margin_3y_avg": 0.72, "gross_margin_trend": "expanding",
        "margin_change_bps": 200, "operating_margin": 0.25, "net_margin": 0.20,
        "capex_to_revenue": 0.015, "net_debt": -4000000000, "net_debt_ebitda": -1.2,
        "is_net_cash": True, "reinvestment_rate": 0.35, "data_quality": "complete"
    },
    {
        "ticker": "MCO", "company_name": "Moody's Corporation", "sector": "Financial Services",
        "market_cap": 85000000000, "price": 480.00, "shares_outstanding": 177000000, "beta": 1.15,
        "incremental_roic": 0.35, "roic_current": 0.32, "roic_3y_avg": 0.30, "roic_wacc_spread": 0.22,
        "revenue_growth_3y": 0.10, "revenue_growth_1y": 0.12, "revenue_current": 7000000000,
        "fcf_conversion": 1.15, "fcf_current": 2400000000, "fcf_3y_avg": 2100000000,
        "gross_margin": 0.72, "gross_margin_3y_avg": 0.71, "gross_margin_trend": "stable",
        "margin_change_bps": 80, "operating_margin": 0.45, "net_margin": 0.32,
        "capex_to_revenue": 0.02, "net_debt": 6000000000, "net_debt_ebitda": 1.8,
        "is_net_cash": False, "reinvestment_rate": 0.25, "data_quality": "complete"
    },
    {
        "ticker": "FTNT", "company_name": "Fortinet Inc", "sector": "Technology",
        "market_cap": 75000000000, "price": 105.0, "shares_outstanding": 750000000, "beta": 1.10,
        "incremental_roic": 0.40, "roic_current": 0.45, "roic_3y_avg": 0.42, "roic_wacc_spread": 0.35,
        "revenue_growth_3y": 0.18, "revenue_growth_1y": 0.12, "revenue_current": 5800000000,
        "fcf_conversion": 1.30, "fcf_current": 1900000000, "fcf_3y_avg": 1500000000,
        "gross_margin": 0.77, "gross_margin_3y_avg": 0.76, "gross_margin_trend": "expanding",
        "margin_change_bps": 120, "operating_margin": 0.28, "net_margin": 0.24,
        "capex_to_revenue": 0.025, "net_debt": -3500000000, "net_debt_ebitda": -1.8,
        "is_net_cash": True, "reinvestment_rate": 0.30, "data_quality": "complete"
    },
    {
        "ticker": "INTU", "company_name": "Intuit Inc", "sector": "Technology",
        "market_cap": 180000000000, "price": 640.00, "shares_outstanding": 281000000, "beta": 1.05,
        "incremental_roic": 0.28, "roic_current": 0.22, "roic_3y_avg": 0.21, "roic_wacc_spread": 0.12,
        "revenue_growth_3y": 0.14, "revenue_growth_1y": 0.13, "revenue_current": 16500000000,
        "fcf_conversion": 1.20, "fcf_current": 5500000000, "fcf_3y_avg": 4500000000,
        "gross_margin": 0.79, "gross_margin_3y_avg": 0.78, "gross_margin_trend": "stable",
        "margin_change_bps": 60, "operating_margin": 0.28, "net_margin": 0.22,
        "capex_to_revenue": 0.02, "net_debt": 4000000000, "net_debt_ebitda": 0.7,
        "is_net_cash": False, "reinvestment_rate": 0.35, "data_quality": "complete"
    },
    {
        "ticker": "CPRT", "company_name": "Copart Inc", "sector": "Industrials",
        "market_cap": 55000000000, "price": 57.00, "shares_outstanding": 965000000, "beta": 1.00,
        "incremental_roic": 0.32, "roic_current": 0.28, "roic_3y_avg": 0.27, "roic_wacc_spread": 0.18,
        "revenue_growth_3y": 0.15, "revenue_growth_1y": 0.12, "revenue_current": 4200000000,
        "fcf_conversion": 1.05, "fcf_current": 1400000000, "fcf_3y_avg": 1200000000,
        "gross_margin": 0.46, "gross_margin_3y_avg": 0.45, "gross_margin_trend": "stable",
        "margin_change_bps": 80, "operating_margin": 0.38, "net_margin": 0.32,
        "capex_to_revenue": 0.08, "net_debt": -2000000000, "net_debt_ebitda": -1.2,
        "is_net_cash": True, "reinvestment_rate": 0.40, "data_quality": "complete"
    },
    {
        "ticker": "ODFL", "company_name": "Old Dominion Freight", "sector": "Industrials",
        "market_cap": 45000000000, "price": 210.00, "shares_outstanding": 214000000, "beta": 1.05,
        "incremental_roic": 0.25, "roic_current": 0.28, "roic_3y_avg": 0.27, "roic_wacc_spread": 0.18,
        "revenue_growth_3y": 0.09, "revenue_growth_1y": 0.05, "revenue_current": 6200000000,
        "fcf_conversion": 0.85, "fcf_current": 1100000000, "fcf_3y_avg": 1000000000,
        "gross_margin": 0.42, "gross_margin_3y_avg": 0.41, "gross_margin_trend": "stable",
        "margin_change_bps": 50, "operating_margin": 0.28, "net_margin": 0.22,
        "capex_to_revenue": 0.12, "net_debt": -1500000000, "net_debt_ebitda": -0.8,
        "is_net_cash": True, "reinvestment_rate": 0.45, "data_quality": "complete"
    },
    {
        "ticker": "MSCI", "company_name": "MSCI Inc", "sector": "Financial Services",
        "market_cap": 48000000000, "price": 610.00, "shares_outstanding": 79000000, "beta": 1.10,
        "incremental_roic": 0.38, "roic_current": 0.35, "roic_3y_avg": 0.33, "roic_wacc_spread": 0.25,
        "revenue_growth_3y": 0.12, "revenue_growth_1y": 0.14, "revenue_current": 2800000000,
        "fcf_conversion": 1.25, "fcf_current": 1300000000, "fcf_3y_avg": 1100000000,
        "gross_margin": 0.82, "gross_margin_3y_avg": 0.81, "gross_margin_trend": "expanding",
        "margin_change_bps": 100, "operating_margin": 0.55, "net_margin": 0.40,
        "capex_to_revenue": 0.02, "net_debt": 4500000000, "net_debt_ebitda": 2.5,
        "is_net_cash": False, "reinvestment_rate": 0.20, "data_quality": "complete"
    },
]


def generate_sample_data(output_file: str = "sample_universe_data.csv") -> pd.DataFrame:
    """Generate sample data for testing the screening system."""
    df = pd.DataFrame(SAMPLE_DATA)
    df["fetch_date"] = datetime.now().isoformat()
    df.to_csv(output_file, index=False)
    print(f"✅ Sample data generated: {output_file} ({len(df)} companies)")
    return df


if __name__ == "__main__":
    generate_sample_data()
