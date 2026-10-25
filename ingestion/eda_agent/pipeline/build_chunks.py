"""
build_chunks.py

Joins root_text verses with their matching commentary (same book, chapter,
exact unit_id) into retrieval-ready chunks. Colophons are excluded (not
TK content). Commentary with a range unit_id that doesn't exactly match
a single verse's unit_id is kept as a standalone chunk, NOT linked —
range-overlap joining is a known v1 limitation, not handled here.

Output: one JSON object per line, each a retrieval chunk:
  {
    "chunk_id": "<book>_<chapter>_<unit_id>",
    "book": ..., "chapter": ..., "unit_id": ...,
    "chunk_type": "verse_with_commentary" | "verse_only" | "commentary_only",
    "text": "<verse>\n\nCommentary: <commentary>"   (or just one part)
  }
"""

import json
from collections import defaultdict

IN_FILE = "data/processed/niimh_verses_deduped.jsonl"
OUT_FILE = "data/processed/chunks.jsonl"

# group[(book, chapter)] = {"root": {unit_id: text}, "commentary": {unit_id: text}}
grouped = defaultdict(lambda: {"root": {}, "commentary": {}})

with open(IN_FILE, encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        if c["unit_type"] == "colophon":
            continue  # not TK content, excluded from retrieval corpus

        book, chapter, _page = c["doc_id"].split("_")
        bucket = "root" if c["unit_type"] == "root_text" else "commentary"
        # dedup already guarantees one canonical entry per unique text,
        # but multiple distinct unit_ids can still land in the same
        # (book, chapter) — last-write-wins here is fine for v1
        grouped[(book, chapter)][bucket][c["unit_id"]] = c["text"]

chunks = []
verse_with_commentary = 0
verse_only = 0
commentary_only = 0

for (book, chapter), buckets in grouped.items():
    root = buckets["root"]
    commentary = buckets["commentary"]
    used_commentary_ids = set()

    for unit_id, verse_text in root.items():
        chunk_id = f"{book}_{chapter}_{unit_id}"
        if unit_id in commentary:
            text = f"{verse_text}\n\nCommentary: {commentary[unit_id]}"
            chunk_type = "verse_with_commentary"
            used_commentary_ids.add(unit_id)
            verse_with_commentary += 1
        else:
            text = verse_text
            chunk_type = "verse_only"
            verse_only += 1

        chunks.append({
            "chunk_id": chunk_id,
            "book": book,
            "chapter": chapter,
            "unit_id": unit_id,
            "chunk_type": chunk_type,
            "text": text,
        })

    # commentary that never matched a verse (e.g. range unit_ids) — keep standalone
    for unit_id, comm_text in commentary.items():
        if unit_id in used_commentary_ids:
            continue
        chunks.append({
            "chunk_id": f"{book}_{chapter}_{unit_id}_c",
            "book": book,
            "chapter": chapter,
            "unit_id": unit_id,
            "chunk_type": "commentary_only",
            "text": comm_text,
        })
        commentary_only += 1

with open(OUT_FILE, "w", encoding="utf-8") as out:
    for chunk in chunks:
        out.write(json.dumps(chunk, ensure_ascii=False) + "\n")

print(f"Total chunks: {len(chunks)}")
print(f"  verse_with_commentary: {verse_with_commentary}")
print(f"  verse_only: {verse_only}")
print(f"  commentary_only: {commentary_only}")