import json
bad = set()
with open("data/processed/niimh_verses.jsonl", encoding="utf-8") as f:
    for line in f:
        parts = json.loads(line)["doc_id"].split("_")
        if len(parts) != 3:
            bad.add(json.loads(line)["doc_id"])
print(len(bad), "doc_ids don't fit book_chapter_page")
print(list(bad)[:10])