"""
The bouncer.

Before we spend anything on the model, we check the user's message against a
list of red-flag patterns: hate, calls for violence, attempts to twist
scripture, and "ignore your instructions" style jailbreaks. It's deliberately
simple (regex, no AI) so it's fast and easy to reason about.

is_safe() guards normal questions; is_image_safe() adds a few extra checks for
picture requests.
"""
import re

# If any of these match the message, we refuse. Grouped by the kind of abuse.
_BLOCK_PATTERNS = [
    # Twisting / faking scripture
    r"\b(rewrite|change|alter|edit|modify|twist|distort|reinterpret|fake|invent|make up|fabricate)\b.{0,40}\b(verse|verses|scripture|scriptures|bible|gospel|john \d|psalm)",
    r"\b(rewrite|change|alter|edit|modify|twist|distort|reinterpret)\b.{0,40}\d+:\d+",
    r"\binvent\b.{0,20}\b(a |an |some )?(bible )?verse",
    r"\bmake up\b.{0,20}\b(a |an |some )?(bible )?verse",
    # Jailbreak / prompt injection
    r"\bignore\b.{0,30}\b(previous|prior|above|all)\b.{0,20}\b(instruction|instructions|rules|prompt)",
    r"\bdisregard\b.{0,30}\b(instruction|instructions|rules|system prompt)",
    r"\byou are now\b",
    r"\bact as\b.{0,30}\b(dan|jailbreak|unfiltered)",
    # Hate, violence, extremism (even when dressed up as religious)
    r"\b(kill|murder|attack|harm|bomb|exterminate|cleanse)\b.{0,40}\b(jew|jews|muslim|muslims|christian|christians|gay|atheist|infidel|non-?believer)",
    r"\b(christian|religious|holy)\b.{0,20}\b(propaganda|extremism)\b",
    r"\b(propaganda|content)\b.{0,30}\b(encourag\w*|promot\w*|support\w*|incit\w*)\b.{0,20}\b(violence|hate|racism|terror)",
    r"\b(justify|support|defend)\b.{0,30}\b(racism|slavery|genocide|terrorism|violence)\b",
    r"\bholy war\b.{0,30}\b(against|kill|attack)",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _BLOCK_PATTERNS]


def is_safe(text: str):
    """Check a message. Returns (True, None) if it's fine, or (False, reason) if not."""
    if not text or not text.strip():
        return False, "empty message"
    for pattern in _COMPILED:
        if pattern.search(text):
            return False, "blocked by content policy"
    return True, None


# Extra patterns for image prompts on top of the general checks above.
_IMAGE_BLOCK = [
    r"\b(hate|hateful|racist|nazi|kkk|extremist|terror)\b",
    r"\b(gore|gory|graphic violence|massacre|torture|beheading)\b",
    r"\b(kill|murder|attack|bomb)\b.{0,30}\b(people|jew|muslim|christian|gay)",
    r"\b(propaganda)\b.{0,20}\b(violence|hate|war)",
]
_IMAGE_COMPILED = [re.compile(p, re.IGNORECASE) for p in _IMAGE_BLOCK]


def is_image_safe(text: str):
    """Same as is_safe, plus a few image-only checks (gore, hateful imagery, ...)."""
    safe, reason = is_safe(text)
    if not safe:
        return safe, reason
    for pattern in _IMAGE_COMPILED:
        if pattern.search(text):
            return False, "unsafe image request"
    return True, None
