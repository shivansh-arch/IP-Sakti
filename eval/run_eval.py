"""
eval/run_eval.py — measure v1 vs v2 retrieval on eval/holdout_cases.json.

    python eval/run_eval.py                 # report v1 and v2 on dev + test
    python eval/run_eval.py --calibrate     # sweep v2 threshold on DEV split,
                                            # report the chosen value on TEST
    python eval/run_eval.py --verbose       # per-query lines

Metrics (per split):
  answer_acc    positives: answered AND top-1 is relevant
  p@5           positives: relevant hits among the top 5 (abstained -> 0)
  false_abst    positives the system wrongly abstained on
  neg_abst      negatives correctly abstained on
  overall       (positives with relevant top-1 + correctly abstained negatives) / all

Patent -> TK evidence (no split; derived from data):
  for every patent the lexicon tags with >=1 plant, is the best NIIMH chunk
  one that actually names one of the patent's plants?

Relevance is judged from each hit's RAW text by the lexicon tagger, the same
judge for both systems. See the caveat in holdout_cases.json.
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from api import search  # noqa: E402
from lexicon import Tags, tag  # noqa: E402

CASES = "eval/holdout_cases.json"
PATENTS = "data/processed/patents_tagged.jsonl"


def relevant(hit_text: str, case: dict) -> bool:
    t = tag(hit_text, "sa")
    ok_p = not case.get("plants") or bool(set(case["plants"]) & set(t.plants))
    ok_c = not case.get("conditions") or bool(set(case["conditions"]) & set(t.conditions))
    return ok_p and ok_c


def run_raw(system: str, cases: list[dict]) -> list[dict]:
    """Retrieve once per query; abstention is re-decided later per threshold."""
    fn = search.search_niimh_v1 if system == "v1" else search.search_niimh_v2
    rows = []
    for c in cases:
        r = fn(c["query"], k=5)
        qt = r["query_entities"]
        rows.append({"case": c, "results": r["results"],
                     "qtags": Tags(**qt) if qt else Tags(),
                     "rel": [relevant(h["payload"]["text"], c) for h in r["results"]]})
    return rows


def decide(row: dict, system: str, threshold: float) -> bool:
    if system == "v1":
        return not row["results"] or row["results"][0]["score"] < threshold
    return search.abstain(row["results"], row["qtags"], threshold)


def metrics(rows: list[dict], system: str, threshold: float, verbose=False) -> dict:
    pos = [r for r in rows if r["case"]["expect"] == "match"]
    neg = [r for r in rows if r["case"]["expect"] == "abstain"]
    ans_ok = p5 = fa = na = 0
    for r in rows:
        abst = decide(r, system, threshold)
        c = r["case"]
        if c["expect"] == "match":
            top_ok = not abst and bool(r["rel"]) and r["rel"][0]
            ans_ok += top_ok
            p5 += 0 if abst else sum(r["rel"]) / 5
            fa += abst
            mark = "OK " if top_ok else ("ABS" if abst else "BAD")
        else:
            na += abst
            mark = "OK " if abst else "FP "
        if verbose:
            top = r["results"][0] if r["results"] else None
            print(f"  [{mark}] {c['id']:<4} {c['query'][:42]:<42} "
                  f"top={top['score'] if top else None} rel={sum(r['rel'])}/5")
    n = len(rows)
    return {
        "answer_acc": round(ans_ok / len(pos), 3) if pos else None,
        "p@5": round(p5 / len(pos), 3) if pos else None,
        "false_abst": round(fa / len(pos), 3) if pos else None,
        "neg_abst": round(na / len(neg), 3) if neg else None,
        "overall": round((ans_ok + na) / n, 3) if n else None,
        "n": n,
    }


def patent_evidence(system: str) -> dict:
    if not os.path.exists(PATENTS):
        return {}
    with open(PATENTS, encoding="utf-8") as f:
        pats = [p for p in map(json.loads, f) if p["plants"]]
    hits = 0
    for p in pats:
        if system == "v2":
            ev = search.niimh_evidence_for_patent(p, k=1)
        else:
            ev = search.search_niimh_v1(p["text"], k=1)["results"]
        if ev and set(p["plants"]) & set(tag(ev[0]["payload"]["text"], "sa").plants):
            hits += 1
    return {"patents_with_plants": len(pats), "top1_shares_plant": hits,
            "rate": round(hits / len(pats), 3) if pats else None}


def main():
    verbose = "--verbose" in sys.argv
    with open(CASES, encoding="utf-8") as f:
        cases = json.load(f)["niimh_queries"]
    split = {s: [c for c in cases if c["split"] == s] for s in ("dev", "test")}

    report = {}
    for system, thr in (("v1", search.V1_THRESHOLD), ("v2", search.V2_NIIMH_THRESHOLD)):
        raw = {s: run_raw(system, cs) for s, cs in split.items()}
        if system == "v2" and "--calibrate" in sys.argv:
            grid = [round(0.30 + 0.01 * i, 2) for i in range(51)]
            best = max(grid, key=lambda t: (metrics(raw["dev"], system, t)["overall"], -abs(t - 0.55)))
            print(f"[calibrate] best v2 threshold on DEV = {best}")
            thr = best
        report[system] = {"threshold": thr}
        for s in ("dev", "test"):
            if verbose:
                print(f"--- {system} / {s} (threshold {thr})")
            report[system][s] = metrics(raw[s], system, thr, verbose)
        report[system]["patent_evidence"] = patent_evidence(system)

    print(json.dumps(report, indent=2))
    os.makedirs("eval/results", exist_ok=True)
    with open("eval/results/latest.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
