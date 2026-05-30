"""
Sanity-check each verse before it goes into the database.

Two things happen here: we make sure a record has all four fields and they make
sense, and we tidy it up (proper book name, ints for chapter/verse, trimmed
text). Bad records are reported rather than crashing the whole import.
"""
from app.services import verse_lookup

_REQUIRED = ("book", "chapter", "verse", "text")


def validate_record(record: dict):
    """Check and clean one verse. Returns (True, tidy_record) or (False, reason)."""
    # Every field must be present and non-empty.
    for field in _REQUIRED:
        if field not in record or record[field] in (None, ""):
            return False, f"missing field '{field}'"

    # The book has to be one we actually recognise.
    book = verse_lookup.normalize_book(str(record["book"]))
    if not book:
        return False, f"unknown book '{record['book']}'"

    # Chapter and verse need to be numbers.
    try:
        chapter = int(record["chapter"])
        verse = int(record["verse"])
    except (TypeError, ValueError):
        return False, "chapter/verse must be integers"

    text = str(record["text"]).strip()
    if not text:
        return False, "empty text"

    return True, {"book": book, "chapter": chapter, "verse": verse, "text": text}


def validate_all(records):
    """Run every record through validate_record.

    Returns (valid_records, errors); errors are (index, reason) pairs so you can
    see which ones were skipped and why.
    """
    valid, errors = [], []
    for i, rec in enumerate(records):
        ok, result = validate_record(rec)
        if ok:
            valid.append(result)
        else:
            errors.append((i, result))
    return valid, errors
