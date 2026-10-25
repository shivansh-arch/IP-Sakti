"""
dedup_by_content.py

Deduplicates candidates by normalized TEXT CONTENT, not by unit_id.
This replaces the earlier (book, chapter, unit_id, unit_type) key-based
approach, which broke when colophons/unmarked commentary collided on id.

Within a duplicate group, keeps the candidate with the FEWEST flags
(prefer a clean double-danda match over a single-danda or unmarked one),
breaking ties by lowest doc_id/page — i.e. prefer the "cleanest" copy,
not just the first one encountered.
"""

import json
import re
from collections import defaultdict

IN_FILE = "data/processed/niimh_verses.jsonl"
OUT_FILE = "data/processed/niimh_verses_deduped.jsonl"

WHITESPACE_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Collapse whitespace and lowercase for comparison only —
    the ORIGINAL text (not this normalized form) is what gets kept."""
    return WHITESPACE_RE.sub(" ", text.strip()).lower()


groups = defaultdict(list)

with open(IN_FILE, encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        key = normalize(c["text"])
        groups[key].append(c)

kept = 0
dropped = 0

with open(OUT_FILE, "w", encoding="utf-8") as out:
    for key, entries in groups.items():
        # prefer fewest flags (cleanest extraction), then lowest doc_id as tiebreak
        entries.sort(key=lambda c: (len(c.get("flags") or []), c["doc_id"]))
        canonical = entries[0]
        out.write(json.dumps(canonical, ensure_ascii=False) + "\n")
        kept += 1
        dropped += len(entries) - 1

print(f"Kept: {kept}")
print(f"Dropped as duplicates: {dropped}")
print(f"Dedup rate: {dropped / (kept + dropped) * 100:.1f}%")