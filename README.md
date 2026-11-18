# IP-SAKTI: Traditional Knowledge Prior Art Intelligence Platform

IP-SAKTI links classical Ayurvedic literature (**Charaka Samhita**, via the NIIMH e-Samhita) to modern herbal-medicine patents. It surfaces possible prior-art overlap for **Section 3(p) of the Indian Patents Act, 1970**, which excludes traditional knowledge from patentability.

> **Status: v2 research prototype.** Its results are leads for an expert to review, not legal findings. The original Sanskrit is always the evidence; the English text is a machine-generated aid.

---

## How it works

The verse corpus is **romanized Sanskrit** (ITRANS-style, e.g. `haridrA`, `kuShTha`) and the patents are **English**. A general embedding model can't match the two directly. v1 tried, and it scored 5.6% on the eval. v2 bridges them with a curated lexicon:

```
NIIMH HTML ─► niimh_adapter ─► dedup_by_content ─► build_chunks ─► chunks.jsonl (11,364)
                                                                      │
Patents (82, India A61K36) ─────────────────────────────┐             │
                                                        ▼             ▼
                              lexicon/ (74 plants, 38 conditions: Sanskrit ↔ English ↔ botanical)
                                                        │  tag_entities.py
                                                        ▼
                     chunks_tagged.jsonl  +  patents_tagged.jsonl
                     (plants, conditions, english_view, e.g.
                      "Substances: Turmeric (Curcuma longa). Indications: Skin disease")
                                                        │  embed_v2.py  (bge-small-en-v1.5)
                                                        ▼
                     Qdrant: ip_sakti_niimh_v2 (5,250 therapeutic chunks), ip_sakti_patents_v2
                                                        │
                     api/search.py  hybrid score = 0.5·cosine + 0.5·entity overlap
                                    + honest abstention (calibrated threshold, and
                                      the hit must share the query's named entities)
                                                        │
                     api/main.py (FastAPI)  ◄──►  frontend/index.html
```

## Evaluation (`eval/run_eval.py`)

There are 52 queries: 36 should match and 16 are off-topic and should be refused. They are split into **dev**, used to calibrate the threshold to 0.59, and **test**, which is only reported. The table shows test-split results:

| Metric | v1 (MiniLM, raw Sanskrit) | **v2 (lexicon hybrid)** |
|---|---|---|
| Correct top result (positive queries) | 5.6% | **94.4%** |
| Precision@5 | 2.2% | **81.1%** |
| Correct abstention (off-topic queries) | 50% | **100%** |
| Patent → verse sharing its plant (13 patents) | 0 / 13 | **10 / 13** |

**Caveat:** relevance is judged by the lexicon tagger on each hit's raw text. That proves the right *entities* were found, not that the therapeutic claim matches, and v2 is judged by the same lexicon it uses to search. The next step is pairs labelled by a human expert in `data/labeled/`.

Only 13 of the 82 patents mention any plant from Charaka (most cover hops, cannabis, rye or Chinese herbs), so for most patents the right answer is "no traditional-knowledge overlap".

## Quickstart

```powershell
.\.venv\Scripts\pip install -r requirements.txt pytest
copy .env.example .env          # then choose a Qdrant mode (see below)

# Build the data (once)
.\.venv\Scripts\python ingestion\eda_agent\pipeline\tag_entities.py
.\.venv\Scripts\python ingestion\eda_agent\pipeline\embed_v2.py --v1   # --v1 also builds the baseline

# Run
.\.venv\Scripts\uvicorn api.main:app --reload --port 8000              # http://localhost:8000/docs
python -m http.server 3000 --directory frontend                        # http://localhost:3000

# Verify
.\.venv\Scripts\python -m pytest tests -q
.\.venv\Scripts\python eval\run_eval.py --calibrate --verbose
```

**Qdrant modes** (`api/search.py`, first match wins):
- `QDRANT_URL` + `QDRANT_API_KEY`: Qdrant Cloud.
- `QDRANT_PATH=qdrant_local`: embedded storage with no server or Docker. The embedded store allows only one process at a time, so stop the API before running the eval.
- Neither set: `localhost:6333` from `docker compose up -d`.

**Deploy** with the `Dockerfile` (Render or any Docker host). It contains only the API and lexicon, with the model built in. Point `QDRANT_URL` at a cloud cluster that already holds the `*_v2` collections.

## Optional: an English gloss from a free LLM

`ingestion/eda_agent/pipeline/enrich_chunks.py` adds a one-sentence English gloss to each chunk. It is resumable and can use **Ollama** locally or the **Gemini free tier** (`GEMINI_API_KEY`).

We tested local `llama3.2:3b` and it **hallucinated badly** on romanized Sanskrit. It described epistemology passages as "poison antidotes", so v2 ships **lexicon-only**. If you run this script, use Gemini, spot-check the output, then re-run `tag_entities.py` and `embed_v2.py`. Any gloss is appended after the lexicon description and never replaces it.

## Repository map

| Path | What |
|---|---|
| `lexicon/` | `plants.json`, `conditions.json` and `tagger.py`. Their regexes guard against false friends, documented in the tests. |
| `api/search.py` | v1 and v2 retrieval, hybrid scoring, abstention, Qdrant client factory |
| `api/main.py` | FastAPI: `POST /query` and `GET /health` |
| `ingestion/eda_agent/` | NIIMH adapter, then dedup, chunks, tags, embeddings. The `query_rag.py` and `compare_sources.py` scripts are the v1 command-line tools. |
| `eval/` | `holdout_cases.json` and `run_eval.py`. Results go to `eval/results/latest.json`. |
| `tests/` | pytest: lexicon, search logic (Qdrant mocked), NIIMH adapter |
| `frontend/` | Single-page app (`index.html`) and the original Stitch mockups (`stitch-screens/`) |
| `notes/` | Exploration findings, scrape logs, `architecture.md` |

## Roadmap
- Expert-labelled evaluation pairs, so precision covers the actual claims, not just the entities.
- Indian Kanoon case law (not started).
- Devanagari query input (needs a transliteration step into the corpus scheme).
- More lexicon coverage, especially formulations and synonyms for each plant.
