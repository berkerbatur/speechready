"""Turkish number words and suffix helpers (vowel harmony, consonant softening)."""

from __future__ import annotations

_ONES = ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
_TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]
_SCALES = [(10**9, "milyar"), (10**6, "milyon"), (10**3, "bin")]

_VOWELS = "aeıioöuü"
_BACK = set("aıou")
_ROUND = set("oöuü")
_VOICELESS = set("çfhkpsşt")


def cardinal(n: int) -> str:
    if n < 0:
        return "eksi " + cardinal(-n)
    if n == 0:
        return "sıfır"
    parts: list[str] = []
    for value, name in _SCALES:
        if n >= value:
            head, n = divmod(n, value)
            parts.append(name if (head == 1 and value == 1000) else f"{cardinal(head)} {name}")
    if n >= 100:
        head, n = divmod(n, 100)
        parts.append("yüz" if head == 1 else f"{_ONES[head]} yüz")
    if n >= 10:
        head, n = divmod(n, 10)
        parts.append(_TENS[head])
    if n > 0:
        parts.append(_ONES[n])
    return " ".join(parts)


def last_vowel(word: str) -> str:
    for ch in reversed(word.lower()):
        if ch in _VOWELS:
            return ch
    return "e"


def harmony_i(word: str) -> str:
    """Four-way harmony vowel (ı i u ü) for the last vowel of `word`."""
    v = last_vowel(word)
    if v in _BACK:
        return "u" if v in _ROUND else "ı"
    return "ü" if v in _ROUND else "i"


def harmony_a(word: str) -> str:
    """Two-way harmony vowel (a e)."""
    return "a" if last_vowel(word) in _BACK else "e"


def soften(word: str) -> str:
    """Final consonant softening before a vowel-initial suffix: dört -> dörd, çeyrek -> çeyreğ."""
    if word.endswith("dört"):
        return word[:-1] + "d"
    if word.endswith("k") and sum(ch in _VOWELS for ch in word) >= 2:
        return word[:-1] + "ğ"
    return word


def attach(word: str, suffix: str) -> str:
    """Join a spoken word and the suffix the writer attached to the numeral or abbreviation.

    The writer harmonised the suffix against what they wrote (3'te -> üçte works
    as is), but a buffer consonant may be wrong for the spoken word: yarım + sı
    -> yarımı, kilometre + i -> kilometreyi.
    """
    if not suffix:
        return word
    ends_in_vowel = word[-1] in _VOWELS
    if suffix[0] in "sy" and len(suffix) > 1 and suffix[1] in _VOWELS and not ends_in_vowel:
        suffix = suffix[1:]  # drop the buffer consonant after a consonant
    elif suffix[0] in _VOWELS and ends_in_vowel:
        suffix = "y" + suffix  # insert a buffer consonant between two vowels
    if suffix[0] in _VOWELS:
        word = soften(word)
    return word + suffix


def reharmonize(word: str, suffix: str) -> str:
    """Re-harmonise a suffix written against an abbreviation (TL'ye, 1/4'ü) for the spoken word (liraya, çeyreği)."""
    if not suffix:
        return suffix
    two, four = harmony_a(word), harmony_i(word)
    return "".join(two if ch in "ae" else four if ch in "ıiuü" else ch for ch in suffix)


def ordinal(n: int) -> str:
    """üçüncü, dördüncü, yirmi birinci."""
    words = cardinal(n)
    head, _, last = words.rpartition(" ")
    v = harmony_i(last)
    if last[-1] in _VOWELS:
        last = last + "nc" + v
    else:
        last = soften(last) + v + "nc" + v
    return (head + " " if head else "") + last


def locative(word: str) -> str:
    """üç -> üçte, dört -> dörtte, on -> onda, beş -> beşte."""
    a = harmony_a(word)
    consonant = "t" if word[-1] in _VOICELESS else "d"
    return word + consonant + a


def digits(s: str) -> str:
    out = []
    for ch in s:
        if ch.isdigit():
            out.append(_ONES[int(ch)])
        elif ch == "+":
            out.append("artı")
    return " ".join(out)


def decimal(whole: str, frac: str | None) -> str:
    text = cardinal(int(whole.replace(".", "")))
    if frac:
        text += " virgül " + (cardinal(int(frac)) if not frac.startswith("0") else digits(frac))
    return text
