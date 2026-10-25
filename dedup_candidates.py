# dedup_candidates.py
import json
from collections import defaultdict

IN_FILE = "data/processed/niimh_verses.jsonl"
OUT_FILE = "data/processed/niimh_verses_deduped.jsonl"

groups = defaultdict(list)

with open(IN_FILE, encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        book, chapter, page = c["doc_id"].split("_")
        key = (book, chapter, c["unit_id"], c["unit_type"])
        groups[key].append((int(page), c))

kept = 0
dropped = 0

with open(OUT_FILE, "w", encoding="utf-8") as out:
    for key, entries in groups.items():
        entries.sort(key=lambda x: x[0])  # lowest page number first
        canonical = entries[0][1]
        out.write(json.dumps(canonical, ensure_ascii=False) + "\n")
        kept += 1
        dropped += len(entries) - 1

print(f"Kept: {kept}")
print(f"Dropped as duplicates: {dropped}")
print(f"Dedup rate: {dropped / (kept + dropped) * 100:.1f}%")