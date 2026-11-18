"""
lexicon — deterministic Sanskrit <-> English entity tagging.

Why this exists: the NIIMH corpus is romanized Sanskrit (ITRANS-style), and
patents are English. A general multilingual embedding model has never seen
this romanization, so raw cross-lingual similarity is mostly noise. Tagging
both sides with the SAME controlled vocabulary (plant + condition IDs) gives
an explainable bridge: "patent claims Curcuma longa for skin disease; verse
names haridrA for kuShTha".

Usage:
    from lexicon import tag
    tag("mustamAragvadhaH pAThA triphalA ... haridre", lang="sa")
    tag("Turmeric composition for psoriasis", lang="en")
    tag(user_query)            # lang="auto": runs both matchers
"""

from lexicon.tagger import (  # noqa: F401
    Tags,
    tag,
    normalize_iast,
    describe,
    entity_overlap,
    PLANTS,
    CONDITIONS,
)
