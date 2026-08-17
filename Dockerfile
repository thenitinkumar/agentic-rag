# ── Stage 1: Build the React frontend ──────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend ──────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Build tools needed by some native extensions (chromadb, numpy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so this layer is cached unless requirements change
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model at build time so first query is instant
# (avoids a ~90MB Hugging Face download on container startup)
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy application source
COPY backend/ ./backend/
COPY main.py ./

# Copy the built React app from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy and prepare the startup script
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
