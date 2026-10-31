"""Stage 4: chunk. Sentence segmentation, streaming segmentation, and packing under a limit.

Rules that keep prosody intact:
- a newline is a hard boundary (blocks from the clean stage never merge);
- a sentence ends at . ! ? … followed by whitespace and then an uppercase
  letter, a digit, an opening quote or bracket, or a tag;
- a known abbreviation, a single-letter initial, or a number before the full
  stop never ends a sentence;
- a sentence that is longer than the limit is split at clause punctuation,
  then at spaces, and only as a last resort mid-word.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .intents import SENTINEL_OPEN

_ABBREVIATIONS: dict[str, frozenset[str]] = {
    "en": frozenset(
        """mr mrs ms dr prof sr jr st mt ft vs etc e.g i.e cf no nos inc ltd co corp llc dept est approx
        jan feb mar apr jun jul aug sep sept oct nov dec mon tue wed thu fri sat sun a.m p.m
        u.s u.k e.u ph.d m.d b.a m.a b.sc m.sc fig vol pp ed eds rev gen col lt sgt capt cmdr hon
        ave blvd rd hwy tel ext dept univ assn bros""".split()
    ),
    "tr": frozenset(
        """dr prof doç yrd av sn vb vs vd örn bkz yy t.c no sok cad apt mah alb yzb bşk müh
        oca şub mar nis haz tem ağu eyl eki kas ara ltd şti a.ş san tic dk sa sn bk ör
        hz sf s c çev der haz üniv fak böl hst bul uzm öğr yrd tel""".split()
    ),
}

_END = re.compile(
    r"""(?P<end>[.!?…]+)(?P<close>["'”’)\]»]*)(?P<space>\s+)(?=(?P<next>\S))""",
)
_WORD_BEFORE = re.compile(r"(\S+)$")
_CLAUSE = re.compile(r"[,;:—–]\s+|\s+[-]\s+")


def _lang(locale: str) -> str:
    return (locale or "en").split("-")[0].split("_")[0].lower()


def _abbreviations(locale: str) -> frozenset[str]:
    return _ABBREVIATIONS.get(_lang(locale), frozenset())


def _is_boundary(text: str, m: re.Match[str], abbrs: frozenset[str]) -> bool:
    end = m.group("end")
    nxt = m.group("next")
    before = text[: m.start()]
    word_m = _WORD_BEFORE.search(before)
    word = word_m.group(1) if word_m else ""
    core = word.strip("(\"'“”‘’[").lower()

    if "\n" in m.group("space"):
        return True
    if end.startswith(".") and "…" not in end and "!" not in end and "?" not in end:
        if core in abbrs or core.rstrip(".") in abbrs:
            return False
        if len(core) == 1 and core.isalpha():
            return False  # initial: "J. R. R. Tolkien"
        if core.isdigit() and not nxt[0].isupper():
            return False  # ordinal or list number: "3. madde"
        if re.fullmatch(r"[a-z](\.[a-z])+", core):
            return False  # dotted abbreviation not in the list, e.g. "p.s"
    first = nxt[0]
    if first in "\"'“‘([«<" or first == SENTINEL_OPEN:
        return True
    if first.isupper() or first.isdigit():
        return True
    if first in "¿¡":
        return True
    return False


_LIST_MARKER = re.compile(r"\d{1,3}\.")


def split_sentences(text: str, locale: str = "en-US") -> list[str]:
    """Split text into sentences. Newlines are hard boundaries. Empty sentences are dropped."""
    abbrs = _abbreviations(locale)
    out: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        start = 0
        for m in _END.finditer(line):
            if _LIST_MARKER.fullmatch(line[start : m.end()].strip()):
                continue  # "1. Open the app": the number is the item's marker, not a sentence
            if _is_boundary(line, m, abbrs):
                out.append(line[start : m.end("close")].strip())
                start = m.end()
        tail = line[start:].strip()
        if tail:
            out.append(tail)
    return out


@dataclass
class Segmenter:
    """Streaming sentence segmenter for LLM token feeds.

    `push(text)` returns the sentences that are now complete; `flush()` returns
    whatever is left. A boundary is only confirmed once text after it arrives,
    so a sentence is never cut at "Dr." or "3.14" because the stream paused there.
    """

    locale: str = "en-US"
    max_buffer: int | None = None
    _buffer: str = field(default="", repr=False)

    def push(self, text: str) -> list[str]:
        self._buffer += text
        done: list[str] = []
        while True:
            nl = self._buffer.find("\n")
            if nl < 0:
                break
            head, self._buffer = self._buffer[:nl], self._buffer[nl + 1 :]
            done.extend(split_sentences(head, self.locale))
        sentences = split_sentences(self._buffer, self.locale)
        if len(sentences) > 1:
            complete = sentences[:-1]
            done.extend(complete)
            # keep the unconfirmed tail exactly as it stands (leading spaces dropped)
            idx = self._buffer.rfind(sentences[-1])
            self._buffer = self._buffer[idx:] if idx >= 0 else self._buffer
        if self.max_buffer and len(self._buffer) > self.max_buffer:
            cut = _last_clause_cut(self._buffer, self.max_buffer)
            if cut > 0:
                done.append(self._buffer[:cut].strip())
                self._buffer = self._buffer[cut:].lstrip()
        return [s for s in done if s]

    def flush(self) -> list[str]:
        rest = self._buffer
        self._buffer = ""
        return split_sentences(rest, self.locale)


def _last_clause_cut(text: str, limit: int) -> int:
    window = text[:limit]
    best = -1
    for m in _CLAUSE.finditer(window):
        best = m.end()
    if best > 0:
        return best
    sp = window.rfind(" ")
    return sp + 1 if sp > 0 else limit


def _size(text: str, unit: str) -> int:
    return len(text.encode("utf-8")) if unit == "bytes" else len(text)


def _split_long(sentence: str, limit: int, unit: str) -> list[str]:
    """Split one over-long sentence at clause marks, then spaces, then hard."""
    if _size(sentence, unit) <= limit:
        return [sentence]
    pieces: list[str] = []
    rest = sentence
    while _size(rest, unit) > limit:
        window = rest
        while _size(window, unit) > limit:
            window = window[: max(1, int(len(window) * 0.9))]
        cut = -1
        for m in _CLAUSE.finditer(window):
            cut = m.end()
        if cut <= 0:
            cut = window.rfind(" ") + 1
        if cut <= 0:
            cut = len(window)
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        pieces.append(rest)
    return pieces


def pack(sentences: list[str], limit: int | None, unit: str = "chars", joiner: str = " ") -> list[str]:
    """Greedily join sentences into chunks no larger than `limit`. None = one chunk."""
    if limit is None:
        return [joiner.join(sentences)] if sentences else []
    chunks: list[str] = []
    current = ""
    for s in sentences:
        for piece in _split_long(s, limit, unit):
            candidate = piece if not current else current + joiner + piece
            if current and _size(candidate, unit) > limit:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


__all__ = ["Segmenter", "pack", "split_sentences"]
