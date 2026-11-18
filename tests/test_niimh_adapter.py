"""NIIMH HTML -> Candidate extraction on a synthetic page shaped like the real one."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))
from eda_agent.adapters.niimh_adapter import extract_candidates  # noqa: E402

HTML = """
<div class="hidden" id="sloka_trans_1">athAto dIrghaMjIvitIyamadhyAyaM vyAkhyAsyAmaH||1||</div>
<div class="hidden" id="sloka_trans_2">iti ha smAha bhagavAnAtreyaH||2||</div>
<div class="hidden" id="sloka_trans_3">first half of a verse|</div>
<div class="hidden" id="sloka_trans_4">second half of it||3-4||</div>
<div class="hidden" id="sloka_trans_5">balam|64|</div>
<div class="hidden" id="sloka_trans_6">a trailing line with no marker</div>
<div class="hidden" id="vya_trans_1">commentary on one||1||</div>
"""


def test_extracts_units_and_flags():
    cands = extract_candidates(HTML, "doc1")
    by = {(c.unit_type, c.unit_id): c for c in cands}

    assert by[("root_text", "1")].flags == []
    assert ("colophon", "colophon_2") in by                     # boilerplate kept apart
    assert by[("root_text", "3-4")].text == "first half of a verse| second half of it||3-4||"
    assert by[("root_text", "64")].flags == ["single_danda_marker"]
    unmarked = [c for c in cands if "no_closing_marker" in c.flags]
    assert len(unmarked) == 1 and unmarked[0].text == "a trailing line with no marker"
    assert by[("commentary", "1")].text == "commentary on one||1||"
