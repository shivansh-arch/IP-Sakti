"""
enrich_chunks.py — OPTIONAL: add a one-sentence English gloss per verse chunk.

The lexicon tags (tag_entities.py) already give v2 its English bridge. This
script layers a free-form gloss on top for extra semantic recall. It's
optional because a small free model translates romanized Sanskrit
imperfectly — so the gloss is APPENDED to the lexicon description, never
replaces it, and the original Sanskrit always remains the cited evidence.

Free backends:
  --backend ollama   (default) local model, e.g. llama3.2:3b.  No key, no
                     quota; ~2-6 s/chunk on a laptop.
  --backend gemini   Google AI Studio free tier. Needs GEMINI_API_KEY in
                     .env. Rate-limited client-side (--rpm, default 10).

Resumable: chunk_ids already in the output file are skipped, so you can
Ctrl+C and rerun. Only chunks carrying lexicon entities are glossed (that's
what the v2 index contains).

  python ingestion/eda_agent/pipeline/enrich_chunks.py --limit 50
  python ingestion/eda_agent/pipeline/enrich_chunks.py --backend gemini --model gemini-2.0-flash-lite

Then re-run tag_entities.py and embed_v2.py to fold the glosses in.
"""

import argparse
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from dotenv import load_dotenv  # noqa: E402

from lexicon import describe, tag  # noqa: E402

load_dotenv()

IN_FILE = "data/processed/chunks.jsonl"
OUT_FILE = "data/processed/chunk_glosses.jsonl"
MAX_CHARS = 1200  # long commentary blocks: gloss the head, that's where the claim is

PROMPT = """You are translating a passage from the Charaka Samhita (classical Ayurveda), given in ITRANS romanized Sanskrit.
A dictionary lookup already identified these terms in it (trust these): {hints}

Write ONE plain-English sentence (max 40 words) stating what the passage says: which substances, prepared how, for which condition or effect. If it is not about treatment, say what it is about. Do not invent substances that are not in the passage. Output only the sentence.

Passage:
{text}"""


def ollama(prompt: str, model: str) -> str:
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/generate"
    r = requests.post(url, json={"model": model, "prompt": prompt, "stream": False,
                                 "options": {"temperature": 0.1, "num_predict": 90}}, timeout=180)
    r.raise_for_status()
    return r.json()["response"].strip()


def gemini(prompt: str, model: str) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY is not set (get a free key at https://aistudio.google.com/apikey)")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    r = requests.post(url, headers={"x-goog-api-key": key}, timeout=60, json={
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 120}})
    if r.status_code == 429:
        raise RuntimeError("rate-limited")
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["ollama", "gemini"], default="ollama")
    ap.add_argument("--model", default=None)
    ap.add_argument("--limit", type=int, default=0, help="stop after N new glosses (0 = all)")
    ap.add_argument("--rpm", type=float, default=10, help="gemini requests/minute cap")
    args = ap.parse_args()
    model = args.model or ("llama3.2:3b" if args.backend == "ollama" else "gemini-2.0-flash-lite")
    call = ollama if args.backend == "ollama" else gemini

    done = set()
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, encoding="utf-8") as f:
            done = {json.loads(line)["chunk_id"] for line in f}

    todo = []
    with open(IN_FILE, encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            t = tag(c["text"], "sa")
            if not t.empty and c["chunk_id"] not in done:
                todo.append((c, t))
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(done)} already glossed; {len(todo)} to do with {args.backend}:{model}")

    gap = 60.0 / args.rpm if args.backend == "gemini" else 0
    with open(OUT_FILE, "a", encoding="utf-8") as out:
        for i, (c, t) in enumerate(todo, 1):
            prompt = PROMPT.format(hints=describe(t), text=c["text"][:MAX_CHARS])
            t0 = time.time()
            for attempt in range(4):
                try:
                    gloss = call(prompt, model)
                    break
                except Exception as e:  # network blip / rate limit: back off and retry
                    wait = 2 ** attempt * (15 if "rate" in str(e) else 2)
                    print(f"  retry {c['chunk_id']} in {wait}s ({e})")
                    time.sleep(wait)
            else:
                print(f"  giving up on {c['chunk_id']}")
                continue
            out.write(json.dumps({"chunk_id": c["chunk_id"], "gloss": gloss,
                                  "model": f"{args.backend}:{model}"}, ensure_ascii=False) + "\n")
            out.flush()
            if i % 10 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  last: {gloss[:90]}")
            time.sleep(max(0.0, gap - (time.time() - t0)))


if __name__ == "__main__":
    main()
