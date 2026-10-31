"""Word error rate with a normalization that forgives how STT writes down speech.

The reference is the intended spoken form ("twenty twenty-six"). An STT engine
writes what it heard in its own written conventions ("2026", "9AM", "21st",
"$5", "AB12X9"), so the hypothesis is normalized before scoring:

- markup, punctuation, hyphens and underscores go; case is folded (Turkish i too);
- symbols become words (+ plus, % percent, $ dollars, TL lira);
- letters and digits glued together are split, and short all-caps runs are
  spelled (AB12X9 -> a b 1 2 x 9), on both sides;
- every digit run is expanded as a cardinal, digit by digit, or as a year,
  and the combination with the fewest errors counts;
- as one more candidate, the whole hypothesis is run through speechready's
  own verbalizer, which covers ordinals, decades, dates and currency formats.

Expansions only ever lower the score, and they apply equally to the raw and
the processed transcript, so they cannot favour one side.
"""

from __future__ import annotations

import itertools
import re
import unicodedata

from speechready.verbalize import numbers_en, numbers_tr, verbalize

_TAG = re.compile(r"<[^>]+>|\[[^\]]+\]")
_PUNCT = re.compile(r"[^\w\s']", re.UNICODE)
_DIGITS = re.compile(r"\d+")
_MAX_COMBOS = 64

_SYMBOLS = {
    "en": [(r"\+(?=\s?\d)", " plus "), (r"(\d)\s?%", r"\1 percent "), (r"%\s?(\d)", r"percent \1"),
           (r"\$\s?(\d[\d,]*(?:\.\d+)?)", r"\1 dollars "), (r"€\s?(\d[\d,]*(?:\.\d+)?)", r"\1 euros "), (r"£\s?(\d[\d,]*(?:\.\d+)?)", r"\1 pounds "),
           (r"(\d+)\s*[-–]\s*(\d+)", r"\1 to \2"), (r"\b(\d{1,2}):00\b", r"\1")],
    "tr": [(r"\+(?=\s?\d)", " artı "), (r"%\s?(\d)", r"yüzde \1"), (r"(\d)\s?%", r"yüzde \1"),
           (r"\bTL\b", " lira "), (r"\btürk lirası\b", " lira "), (r"₺\s?(\d[\d.]*(?:,\d+)?)", r"\1 lira "),
           (r"\$\s?(\d[\d.]*(?:,\d+)?)", r"\1 dolar "), (r"€\s?(\d[\d.]*(?:,\d+)?)", r"\1 avro "),
           (r"(\d+)\s*[-–]\s*(\d+)", r"\1 ila \2"), (r"\b(\d{1,2}):00\b", r"\1")],
}


def _lang(locale: str) -> str:
    return locale.split("-")[0].lower()


def _num_words(locale: str):
    return numbers_tr if _lang(locale) == "tr" else numbers_en


def _pre(text: str, locale: str) -> str:
    """Everything before digit expansion: shared by both sides."""
    lang = _lang(locale)
    text = unicodedata.normalize("NFC", text)
    text = _TAG.sub(" ", text)
    text = text.replace("’", "'")
    if lang == "tr":
        text = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", text)  # 1.250 -> 1250
        text = re.sub(r"(?<=\d),(?=\d)", " virgül ", text)  # 3,14 -> 3 virgül 14
    else:
        text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)  # 1,250 -> 1250
        text = re.sub(r"(?<=\d)\.(?=\d)", " point ", text)  # 3.14 -> 3 point 14
    for pat, repl in _SYMBOLS.get(lang, _SYMBOLS["en"]):
        text = re.sub(pat, repl, text, flags=re.IGNORECASE if "lirası" in pat else 0)
    if lang == "en":
        text = re.sub(r"\b(\d+)(st|nd|rd|th)\b", lambda m: numbers_en.ordinal(int(m.group(1))), text)
    text = text.replace("-", " ").replace("_", " ")
    text = re.sub(r"(?<=\d)(?=[^\W\d_])|(?<=[^\W\d_])(?=\d)", " ", text)  # 9AM -> 9 AM, AB12 -> AB 12
    text = re.sub(r"\b([A-ZÇĞİÖŞÜ]{2,4})\b", lambda m: " ".join(m.group(1)), text)  # ABC -> A B C
    text = _PUNCT.sub(" ", text)
    if lang == "tr":
        text = text.replace("I", "ı").replace("İ", "i").lower().replace("ı", "i")  # fold dotted/dotless i
    else:
        text = text.lower()
        text = re.sub(r"\b([ap]) m\b", r"\1m", text)  # a m / p m -> am / pm
    return text


def _expansions(n: str, locale: str) -> list[str]:
    mod = _num_words(locale)
    if len(n) > 15:
        return [mod.digits(n)]
    out = [mod.cardinal(int(n)), mod.digits(n)]
    if _lang(locale) == "en" and len(n) == 4 and 1000 <= int(n) <= 2999:
        out.append(numbers_en.year(int(n)))
    if _lang(locale) == "en" and 1 <= int(n) <= 31:
        out.append(numbers_en.ordinal(int(n)))  # "March 4" for "March fourth"
    return list(dict.fromkeys(out))


def normalize(text: str, locale: str = "en-US", digits_mode: str = "cardinal") -> list[str]:
    """One reading of the text: digits as cardinals (default) or digit by digit."""
    mod = _num_words(locale)
    pre = _pre(text, locale)
    expanded = _DIGITS.sub(lambda m: mod.digits(m.group(0)) if digits_mode == "digits" or len(m.group(0)) > 15 else mod.cardinal(int(m.group(0))), pre)
    return expanded.replace("-", " ").split()


def candidates(hypothesis: str, locale: str) -> list[list[str]]:
    """Every reading of the hypothesis worth scoring."""
    pre = _pre(hypothesis, locale)
    runs = _DIGITS.findall(pre)
    alts = [_expansions(n, locale) for n in runs]
    outs: list[list[str]] = []
    total = 1
    for a in alts:
        total *= len(a)
    if total <= _MAX_COMBOS:
        parts = _DIGITS.split(pre)
        for combo in itertools.product(*alts) if alts else [()]:
            text = parts[0] + "".join(w + parts[k + 1] for k, w in enumerate(combo))
            outs.append(text.replace("-", " ").split())
    else:
        outs.append(normalize(hypothesis, locale, "cardinal"))
        outs.append(normalize(hypothesis, locale, "digits"))
    try:
        outs.append(normalize(verbalize(hypothesis, locale), locale))
    except Exception:  # noqa: BLE001 - the verbalizer is a convenience here, never a failure
        pass
    return outs


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
    best = min(edit_distance(ref, h) for h in candidates(hypothesis, locale))
    return best / len(ref)


def is_misread(reference: str, hypothesis: str, locale: str = "en-US", threshold: float = 0.2) -> bool:
    return wer(reference, hypothesis, locale) > threshold
