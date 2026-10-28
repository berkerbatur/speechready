"""Build the evaluation corpus from the shared spec fixtures plus the extra files in eval/corpus.

A line has: id, locale, cls (the problem class), raw (what a developer would send
without the library), intended (the words a listener should hear).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec" / "fixtures"
EXTRA = ROOT / "eval" / "corpus"

# fixture files whose inputs are realistic things people send to TTS
_FIXTURE_FILES = ("verbalize-", "clean-", "pipeline-", "lexicon")


@dataclass(frozen=True)
class Line:
    id: str
    locale: str
    cls: str
    raw: str
    intended: str


def _cls(stem: str, case_id: str) -> str:
    family = stem.split("-", 1)[-1] if "-" in stem else stem
    return f"{family}/{case_id.split('-')[0]}"


def from_fixtures(locales: tuple[str, ...] = ("en", "tr")) -> list[Line]:
    lines: list[Line] = []
    for lang in locales:
        for path in sorted((SPEC / lang).glob("*.yaml")):
            if not path.stem.startswith(_FIXTURE_FILES):
                continue
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            locale = doc.get("locale", "en-US")
            for case in doc.get("cases", []):
                if case.get("skip") or "lexicon" in case or "stream" in case or "options" in case or not isinstance(case.get("input"), str):
                    continue  # option-dependent expectations are skipped: the eval runs with default options
                expect = case["expect"]
                intended = " ".join(expect) if isinstance(expect, list) else expect
                lines.append(Line(f"{lang}/{path.stem}/{case['id']}", case.get("locale", locale), _cls(path.stem, case["id"]), case["input"], intended))
    return lines


def from_extra(locales: tuple[str, ...] = ("en", "tr")) -> list[Line]:
    lines: list[Line] = []
    for path in sorted(EXTRA.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        locale = doc.get("locale", "en-US")
        if locale.split("-")[0] not in locales:
            continue
        for case in doc.get("cases", []):
            lines.append(Line(f"{path.stem}/{case['id']}", locale, case.get("cls", doc.get("cls", path.stem)), case["input"], case.get("intended", case["input"])))
    return lines


def build(locales: tuple[str, ...] = ("en", "tr"), limit: int | None = None) -> list[Line]:
    lines = from_fixtures(locales) + from_extra(locales)
    return lines[:limit] if limit else lines
