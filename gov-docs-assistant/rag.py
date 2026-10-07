"""Core logic: read documents -> chunk -> embed -> store -> search -> answer.
Everything runs locally via Ollama + ChromaDB.
"""
import os
import re
import hashlib
from pathlib import Path

import chromadb
import ollama
from rank_bm25 import BM25Okapi

# ---------- settings (change with environment variables) ----------
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")        # multilingual (English + Bahasa Malaysia)
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")       # small, runs on most laptops
DOCS_DIR = Path(os.getenv("DOCS_DIR", "docs"))
DB_DIR = os.getenv("DB_DIR", "db")
COLLECTION = "gov_docs"
CHUNK_SIZE = 900        # characters per chunk
CHUNK_OVERLAP = 150     # characters shared between neighbouring chunks
MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "0.65"))  # above this = "not relevant enough"

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}


# ---------- 1. reading files ----------
def load_file(path: Path):
    """Return a list of (page_number, text)."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        import fitz  # PyMuPDF
        pages = []
        with fitz.open(path) as pdf:
            for i, page in enumerate(pdf, start=1):
                pages.append((i, page.get_text()))
        return pages
    if ext == ".docx":
        import docx
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        d = docx.Document(str(path))
        parts = []
        # walk the body in order so paragraphs AND tables are both read
        for child in d.element.body.iterchildren():
            if child.tag.endswith("}p"):
                parts.append(Paragraph(child, d).text)
            elif child.tag.endswith("}tbl"):
                for row in Table(child, d).rows:
                    cells = []
                    for c in row.cells:
                        t = c.text.strip()
                        if t and (not cells or cells[-1] != t):  # merged cells repeat their text
                            cells.append(t)
                    if cells:
                        parts.append(" | ".join(cells))
        return [(1, "\n".join(parts))]
    if ext in {".txt", ".md"}:
        return [(1, path.read_text(encoding="utf-8", errors="ignore"))]
    return []


# ---------- 2. chunking ----------
def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):  # try to cut at a sentence/paragraph end
            cut = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if cut > start + size // 2:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


# ---------- 3. embeddings + database ----------
def embed(texts, batch=16):
    out = []
    for i in range(0, len(texts), batch):
        out.extend(ollama.embed(model=EMBED_MODEL, input=texts[i:i + batch])["embeddings"])
    return out


def get_collection():
    client = chromadb.PersistentClient(path=DB_DIR)
    return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def guess_doc_type(path: Path):
    """docs/sop/x.pdf -> 'sop'. Files directly in docs/ -> 'general'."""
    try:
        rel = path.relative_to(DOCS_DIR)
        return rel.parts[0].lower() if len(rel.parts) > 1 else "general"
    except ValueError:
        return "general"


def guess_year(name: str):
    m = re.search(r"(19|20)\d{2}", name)
    return m.group(0) if m else ""


def ingest_file(path: Path, doc_type: str = None):
    path = Path(path)
    doc_type = doc_type or guess_doc_type(path)
    ids, docs, metas = [], [], []
    for page_no, text in load_file(path):
        for j, chunk in enumerate(chunk_text(text)):
            ids.append(hashlib.md5(f"{path.name}|{page_no}|{j}|{chunk[:50]}".encode()).hexdigest())
            # put the document name inside the text, so questions like "Milestone 1" can match it
            docs.append(f"Document: {path.stem}\n{chunk}")
            metas.append({"source": path.name, "page": page_no,
                          "doc_type": doc_type, "year": guess_year(path.name)})
    if not docs:
        return 0
    col = get_collection()
    col.upsert(ids=ids, documents=docs, embeddings=embed(docs), metadatas=metas)
    return len(docs)


def reset_collection():
    """Wipe the index so old chunks never linger after files change."""
    client = chromadb.PersistentClient(path=DB_DIR)
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    _cache["count"] = -1


def ingest_all(progress=print):
    reset_collection()
    total = 0
    files = [p for p in DOCS_DIR.rglob("*") if p.suffix.lower() in SUPPORTED]
    for p in sorted(files):
        n = ingest_file(p)
        progress(f"{p.name}: {n} chunks")
        total += n
    return total


def list_doc_types():
    col = get_collection()
    if col.count() == 0:
        return []
    metas = col.get(include=["metadatas"])["metadatas"]
    return sorted({m["doc_type"] for m in metas})


# ---------- library overview (answers "what files do you have?" without the AI) ----------
def library_summary():
    """{doc_type: {file_name: {"pages": n, "chunks": n}}} built from the database."""
    col = get_collection()
    if col.count() == 0:
        return {}
    lib = {}
    for m in col.get(include=["metadatas"])["metadatas"]:
        info = lib.setdefault(m["doc_type"], {}).setdefault(m["source"], {"pages": 0, "chunks": 0})
        info["pages"] = max(info["pages"], int(m["page"]))
        info["chunks"] += 1
    return lib


def file_label(name, info):
    if name.lower().endswith(".pdf"):
        n = info["pages"]
        return f"{name} ({n} page{'s' if n != 1 else ''})"
    return name


_ITEM = r"(?:files?|documents?|docs?|pdfs?|reports?)"
_CATALOG_REGEXES = [
    rf"\bhow many {_ITEM}\b",
    rf"^\W*(?:please )?(?:list|show|display)(?: me)?(?: all)?(?: the)?(?: available| indexed| uploaded)? {_ITEM}"
    rf"(?: you have| available| indexed| uploaded)?(?: (?:in|under|inside) .*)?\W*$",
    rf"\bwhat {_ITEM} (?:do you have|are (?:there|available|indexed|uploaded|stored)|have been (?:uploaded|indexed))",
    rf"\bwhich {_ITEM} (?:do you have|are (?:there|available|indexed|uploaded|stored))",
    rf"\b{_ITEM} (?:are )?(?:in|under|inside) (?:the )?[\w -]*(?:folder|library)\b",
    r"\bberapa(?: banyak)? (?:fail|dokumen)\b",
    r"\bsenarai (?:semua )?(?:fail|dokumen)\b",
]
# "how many documents are required to apply..." is a content question, not a library question
_NOT_CATALOG = re.compile(r"\b(required|require|needed|need|must|submit|attach|supporting|procedure|steps|apply|application)\b")


def answer_catalog_question(question: str):
    """If the question is about the library itself (counts / lists of files), answer it from the
    database and return markdown. Otherwise return None."""
    q = question.lower().strip()
    lib = library_summary()
    types = sorted(lib, key=len, reverse=True)

    hit = any(re.search(p, q) for p in _CATALOG_REGEXES)
    if not hit and types:  # e.g. "list all circulars"
        types_re = "|".join(re.escape(t) for t in types)
        hit = bool(re.search(rf"^\W*(?:list|show|display)(?: me)?(?: all)?(?: the)? (?:{types_re})s?\W*$", q))
    if not hit or _NOT_CATALOG.search(q):
        return None
    if not lib:
        return "No documents are indexed yet. Add some in the sidebar or run `python ingest.py`."

    wanted = [t for t in types if re.search(rf"\b{re.escape(t)}s?\b", q)]
    m = re.search(r"\b([\w-]+) (?:folder|category)\b", q)
    if m and not wanted and m.group(1) not in {"the", "a", "this", "that", "which", "each", "every", "what", "any"}:
        return (f"I couldn't find a folder called **{m.group(1)}**. "
                f"Available folders: {', '.join(f'**{t}**' for t in sorted(lib))}.")

    scope = {t: lib[t] for t in wanted} if wanted else lib
    total = sum(len(v) for v in scope.values())
    s = "" if total == 1 else "s"
    where = (f"in {', '.join(f'**{t}**' for t in sorted(scope))}" if wanted
             else f"in the library, across {len(scope)} folder{'' if len(scope) == 1 else 's'}")
    out = [f"There {'is' if total == 1 else 'are'} **{total} file{s}** {where}:", ""]
    for t in sorted(scope):
        out.append(f"**{t}** ({len(scope[t])} file{'' if len(scope[t]) == 1 else 's'})")
        out.append("")
        out += [f"- {file_label(n, i)}" for n, i in sorted(scope[t].items())]
        out.append("")
    return "\n".join(out)


# ---------- 4. search (meaning + keywords) ----------
_cache = {"count": -1}


def _tok(s: str):
    return re.findall(r"\w+", s.lower())


def _bm25(col):
    n = col.count()
    if _cache["count"] != n:
        data = col.get(include=["documents", "metadatas"])
        _cache.update(count=n, ids=data["ids"], docs=data["documents"], metas=data["metadatas"],
                      bm25=BM25Okapi([_tok(d) for d in data["documents"]]) if data["documents"] else None)
    return _cache


def retrieve(question: str, k: int = 5, doc_types=None):
    """Return (hits, best_distance). Each hit = {text, meta}."""
    col = get_collection()
    if col.count() == 0:
        return [], None
    where = {"doc_type": {"$in": list(doc_types)}} if doc_types else None

    # (a) semantic search
    sem = col.query(query_embeddings=embed([question]), n_results=min(20, col.count()),
                    where=where, include=["documents", "metadatas", "distances"])
    sem_ids = sem["ids"][0]
    best_dist = sem["distances"][0][0] if sem["distances"][0] else None
    store = {i: {"text": t, "meta": m} for i, t, m in zip(sem_ids, sem["documents"][0], sem["metadatas"][0])}

    # (b) keyword search (good for exact things like "Circular 3/2024")
    c = _bm25(col)
    kw_ids = []
    if c["bm25"] is not None:
        scores = c["bm25"].get_scores(_tok(question))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:20]
        for i in order:
            if scores[i] <= 0:
                break
            if doc_types and c["metas"][i]["doc_type"] not in doc_types:
                continue
            kw_ids.append(c["ids"][i])
            store.setdefault(c["ids"][i], {"text": c["docs"][i], "meta": c["metas"][i]})

    # (c) merge the two rankings (reciprocal rank fusion)
    score = {}
    for ranking in (sem_ids, kw_ids):
        for rank, cid in enumerate(ranking):
            score[cid] = score.get(cid, 0) + 1 / (60 + rank)
    top = sorted(score, key=score.get, reverse=True)[:k]
    return [store[i] for i in top], best_dist


# ---------- 5. answer with citations ----------
SYSTEM_PROMPT = (
    "You are an assistant for government staff. Answer the question using ONLY the numbered "
    "context passages below. After each fact, cite the passage number like [1] or [2]. "
    "If the context does not contain the answer, say you could not find it in the documents. "
    "Answer in the same language as the question. Be short and clear."
)


def answer_stream(question: str, hits):
    context = "\n\n".join(
        f"[{i}] ({h['meta']['source']}, page {h['meta']['page']})\n{h['text']}"
        for i, h in enumerate(hits, start=1)
    )
    stream = ollama.chat(
        model=LLM_MODEL,
        stream=True,
        options={"temperature": 0.1},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    for part in stream:
        yield part["message"]["content"]