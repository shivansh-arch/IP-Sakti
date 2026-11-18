"""
embed_v2.py

Builds the v2 collections from tag_entities.py output:

  ip_sakti_niimh_v2    only chunks with >=1 lexicon entity (therapeutic
                       content); vector = bge-small(english_view)
  ip_sakti_patents_v2  every patent; vector = bge-small(title + abstract)

v2 vectors come from api.search.embed_v2 (ONNX bge-small via fastembed), the
same function the API embeds queries with.

Payload keys `plants` / `conditions` get keyword indexes so the hybrid
search can pull entity-filtered candidates.

Flags:
  --v1   also (re)build the v1 baseline collections from raw text with
         MiniLM — needed for eval when using a fresh local QDRANT_PATH.

Run from repo root:  python ingestion/eda_agent/pipeline/embed_v2.py [--v1]
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams  # noqa: E402

from api.search import (V1_MODEL, V1_NIIMH, V1_PATENTS, V2_MODEL, V2_NIIMH,  # noqa: E402
                        V2_PATENTS, embed_v2, get_client, get_model)

CHUNKS = "data/processed/chunks_tagged.jsonl"
PATENTS = "data/processed/patents_tagged.jsonl"
BATCH = 256


def stable_id(key: str) -> int:
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def build(collection, model_name, rows, text_of, id_of, normalize, index_entities):
    client = get_client()
    v2 = model_name == V2_MODEL  # v2 uses the same ONNX embedder the API serves with
    model = None if v2 else get_model(model_name)
    size = 384 if v2 else model.get_sentence_embedding_dimension()
    if client.collection_exists(collection):
        client.delete_collection(collection)
    client.create_collection(collection, vectors_config=VectorParams(
        size=size, distance=Distance.COSINE))
    if index_entities:
        for key in ("plants", "conditions"):
            try:
                client.create_payload_index(collection, key, PayloadSchemaType.KEYWORD)
            except Exception:
                pass  # embedded local mode doesn't support payload indexes; filters still work
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        texts = [text_of(r) for r in batch]
        vecs = embed_v2(texts) if v2 else model.encode(
            texts, normalize_embeddings=normalize, show_progress_bar=False).tolist()
        client.upsert(collection, points=[
            PointStruct(id=stable_id(id_of(r)), vector=v, payload=r)
            for r, v in zip(batch, vecs)])
        print(f"  {collection}: {min(i + BATCH, len(rows))}/{len(rows)}", flush=True)
    print(f"Done: {collection} ({len(rows)} points)")


def main():
    chunks, patents = load(CHUNKS), load(PATENTS)
    tk = [c for c in chunks if c["plants"] or c["conditions"]]
    print(f"{len(tk)}/{len(chunks)} chunks carry lexicon entities -> v2 index")

    build(V2_NIIMH, V2_MODEL, tk, lambda r: r["english_view"], lambda r: r["chunk_id"],
          normalize=True, index_entities=True)
    build(V2_PATENTS, V2_MODEL, patents, lambda r: r["text"], lambda r: r["publication_number"],
          normalize=True, index_entities=True)

    if "--v1" in sys.argv:
        build(V1_NIIMH, V1_MODEL, chunks, lambda r: r["text"], lambda r: r["chunk_id"],
              normalize=False, index_entities=False)
        build(V1_PATENTS, V1_MODEL, patents, lambda r: r["text"], lambda r: r["publication_number"],
              normalize=False, index_entities=False)


if __name__ == "__main__":
    main()
