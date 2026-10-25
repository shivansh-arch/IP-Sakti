import json
from collections import defaultdict

by_doc = defaultdict(list)
with open("data/processed/niimh_verses.jsonl", encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        by_doc[c["doc_id"]].append(c)

worst = max(by_doc, key=lambda d: len(by_doc[d]))
print(worst, len(by_doc[worst]))
for c in by_doc[worst][:15]:
    print(c["unit_type"], c["unit_id"], repr(c["text"][:60]))