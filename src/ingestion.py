"""
Ingestion: load markdown docs -> chunk -> embed -> persist to a local
Chroma collection.

Chunking is a simple recursive character splitter (paragraph -> sentence
fallback) rather than a hand-wavy fixed-size split, so chunk boundaries
tend to land on natural breakpoints. This is intentionally dependency-light
(no heavy text-splitting library) so the logic is easy to read and reason
about in an interview.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .config import SETTINGS, DOCS_DIR, CHROMA_DIR


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Recursively split on paragraph, then sentence, then hard character
    boundaries, merging pieces up to chunk_size with chunk_overlap carried
    between adjacent chunks."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    buffer = ""

    def flush():
        nonlocal buffer
        if buffer.strip():
            chunks.append(buffer.strip())
        buffer = ""

    for para in paragraphs:
        candidate = f"{buffer}\n\n{para}".strip() if buffer else para
        if len(candidate) <= chunk_size:
            buffer = candidate
            continue
        # paragraph alone is too big, or buffer+para overflowed: flush then
        # possibly split the paragraph itself on sentences
        flush()
        if len(para) <= chunk_size:
            buffer = para
        else:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            sbuf = ""
            for sent in sentences:
                cand = f"{sbuf} {sent}".strip() if sbuf else sent
                if len(cand) <= chunk_size:
                    sbuf = cand
                else:
                    if sbuf:
                        chunks.append(sbuf.strip())
                    sbuf = sent
            if sbuf:
                buffer = sbuf
    flush()

    if chunk_overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-chunk_overlap:]
            overlapped.append((tail + " " + chunks[i]).strip())
        return overlapped
    return chunks


def load_documents(docs_dir: Path = DOCS_DIR) -> List[dict]:
    docs = []
    for path in sorted(docs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title_match = re.match(r"#\s*(.+)", text)
        title = title_match.group(1).strip() if title_match else path.stem
        docs.append({"source": path.name, "title": title, "text": text})
    return docs


def build_vector_index(persist_dir: Path = CHROMA_DIR, docs_dir: Path = DOCS_DIR) -> int:
    """Build (or rebuild) the Chroma collection. Returns number of chunks indexed."""
    import chromadb
    from chromadb.utils import embedding_functions

    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))

    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=SETTINGS.embedding_model
    )

    # Fresh build each time ingestion is run explicitly.
    try:
        client.delete_collection("docs")
    except Exception:
        pass
    collection = client.create_collection("docs", embedding_function=embed_fn)

    documents, metadatas, ids = [], [], []
    for doc in load_documents(docs_dir):
        chunks = split_text(doc["text"], SETTINGS.chunk_size, SETTINGS.chunk_overlap)
        for i, chunk in enumerate(chunks):
            documents.append(chunk)
            metadatas.append({"source": doc["source"], "title": doc["title"], "chunk_index": i})
            ids.append(f"{doc['source']}::{i}")

    if documents:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
    return len(documents)


if __name__ == "__main__":
    n = build_vector_index()
    print(f"Indexed {n} chunks into {CHROMA_DIR}")
