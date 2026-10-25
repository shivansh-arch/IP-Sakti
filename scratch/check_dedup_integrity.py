# check_dedup_integrity.py
import json
from collections import defaultdict

IN_FILE = "data/processed/niimh_verses.jsonl"

groups = defaultdict(list)
with open(IN_FILE, encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        book, chapter, page = c["doc_id"].split("_")
        key = (book, chapter, c["unit_id"], c["unit_type"])
        groups[key].append(c["text"])

mismatched = 0
examples = []

for key, texts in groups.items():
    if len(set(texts)) > 1:
        mismatched += 1
        if len(examples) < 5:
            examples.append((key, set(texts)))

print(f"Groups with >1 entry: {sum(1 for t in groups.values() if len(t) > 1)}")
print(f"Groups with mismatched text: {mismatched}")

for key, texts in examples:
    print(f"\nKey: {key}")
    for t in texts:
        print(f"  {t[:80]!r}")