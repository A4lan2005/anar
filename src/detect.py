import re

import pymorphy3

from .config import (
    ABSTRACT_SUFFIXES,
    MAX_PHRASE_LEN,
    METADATA_PREFIXES,
    MIN_PHRASE_LEN,
    OPERATION_LEAD_WORDS,
)

_morph = pymorphy3.MorphAnalyzer()

_NUMBER_ONLY = re.compile(r"^[\d\s.,:]+$")
_TIME_LIKE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
_MEASUREMENT = re.compile(r"^\d+\s*замер$", re.I)


def _first_word(text: str) -> str:
    match = re.match(r"^[\s«\"'(]*([A-Za-zА-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүІі]+)", text)
    return match.group(1) if match else ""


def _has_abstract_suffix(word: str) -> bool:
    lower = word.lower()
    return any(lower.endswith(suffix) for suffix in ABSTRACT_SUFFIXES)


def is_metadata_line(text: str) -> bool:
    lower = text.lower().strip()
    if _NUMBER_ONLY.match(lower):
        return True
    if _TIME_LIKE.match(lower):
        return True
    if _MEASUREMENT.match(lower):
        return True
    if lower in {"1 замер", "2 замер", "3 замер"}:
        return True
    return any(lower.startswith(prefix) for prefix in METADATA_PREFIXES)


def is_abstract_phrase(text: str) -> bool:
    if not isinstance(text, str):
        return False

    text = text.strip()
    if not text or len(text) < MIN_PHRASE_LEN or len(text) > MAX_PHRASE_LEN:
        return False

    if is_metadata_line(text):
        return False

    word = _first_word(text)
    if not word:
        return False

    lower_word = word.lower()
    if lower_word in OPERATION_LEAD_WORDS:
        return True

    parsed = _morph.parse(word)
    if not parsed:
        return False

    best = parsed[0]
    tag = set(str(best.tag).split(","))

    if "NOUN" in tag:
        if _has_abstract_suffix(word) or _has_abstract_suffix(best.normal_form):
            return True
        # Any multi-word phrase starting with a common-length noun is likely an operation name.
        if len(text) >= 20 and "Name" not in tag:
            return True

    if tag & {"VERB", "INFN", "PRTF", "PRTS"}:
        return True

    return False
