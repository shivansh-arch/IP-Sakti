"""
api/main.py

FastAPI wrapper around api/search.py.

Run:  uvicorn api.main:app --reload --port 8000
Then: POST http://localhost:8000/query  {"query": "turmeric for skin disease"}
      or browse http://localhost:8000/docs

RETRIEVAL_ENGINE=v2 (default) uses the lexicon-bridged hybrid search;
RETRIEVAL_ENGINE=v1 serves the original MiniLM baseline for comparison.
See api/search.py for how Qdrant is located (cloud / embedded / localhost).

Response shape is backward compatible with the v1 frontend: every v1 field
is still present; v2 only ADDS fields (query_entities, matched, english_view,
tk_evidence, ...).
"""

import json
import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api import search
from lexicon import CONDITIONS, PLANTS

ENGINE = os.environ.get("RETRIEVAL_ENGINE", "v2")
TOP_K = 5

app = FastAPI(title=f"IP-SAKTI API ({ENGINE})")

# Open CORS for local dev / demo — set ALLOWED_ORIGINS="https://your.site"
# (comma-separated) before a real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


# adhyaya_val -> {sthana, sthana_name, adhyaya, title}, built from the NIIMH
# chapter map so verses can be cited as e.g. "Cikitsasthana 7.142".
_CHAPTERS = json.loads((Path(__file__).parent / "chapters.json").read_text(encoding="utf-8"))


def _citation(p: dict) -> dict | None:
    ch = _CHAPTERS.get(str(p.get("chapter")))
    if not ch or ch["sthana"] != str(p.get("book")):
        return None
    unit = str(p.get("unit_id") or "")
    verse = unit if unit and not unit.startswith(("unmarked", "colophon")) else None
    label = f"{ch['sthana_name']} {ch['adhyaya'] or ''}".strip() + (f".{verse}" if verse and ch["adhyaya"] else (f", v. {verse}" if verse else ""))
    return {**ch, "verse": verse, "label": label}


def _chunk(r: dict) -> dict:
    p = r["payload"]
    return {
        "citation": _citation(p),
        "score": r["score"],
        "dense_score": r["dense"],
        "entity_score": r["entity"],
        "matched": r["shared"],
        "chunk_id": p.get("chunk_id"),
        "chunk_type": p.get("chunk_type"),
        "book": p.get("book"),
        "chapter": p.get("chapter"),
        "text": p.get("text"),
        "english_view": p.get("english_view"),
        "gloss": p.get("gloss"),
    }


def _patent(r: dict) -> dict:
    p = r["payload"]
    ev = search.niimh_evidence_for_patent(p, k=1)
    return {
        "score": r["score"],
        "matched": r["shared"],
        "publication_number": p.get("publication_number"),
        "publication_date": p.get("publication_date"),
        "plants": p.get("plants"),
        "conditions": p.get("conditions"),
        "text": (p.get("text") or "")[:300],
        # the closest Charaka verse for THIS patent, judged on the patent's
        # own entities — the actual prior-art link a reviewer would check
        "tk_evidence": _chunk(ev[0]) if ev and ev[0]["entity"] > 0 else None,
    }


@app.post("/query")
def query(request: QueryRequest):
    q = request.query.strip()

    if ENGINE == "v1":
        n = search.search_niimh_v1(q, k=TOP_K)
        model = search.get_model(search.V1_MODEL)
        pts = search.get_client().query_points(search.V1_PATENTS, query=model.encode(q).tolist(),
                                               limit=3, with_payload=True).points
        patents = [{"score": p.score, "publication_number": p.payload.get("publication_number"),
                    "text": (p.payload.get("text") or "")[:300]} for p in pts]
        return {
            "engine": "v1",
            "niimh": {"abstained": n["abstained"], "threshold": n["threshold"],
                      "top_score": n["results"][0]["score"] if n["results"] else None,
                      "results": [] if n["abstained"] else [_chunk(r) for r in n["results"]]},
            "potential_patent_overlap": patents,
            "quality_note": "v1 baseline: multilingual MiniLM over raw romanized Sanskrit.",
        }

    # NIIMH and patent search run INDEPENDENTLY — a confident patent match is
    # never hidden because NIIMH abstained, and vice versa.
    n = search.search_niimh_v2(q, k=TOP_K)
    pt = search.search_patents_v2(q, k=3)
    return {
        "engine": "v2",
        "query_entities": n["query_entities"],
        "niimh": {
            "abstained": n["abstained"],
            "top_score": n["results"][0]["score"] if n["results"] else None,
            "threshold": n["threshold"],
            "results": [] if n["abstained"] else [_chunk(r) for r in n["results"]],
        },
        "potential_patent_overlap": [] if pt["abstained"] else [_patent(r) for r in pt["results"]],
        "patents_abstained": pt["abstained"],
        "quality_note": (
            "v2 hybrid retrieval: score = 0.5 x semantic similarity of the English "
            "description + 0.5 x overlap of lexicon-tagged plants/conditions. "
            "Matches are leads for expert review, not legal findings — the original "
            "Sanskrit text is the evidence; English views are machine-generated aids."
        ),
    }


@lru_cache(maxsize=1)
def _stats() -> dict:
    c = search.get_client()
    return {
        "niimh_passages_indexed": c.count(search.V2_NIIMH).count,
        "patents_indexed": c.count(search.V2_PATENTS).count,
        "lexicon_plants": len(PLANTS),
        "lexicon_conditions": len(CONDITIONS),
        "embedding_model": search.V2_MODEL,
        "niimh_threshold": search.V2_NIIMH_THRESHOLD,
    }


@app.get("/stats")
def stats():
    return _stats()


@app.get("/health")
def health():
    return {"status": "ok", "engine": ENGINE}
