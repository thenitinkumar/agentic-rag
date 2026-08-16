"""SQLite helper shared by health and companies routes."""
from __future__ import annotations

import sqlite3

from backend.pipeline.config import SQLITE_PATH

from ..schemas import CompanyOut


def load_companies() -> list[CompanyOut]:
    if not SQLITE_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        rows = conn.execute(
            """SELECT ticker, company_name, sector, COUNT(*) AS quarters
               FROM financials
               GROUP BY ticker, company_name, sector
               ORDER BY sector, company_name"""
        ).fetchall()
        conn.close()
        return [
            CompanyOut(ticker=r[0], name=r[1], sector=r[2], quarters_available=r[3])
            for r in rows
        ]
    except Exception:
        return []
