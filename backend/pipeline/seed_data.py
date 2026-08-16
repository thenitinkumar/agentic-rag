"""
Seed entry point for the Earnings Intelligence pipeline.
Delegates to data_fetcher which pulls real data from:
  - yfinance  (quarterly financials — free, no key)
  - FMP API   (earnings call transcripts — free tier with FMP_API_KEY)
"""
from .data_fetcher import seed_all

__all__ = ["seed_all"]
