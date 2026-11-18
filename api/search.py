"""
api/search.py — the retrieval engine, shared by the API, the eval harness,
and the pipeline scripts, so all three measure exactly the same thing.

Two systems:

  v1  (baseline)  multilingual MiniLM over raw romanized Sanskrit.
                  Kept so the eval can show the before/after numbers.

  v2  (hybrid)    1. Every verse chunk is tagged with lexicon entities
                     (plants + conditions) and rendered as an English
                     description ("Substances: Turmeric (Curcuma longa).
                     Indications: Skin disease"), optionally followed by an
                     LLM gloss. That English text is what gets embedded.
                  2. The query is tagged with the same lexicon.
                  3. Candidates = dense top-N  UNION  entity-filtered top-N.
                  4. score = W_DENSE * cosine + W_ENTITY * entity_overlap
                     (pure cosine when the query has no lexicon entities).
                  5. Abstain unless the best candidate clears the
                     calibrated threshold AND, if the query named entities,
                     actually shares at least one of them.

Qdrant connection (first match wins):
  QDRANT_URL (+ QDRANT_API_KEY)  -> Qdrant Cloud / remote server
  QDRANT_PATH                    -> embedded local storage, no server needed
  (neither)                      -> localhost:6333 (docker compose)
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny

from lexicon import Tags, entity_overlap, tag

load_dotenv()

# ---- v1 -------------------------------------------------------------------
V1_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
V1_NIIMH = "ip_sakti_niimh"
V1_PATENTS = "ip_sakti_patents"
V1_THRESHOLD = 0.30

# ---- v2 -------------------------------------------------------------------
# bge-small: 33M params / ~130 MB — fits a free-tier container, and is a far
# stronger English retriever than MiniLM-multilingual.
V2_MODEL = "BAAI/bge-small-en-v1.5"
V2_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
V2_NIIMH = "ip_sakti_niimh_v2"
V2_PATENTS = "ip_sakti_patents_v2"
W_DENSE, W_ENTITY = 0.5, 0.5
CANDIDATES = 50
# Calibrated by eval/run_eval.py --calibrate (see eval/README in notes/architecture.md).
V2_NIIMH_THRESHOLD = float(os.environ.get("V2_NIIMH_THRESHOLD", 0.55))
V2_PATENT_THRESHOLD = float(os.environ.get("V2_PATENT_THRESHOLD", 0.55))


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    url, path = os.environ.get("QDRANT_URL"), os.environ.get("QDRANT_PATH")
    if url:
        return QdrantClient(url=url, api_key=os.environ.get("QDRANT_API_KEY"),
                            check_compatibility=False, timeout=30)
    if path:
        return QdrantClient(path=path)
    return QdrantClient(host="localhost", port=6333, check_compatibility=False)


@lru_cache(maxsize=2)
def get_model(name: str):
    from sentence_transformers import SentenceTransformer  # heavy import, keep lazy
    return SentenceTransformer(name)


def encode_query_v2(text: str) -> list[float]:
    return get_model(V2_MODEL).encode(V2_QUERY_PREFIX + text, normalize_embeddings=True).tolist()


def _doc_tags(payload: dict) -> Tags:
    return Tags(plants=payload.get("plants") or [], conditions=payload.get("conditions") or [])


def _entity_filter(q: Tags):
    should = []
    if q.plants:
        should.append(FieldCondition(key="plants", match=MatchAny(any=q.plants)))
    if q.conditions:
        should.append(FieldCondition(key="conditions", match=MatchAny(any=q.conditions)))
    return Filter(should=should) if should else None


def hybrid_search(collection: str, vector: list[float], qtags: Tags, k: int) -> list[dict]:
    """Union of dense and entity-filtered candidates, reranked by hybrid score."""
    client = get_client()
    pts = {p.id: p for p in client.query_points(collection, query=vector, limit=CANDIDATES,
                                                with_payload=True).points}
    flt = _entity_filter(qtags)
    if flt is not None:
        for p in client.query_points(collection, query=vector, query_filter=flt,
                                     limit=CANDIDATES, with_payload=True).points:
            pts.setdefault(p.id, p)

    scored = []
    for p in pts.values():
        ent, shared = entity_overlap(qtags, _doc_tags(p.payload))
        score = p.score if qtags.empty else W_DENSE * p.score + W_ENTITY * ent
        scored.append({"score": round(float(score), 4), "dense": round(float(p.score), 4),
                       "entity": round(ent, 4), "shared": shared, "payload": p.payload})
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:k]


def abstain(results: list[dict], qtags: Tags, threshold: float) -> bool:
    if not results or results[0]["score"] < threshold:
        return True
    # The query named concrete plants/conditions but the best hit shares none
    # of them: that's a vibes-only match, exactly what abstention is for.
    return not qtags.empty and results[0]["entity"] == 0


# ---- public API -------------------------------------------------------------

def search_niimh_v2(query: str, k: int = 5) -> dict:
    qtags = tag(query, "auto")
    res = hybrid_search(V2_NIIMH, encode_query_v2(query), qtags, k)
    return {"query_entities": qtags.to_dict(), "results": res,
            "abstained": abstain(res, qtags, V2_NIIMH_THRESHOLD),
            "threshold": V2_NIIMH_THRESHOLD}


def search_patents_v2(query: str, k: int = 3) -> dict:
    qtags = tag(query, "auto")
    res = hybrid_search(V2_PATENTS, encode_query_v2(query), qtags, k)
    return {"results": res, "abstained": abstain(res, qtags, V2_PATENT_THRESHOLD),
            "threshold": V2_PATENT_THRESHOLD}


def niimh_evidence_for_patent(payload: dict, k: int = 1) -> list[dict]:
    """Closest TK verse for a patent, scored by the patent's own entities."""
    ptags = _doc_tags(payload)
    if ptags.empty:
        return []
    vec = get_model(V2_MODEL).encode(V2_QUERY_PREFIX + payload.get("text", ""),
                                     normalize_embeddings=True).tolist()
    return hybrid_search(V2_NIIMH, vec, ptags, k)


def search_niimh_v1(query: str, k: int = 5) -> dict:
    vec = get_model(V1_MODEL).encode(query).tolist()
    pts = get_client().query_points(V1_NIIMH, query=vec, limit=k, with_payload=True).points
    res = [{"score": round(float(p.score), 4), "dense": round(float(p.score), 4), "entity": None,
            "shared": None, "payload": p.payload} for p in pts]
    return {"query_entities": None, "results": res,
            "abstained": not res or res[0]["score"] < V1_THRESHOLD, "threshold": V1_THRESHOLD}
