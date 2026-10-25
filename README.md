# IP-SAKTI

A retrieval pipeline that answers traditional-knowledge (Ayurveda) queries
grounded in classical texts, and cross-references them against patent
filings to flag potential overlap — built as a personal project based on
the Smart India Hackathon problem statement SIH26045 (IP-SAKTI Sahayak,
Ministry of AYUSH).

**Status: working local prototype / MVP backend.** This is not a hosted or
deployed product — everything currently runs locally via Docker. See
[Known Limitations](#known-limitations) before using any output as a
confirmed finding.

## What it does

1. Ingests and cleans verses + commentary from NIIMH's e-Samhita (Charaka
   Samhita digitized text)
2. Ingests India-jurisdiction, plant-based medicinal patents (CPC `A61K36`)
   from the Google Patents public BigQuery dataset
3. Embeds both corpora with a multilingual sentence-transformer and stores
   them in separate Qdrant collections
4. Given a query, searches traditional-knowledge text with an honest
   **abstention** when evidence is weak, and independently checks for
   potential patent overlap — the two never gate each other
5. Exposes this via a FastAPI endpoint and a minimal web frontend

## Architecture

```
NIIMH HTML pages          Google Patents (BigQuery)
       │                          │
   adapter/parser            SQL query (CPC + country filter)
       │                          │
  dedup (content-hash)      JSON export
       │                          │
  verse+commentary chunking       │
       │                          │
       ▼                          ▼
  sentence-transformers embeddings (same model, both sources)
       │                          │
       ▼                          ▼
  Qdrant: ip_sakti_niimh    Qdrant: ip_sakti_patents
                │                 │
                └────────┬────────┘
                         ▼
                  FastAPI /query endpoint
                   (independent search,
                    honest NIIMH abstention)
                         │
                         ▼
                  Static HTML/JS frontend
```

## Tech stack

- **Ingestion:** Python, BeautifulSoup (HTML parsing), Google BigQuery (patents)
- **Embeddings:** `sentence-transformers` — `paraphrase-multilingual-MiniLM-L12-v2`
- **Vector store:** Qdrant (Docker)
- **API:** FastAPI + Uvicorn
- **Frontend:** vanilla HTML/CSS/JS (no build step)
- *(Postgres is provisioned in `docker-compose.yml` for future structured/relational needs — not yet wired into the pipeline.)*

## Setup

### Prerequisites
- Python 3.10+
- Docker Desktop running

### Install
```powershell
pip install -r requirements.txt
docker-compose up -d
```

### Data pipeline (NIIMH)
```powershell
python test_niimh_candidates.py
python ingestion\eda_agent\pipeline\validate_candidates.py data\processed\niimh_verses.jsonl
python ingestion\eda_agent\pipeline\dedup_by_content.py
python ingestion\eda_agent\pipeline\build_chunks.py
python ingestion\eda_agent\pipeline\embed_and_upsert.py
```

### Data pipeline (Patents)
Patents are pulled manually via the BigQuery console (see `notes/` for the
query used) and saved to `data/raw/patents/india_a61k36_patents.json`, then:
```powershell
python ingestion\eda_agent\pipeline\embed_patents.py
```

### Run the API
```powershell
uvicorn api.main:app --reload --port 8000
```
Interactive docs at `http://localhost:8000/docs`.

### Run the frontend
Open `frontend\index.html` directly in a browser (no server needed).

## Known limitations

This section is here on purpose — treat it as part of the project, not a
footnote.

- **Cross-lingual retrieval gap.** The embedding model matches English
  queries against Sanskrit/IAST-transliterated text noticeably more weakly
  than same-language matches. A relevant English query can score well
  below a relevant Sanskrit-term query for the same concept.
- **Generic-attractor chunks.** Some short, term-dense NIIMH chunks
  surface as top matches for multiple unrelated queries — a sign of
  partial lexical rather than deep semantic matching. Treat any single
  NIIMH match with some skepticism until this is addressed.
- **Small patent sample (82 records).** Strict filtering (India
  jurisdiction + CPC `A61K36` + English abstract present) leaves a small
  usable set — most India-origin patents in this dataset lack an English
  abstract at all. Scope was deliberately kept to India-only for build
  speed; a global pull would better match the actual TK-overlap use case
  this project is aimed at, at higher BigQuery cost.
- **Verse–commentary join is incomplete.** Only ~12.6% of NIIMH chunks
  are verse+commentary pairs; the rest are standalone verse or commentary
  chunks, because the join only matches exact `unit_id` — commentary
  spanning a verse range isn't linked. Documented, not yet fixed.
- **No re-ranking.** Retrieval is raw cosine similarity only — there's no
  second-pass re-ranking step, which would likely improve precision on
  top results.
- **Not deployed.** Local Docker only; no auth, no multi-tenancy, no
  hosting.

## License

MIT — see `LICENSE`.
