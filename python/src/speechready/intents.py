"""Pacing intents written inline in the input and carried through the pipeline.

Developers write `[pause 500ms]`, `[spell AB12]` or `[em really]` in their text,
or an SSML `<break time="500ms"/>` they already had. `extract` replaces each one
with a private-use sentinel so cleaning and verbalizing leave it alone; the
compile stage renders every sentinel in the target provider's own syntax.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SENTINEL_OPEN = ""
SENTINEL_CLOSE = ""

_INTENT_TAG = re.compile(
    r"\[(?P<kind>pause|spell|em|ipa)(?:\s+(?P<arg>[^\]]*?))?\s*\](?!\()",
    re.IGNORECASE,
)
_SSML_BREAK = re.compile(
    r"""<break\s+(?:time\s*=\s*["'](?P<time>[^"']+)["']|strength\s*=\s*["'](?P<strength>[^"']+)["'])[^>]*/?>""",
    re.IGNORECASE,
)
_SENTINEL = re.compile(f"{SENTINEL_OPEN}(\\d+){SENTINEL_CLOSE}")

_STRENGTH_MS = {"x-weak": 250, "weak": 500, "medium": 750, "strong": 1000, "x-strong": 1250}
DEFAULT_PAUSE_MS = 500


@dataclass(frozen=True)
class Intent:
    kind: str  # pause | spell | em | phoneme
    ms: int = 0  # pause only
    text: str = ""  # spell, em and phoneme: the words as written
    ipa: str = ""  # phoneme: IPA transcription
    say: str = ""  # phoneme: respelling fallback for providers without phoneme tags


def parse_duration_ms(value: str | None) -> int:
    """'1.5s', '500ms', '2' (seconds) -> milliseconds. Unparseable -> the default."""
    if not value:
        return DEFAULT_PAUSE_MS
    v = value.strip().lower()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(ms|s)?", v)
    if not m:
        return DEFAULT_PAUSE_MS
    number, unit = float(m.group(1)), m.group(2)
    if unit == "ms":
        return int(round(number))
    return int(round(number * 1000))


def extract(text: str, intents: list[Intent] | None = None) -> tuple[str, list[Intent]]:
    """Replace every inline intent with a sentinel; return the text and the intents in order.

    Pass an existing list to append to it (the pipeline runs a second pass after
    cleaning, because the cleaner can turn markdown emphasis into `[em ...]`).
    """
    intents = intents if intents is not None else []

    def _add(intent: Intent) -> str:
        intents.append(intent)
        return f"{SENTINEL_OPEN}{len(intents) - 1}{SENTINEL_CLOSE}"

    def _ssml(m: re.Match[str]) -> str:
        if m.group("time"):
            return _add(Intent("pause", ms=parse_duration_ms(m.group("time"))))
        return _add(Intent("pause", ms=_STRENGTH_MS.get(m.group("strength").lower(), DEFAULT_PAUSE_MS)))

    def _tag(m: re.Match[str]) -> str:
        kind = m.group("kind").lower()
        arg = (m.group("arg") or "").strip()
        if kind == "pause":
            return _add(Intent("pause", ms=parse_duration_ms(arg)))
        if not arg:
            return ""
        if kind == "ipa":
            word, _, transcription = arg.partition(" ")
            if not transcription:
                return word
            return _add(Intent("phoneme", text=word, ipa=transcription.strip()))
        return _add(Intent(kind, text=arg))

    text = _SSML_BREAK.sub(_ssml, text)
    text = _INTENT_TAG.sub(_tag, text)
    return text, intents


def split_on_sentinels(text: str) -> list[tuple[str, int | None]]:
    """Split text into (segment, intent_index) pairs; plain text has index None."""
    parts: list[tuple[str, int | None]] = []
    pos = 0
    for m in _SENTINEL.finditer(text):
        if m.start() > pos:
            parts.append((text[pos : m.start()], None))
        parts.append(("", int(m.group(1))))
        pos = m.end()
    if pos < len(text):
        parts.append((text[pos:], None))
    return parts


def strip_sentinels(text: str) -> str:
    return _SENTINEL.sub("", text)
