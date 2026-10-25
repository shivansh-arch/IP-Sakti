from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Candidate:
    """One structural unit extracted from a raw document — a verse, a holding, a claim."""
    source: str                      # "niimh" | "kanoon" | "patents"
    doc_id: str                      # chapter_id, case_id, patent_id
    unit_id: str                     # verse_num, holding_index, claim_num
    text: str
    unit_type: str                   # "root_text" | "commentary" | "holding" | "claim"
    raw_meta: dict = field(default_factory=dict)  # anything source-specific worth keeping
    flags: list[str] = field(default_factory=list) # e.g. "no_closing_marker", "ambiguous_boundary"