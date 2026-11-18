"""
tag_entities.py

Runs the lexicon tagger over both corpora and writes the v2 inputs:

  data/processed/chunks_tagged.jsonl    every NIIMH chunk + plants/conditions
                                        + english_view (what v2 embeds)
  data/processed/patents_tagged.jsonl   every patent + plants/conditions

If data/processed/chunk_glosses.jsonl exists (from enrich_chunks.py), its
LLM gloss is appended to english_view. The lexicon description always
comes first — it's deterministic and verified; the gloss is best-effort.

Run from repo root:  python ingestion/eda_agent/pipeline/tag_entities.py
"""

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from lexicon import describe, tag  # noqa: E402

CHUNKS_IN = "data/processed/chunks.jsonl"
GLOSSES_IN = "data/processed/chunk_glosses.jsonl"
PATENTS_IN = "data/raw/patents/india_a61k36_patents.json"
CHUNKS_OUT = "data/processed/chunks_tagged.jsonl"
PATENTS_OUT = "data/processed/patents_tagged.jsonl"


def load_glosses() -> dict:
    if not os.path.exists(GLOSSES_IN):
        return {}
    out = {}
    with open(GLOSSES_IN, encoding="utf-8") as f:
        for line in f:
            g = json.loads(line)
            if g.get("gloss"):
                out[g["chunk_id"]] = g["gloss"]
    return out


def main():
    glosses = load_glosses()
    stats = Counter()
    with open(CHUNKS_IN, encoding="utf-8") as f, open(CHUNKS_OUT, "w", encoding="utf-8") as out:
        for line in f:
            c = json.loads(line)
            t = tag(c["text"], "sa")
            view = describe(t)
            gloss = glosses.get(c["chunk_id"])
            if gloss:
                view = f"{view}. {gloss}" if view else gloss
                stats["with_gloss"] += 1
            c.update(t.to_dict(), english_view=view, gloss=gloss)
            stats["chunks"] += 1
            stats["tagged"] += not t.empty
            out.write(json.dumps(c, ensure_ascii=False) + "\n")

    with open(PATENTS_IN, encoding="utf-8") as f:
        patents = json.load(f)
    with open(PATENTS_OUT, "w", encoding="utf-8") as out:
        for p in patents:
            text = f"{p.get('title') or ''} {p.get('abstract') or ''}".strip()
            if not text:
                continue
            t = tag(text, "en")
            out.write(json.dumps({
                "publication_number": p["publication_number"],
                "publication_date": p.get("publication_date"),
                "cpc_codes": sorted(set(p.get("cpc_codes") or [])),
                "text": text, **t.to_dict(),
            }, ensure_ascii=False) + "\n")
            stats["patents"] += 1
            stats["patents_with_plant"] += bool(t.plants)
            stats["patents_tagged"] += not t.empty

    print(dict(stats))
    print(f"Wrote {CHUNKS_OUT} and {PATENTS_OUT}")


if __name__ == "__main__":
    main()
