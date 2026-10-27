"""Word error rate with a normalization that forgives how STT formats numbers.

Both sides are lowercased, stripped of punctuation and markup, and digits are
expanded to words. Because an STT engine may write "555" for speech that said
"five five five", the hypothesis is expanded both ways (as a cardinal and digit
by digit) and the better score counts.
"""

from __future__ import annotations

import re
import unicodedata

from speechready.verbalize import numbers_en, numbers_tr

_TAG = re.compile(r"<[^>]+>|\[[^\]]+\]")
_PUNCT = re.compile(r"[^\w\s']", re.UNICODE)
_DIGITS = re.compile(r"\d+")


def _lang(locale: str) -> str:
    return locale.split("-")[0].lower()


def _num_words(locale: str):
    return numbers_tr if _lang(locale) == "tr" else numbers_en


def normalize(text: str, locale: str = "en-US", digits_mode: str = "cardinal") -> list[str]:
    mod = _num_words(locale)
    text = unicodedata.normalize("NFC", text)
    text = _TAG.sub(" ", text)
    text = text.replace("-", " ").replace("’", "'")
    if _lang(locale) == "tr":
        text = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", text)  # 1.250 -> 1250
        text = re.sub(r"(?<=\d),(?=\d)", " virgül ", text)  # 3,14 -> 3 virgül 14
    else:
        text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)  # 1,250 -> 1250
        text = re.sub(r"(?<=\d)\.(?=\d)", " point ", text)  # 3.14 -> 3 point 14
    text = _PUNCT.sub(" ", text)
    if _lang(locale) == "tr":
        lower = text.replace("I", "ı").replace("İ", "i").lower().replace("ı", "i")  # fold dotted/dotless i
    else:
        lower = text.lower()

    def expand(m: re.Match[str]) -> str:
        n = m.group(0)
        if digits_mode == "digits" or len(n) > 15:
            return mod.digits(n)
        return mod.cardinal(int(n))

    lower = _DIGITS.sub(expand, lower)
    return lower.split()


def edit_distance(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def wer(reference: str, hypothesis: str, locale: str = "en-US") -> float:
    ref = normalize(reference, locale)
    if not ref:
        return 0.0
    best = min(
        edit_distance(ref, normalize(hypothesis, locale, "cardinal")),
        edit_distance(ref, normalize(hypothesis, locale, "digits")),
    )
    return best / len(ref)


def is_misread(reference: str, hypothesis: str, locale: str = "en-US", threshold: float = 0.2) -> bool:
    return wer(reference, hypothesis, locale) > threshold
