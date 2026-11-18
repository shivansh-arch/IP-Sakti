# IP-SAKTI

A retrieval pipeline that answers traditional-knowledge (Ayurveda) queries grounded in classical texts, and cross-references them against patent filings to flag potential overlap. It's a personal project based on the Smart India Hackathon problem statement SIH26045 (IP-SAKTI Sahayak, Ministry of AYUSH).

The aim is to surface **prior art** from the **Charaka Samhita** (via NIIMH e-Samhita) for herbal-medicine patents, in the spirit of **Section 3(p) of the Indian Patents Act, 1970**, which excludes traditional knowledge from patentability.

**Status: working local prototype (v2 retrieval).** It is not a hosted product. See [Known limitations](#known-limitations) before treating any output as a confirmed finding. Results are leads for expert review, not legal findings; the original Sanskrit text is always the evidence.

## What it does

1. Ingests and cleans verses and commentary from NIIMH's e-Samhita (digitised Charaka Samhita text).
2. Ingests India-jurisdiction, plant-based medicinal patents (CPC `A61K36`) from the Google Patents public BigQuery dataset.
3. **Tags both corpora with a curated lexicon** of 74 plants and 38 conditions, mapping Sanskrit, English and botanical names (`haridrA` ↔ turmeric ↔ *Curcuma longa*).
4. Embeds an English description of each tagged passage and each patent, and stores them in separate Qdrant collections.
5. Given a query, searches the classical text with **hybrid scoring** (semantic similarity plus shared plants and conditions) and an honest **abstention** when evidence is weak. It independently checks for patent overlap; the two searches never gate each other.
6. Exposes this via a FastAPI endpoint and a static web frontend that cites passages by *sthāna* and *adhyāya*, for example *Cikitsāsthāna 29.142*.

## Why v2

The corpus is **romanised Sanskrit** (ITRANS-style, e.g. `haridrA`, `kuShTha`) and the patents are **English**. v1 embedded the raw Sanskrit with a multilingual model that has never seen this romanisation, so cross-lingual matches were mostly noise. On the evaluation set it ranked the right passage first for 5.6% of held-out queries.

v2 bridges the two languages with a controlled vocabulary instead of hoping the embedding model learns Sanskrit. The design rationale is in [`notes/architecture.md`](notes/architecture.md).

## Architecture

```
NIIMH HTML pages                         Google Patents (BigQuery)
       │                                          │
  niimh_adapter (verse/commentary parser)    SQL query (CPC + country filter)
       │                                          │
  dedup_by_content ─► build_chunks           JSON export (82 patents)
       │   chunks.jsonl (11,364)                  │
       └──────────────────┬───────────────────────┘
                          ▼
     lexicon/  74 plants · 38 conditions  (Sanskrit ↔ English ↔ botanical)
                          │  tag_entities.py
                          ▼
     chunks_tagged.jsonl + patents_tagged.jsonl
     (plants, conditions, english_view, e.g.
      "Substances: Turmeric (Curcuma longa). Indications: Skin disease")
                          │  embed_v2.py  (BAAI/bge-small-en-v1.5)
                          ▼
     Qdrant: ip_sakti_niimh_v2 (5,250 passages) · ip_sakti_patents_v2 (82)
                          │
     api/search.py   score = 0.5 · cosine + 0.5 · entity overlap
                     + abstention (calibrated threshold, and the best hit
                       must share the query's named plants/conditions)
                          │
     api/main.py (FastAPI: /query, /stats, /health)  ◄──►  frontend/index.html
```

## Evaluation (`eval/run_eval.py`)

There are 52 queries: 36 that should match and 16 off-topic ones that should be refused. They are split into **dev**, used to calibrate the threshold to 0.59, and **test**, which is only reported. The table shows test-split results:

| Metric | v1 (MiniLM, raw Sanskrit) | **v2 (lexicon hybrid)** |
|---|---|---|
| Correct top result (positive queries) | 5.6% | **94.4%** |
| Precision@5 | 2.2% | **81.1%** |
| Correct abstention (off-topic queries) | 50% | **100%** |
| Patent → passage sharing its plant (13 patents) | 0 / 13 | **10 / 13** |

**Caveat:** relevance is judged by the lexicon tagger on each hit's raw text. That shows the right *entities* were found, not that the therapeutic claim matches, and v2 is judged by the same lexicon it searches with. Expert-labelled pairs are the next step.

## Tech stack

- **Ingestion:** Python, BeautifulSoup (HTML parsing), Google BigQuery (patents)
- **Entity bridge:** curated regex lexicon (`lexicon/`) with tests for each false friend
- **Embeddings:** `BAAI/bge-small-en-v1.5` for v2, served through ONNX (`fastembed`). It gives the same vectors as `sentence-transformers` (cosine 1.0000) at a fraction of the memory. `paraphrase-multilingual-MiniLM-L12-v2` (PyTorch) is kept as the offline v1 baseline.
- **Vector store:** Qdrant: Cloud, embedded local storage, or Docker
- **API:** FastAPI + Uvicorn
- **Frontend:** plain HTML/CSS/JS with no build step
- *(Postgres is provisioned in `docker-compose.yml` for future structured needs but is not yet wired into the pipeline.)*

## Setup

### Prerequisites
- Python 3.10+
- A Qdrant instance: Qdrant Cloud, Docker Desktop (`docker compose up -d`), or nothing at all (embedded local mode, see below)

### Install
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt pytest
copy .env.example .env      # then choose a Qdrant mode
```

**Qdrant modes** (`api/search.py`, first match wins):
- `QDRANT_URL` + `QDRANT_API_KEY`: Qdrant Cloud.
- `QDRANT_PATH=qdrant_local`: embedded storage with no server or Docker. Only one process can open it at a time.
- Neither set: `localhost:6333` from `docker compose up -d`.

### Data pipeline (NIIMH)
```powershell
python test_niimh_candidates.py
python ingestion\eda_agent\pipeline\validate_candidates.py data\processed\niimh_verses.jsonl
python ingestion\eda_agent\pipeline\dedup_by_content.py
python ingestion\eda_agent\pipeline\build_chunks.py
```

### Data pipeline (Patents)
Patents are pulled manually through the BigQuery console (the query is in `notes/`) and saved to `data/raw/patents/india_a61k36_patents.json`.

### Tag and index (v2)
```powershell
python ingestion\eda_agent\pipeline\tag_entities.py
python ingestion\eda_agent\pipeline\embed_v2.py          # add --v1 to also build the baseline
```

### Run
```powershell
.\.venv\Scripts\uvicorn api.main:app --port 8000          # docs: http://localhost:8000/docs
python -m http.server 3000 --directory frontend          # http://localhost:3000
```
You can also open `frontend\index.html` directly in a browser.

### Verify
```powershell
.\.venv\Scripts\python -m pytest tests -q
.\.venv\Scripts\python eval\run_eval.py --calibrate --verbose
```

### Deploy (Render, free)
The `Dockerfile` builds one image that serves both the API and the website, with the ONNX model built in and no PyTorch. Locally it peaks at about 340 MB of RAM, under Render's 512 MB free tier.

1. Open https://dashboard.render.com/blueprint/new?repo=https://github.com/shivansh-arch/IP-Sakti. `render.yaml` defines the service.
2. Enter `QDRANT_URL` and `QDRANT_API_KEY` when Render asks. They point at a Qdrant cluster that already holds the `*_v2` collections.
3. Render builds and deploys, and redeploys on every push to `Main`. Free instances sleep after 15 minutes idle and take about a minute to wake.

The same image also runs on a Hugging Face Docker Space (`deploy/push_space.py`), but those now need an HF PRO plan.

### Optional: English gloss from a free LLM
`ingestion/eda_agent/pipeline/enrich_chunks.py` adds a one-sentence gloss to each passage, using Ollama locally or the Gemini free tier. It is resumable. Local `llama3.2:3b` **hallucinated** on romanised Sanskrit in testing, so v2 ships lexicon-only. If you use it, use a stronger model and spot-check the output. Any gloss is appended after the lexicon description and never replaces it.

## Known limitations

This section is here on purpose. Treat it as part of the project, not a footnote.

- **Cross-lingual gap: mitigated, not solved.** v2 bridges English and romanised Sanskrit through the lexicon, but a plant or condition outside its 74 + 38 entries gets semantic similarity alone and usually abstains. Devanagari input (हरिद्रा) isn't transliterated yet.
- **Ambiguous Sanskrit terms.** Words with two meanings are mostly left out of the lexicon (`nAgara` is ginger or city; `abhayA` is haritaki or fearless). `kuShTha` is kept as *skin disease*, but in ingredient lists it is often the herb costus (*Saussurea*), so some "skin disease" matches are really ingredient lists.
- **Generic-attractor chunks: reduced.** Long commentary passages mention many diseases as examples and pick up many tags. Requiring query entities to be shared before answering cuts down vague matches, but these passages can still rank higher than they deserve. Weighting entities by how often they appear (IDF) would help.
- **Evaluation is lexicon-judged.** See the caveat above. The numbers show entity retrieval, not verified prior art.
- **Small patent sample (82 records).** Strict filtering (India jurisdiction, CPC `A61K36`, English abstract present) leaves a small set; most India-origin patents in this dataset have no English abstract. Only 13 of the 82 mention a plant from Charaka, so for most of them the correct answer is no traditional-knowledge overlap. A global pull would suit the use case better, at higher BigQuery cost.
- **Verse–commentary join is incomplete.** Only about 12.6% of NIIMH chunks are verse+commentary pairs. The join matches exact `unit_id` only, so commentary spanning a verse range isn't linked.
- **Free-tier hosting.** The Render deployment sleeps when idle and has no auth or rate limiting.

## Repository map

| Path | What |
|---|---|
| `lexicon/` | `plants.json`, `conditions.json` and `tagger.py`; the false-friend guards are documented in the tests |
| `api/search.py` | v1 and v2 retrieval, hybrid scoring, abstention, Qdrant client factory |
| `api/main.py` | FastAPI: `POST /query`, `GET /stats`, `GET /health` |
| `api/chapters.json` | *Adhyāya* map used to cite passages by *sthāna* and chapter |
| `ingestion/eda_agent/` | NIIMH adapter, then dedup, chunks, tags, embeddings (`query_rag.py` and `compare_sources.py` are the v1 command-line tools) |
| `eval/` | Test cases and harness; results in `eval/results/latest.json` |
| `tests/` | pytest: lexicon, search logic (Qdrant mocked), NIIMH adapter |
| `frontend/` | Search interface (`index.html`) and the original Stitch mockups |
| `notes/` | Exploration findings, scrape logs, `architecture.md` |

## License

MIT. See `LICENSE`.
