"""
query_rag.py

Minimal RAG query loop: embed query -> search Qdrant -> abstain if the
top match's similarity is below threshold, otherwise return the chunks
as grounding.

THRESHOLD IS A GUESS (0.5). Not calibrated. Run real queries — some that
should clearly match Charaka Samhita content, some that clearly shouldn't
(totally unrelated topics) — and look at the score gap before trusting
this in a demo.
"""

import sys
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

COLLECTION_NAME = "ip_sakti_niimh"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 5
SIMILARITY_THRESHOLD = 0.3  # calibrated from 3 test queries: unrelated=0.153,
                             # relevant-English=0.336, relevant-Sanskrit-term=0.545.
                             # Still provisional — test more queries before demo.


def query(text: str, model: SentenceTransformer, client: QdrantClient):
    vector = model.encode(text).tolist()
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        limit=TOP_K,
    )
    results = response.points

    if not results or results[0].score < SIMILARITY_THRESHOLD:
        top_score = results[0].score if results else None
        print(f"\n[ABSTAIN] No strong TK evidence found for this query.")
        print(f"(Top match score: {top_score}, threshold: {SIMILARITY_THRESHOLD})")
        return

    print(f"\nTop {len(results)} matches:")
    for r in results:
        payload = r.payload
        print(f"\n--- score={r.score:.3f} | {payload['chunk_id']} ({payload['chunk_type']}) ---")
        print(payload["text"][:300])


def main():
    model = SentenceTransformer(MODEL_NAME)
    client = QdrantClient(host="localhost", port=6333, check_compatibility=False)

    if len(sys.argv) > 1:
        query(" ".join(sys.argv[1:]), model, client)
    else:
        print("Interactive mode — type a query, or 'quit' to exit.")
        while True:
            text = input("\n> ").strip()
            if text.lower() in ("quit", "exit"):
                break
            if text:
                query(text, model, client)


if __name__ == "__main__":
    main()
