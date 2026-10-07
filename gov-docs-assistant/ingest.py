"""Run this once (and again whenever you add documents to the docs/ folder):

    python ingest.py
"""
from rag import ingest_all, DOCS_DIR

if __name__ == "__main__":
    print(f"Reading documents from: {DOCS_DIR.resolve()}")
    total = ingest_all()
    print(f"\nDone. {total} chunks indexed.")
