"""
tagger.py — compile the lexicon JSON files into regex matchers and tag text.

Two matchers per entity:
  * sa: case-SENSITIVE stem regexes over ITRANS-style romanization. Case
        carries meaning there (A = long a, T = retroflex t), so we never
        lowercase Sanskrit input.
  * en: case-insensitive, anchored at a word start (\b) so "pain" does not
        fire inside "Spain", but "diabet" still catches diabetes/diabetic.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

_DIR = Path(__file__).parent


def _load(name: str) -> dict:
    with open(_DIR / name, encoding="utf-8") as f:
        raw = json.load(f)["entries"]
    compiled = {}
    for e in raw:
        compiled[e["id"]] = {
            **e,
            "_sa": [re.compile(p) for p in e.get("sa", [])],
            "_en": [re.compile(r"\b" + re.escape(p), re.IGNORECASE) for p in e.get("en", [])],
        }
    return compiled


PLANTS = _load("plants.json")
CONDITIONS = _load("conditions.json")

# IAST / common diacritics -> the corpus's ITRANS-style scheme, so a user can
# type "haridrā" or "jvara" and still hit the Sanskrit matchers.
_IAST = [
    ("ā", "A"), ("ī", "I"), ("ū", "U"), ("ṛ", "Ru"), ("ṝ", "RU"), ("ḷ", "Lu"),
    ("ṣ", "Sh"), ("ś", "sh"), ("ṇ", "N"), ("ṭ", "T"), ("ḍ", "D"), ("ñ", "~j"),
    ("ṅ", "~g"), ("ṃ", "M"), ("ṁ", "M"), ("ḥ", "H"),
]


def normalize_iast(text: str) -> str:
    for a, b in _IAST:
        text = text.replace(a, b)
    return text


@dataclass
class Tags:
    plants: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.plants and not self.conditions

    def to_dict(self) -> dict:
        return {"plants": self.plants, "conditions": self.conditions}


def _match(table: dict, text: str, lang: str) -> list[str]:
    hits = []
    for eid, e in table.items():
        pats = []
        if lang in ("sa", "auto"):
            pats += e["_sa"]
        if lang in ("en", "auto"):
            pats += e["_en"]
        if any(p.search(text) for p in pats):
            hits.append(eid)
    return hits


def tag(text: str, lang: str = "auto") -> Tags:
    """lang: 'sa' (corpus verses), 'en' (patents), 'auto' (user queries)."""
    if not text:
        return Tags()
    if lang in ("sa", "auto"):
        text = normalize_iast(text)
    return Tags(
        plants=_match(PLANTS, text, lang),
        conditions=_match(CONDITIONS, text, lang),
    )


def describe(tags: Tags) -> str:
    """Plain-English rendering of tags — the text we embed for v2 search."""
    parts = []
    if tags.plants:
        parts.append("Substances: " + "; ".join(
            f"{PLANTS[p]['name']} ({PLANTS[p]['botanical']})" for p in tags.plants))
    if tags.conditions:
        parts.append("Indications: " + "; ".join(CONDITIONS[c]["name"] for c in tags.conditions))
    return ". ".join(parts)


def entity_overlap(query: Tags, doc: Tags) -> tuple[float, dict]:
    """
    Fraction of the QUERY's entities that the document also has, with plants
    weighted 0.6 and conditions 0.4 (a shared plant is stronger prior-art
    evidence than a shared indication — "fever" is in hundreds of verses).
    If the query only has one kind of entity, that kind gets full weight.

    Returns (score in [0,1], {"plants": [...shared], "conditions": [...shared]}).
    """
    sp = sorted(set(query.plants) & set(doc.plants))
    sc = sorted(set(query.conditions) & set(doc.conditions))
    shared = {"plants": sp, "conditions": sc}
    if query.empty:
        return 0.0, shared
    fp = len(sp) / len(query.plants) if query.plants else None
    fc = len(sc) / len(query.conditions) if query.conditions else None
    if fp is not None and fc is not None:
        return 0.6 * fp + 0.4 * fc, shared
    return (fp if fp is not None else fc), shared
