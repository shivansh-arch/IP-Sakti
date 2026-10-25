# find_dupe_source.py
import json

target_text = "tiktasyatamasyashosham kasam cashu vyapohati| mrudvika brumhani vrushya madhura snigdhashitala||126||"

matches = []
with open("data/processed/niimh_verses.jsonl", encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        if c["text"].strip().lower() == target_text.lower():
            matches.append(c)

print(f"Found {len(matches)} exact matches (case-insensitive)")
doc_ids = [m["doc_id"] for m in matches]
print("Unique doc_ids involved:", len(set(doc_ids)))
for m in matches[:20]:
    print(m["doc_id"], m["unit_id"], m["unit_type"], repr(m["text"][:50]))