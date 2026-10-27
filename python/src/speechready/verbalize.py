"""Stage 2: verbalize. Rewrites only the tokens a model is likely to misread.

Rules are per language and arrive with the next release: phone numbers, IDs,
dates in the stated locale, years, currency decimals, units, ranges and acronyms
from a lexicon. Until then this stage leaves text unchanged.
"""

from __future__ import annotations

from .changes import Recorder

STAGE = "verbalize"


def verbalize(text: str, locale: str = "en-US", recorder: Recorder | None = None) -> str:
    return text


__all__ = ["verbalize"]
