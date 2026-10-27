"""Turkish verbalization rules, in the order they run.

Turkish text carries case and possessive suffixes on numerals with an
apostrophe (3'te, 1990'da, %50'si) and uses a dot for thousands and a comma
for decimals. Foreign TTS models get all of these wrong, so they are the
first things this module rewrites.
"""

from __future__ import annotations

import re

from . import Rule
from .numbers_tr import attach, cardinal, decimal, digits, locative, ordinal, reharmonize

_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
_APOS = "['’]"
_LOWER = "a-zçğıöşü"
_UPPER = "A-ZÇĞİÖŞÜ"


def _date_words(y: int, m: int, d: int, suffix: str = "") -> str | None:
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    if y < 100:
        y += 2000 if y < 70 else 1900
    return f"{cardinal(d)} {_MONTHS[m - 1]} {attach(cardinal(y), suffix)}"


def _date_dmy(m: re.Match[str], locale: str) -> str | None:
    return _date_words(int(m.group(3)), int(m.group(2)), int(m.group(1)), m.group(4) or "")


def _date_iso(m: re.Match[str], locale: str) -> str | None:
    return _date_words(int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) or "")


def _digit_groups(m: re.Match[str], locale: str) -> str | None:
    raw, suffix = m.group(1), m.group(2) or ""
    count = sum(ch.isdigit() for ch in raw)
    if count < 7 or count > 16:
        return None
    groups = [g for g in re.split(r"[\s.\-()]+", raw) if g]
    return attach(", ".join(digits(g) for g in groups), suffix)


def _time_words(hh: str, mm: str) -> str:
    h, minute = int(hh), int(mm)
    hour = cardinal(h)
    if minute == 0:
        return f"{hour} sıfır sıfır"
    return f"{hour} {cardinal(minute) if mm[0] != '0' else 'sıfır ' + cardinal(minute)}"


def _time(m: re.Match[str], locale: str) -> str | None:
    words = _time_words(m.group(1), m.group(2))
    return attach(words, m.group(3) or "")


def _time_range(m: re.Match[str], locale: str) -> str | None:
    return f"{_time_words(m.group(1), m.group(2))} ile {_time_words(m.group(3), m.group(4))}"


def _currency_postfix(m: re.Match[str], locale: str) -> str | None:
    whole, _, frac = m.group(1).partition(",")
    scale = f" {m.group(2)}" if m.group(2) else ""
    unit, _ = _CURRENCY[m.group(3)]
    return f"{decimal(whole, frac or None)}{scale} {attach(unit, reharmonize(unit, m.group(4) or ''))}"


_CURRENCY = {
    "₺": ("lira", "kuruş"), "TL": ("lira", "kuruş"), "TRY": ("lira", "kuruş"),
    "$": ("dolar", "sent"), "USD": ("dolar", "sent"),
    "€": ("avro", "sent"), "EUR": ("avro", "sent"),
    "£": ("sterlin", "peni"), "GBP": ("sterlin", "peni"),
}


def _money(symbol: str, whole: str, frac: str | None, suffix: str = "") -> str:
    unit, sub = _CURRENCY[symbol]
    amount = cardinal(int(whole.replace(".", "")))
    if frac:
        cents = int(frac.ljust(2, "0")[:2])
        if cents:
            return f"{amount} {unit} {cardinal(cents)} {attach(sub, reharmonize(sub, suffix))}"
    return f"{amount} {attach(unit, reharmonize(unit, suffix))}"


def _currency_prefix(m: re.Match[str], locale: str) -> str | None:
    return _money(m.group(1), m.group(2), m.group(3), m.group(4) or "")


def _currency_suffix(m: re.Match[str], locale: str) -> str | None:
    return _money(m.group(3).upper(), m.group(1), m.group(2), m.group(4) or "")


def _percent(m: re.Match[str], locale: str) -> str | None:
    number = m.group(1) or m.group(3)
    suffix = m.group(2) or m.group(4) or ""
    whole, _, frac = number.partition(",")
    words = decimal(whole, frac or None)
    return "yüzde " + attach(words, suffix)


_UNITS = {
    "km/sa": "kilometre", "km/s": "kilometre", "km": "kilometre", "cm": "santimetre", "mm": "milimetre",
    "kg": "kilogram", "mg": "miligram", "GB": "gigabayt", "MB": "megabayt", "KB": "kilobayt", "TB": "terabayt",
    "ms": "milisaniye", "sn": "saniye", "dk": "dakika", "sa": "saat", "°C": "derece", "°": "derece",
}
_UNIT_ALTERNATION = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))


def _unit(m: re.Match[str], locale: str) -> str | None:
    number, unit, suffix = m.group(1), m.group(2), m.group(3) or ""
    word = _UNITS[unit]
    if unit in ("km/sa", "km/s"):
        return f"saatte {number} {attach(word, reharmonize(word, suffix))}"
    return f"{number} {attach(word, reharmonize(word, suffix))}"


_FRACTION_NAMES = {(1, 2): "yarım", (1, 4): "çeyrek"}


def _fraction(m: re.Match[str], locale: str) -> str | None:
    num, den, suffix = int(m.group(1)), int(m.group(2)), m.group(3) or ""
    if num >= den:
        return None
    if (num, den) in _FRACTION_NAMES:
        word = _FRACTION_NAMES[(num, den)]
        return attach(word, reharmonize(word, suffix))
    return f"{locative(cardinal(den))} {attach(cardinal(num), suffix)}"


def _range(m: re.Match[str], locale: str) -> str | None:
    a, b = m.group(1), m.group(2)
    if len(a) > 4 or len(b) > 4:
        return None
    return f"{a} ila {b}"


def _thousands(m: re.Match[str], locale: str) -> str | None:
    whole, frac, suffix = m.group(1), m.group(2), m.group(3) or ""
    return attach(decimal(whole, frac), suffix)


def _decimal_comma(m: re.Match[str], locale: str) -> str | None:
    return attach(decimal(m.group(1), m.group(2)), m.group(3) or "")


def _suffixed_number(m: re.Match[str], locale: str) -> str | None:
    n, suffix = int(m.group(1)), m.group(2)
    if re.fullmatch(r"(?:[ıiuü]nc[ıiuü]|nc[ıiuü])", suffix):
        return ordinal(n)
    return attach(cardinal(n), suffix)


def _ordinal_dot(m: re.Match[str], locale: str) -> str | None:
    return ordinal(int(m.group(1)))


_ABBREVIATIONS = {
    "vb": "ve benzeri", "vs": "vesaire", "vd": "ve diğerleri", "örn": "örneğin", "bkz": "bakınız",
    "Dr": "Doktor", "Prof": "Profesör", "Doç": "Doçent", "Av": "Avukat", "Sn": "Sayın",
    "No": "numara", "no": "numara", "Tel": "telefon", "tel": "telefon", "yy": "yüzyıl",
    "Cad": "Caddesi", "Sok": "Sokak", "Mah": "Mahallesi", "Apt": "Apartmanı", "Bul": "Bulvarı",
    "T.C": "Türkiye Cumhuriyeti", "Ltd": "Limited", "Şti": "Şirketi", "A.Ş": "Anonim Şirketi",
    "Üniv": "Üniversitesi", "Fak": "Fakültesi", "Böl": "Bölümü", "Hst": "Hastanesi", "Müh": "Mühendisi",
    "Alb": "Albay", "Yzb": "Yüzbaşı", "Bşk": "Başkanı", "Yrd": "Yardımcı", "Uzm": "Uzman", "Öğr": "Öğretim",
}
_ABBR_ALTERNATION = "|".join(re.escape(a) for a in sorted(_ABBREVIATIONS, key=len, reverse=True))


def _abbreviation(m: re.Match[str], locale: str) -> str | None:
    return _ABBREVIATIONS[m.group(1)]


_VOWELS_UP = set("AEIİOÖUÜ")


def _alnum(m: re.Match[str], locale: str) -> str | None:
    token = m.group(0)
    if len(token.replace("-", "")) < 4:
        return None
    runs = re.findall(rf"[{_UPPER}]+|\d+", token)
    out = []
    for run in runs:
        if run.isdigit():
            out.append(cardinal(int(run)) if len(runs) == 2 and len(run) <= 2 else digits(run))
        elif len(run) >= 3 and _VOWELS_UP & set(run):
            out.append(run)
        else:
            out.append(" ".join(run))
    return " ".join(out)


_SEP = r"(?:[ \-]|\.(?!\s))"
_SUFFIX = rf"(?:{_APOS}([{_LOWER}]+))?"

RULES: list[Rule] = [
    Rule("verbalize.abbreviation", re.compile(rf"(?<![\w.])({_ABBR_ALTERNATION})\.(?![{_LOWER}{_UPPER}])"), _abbreviation, "abbreviation read in full"),
    Rule("verbalize.date.dmy", re.compile(rf"\b(\d{{1,2}})[./](\d{{1,2}})[./](\d{{4}}|\d{{2}})\b{_SUFFIX}"), _date_dmy, "date read as day, month name, year"),
    Rule("verbalize.date.iso", re.compile(rf"\b(\d{{4}})-(\d{{2}})-(\d{{2}})\b{_SUFFIX}"), _date_iso, "ISO date read as day, month name, year"),
    Rule(
        "verbalize.phone",
        re.compile(rf"(?<![\w.])((?:\+?\d{{1,3}}{_SEP})?(?:\(\d{{2,4}}\)[ \-]?|\d{{2,4}}{_SEP})(?:\d{{2,4}}{_SEP}){{1,4}}\d{{2,4}}){_SUFFIX}(?![\w\-]|[.,]\d)"),
        _digit_groups,
        "digit groups read digit by digit with a pause between groups",
    ),
    Rule("verbalize.digits.long", re.compile(r"(?<![\w.,])\d{7,}(?![\w]|[.,]\d)"), lambda m, loc: digits(m.group(0)), "long digit string read digit by digit"),
    Rule("verbalize.time.range", re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\s?[-–]\s?([01]?\d|2[0-3]):([0-5]\d)\b"), _time_range, "time range read with 'ile'"),
    Rule("verbalize.time", re.compile(rf"\b([01]?\d|2[0-3]):([0-5]\d)\b(?!:){_SUFFIX}"), _time, "clock time read as hours and minutes"),
    Rule("verbalize.currency.postfix", re.compile(rf"(?<![\w.,])(\d+(?:,\d+)?)\s?(bin|milyon|milyar)?\s?([₺$€£]){_SUFFIX}(?![\w])"), _currency_postfix, "currency symbol after the amount read as words"),
    Rule("verbalize.currency", re.compile(rf"([₺$€£])\s?(\d{{1,3}}(?:\.\d{{3}})*|\d+)(?:,(\d{{1,2}}))?{_SUFFIX}(?![\w]|[.,]\d)"), _currency_prefix, "currency amount read as words"),
    Rule("verbalize.currency.code", re.compile(rf"(?<![\w.,])(\d{{1,3}}(?:\.\d{{3}})*|\d+)(?:,(\d{{1,2}}))?\s?(TL|TRY|USD|EUR|GBP)\b{_SUFFIX}"), _currency_suffix, "currency code read as words"),
    Rule("verbalize.percent", re.compile(rf"%\s?(\d+(?:,\d+)?){_SUFFIX}|(?<![\w.])(\d+(?:,\d+)?)\s?%{_SUFFIX}"), _percent, "percent read as 'yüzde'"),
    Rule("verbalize.unit", re.compile(rf"(?<![\w.,])(\d+(?:,\d+)?)\s?({_UNIT_ALTERNATION}){_SUFFIX}(?![\w/])"), _unit, "unit abbreviation read as a word"),
    Rule("verbalize.fraction", re.compile(rf"(?<![\d/])([1-9])/([2-9]|10){_SUFFIX}(?![\d/])"), _fraction, "fraction read as words"),
    Rule("verbalize.range", re.compile(r"(?<![\w.,\-/:])(\d+)\s?[-–]\s?(\d+)(?![\w\-/:]|[.,]\d)"), _range, "number range read with 'ila'"),
    Rule("verbalize.thousands", re.compile(rf"(?<![\w.,])(\d{{1,3}}(?:\.\d{{3}})+)(?:,(\d+))?{_SUFFIX}(?![\w]|[.,]\d)"), _thousands, "dotted thousands read as a number, not a decimal"),
    Rule("verbalize.decimal", re.compile(rf"(?<![\w.,])(\d+),(\d+){_SUFFIX}(?![\w]|[.,]\d)"), _decimal_comma, "decimal comma read as 'virgül'"),
    Rule("verbalize.suffix", re.compile(rf"\b(\d+){_APOS}([{_LOWER}]+)\b"), _suffixed_number, "numeral with a suffix read as one word"),
    Rule("verbalize.ordinal", re.compile(rf"\b(\d{{1,3}})\.(?=\s+[{_LOWER}])"), _ordinal_dot, "numeral with a dot before a lowercase word read as an ordinal"),
    Rule("verbalize.minus", re.compile(r"(?<![\w.)\-–])[-–](?=\d)"), lambda m, loc: "eksi ", "leading minus read as a word"),
    Rule("verbalize.alnum", re.compile(rf"\b(?=[{_UPPER}0-9-]*\d)(?=[{_UPPER}0-9-]*[{_UPPER}])[{_UPPER}0-9]+(?:-[{_UPPER}0-9]+)*\b"), _alnum, "identifier spelled out"),
]
