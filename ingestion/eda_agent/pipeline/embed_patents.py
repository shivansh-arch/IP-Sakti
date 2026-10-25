"""
embed_patents.py

Embeds India A61K36 patent abstracts and upserts into a SEPARATE Qdrant
collection (ip_sakti_patents) from the NIIMH one — keeps sources distinct
so later cross-source overlap comparison is explicit, not tangled.
"""

import json
import hashlib

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

IN_FILE = "data/raw/patents/india_a61k36_patents.json"
COLLECTION_NAME = "ip_sakti_patents"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"  # same model as NIIMH — required for comparable vector space


def stable_id(publication_number: str) -> int:
    return int(hashlib.sha256(publication_number.encode("utf-8")).hexdigest()[:16], 16)


def main():
    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    vector_size = model.get_sentence_embedding_dimension()

    with open(IN_FILE, encoding="utf-8") as f:
        patents = json.load(f)
    print(f"Loaded {len(patents)} patents")

    chunks = []
    for p in patents:
        title = p.get("title") or ""
        abstract = p.get("abstract") or ""
        text = f"{title} {abstract}".strip()
        if not text:
            continue  # skip anything with no usable text at all
        chunks.append({
            "publication_number": p["publication_number"],
            "publication_date": p.get("publication_date"),
            "cpc_codes": sorted(set(p.get("cpc_codes") or [])),  # dedup noisy repeated codes
            "text": text,
        })
    print(f"{len(chunks)} chunks with usable text")

    client = QdrantClient(host="localhost", port=6333, check_compatibility=False)
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True)

    points = [
        PointStruct(
            id=stable_id(c["publication_number"]),
            vector=emb.tolist(),
            payload=c,
        )
        for c, emb in zip(chunks, embeddings)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"Done. {len(points)} patent chunks embedded and upserted into '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    main()