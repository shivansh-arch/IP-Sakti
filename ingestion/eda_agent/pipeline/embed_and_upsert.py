"""
embed_and_upsert.py

Embeds chunks.jsonl using a local multilingual sentence-transformer and
upserts into Qdrant. Payload carries full chunk metadata — no Postgres
dependency for v1.
"""

import json
import hashlib

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

IN_FILE = "data/processed/chunks.jsonl"
COLLECTION_NAME = "ip_sakti_niimh"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 64


def stable_id(chunk_id: str) -> int:
    """Deterministic integer point ID from chunk_id — re-running this
    script upserts (overwrites) the same points instead of duplicating."""
    return int(hashlib.sha256(chunk_id.encode("utf-8")).hexdigest()[:16], 16)


def main():
    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    vector_size = model.get_sentence_embedding_dimension()
    print(f"Vector size: {vector_size}")

    chunks = []
    with open(IN_FILE, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    print(f"Loaded {len(chunks)} chunks")

    client = QdrantClient(host="localhost", port=6333)

    # Recreate collection fresh each run — fine for v1 iteration.
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

    total_upserted = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        embeddings = model.encode(texts, show_progress_bar=False)

        points = [
            PointStruct(
                id=stable_id(c["chunk_id"]),
                vector=emb.tolist(),
                payload=c,  # full chunk metadata: chunk_id, book, chapter, unit_id, chunk_type, text
            )
            for c, emb in zip(batch, embeddings)
        ]
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        total_upserted += len(points)
        print(f"Upserted {total_upserted}/{len(chunks)}")

    print(f"Done. {total_upserted} chunks embedded and upserted into '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    main()