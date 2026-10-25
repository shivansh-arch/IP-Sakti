import os
import json
from ingestion.eda_agent.adapters.niimh_adapter import extract_candidates

RAW_DIR = "data/raw/niimh"
OUT_FILE = "data/processed/niimh_verses.jsonl"

files = sorted(os.listdir(RAW_DIR))
print(f"Processing {len(files)} files")

total_candidates = 0
error_count = 0

with open(OUT_FILE, "w", encoding="utf-8") as out:
    for fname in files:
        path = os.path.join(RAW_DIR, fname)
        doc_id = fname.replace(".html", "")  # e.g. "1_1_5"

        try:
            with open(path, "r", encoding="utf-8") as f:
                html = f.read()
            candidates = extract_candidates(html, doc_id=doc_id)
            for c in candidates:
                out.write(json.dumps({
                    "source": c.source,
                    "doc_id": c.doc_id,
                    "unit_id": c.unit_id,
                    "unit_type": c.unit_type,
                    "text": c.text,
                    "flags": c.flags,
                }, ensure_ascii=False) + "\n")
                total_candidates += 1
        except Exception as e:
            print(f"FAILED on {fname}: {e}")
            error_count += 1

print(f"\nTotal candidates extracted: {total_candidates}")
print(f"Files with errors: {error_count}")