"""
api/main.py

Single endpoint wrapping the existing RAG query + cross-source overlap
logic into something demoable, instead of separate terminal scripts.

Run: uvicorn api.main:app --reload --port 8000
Then: POST http://localhost:8000/query  with JSON body {"query": "..."}
Or browse http://localhost:8000/docs for interactive Swagger UI.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
NIIMH_COLLECTION = "ip_sakti_niimh"
PATENTS_COLLECTION = "ip_sakti_patents"
NIIMH_THRESHOLD = 0.3  # reverted — lowering to 0.25 let noise through (generic-attractor
                       # chunks), not real matches. The cross-lingual gap is better handled
                       # by decoupling NIIMH/patent search (below) than by threshold tuning.
TOP_K = 5

app = FastAPI(title="IP-SAKTI API (v1)")

# Open CORS for local dev — tighten this before any real deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load once at startup, not per-request
model = SentenceTransformer(MODEL_NAME)
client = QdrantClient(host="localhost", port=6333, check_compatibility=False)


class QueryRequest(BaseModel):
    query: str


@app.post("/query")
def query(request: QueryRequest):
    vector = model.encode(request.query).tolist()

    # NIIMH and patent search run INDEPENDENTLY — a confident patent match
    # must never be hidden just because NIIMH's (weaker, cross-lingual)
    # search had a bad day, and vice versa.
    niimh_response = client.query_points(
        collection_name=NIIMH_COLLECTION,
        query=vector,
        limit=TOP_K,
    )
    niimh_points = niimh_response.points
    niimh_abstained = not niimh_points or niimh_points[0].score < NIIMH_THRESHOLD

    niimh_section = {
        "abstained": niimh_abstained,
        "top_score": niimh_points[0].score if niimh_points else None,
        "threshold": NIIMH_THRESHOLD,
        "results": [] if niimh_abstained else [
            {
                "score": p.score,
                "chunk_id": p.payload.get("chunk_id"),
                "chunk_type": p.payload.get("chunk_type"),
                "text": p.payload.get("text"),
            }
            for p in niimh_points
        ],
    }

    patent_response = client.query_points(
        collection_name=PATENTS_COLLECTION,
        query=vector,
        limit=3,
    )
    patent_results = [
        {
            "score": p.score,
            "publication_number": p.payload.get("publication_number"),
            "text": p.payload.get("text", "")[:300],
        }
        for p in patent_response.points
    ]

    return {
        "niimh": niimh_section,
        "potential_patent_overlap": patent_results,
        "quality_note": (
            "v1 retrieval quality: NIIMH (Sanskrit) matching is weaker than "
            "patent (English) matching due to a cross-lingual embedding gap — "
            "NIIMH abstention does not mean the patent results are wrong, and "
            "patent results are leads for manual review, not confirmed findings."
        ),
    }


@app.get("/health")
def health():
    return {"status": "ok"}