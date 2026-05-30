"""
Catch made-up scripture.

The model is good but it will occasionally cite a verse that doesn't exist
("Matthew 99:99"). After it answers, we scan the reply for references like
(John 3:16), check each one against the real Bible, and quietly swap out any
that aren't real. We also hand back the list of references that checked out.
"""
from app.services import verse_lookup

# What we drop in place of a reference that isn't real.
_UNVERIFIED = "(I could not verify that scripture reference)"


def validate_response(text: str):
    """Clean a reply and collect its valid citations.

    Returns (cleaned_text, citations) where citations looks like
    ["John 3:16", "Romans 8:28"] and cleaned_text has any fake references
    replaced with the "could not verify" note.
    """
    if not text:
        return text, []

    _, _, ref_re = verse_lookup._load()
    citations = []

    def keep_or_flag(match):
        verses = verse_lookup._match_to_verses(match)
        # A reference is only trustworthy if every verse it names really exists.
        if not verses or not all(verse_lookup.reference_exists(**v) for v in verses):
            return _UNVERIFIED

        # Rebuild a tidy label, e.g. "John 3:16" or "John 3:16-18".
        book, chapter = verses[0]["book"], verses[0]["chapter"]
        start, end = verses[0]["verse"], verses[-1]["verse"]
        label = f"{book} {chapter}:{start}" + (f"-{end}" if end != start else "")
        if label not in citations:
            citations.append(label)
        return match.group(0)  # leave the original text untouched

    cleaned = ref_re.sub(keep_or_flag, text)
    return cleaned, citations


def extract_citations(text: str):
    """Just the valid references in the text (ignores the cleaned-up copy)."""
    return validate_response(text)[1]
