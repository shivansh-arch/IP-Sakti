# Architecture & design decisions

## Why v1 failed
v1 embedded romanized Sanskrit (`sheShatvAdAyuSho yApyam...`) with `paraphrase-multilingual-MiniLM-L12-v2`. That model was trained on natural-language text in many languages, but never on ITRANS romanization, so it sees the verses as meaningless word fragments.

The calibration had already hinted at this: an unrelated query scored 0.15 and a relevant English one only 0.34. On the eval, v1 got 1 of 18 test positives right, refused only half of the off-topic queries, and never linked a patent to a verse that shared its plant.

## The v2 bridge: a controlled vocabulary
Rather than hoping an embedding model learns Sanskrit, v2 tags both sides with the **same IDs**:
- `haridrA` / `turmeric` / `Curcuma longa` all become `turmeric`
- `kuShTha` / `psoriasis` / `dermatitis` all become `skin_disease`

Three reasons for this approach:
- **It's explainable.** "The patent claims turmeric for skin disease, and verse 6_95_142 names *haridrA* for *kuShTha*" is the kind of argument a patent examiner can check.
- **It's free and deterministic.** No LLM calls, so the same input always gives the same tags.
- **It's testable.** Every guard against a false friend has a test.

The cost is that coverage is limited to the lexicon: 74 plants and 38 conditions. A query about anything outside it gets embedding similarity only, and usually abstains.

### Matching rules
- Sanskrit patterns are case-sensitive, because case is phonemic in this scheme: `kAs` (cough) ≠ `kas` (who).
- They match stems as substrings, because sandhi fuses words (`pippalIpippalImUla`).
- Lookbehinds and lookaheads remove false friends found by reading the matches in context, for example:
  - `bhaviShyati` is the future tense of "to be", not poison
  - `tvacA` means skin, not sweet flag
  - `darshana` means seeing, not hemorrhoids
  - `amedhya` means impure, not a cognitive tonic
  - `abhiShyandi` is a property of foods, not an eye disease
- English patterns are anchored at the start of a word, so "pain" doesn't match "Spain" and "alcoholic extract" isn't tagged as alcoholism.

## Scoring
`score = 0.5 · cosine(bge(query), bge(english_view)) + 0.5 · entity_overlap`

Entity overlap is the fraction of the query's entities that the chunk also has, with plants weighted 0.6 and conditions 0.4. Plants count for more because a shared plant is stronger evidence than a shared indication: fever appears in 675 chunks.

Candidates are the top 50 by embedding similarity, combined with the top 50 entity-filtered results. Without the filtered set, a low-cosine chunk that names exactly the right plant could be missed.

**Abstention** happens when the top score is below 0.59 (calibrated on the dev split). It also happens when the query named entities and the best hit shares none of them, because that match rests on similar wording alone.

## Why bge-small
It is 33M parameters (about 130 MB), small enough for a free-tier container, and a strong English retriever. Because v2 embeds English descriptions, a multilingual model is no longer needed.

## What the gloss experiment showed
`llama3.2:3b` through Ollama, given lexicon hints, still made up content for passages with no treatment in them. The gloss stays optional and is only ever *appended* to the lexicon description.

## Known limitations
- The eval's relevance is defined by the lexicon (see the README caveat).
- Long commentary chunks list many diseases as examples, so they pick up many tags. Weighting entities by how often they appear (IDF) could rank them down.
- The patent set has only 82 abstracts, most unrelated to Ayurveda. The patent threshold reuses the NIIMH one.
- Synonyms that mean two things are left out on purpose (`nAgara` is ginger or city, `abhayA` is haritaki or fearless, `kuShTha` is both a plant and a disease), which lowers recall.
