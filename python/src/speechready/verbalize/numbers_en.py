"""English number words: cardinals, ordinals, years, digit strings."""

from __future__ import annotations

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES = [(10**9, "billion"), (10**6, "million"), (10**3, "thousand"), (100, "hundred")]
_ORDINAL_IRREGULAR = {
    "one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
    "nine": "ninth", "twelve": "twelfth",
}


def cardinal(n: int) -> str:
    if n < 0:
        return "minus " + cardinal(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + ("-" + _ONES[ones] if ones else "")
    for value, name in _SCALES:
        if n >= value:
            head, rest = divmod(n, value)
            words = cardinal(head) + " " + name
            if rest:
                words += " " + cardinal(rest)
            return words
    return str(n)


def ordinal(n: int) -> str:
    words = cardinal(n)
    head, sep, last = words.rpartition(" ") if " " in words else ("", "", words)
    if "-" in last:
        tens, _, ones = last.rpartition("-")
        last = tens + "-" + _ordinal_word(ones)
    else:
        last = _ordinal_word(last)
    return head + sep + last


def _ordinal_word(word: str) -> str:
    if word in _ORDINAL_IRREGULAR:
        return _ORDINAL_IRREGULAR[word]
    if word.endswith("y"):
        return word[:-1] + "ieth"
    return word + "th"


def year(n: int) -> str:
    """Spoken year: 1999 -> nineteen ninety-nine, 2005 -> two thousand five, 2026 -> twenty twenty-six."""
    if n < 1000 or n > 9999:
        return cardinal(n)
    high, low = divmod(n, 100)
    if low == 0:
        if high % 10 == 0:
            return cardinal(n)  # 2000, 3000
        return cardinal(high) + " hundred"  # 1900, 2100
    if 2000 <= n <= 2009:
        return "two thousand " + cardinal(low)
    if low < 10:
        return cardinal(high) + " oh " + cardinal(low)  # 1905 -> nineteen oh five
    return cardinal(high) + " " + cardinal(low)


def digits(s: str) -> str:
    """Each digit as a word; non-digits pass through as their spoken form where known."""
    out = []
    for ch in s:
        if ch.isdigit():
            out.append(_ONES[int(ch)])
        elif ch == "+":
            out.append("plus")
    return " ".join(out)


def decimal(whole: str, frac: str | None) -> str:
    text = cardinal(int(whole.replace(",", "")))
    if frac:
        text += " point " + " ".join(_ONES[int(c)] for c in frac)
    return text
