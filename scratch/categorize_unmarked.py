# categorize_unmarked.py
import json
import re

single_danda_end = re.compile(r"\|(\d+(?:-\d+)?)\|\s*$")
no_number_end = re.compile(r"\|\|?\s*$")

single_danda = 0
no_marker_at_all = 0
other = 0

with open("data/processed/niimh_verses.jsonl", encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        if "no_closing_marker" in (c.get("flags") or []):
            text = c["text"].strip()
            if single_danda_end.search(text):
                single_danda += 1
            elif no_number_end.search(text) or not re.search(r"\d", text[-10:]):
                no_marker_at_all += 1
            else:
                other += 1

print(f"Single-danda truncated (|N|): {single_danda}")
print(f"No marker at all (section tags etc): {no_marker_at_all}")
print(f"Other/unclassified: {other}")