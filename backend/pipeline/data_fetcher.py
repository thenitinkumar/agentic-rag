"""
Fetches real S&P 500 financial data for the Earnings Intelligence pipeline.

  - Quarterly income statement data via yfinance (free, no API key required)
  - Earnings call transcripts via Financial Modeling Prep API
      Free tier: 250 requests/day — sign up at https://financialmodelingprep.com
      Without a key, placeholder transcript files are written so the pipeline
      still runs (just with no real transcript content to search over).

SQL table created: financials
Transcript files written to: data/docs/<ticker>_Q<n>_<year>_transcript.md
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

from .config import SETTINGS, SQLITE_PATH, DOCS_DIR

# 15 companies across 6 sectors — good cross-sectional coverage for demos
COMPANIES = [
    {"ticker": "AAPL",  "name": "Apple Inc.",               "sector": "Technology"},
    {"ticker": "MSFT",  "name": "Microsoft Corp.",          "sector": "Technology"},
    {"ticker": "NVDA",  "name": "NVIDIA Corp.",             "sector": "Technology"},
    {"ticker": "META",  "name": "Meta Platforms Inc.",      "sector": "Technology"},
    {"ticker": "GOOGL", "name": "Alphabet Inc.",            "sector": "Technology"},
    {"ticker": "AMZN",  "name": "Amazon.com Inc.",          "sector": "Consumer Discretionary"},
    {"ticker": "TSLA",  "name": "Tesla Inc.",               "sector": "Consumer Discretionary"},
    {"ticker": "WMT",   "name": "Walmart Inc.",             "sector": "Consumer Staples"},
    {"ticker": "JPM",   "name": "JPMorgan Chase & Co.",     "sector": "Financials"},
    {"ticker": "BAC",   "name": "Bank of America Corp.",    "sector": "Financials"},
    {"ticker": "JNJ",   "name": "Johnson & Johnson",        "sector": "Healthcare"},
    {"ticker": "UNH",   "name": "UnitedHealth Group Inc.",  "sector": "Healthcare"},
    {"ticker": "XOM",   "name": "Exxon Mobil Corp.",        "sector": "Energy"},
    {"ticker": "CAT",   "name": "Caterpillar Inc.",         "sector": "Industrials"},
    {"ticker": "MCD",   "name": "McDonald's Corp.",         "sector": "Consumer Discretionary"},
]

# Possible row names in yfinance income statement DataFrames
# (names vary across yfinance versions and by company)
_REVENUE_NAMES = ("Total Revenue", "Revenue", "Net Revenue")
_GROSS_NAMES   = ("Gross Profit",)
_OPINC_NAMES   = ("Operating Income", "EBIT", "Operating Income Or Loss")
_NETINC_NAMES  = ("Net Income", "Net Income Common Stockholders",
                   "Net Income From Continuing Operations")
_EPS_NAMES     = ("Basic EPS", "Diluted EPS", "Basic Earnings Per Share")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        import pandas as pd
        f = float(val)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def _get(df, date, *names) -> Optional[float]:
    """Return the first matching metric from a DataFrame column, or None."""
    for name in names:
        if name in df.index:
            return _safe_float(df.loc[name, date])
    return None


# ---------------------------------------------------------------------------
# Financial data (yfinance)
# ---------------------------------------------------------------------------

def fetch_quarterly_financials(ticker: str, meta: dict) -> list[dict]:
    """Fetch quarterly income statement data for one ticker via yfinance."""
    import yfinance as yf

    records: list[dict] = []
    try:
        t = yf.Ticker(ticker)

        # Try both attribute names — yfinance renamed this across versions
        df = None
        for attr in ("quarterly_income_stmt", "quarterly_financials"):
            try:
                candidate = getattr(t, attr, None)
                if candidate is not None and not candidate.empty:
                    df = candidate
                    break
            except Exception:
                continue

        if df is None or df.empty:
            print(f"    [{ticker}] no quarterly income data returned by yfinance")
            return records

        dates = sorted(df.columns)  # oldest → newest

        for date in dates:
            revenue = _get(df, date, *_REVENUE_NAMES)
            if revenue is None or revenue == 0:
                continue

            gross   = _get(df, date, *_GROSS_NAMES)
            op_inc  = _get(df, date, *_OPINC_NAMES)
            net_inc = _get(df, date, *_NETINC_NAMES)
            eps     = _get(df, date, *_EPS_NAMES)

            revenue_m    = revenue / 1e6
            gross_margin = (gross   / revenue * 100) if gross   else None
            op_margin    = (op_inc  / revenue * 100) if op_inc  else None
            net_inc_m    = net_inc  / 1e6            if net_inc else None

            records.append({
                "ticker":               ticker,
                "company_name":         meta["name"],
                "sector":               meta["sector"],
                "quarter":              f"Q{date.quarter} {date.year}",
                "fiscal_year":          int(date.year),
                "fiscal_quarter":       int(date.quarter),
                "_date":                date,  # temp — used for YoY, removed before insert
                "revenue_musd":         round(revenue_m,    1),
                "gross_margin_pct":     round(gross_margin, 1) if gross_margin else None,
                "operating_margin_pct": round(op_margin,    1) if op_margin    else None,
                "net_income_musd":      round(net_inc_m,    1) if net_inc_m    else None,
                "eps":                  round(eps,          2) if eps           else None,
                "yoy_revenue_growth_pct": None,
            })

        # Fill YoY revenue growth by comparing each quarter to 4 quarters earlier
        for i in range(4, len(records)):
            curr = records[i]["revenue_musd"]
            prev = records[i - 4]["revenue_musd"]
            if prev and prev > 0:
                records[i]["yoy_revenue_growth_pct"] = round((curr - prev) / prev * 100, 1)

        for r in records:
            r.pop("_date")

    except Exception as e:
        print(f"    [{ticker}] error fetching financials: {e}")

    return records


def build_sqlite(path: Path = SQLITE_PATH) -> int:
    """
    Fetch quarterly financials for all COMPANIES and persist to SQLite.
    Returns the total number of rows inserted.
    """
    import yfinance as yf  # noqa — validate the import is available early

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    cur  = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS financials")
    cur.execute("""
        CREATE TABLE financials (
            ticker                  TEXT,
            company_name            TEXT,
            sector                  TEXT,
            quarter                 TEXT,
            fiscal_year             INTEGER,
            fiscal_quarter          INTEGER,
            revenue_musd            REAL,
            gross_margin_pct        REAL,
            operating_margin_pct    REAL,
            net_income_musd         REAL,
            eps                     REAL,
            yoy_revenue_growth_pct  REAL
        )
    """)

    total = 0
    for meta in COMPANIES:
        ticker = meta["ticker"]
        print(f"  Fetching financials: {ticker} ({meta['name']})")
        records = fetch_quarterly_financials(ticker, meta)
        if records:
            cur.executemany(
                """INSERT INTO financials VALUES (
                    :ticker, :company_name, :sector, :quarter,
                    :fiscal_year, :fiscal_quarter,
                    :revenue_musd, :gross_margin_pct, :operating_margin_pct,
                    :net_income_musd, :eps, :yoy_revenue_growth_pct
                )""",
                records,
            )
            total += len(records)
            print(f"    -> {len(records)} quarters inserted")
        else:
            print(f"    -> no data")
        time.sleep(0.5)  # be polite to Yahoo Finance servers

    conn.commit()
    conn.close()
    return total


# ---------------------------------------------------------------------------
# Transcript data (Financial Modeling Prep API)
# ---------------------------------------------------------------------------

def fetch_transcript(ticker: str, quarter: int, year: int, api_key: str) -> Optional[str]:
    """Fetch one earnings call transcript from the FMP API."""
    import requests

    url = (
        f"https://financialmodelingprep.com/api/v3/earning_call_transcript/{ticker}"
        f"?quarter={quarter}&year={year}&apikey={api_key}"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data and isinstance(data, list) and data[0].get("content"):
            return data[0]["content"]
    except Exception as e:
        print(f"    [{ticker} Q{quarter} {year}] transcript error: {e}")
    return None


def build_transcripts(docs_dir: Path = DOCS_DIR, api_key: Optional[str] = None) -> int:
    """
    Write earnings call transcripts as markdown files for vector ingestion.
    Fetches the last 8 quarters (2 years) per company.
    With a valid FMP API key: downloads real transcript text.
    Without a key: writes placeholder files (pipeline still runs).
    Returns the number of files written.
    """
    import datetime

    docs_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime.now()
    quarters_to_fetch = []
    for offset in range(8):
        month  = now.month - (offset * 3)
        year   = now.year
        while month <= 0:
            month += 12
            year  -= 1
        quarters_to_fetch.append(((month - 1) // 3 + 1, year))

    count = 0
    for meta in COMPANIES:
        ticker  = meta["ticker"]
        name    = meta["name"]
        sector  = meta["sector"]

        for quarter, year in quarters_to_fetch:
            filename = f"{ticker.lower()}_Q{quarter}_{year}_transcript.md"
            filepath = docs_dir / filename

            if filepath.exists():
                count += 1
                continue

            content = None
            if api_key:
                print(f"  Fetching transcript: {ticker} Q{quarter} {year}")
                content = fetch_transcript(ticker, quarter, year, api_key)
                time.sleep(0.3)

            if content:
                md = (
                    f"# {name} Q{quarter} {year} Earnings Call Transcript\n\n"
                    f"**Ticker:** {ticker}  \n"
                    f"**Sector:** {sector}  \n"
                    f"**Period:** Q{quarter} {year}\n\n"
                    f"{content}\n"
                )
            else:
                md = (
                    f"# {name} Q{quarter} {year} Earnings Call\n\n"
                    f"**Ticker:** {ticker}  \n"
                    f"**Sector:** {sector}  \n"
                    f"**Period:** Q{quarter} {year}\n\n"
                    f"Transcript not available. Add FMP_API_KEY to .env "
                    f"(free at financialmodelingprep.com) to fetch real transcripts.\n"
                )

            filepath.write_text(md, encoding="utf-8")
            count += 1

    return count


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def seed_all(fmp_api_key: Optional[str] = None) -> None:
    print("=" * 60)
    print("Step 1/2  Building SQLite from real financials (yfinance)...")
    print("=" * 60)
    rows = build_sqlite()
    print(f"\n  Done — {rows} quarterly records across {len(COMPANIES)} companies.\n")

    print("=" * 60)
    print("Step 2/2  Writing earnings call transcript files...")
    print("=" * 60)
    key  = fmp_api_key or SETTINGS.fmp_api_key or None
    mode = "real transcripts via FMP API" if key else "placeholder files (no FMP_API_KEY set)"
    docs = build_transcripts(api_key=key)
    print(f"\n  Done — {docs} transcript files written ({mode}).")
    if not key:
        print("  Tip: set FMP_API_KEY in .env for real earnings call text.\n")
