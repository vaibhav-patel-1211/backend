"""
Look up Bible verses by their exact reference (e.g. "John 3:16").

This is the non-AI half of retrieval: when someone names a verse we read it
straight from bible.json instead of guessing. It also owns the two things the
citation checker needs: turning "jn"/"JOHN" into "John", and finding references
inside a block of text.

Everything is loaded once into a nested dict so a lookup is just three dict hits.
"""
import json
import re
from functools import lru_cache

from app.config import settings

# Short forms people commonly type. Full book names are matched automatically,
# so we only list the abbreviations here.
_ABBREVIATIONS = {
    "gen": "Genesis", "gn": "Genesis", "ex": "Exodus", "exo": "Exodus",
    "lev": "Leviticus", "lv": "Leviticus", "num": "Numbers", "nm": "Numbers",
    "deut": "Deuteronomy", "dt": "Deuteronomy", "josh": "Joshua", "js": "Joshua",
    "judg": "Judges", "jud": "Judges", "rt": "Ruth", "ps": "Psalms",
    "psa": "Psalms", "psalm": "Psalms", "prov": "Proverbs", "prv": "Proverbs",
    "eccl": "Ecclesiastes", "ec": "Ecclesiastes", "song": "Song of Solomon",
    "isa": "Isaiah", "is": "Isaiah", "jer": "Jeremiah", "jr": "Jeremiah",
    "lam": "Lamentations", "ezek": "Ezekiel", "ez": "Ezekiel", "dan": "Daniel",
    "dn": "Daniel", "hos": "Hosea", "mt": "Matthew", "matt": "Matthew",
    "mk": "Mark", "mrk": "Mark", "lk": "Luke", "luk": "Luke", "jn": "John",
    "jo": "John", "joh": "John", "act": "Acts", "rom": "Romans", "rm": "Romans",
    "1cor": "1 Corinthians", "2cor": "2 Corinthians", "gal": "Galatians",
    "eph": "Ephesians", "phil": "Philippians", "col": "Colossians",
    "heb": "Hebrews", "jas": "James", "jm": "James", "rev": "Revelation",
    "re": "Revelation",
}


@lru_cache(maxsize=1)
def _load():
    """Read bible.json once and prepare everything we look things up against.

    Hands back three things, all cached for the life of the process:
      - index:           verses, nested as index[book][chapter][verse] = text
      - canonical_names: any name/abbreviation (lowercased) -> proper book name
      - ref_re:          a regex that spots "<book> <chapter>:<verse>" in text
    """
    # utf-8-sig so a stray byte-order mark at the start of the file doesn't break us.
    with open(settings.BIBLE_PATH, encoding="utf-8-sig") as f:
        verses = json.load(f)

    index = {}
    canonical_names = {}
    for v in verses:
        book = v["book"]
        index.setdefault(book.lower(), {}).setdefault(int(v["chapter"]), {})[int(v["verse"])] = v["text"]
        canonical_names[book.lower()] = book

    # Let the abbreviations point at the same canonical names.
    for abbr, name in _ABBREVIATIONS.items():
        if name.lower() in index:
            canonical_names[abbr] = name

    # Match the longest names first, otherwise "John" could match inside "1 John".
    names_longest_first = sorted(canonical_names, key=len, reverse=True)
    book_alt = "|".join(re.escape(k) for k in names_longest_first)
    ref_re = re.compile(rf"\b({book_alt})\.?\s+(\d+):(\d+)(?:-(\d+))?", re.IGNORECASE)
    return index, canonical_names, ref_re


def normalize_book(name: str):
    """Turn any spelling/abbreviation into the proper book name, or None if unknown."""
    _, canonical_names, _ = _load()
    return canonical_names.get(name.strip().lower())


def lookup(book: str, chapter: int, verse: int):
    """Return the text of one verse, or None if that book/chapter/verse doesn't exist."""
    index, _, _ = _load()
    canonical = normalize_book(book)
    if not canonical:
        return None
    return index.get(canonical.lower(), {}).get(int(chapter), {}).get(int(verse))


def _match_to_verses(match):
    """Expand one regex match into the verses it covers.

    "John 3:16" -> one entry; "John 3:16-18" -> three. Returns [] for an
    unknown book so callers can simply ignore it.
    """
    book = normalize_book(match.group(1))
    if not book:
        return []
    chapter = int(match.group(2))
    start = int(match.group(3))
    end = int(match.group(4)) if match.group(4) else start  # group(4) is the "-18" part
    return [{"book": book, "chapter": chapter, "verse": v} for v in range(start, end + 1)]


def parse_references(text: str):
    """Find every scripture reference in a piece of text, with ranges expanded.

    Returns a de-duplicated list of {book, chapter, verse} in the order seen.
    """
    _, _, ref_re = _load()
    refs = []
    for match in ref_re.finditer(text):
        for ref in _match_to_verses(match):
            if ref not in refs:
                refs.append(ref)
    return refs


def lookup_references(refs):
    """Given a list of references, return the ones that actually exist as verse dicts."""
    docs = []
    for r in refs:
        text = lookup(r["book"], r["chapter"], r["verse"])
        if text:
            docs.append({**r, "text": text})
    return docs


def reference_exists(book: str, chapter: int, verse: int) -> bool:
    """True if this exact verse is in the Bible."""
    return lookup(book, chapter, verse) is not None
