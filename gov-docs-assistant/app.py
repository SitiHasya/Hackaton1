"""Chat UI. Run with:  streamlit run app.py"""
from pathlib import Path

import streamlit as st

import rag

st.set_page_config(page_title="Ask Our Documents", page_icon="📄", layout="wide")
st.title("📄 Ask Our Documents")
st.caption("Ask a question in English or Bahasa Malaysia. Answers come only from your documents, with sources.")

# ---------------- sidebar ----------------
with st.sidebar:
    st.header("Documents")
    st.write(f"Indexed chunks: **{rag.get_collection().count()}**")

    lib = rag.library_summary()
    with st.expander(f"📚 Library ({sum(len(v) for v in lib.values())} files)"):
        if not lib:
            st.caption("Nothing indexed yet.")
        for t in sorted(lib):
            st.markdown(f"**{t}** ({len(lib[t])})")
            for n, info in sorted(lib[t].items()):
                st.caption("• " + rag.file_label(n, info))

    types = rag.list_doc_types()
    chosen = st.multiselect("Filter by document type", options=types, default=[])
    top_k = st.slider("Passages to use", 2, 8, 5)

    st.divider()
    st.subheader("Add a document")
    up = st.file_uploader("PDF, DOCX, TXT or MD", type=["pdf", "docx", "txt", "md"])
    new_type = st.selectbox("Document type", ["sop", "circular", "minutes", "policy", "guideline", "report", "general"])
    if up and st.button("Add & index"):
        folder = rag.DOCS_DIR / new_type
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / up.name
        dest.write_bytes(up.getbuffer())
        with st.spinner("Indexing..."):
            n = rag.ingest_file(dest, doc_type=new_type)
        st.success(f"Added {up.name} ({n} chunks)")
        st.rerun()

    if st.button("Re-index everything in docs/"):
        with st.spinner("Indexing all documents..."):
            total = rag.ingest_all(progress=lambda m: None)
        st.success(f"Done: {total} chunks")
        st.rerun()

# ---------------- chat ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []


def show_sources(hits):
    with st.expander(f"Sources ({len(hits)})"):
        for i, h in enumerate(hits, start=1):
            m = h["meta"]
            st.markdown(f"**[{i}] {m['source']}** · page {m['page']} · _{m['doc_type']}_")
            st.caption(h["text"][:400] + ("..." if len(h["text"]) > 400 else ""))


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("hits"):
            show_sources(msg["hits"])

question = st.chat_input("e.g. What is the procedure for approving staff leave?")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        catalog = rag.answer_catalog_question(question)  # "how many files...?" answered from the database
        if catalog:
            hits, best = [], None
        else:
            with st.spinner("Searching documents..."):
                hits, best = rag.retrieve(question, k=top_k, doc_types=chosen or None)

        if catalog:
            reply = catalog
            st.markdown(reply)
        elif not hits:
            reply = "No documents are indexed yet. Add some in the sidebar or run `python ingest.py`."
            st.markdown(reply)
            hits = []
        elif best is not None and best > rag.MAX_DISTANCE:
            reply = ("I couldn't find anything relevant to that in the documents, "
                     "so I'd rather not guess. Try rephrasing, or check the document filter.")
            st.markdown(reply)
            hits = []
        else:
            reply = st.write_stream(rag.answer_stream(question, hits))
            show_sources(hits)

    st.session_state.messages.append({"role": "assistant", "content": reply, "hits": hits})