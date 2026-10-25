import re
from bs4 import BeautifulSoup
from eda_agent.core.candidate import Candidate

# Primary marker: "||N||" or range form "||N-M||" — anchored to end of the
# block's text so a verse-range citation embedded mid-commentary doesn't
# falsely trigger a flush.
CLOSING_MARKER_RE = re.compile(r"\|\|(\d+(?:-\d+)?)\|\|[\s\-),;.]*$")

# Fallback: some files use a single danda at the close instead of double
# (e.g. 'balam|64|'). Anchored to end-of-string (allowing only trailing
# punctuation/whitespace after it) — single danda also marks the mid-verse
# pAda break, so real text following it must still block the match.
SINGLE_DANDA_CLOSING_RE = re.compile(r"\|(\d+(?:-\d+)?)\|[\s\-),;.]*$")

# Colophon = chapter-closing boilerplate, e.g.
#   "...ityagniveshakRute tantre carakapratisaMskRute shlokasthAne ... nAma
#    dvAdasho'adhyAyaH||12||"
#   "...iti ha smAha bhagavAnAtreyaH||2||"
# These are NOT verses — they mark chapter/section boundaries and should
# never be mixed into root_text/commentary candidate streams.
COLOPHON_RE = re.compile(
    r"(ityagnivesha|iti\s+ha\s+sm[aA]ha|nAma\s+\S*adhyAyaH|adhyAyaH\s*\|\|)",
    re.IGNORECASE,
)


def extract_candidates(html: str, doc_id: str) -> list[Candidate]:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    def collect(prefix: str, unit_type: str):
        divs = soup.find_all("div", class_="hidden", id=re.compile(rf"^{prefix}_\d+$"))
        buffer = []
        for div in divs:
            text = div.get_text(strip=True)
            buffer.append(text)

            match = CLOSING_MARKER_RE.search(text)
            marker_style = "double"
            if not match:
                match = SINGLE_DANDA_CLOSING_RE.search(text)
                marker_style = "single"

            if match:
                full_text = " ".join(buffer)

                if COLOPHON_RE.search(full_text):
                    candidates.append(Candidate(
                        source="niimh",
                        doc_id=doc_id,
                        unit_id=f"colophon_{match.group(1)}",
                        text=full_text,
                        unit_type="colophon",
                    ))
                else:
                    extra_flags = ["single_danda_marker"] if marker_style == "single" else []
                    candidates.append(Candidate(
                        source="niimh",
                        doc_id=doc_id,
                        unit_id=match.group(1),
                        text=full_text,
                        unit_type=unit_type,
                        flags=extra_flags,
                    ))
                buffer = []
        if buffer:
            # no closing marker found — real data, don't drop it, flag it
            candidates.append(Candidate(
                source="niimh",
                doc_id=doc_id,
                unit_id=f"unmarked_{len(candidates)}",
                text=" ".join(buffer),
                unit_type=unit_type,
                flags=["no_closing_marker"],
            ))
        return

    collect("sloka_trans", "root_text")
    collect("vya_trans", "commentary")
    return candidates