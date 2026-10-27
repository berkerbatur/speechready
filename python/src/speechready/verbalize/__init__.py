"""Stage 2: verbalize. Rewrite only the tokens a TTS model is likely to misread.

Each language has an ordered list of rules. A rule is a regex and a function
that returns the spoken form; it fires only on the pattern, so ordinary prose
and ordinary numbers are left for the model, which reads them well.
Sentinels from the intent stage are never touched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from ..changes import Recorder
from ..intents import SENTINEL_CLOSE, SENTINEL_OPEN

STAGE = "verbalize"


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: re.Pattern[str]
    render: Callable[[re.Match[str], str], str | None]  # (match, locale) -> replacement or None to skip
    note: str = ""


_SENTINEL = re.compile(f"{SENTINEL_OPEN}\\d+{SENTINEL_CLOSE}")


def _rules_for(locale: str) -> list[Rule]:
    lang = (locale or "en").split("-")[0].split("_")[0].lower()
    if lang == "en":
        from . import en

        return en.RULES
    if lang == "tr":
        try:
            from . import tr  # noqa: F401

            return tr.RULES
        except ImportError:
            return []
    return []


def verbalize(text: str, locale: str = "en-US", recorder: Recorder | None = None) -> str:
    rec = recorder or Recorder()
    rules = _rules_for(locale)
    if not rules:
        return text
    parts = _SENTINEL.split(text)
    sentinels = _SENTINEL.findall(text)
    out = []
    for i, segment in enumerate(parts):
        out.append(_apply(segment, rules, locale, rec))
        if i < len(sentinels):
            out.append(sentinels[i])
    return "".join(out)


def _apply(segment: str, rules: list[Rule], locale: str, rec: Recorder) -> str:
    for rule in rules:

        def repl(m: re.Match[str], rule=rule) -> str:
            new = rule.render(m, locale)
            if new is None or new == m.group(0):
                return m.group(0)
            rec.add(STAGE, rule.id, m.group(0), new, rule.note)
            return new

        segment = rule.pattern.sub(repl, segment)
    return segment


__all__ = ["Rule", "verbalize"]
