# classify_mismatches.py
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

unmarked_mismatch = 0
real_id_mismatch = 0
real_id_examples = []

for key, texts in groups.items():
    if len(set(texts)) > 1:
        unit_id = key[2]
        if str(unit_id).startswith("unmarked"):
            unmarked_mismatch += 1
        else:
            real_id_mismatch += 1
            if len(real_id_examples) < 5:
                real_id_examples.append((key, set(texts)))

print(f"Mismatched groups with 'unmarked_*' id: {unmarked_mismatch}")
print(f"Mismatched groups with real unit_id: {real_id_mismatch}")

for key, texts in real_id_examples:
    print(f"\nKey: {key}")
    for t in texts:
        print(f"  {t[:80]!r}")