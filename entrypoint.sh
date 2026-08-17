#!/bin/bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Earnings Intelligence — Starting up"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Seed the SQLite database if it doesn't exist yet
if [ ! -f /app/data/company.db ]; then
    echo "[init] No database found — running seed (this may take a moment)..."
    python main.py seed
    echo "[init] Seed complete."
else
    echo "[init] Database already exists — skipping seed."
fi

# Build the Chroma vector index if it doesn't exist or is empty
if [ ! -d /app/data/chroma_index ] || [ -z "$(ls -A /app/data/chroma_index 2>/dev/null)" ]; then
    echo "[init] No vector index found — running ingest..."
    python main.py ingest
    echo "[init] Ingest complete."
else
    echo "[init] Vector index already exists — skipping ingest."
fi

echo "[init] All systems ready. Starting server on http://0.0.0.0:8000"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
