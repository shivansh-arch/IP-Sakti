"""
validate_candidates.py

Sanity-checks the output of test_niimh_candidates.py before you move on
to dedup/normalization.

Usage:
    python validate_candidates.py path/to/candidates.json
    python validate_candidates.py path/to/candidates.csv
    python validate_candidates.py path/to/candidates.pkl

Expected input shape: a list of dicts (or a list of strings), ideally
each candidate carrying at least a "term"/"text" field and a "file"/
"source" field so per-file stats work. If your extractor only outputs
bare strings, the per-file distribution check will be skipped.
"""

import sys
import json
import pickle
import random
import csv
from collections import Counter
from pathlib import Path


def load_candidates(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        candidates = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    candidates.append(json.loads(line))
        return candidates
    elif suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    elif suffix == ".csv":
        with open(path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    elif suffix in (".pkl", ".pickle"):
        with open(path, "rb") as f:
            return pickle.load(f)
    else:
        raise ValueError(f"Unrecognized file type: {suffix}. Expected .jsonl, .json, .csv, or .pkl")


def get_text(c):
    """Pull the candidate's text out, whether it's a dict or a bare string."""
    if isinstance(c, str):
        return c
    for key in ("text", "term", "candidate", "value", "name"):
        if key in c:
            return c[key]
    return next(iter(c.values()), str(c))


def get_file(c):
    """Group by doc_id (e.g. '1_1_5') — that's the per-file identifier here,
    not 'source', which is likely a constant like 'niimh'."""
    if isinstance(c, dict):
        for key in ("doc_id", "file", "filename", "source_file"):
            if key in c:
                return c[key]
    return None


def flags_check(candidates):
    """If the extractor already tags candidates with flags, surface that
    first — it's cheaper than eyeballing a random sample blind."""
    flagged = [c for c in candidates if isinstance(c, dict) and c.get("flags")]
    print(f"\n=== FLAGS CHECK ===")
    if not any(isinstance(c, dict) and "flags" in c for c in candidates):
        print("No 'flags' field present — skipping.")
        return
    print(f"Candidates with non-empty flags: {len(flagged)} / {len(candidates)}")
    if flagged:
        flag_counter = Counter()
        for c in flagged:
            f = c["flags"]
            if isinstance(f, list):
                flag_counter.update(f)
            else:
                flag_counter[str(f)] += 1
        print("Flag breakdown:")
        for flag, cnt in flag_counter.most_common():
            print(f"  {cnt:>5}  {flag}")
        print("\nSample of flagged candidates:")
        for c in random.sample(flagged, min(10, len(flagged))):
            print(f"  [{c.get('doc_id')}] {get_text(c)!r} -> {c['flags']}")


def unit_type_check(candidates):
    types = [c.get("unit_type") for c in candidates if isinstance(c, dict) and c.get("unit_type")]
    if not types:
        return
    print(f"\n=== UNIT_TYPE BREAKDOWN ===")
    for t, cnt in Counter(types).most_common():
        print(f"  {cnt:>6}  {t}")


def random_sample_check(candidates, n=30):
    print(f"\n=== RANDOM SAMPLE ({n} candidates) ===")
    sample = random.sample(candidates, min(n, len(candidates)))
    for i, c in enumerate(sample, 1):
        print(f"{i:>2}. {get_text(c)!r}")
    print("\n>> Eyeball these. Look for: junk (page numbers, headers),")
    print(">> broken/truncated terms, or things that aren't TK terms at all.")


def distribution_check(candidates, top_n=10):
    files = [get_file(c) for c in candidates]
    if all(f is None for f in files):
        print("\n=== DISTRIBUTION CHECK ===")
        print("No file/source field found on candidates — skipping. "
              "Add a 'file' key per candidate if you want this check.")
        return

    counts = Counter(f for f in files if f is not None)
    total_files = len(counts)
    total_candidates = sum(counts.values())
    avg = total_candidates / total_files if total_files else 0

    print(f"\n=== DISTRIBUTION CHECK ===")
    print(f"Files with candidates: {total_files}")
    print(f"Average candidates/file: {avg:.1f}")

    print(f"\nTop {top_n} files by candidate count (check these for over-firing):")
    for fname, cnt in counts.most_common(top_n):
        flag = "  <-- investigate" if cnt > avg * 5 else ""
        print(f"  {cnt:>5}  {fname}{flag}")


def duplicate_check(candidates):
    texts = [get_text(c).strip().lower() for c in candidates]
    total = len(texts)
    unique = len(set(texts))
    dup_rate = (total - unique) / total * 100 if total else 0

    print(f"\n=== DUPLICATE CHECK (exact, case-insensitive) ===")
    print(f"Total candidates: {total}")
    print(f"Unique candidates: {unique}")
    print(f"Duplicate rate: {dup_rate:.1f}%")

    most_common = Counter(texts).most_common(10)
    print("\nMost repeated candidates:")
    for text, cnt in most_common:
        print(f"  {cnt:>5}  {text!r}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python validate_candidates.py <path_to_candidates_file>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    candidates = load_candidates(path)
    print(f"Loaded {len(candidates)} candidates from {path}")

    flags_check(candidates)
    unit_type_check(candidates)
    random_sample_check(candidates)
    distribution_check(candidates)
    duplicate_check(candidates)


if __name__ == "__main__":
    main()