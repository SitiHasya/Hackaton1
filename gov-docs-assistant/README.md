# Ask Our Documents (local RAG)

Ask questions about government documents (SOPs, circulars, minutes, reports) and get answers
with sources. Everything runs on your own computer: no data leaves the machine.

## One-time setup

1. Install Ollama: https://ollama.com/download
2. Download the two models (needs internet, once only):

   ```
   ollama pull bge-m3          # reads meaning (English + Malay)
   ollama pull llama3.2:3b     # writes the answers (small, laptop friendly)
   ```

   Weak laptop (8 GB RAM)? Try `llama3.2:1b`. Strong laptop / GPU? Try `qwen2.5:7b` or `llama3.1:8b`.
   Switch models with: `set LLM_MODEL=qwen2.5:7b` (Windows) or `export LLM_MODEL=qwen2.5:7b` (Mac/Linux).

3. Install Python packages:

   ```
   python -m venv venv
   venv\Scripts\activate        # Windows   (Mac/Linux: source venv/bin/activate)
   pip install -r requirements.txt
   ```

## Run it

1. Put documents in the `docs/` folder. The sub-folder name becomes the document type:
   `docs/sop/`, `docs/circular/`, `docs/minutes/` (make any folder you like).
2. Index them: `python ingest.py`
3. Start the app: `streamlit run app.py`

You can also upload documents from the app's sidebar.

## Tips for the demo

- Use text-based PDFs (you can select the text). Scanned PDFs need OCR, which this starter skips.
- Put the year in the filename (`circular_3_2024.pdf`) and it shows up as metadata.
- If it refuses too often, raise `MAX_DISTANCE` (default 0.65). If it answers off-topic questions, lower it.
- Prepare 5 to 6 questions: simple lookup, one combining two documents, one in Bahasa Malaysia,
  and one that should be refused ("What is the CEO's salary?" when no document says so).

## Files

| File | What it does |
|---|---|
| `rag.py` | The brain: read, chunk, embed, store, search, answer |
| `ingest.py` | Command to index everything in `docs/` |
| `app.py` | The chat website (Streamlit) |
