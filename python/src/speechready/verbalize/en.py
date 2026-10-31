"""English verbalization rules, in the order they run."""

from __future__ import annotations

import re

from . import Rule, option
from .numbers_en import cardinal, decimal, digits, ordinal, year

_MONTHS = [
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
]
_DAY_FIRST_LOCALES = {"en-GB", "en-AU", "en-NZ", "en-IE", "en-IN", "en-ZA"}


def _day_first(locale: str) -> bool:
    return locale in _DAY_FIRST_LOCALES


def _date_words(y: int, m: int, d: int) -> str | None:
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    if y < 100:
        y += 2000 if y < 70 else 1900
    return f"{_MONTHS[m - 1]} {ordinal(d)}, {year(y)}"


# --- dates -----------------------------------------------------------------------


def _date_iso(m: re.Match[str], locale: str) -> str | None:
    return _date_words(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _date_slash(m: re.Match[str], locale: str) -> str | None:
    a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if _day_first(locale):
        return _date_words(y, b, a)
    return _date_words(y, a, b)


def _date_dot(m: re.Match[str], locale: str) -> str | None:
    return _date_words(int(m.group(3)), int(m.group(2)), int(m.group(1)))


# --- digit strings ---------------------------------------------------------------


def _digit_groups(m: re.Match[str], locale: str) -> str | None:
    raw = m.group(0)
    count = sum(ch.isdigit() for ch in raw)
    if count < 7 or count > 16:
        return None
    groups = [g for g in re.split(r"[\s.\-()]+", raw) if g]
    return ", ".join(digits(g) for g in groups)


def _long_digits(m: re.Match[str], locale: str) -> str | None:
    return digits(m.group(0))


# --- time ----------------------------------------------------------------------------


def _time(m: re.Match[str], locale: str) -> str | None:
    hour, minute, suffix = m.group(1), m.group(2), m.group(3)
    if suffix:
        return None  # "2:30 pm" is read correctly as it stands
    h = int(hour)
    if h >= 13:
        return f"{h - 12}:{minute} PM"
    if h == 0:
        return f"12:{minute} AM"
    if hour.startswith("0"):
        return f"{h}:{minute} AM"
    return None


# --- currency --------------------------------------------------------------------------

_CURRENCY = {
    "$": ("dollar", "dollars", "cent", "cents"),
    "€": ("euro", "euros", "cent", "cents"),
    "£": ("pound", "pounds", "penny", "pence"),
    "¥": ("yen", "yen", None, None),
    "₺": ("lira", "lira", "kuruş", "kuruş"),
    "USD": ("dollar", "dollars", "cent", "cents"),
    "EUR": ("euro", "euros", "cent", "cents"),
    "GBP": ("pound", "pounds", "penny", "pence"),
    "TRY": ("lira", "lira", "kuruş", "kuruş"),
    "TL": ("lira", "lira", "kuruş", "kuruş"),
}
_MAGNITUDE = {"k": "thousand", "m": "million", "bn": "billion", "b": "billion", "thousand": "thousand", "million": "million", "billion": "billion"}


def _money_words(symbol: str, whole: str, frac: str | None, magnitude: str | None) -> str:
    one, many, cent_one, cent_many = _CURRENCY[symbol]
    amount = int(whole.replace(",", ""))
    if magnitude:
        return f"{decimal(whole, frac)} {_MAGNITUDE[magnitude.lower()]} {many}"
    if frac is not None and cent_one:
        cents = int(frac.ljust(2, "0")[:2])
        main = "" if amount == 0 else f"{cardinal(amount)} {one if amount == 1 else many}"
        if cents == 0:
            return main or f"zero {many}"
        tail = f"{cardinal(cents)} {cent_one if cents == 1 else cent_many}"
        return f"{main} and {tail}" if main else tail
    if frac is not None:
        return f"{decimal(whole, frac)} {many}"
    return f"{cardinal(amount)} {one if amount == 1 else many}"


def _currency_range(m: re.Match[str], locale: str) -> str | None:
    symbol = m.group(1)
    _, many, _, _ = _CURRENCY[symbol]
    return f"{cardinal(int(m.group(2).replace(',', '')))} to {cardinal(int(m.group(3).replace(',', '')))} {many}"


def _currency_prefix(m: re.Match[str], locale: str) -> str | None:
    return _money_words(m.group(1), m.group(2), m.group(3), m.group(4))


def _currency_code(m: re.Match[str], locale: str) -> str | None:
    return _money_words(m.group(3).upper(), m.group(1), m.group(2), None)


# --- percent, units, fractions, ranges ----------------------------------------------------


def _percent(m: re.Match[str], locale: str) -> str | None:
    return f"{m.group(1)} percent"


_UNITS = {
    "km/h": ("kilometer per hour", "kilometers per hour"),
    "km": ("kilometer", "kilometers"),
    "cm": ("centimeter", "centimeters"),
    "mm": ("millimeter", "millimeters"),
    "kg": ("kilogram", "kilograms"),
    "mg": ("milligram", "milligrams"),
    "lbs": ("pound", "pounds"),
    "lb": ("pound", "pounds"),
    "oz": ("ounce", "ounces"),
    "mph": ("mile per hour", "miles per hour"),
    "mi": ("mile", "miles"),
    "ft": ("foot", "feet"),
    "GB": ("gigabyte", "gigabytes"),
    "MB": ("megabyte", "megabytes"),
    "KB": ("kilobyte", "kilobytes"),
    "TB": ("terabyte", "terabytes"),
    "ms": ("millisecond", "milliseconds"),
    "min": ("minute", "minutes"),
    "hrs": ("hour", "hours"),
    "hr": ("hour", "hours"),
    "kWh": ("kilowatt hour", "kilowatt hours"),
    "kHz": ("kilohertz", "kilohertz"),
    "MHz": ("megahertz", "megahertz"),
    "GHz": ("gigahertz", "gigahertz"),
    "Hz": ("hertz", "hertz"),
    "fps": ("frame per second", "frames per second"),
    "°C": ("degree Celsius", "degrees Celsius"),
    "°F": ("degree Fahrenheit", "degrees Fahrenheit"),
    "°": ("degree", "degrees"),
}
_UNIT_ALTERNATION = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))


def _unit(m: re.Match[str], locale: str) -> str | None:
    number, unit = m.group(1), m.group(2)
    one, many = _UNITS[unit]
    is_one = number in ("1", "1.0")
    return f"{number} {one if is_one else many}"


_FRACTIONS = {2: ("half", "halves"), 3: ("third", "thirds"), 4: ("quarter", "quarters"),
              5: ("fifth", "fifths"), 8: ("eighth", "eighths"), 10: ("tenth", "tenths")}


def _fraction(m: re.Match[str], locale: str) -> str | None:
    num, den = int(m.group(1)), int(m.group(2))
    if num >= den:
        return None
    if option("fractions", "spoken") == "division":
        return f"{cardinal(num)} over {cardinal(den)}"
    if den not in _FRACTIONS:
        return None
    one, many = _FRACTIONS[den]
    return f"{cardinal(num)} {one if num == 1 else many}"


def _range(m: re.Match[str], locale: str) -> str | None:
    a, b = m.group(1), m.group(2)
    short = len(a.replace(".", "")) <= 3 and len(b.replace(".", "")) <= 3
    years = re.fullmatch(r"(19|20)\d\d", a) and re.fullmatch(r"(19|20)\d\d", b)
    if not (short or years):
        return None
    return f"{a} to {b}"


# --- years and ordinals -----------------------------------------------------------------------


def _year_in_context(m: re.Match[str], locale: str) -> str | None:
    return f"{m.group(1)} {year(int(m.group(2)))}"


def _decade(m: re.Match[str], locale: str) -> str | None:
    words = year(int(m.group(1)))
    head, _, last = words.rpartition(" ")
    plural = last[:-1] + "ies" if last.endswith("y") else last + "s"
    return (head + " " if head else "") + plural


def _ordinal(m: re.Match[str], locale: str) -> str | None:
    return ordinal(int(m.group(1)))


# --- alphanumeric identifiers ------------------------------------------------------------------

_VOWELS = set("AEIOUY")


def _alnum(m: re.Match[str], locale: str) -> str | None:
    token = m.group(0)
    if len(token.replace("-", "")) < 4:
        return None
    out: list[str] = []
    runs = re.findall(r"[A-Z]+|\d+", token)
    for run in runs:
        if run.isdigit():
            out.append(cardinal(int(run)) if len(runs) == 2 and len(run) <= 2 else digits(run))
        elif len(run) >= 3 and _VOWELS & set(run):
            out.append(run)
        else:
            out.append(" ".join(run))
    return " ".join(out)


# a separator inside a phone number: space, dash, or a dot that is not followed by whitespace
_SEP = r"(?:[ \-]|\.(?!\s))"


def _time_range(m: re.Match[str], locale: str) -> str | None:
    return f"{m.group(1)} to {m.group(2)}"


_PER = {"mo": "month", "month": "month", "yr": "year", "year": "year", "hr": "hour", "hour": "hour", "min": "minute", "minute": "minute", "day": "day", "week": "week", "wk": "week"}

RULES: list[Rule] = [
    Rule("verbalize.date.iso", re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), _date_iso, "ISO date read as month, day, year"),
    Rule("verbalize.date.slash", re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\b"), _date_slash, "numeric date read in the locale's order"),
    Rule("verbalize.date.dot", re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b"), _date_dot, "dotted date read as day, month, year"),
    Rule(
        "verbalize.phone",
        re.compile(rf"(?<![\w.])(?:\+?\d{{1,3}}{_SEP})?(?:\(\d{{2,4}}\)[ \-]?|\d{{2,4}}{_SEP})(?:\d{{2,4}}{_SEP}){{1,4}}\d{{2,4}}(?![\w\-]|[.,]\d)"),
        _digit_groups,
        "digit groups read digit by digit with a pause between groups",
    ),
    Rule("verbalize.number_sign", re.compile(r"#(?=\d)"), lambda m, loc: "number ", "number sign read as a word"),
    Rule("verbalize.digits.long", re.compile(r"(?<![\w.,])\d{7,}(?![\w]|[.,]\d)"), _long_digits, "long digit string read digit by digit"),
    Rule("verbalize.time.range", re.compile(r"\b(\d{1,2}:\d{2})\s?[-–]\s?(\d{1,2}:\d{2})\b"), _time_range, "time range read with 'to'"),
    Rule("verbalize.time", re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b(?!:)(?:\s?(am|pm|AM|PM|a\.m\.|p\.m\.))?"), _time, "24-hour time read as 12-hour"),
    Rule("verbalize.currency.range", re.compile(r"([$€£¥₺])\s?(\d[\d,]*)\s?[-–]\s?[$€£¥₺]?\s?(\d[\d,]*)(?![\d]|[.,]\d)"), _currency_range, "currency range read as words"),
    Rule(
        "verbalize.currency",
        re.compile(r"([$€£¥₺])\s?(\d[\d,]*)(?:\.(\d{1,2}))?\s?(k|K|m|M|bn|B|thousand|million|billion)?(?![\w]|[.,]\d)"),
        _currency_prefix,
        "currency amount read as words",
    ),
    Rule("verbalize.currency.code", re.compile(r"(?<![\w.])(\d[\d,]*)(?:\.(\d{1,2}))?\s?(USD|EUR|GBP|TRY|TL)\b"), _currency_code, "currency code read as words"),
    Rule(
        "verbalize.per",
        re.compile(r"\b(dollars?|cents?|euros?|pounds?|\d)/(mo|month|yr|year|hr|hour|min|minute|day|week|wk)\b"),
        lambda m, loc: f"{m.group(1)} per {_PER[m.group(2)]}",
        "slash before a period read as 'per'",
    ),
    Rule("verbalize.percent", re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?%|%\s?(\d+(?:\.\d+)?)"), lambda m, loc: f"{m.group(1) or m.group(2)} percent", "percent sign read as a word"),
    Rule("verbalize.unit", re.compile(rf"(?<![\w.])(\d+(?:\.\d+)?)\s?({_UNIT_ALTERNATION})(?![\w/])"), _unit, "unit abbreviation read as a word"),
    Rule("verbalize.fraction", re.compile(r"(?<![\d/])([1-9])/([2-9]|10)(?![\d/])"), _fraction, "fraction read as words"),
    Rule("verbalize.range", re.compile(r"(?<![\w.,\-/:])(\d+(?:\.\d+)?)\s?[-–]\s?(\d+(?:\.\d+)?)(?![\w\-/:]|[.,]\d)"), _range, "number range read with 'to'"),
    Rule("verbalize.year", re.compile(r"\b(in|In|since|Since|by|from|until|till|before|after|during|circa|year|est\.|©)\s+(1[1-9]\d\d|20\d\d)\b(?![\w.,]?\d)"), _year_in_context, "year read as a year"),
    Rule("verbalize.decade", re.compile(r"\b(1[1-9]\d0|20\d0)s\b"), _decade, "decade read as a year"),
    Rule("verbalize.ordinal", re.compile(r"\b(\d{1,4})(?:st|nd|rd|th)\b"), _ordinal, "ordinal read as words"),
    Rule("verbalize.minus", re.compile(r"(?<![\w.)\-–])[-–](?=\d)"), lambda m, loc: "minus ", "leading minus read as a word"),
    Rule("verbalize.alnum", re.compile(r"\b(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9]+(?:-[A-Z0-9]+)*\b"), _alnum, "identifier spelled out"),
]
