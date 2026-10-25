"""
compare_sources.py

For every patent in ip_sakti_patents, finds its closest match in
ip_sakti_niimh and reports the score. Sorted descending — highest
scores are the most "suspicious" potential overlaps to review first.

No threshold applied yet — this run is to SEE the score distribution
for patent-vs-NIIMH pairs specifically, since this is a different
embedding pairing than the query-vs-corpus calibration done earlier.
"""

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

NIIMH_COLLECTION = "ip_sakti_niimh"
PATENTS_COLLECTION = "ip_sakti_patents"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def main():
    model = SentenceTransformer(MODEL_NAME)
    client = QdrantClient(host="localhost", port=6333, check_compatibility=False)

    # Pull all patents back out (with their stored text) via scroll
    patents = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=PATENTS_COLLECTION,
            limit=100,
            offset=offset,
            with_payload=True,
        )
        patents.extend(points)
        if offset is None:
            break

    print(f"Comparing {len(patents)} patents against NIIMH corpus...\n")

    results = []
    for p in patents:
        text = p.payload["text"]
        vector = model.encode(text).tolist()
        response = client.query_points(
            collection_name=NIIMH_COLLECTION,
            query=vector,
            limit=1,
        )
        if response.points:
            top = response.points[0]
            payload = top.payload or {}
            results.append({
                "publication_number": p.payload.get("publication_number", "UNKNOWN"),
                "patent_text": text[:150],
                "score": top.score,
                "niimh_chunk_id": payload.get("chunk_id", "MISSING"),
                "niimh_text": payload.get("text", "")[:150],
            })

    results.sort(key=lambda r: r["score"], reverse=True)

    print("=== Top 15 potential overlaps (highest score first) ===\n")
    for r in results[:15]:
        print(f"score={r['score']:.3f} | {r['publication_number']}")
        print(f"  Patent: {r['patent_text']}")
        print(f"  NIIMH ({r['niimh_chunk_id']}): {r['niimh_text']}")
        print()

    scores = [r["score"] for r in results]
    print(f"Score range: min={min(scores):.3f}, max={max(scores):.3f}, "
          f"avg={sum(scores)/len(scores):.3f}")


if __name__ == "__main__":
    main()
