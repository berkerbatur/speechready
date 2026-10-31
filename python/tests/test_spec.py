"""Run every fixture in ../spec/fixtures against the Python implementation."""

from pathlib import Path

import pytest
import yaml

from speechready import CleanOptions, Lexicon, Segmenter, clean, load_profile, pack, prepare, split_sentences
from speechready.verbalize import verbalize

SPEC = Path(__file__).resolve().parents[2] / "spec" / "fixtures"


def _cases():
    for path in sorted(SPEC.rglob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        for case in doc.get("cases", []):
            yield pytest.param(doc, case, id=f"{path.parent.name}/{path.stem}::{case['id']}")


def _run(doc: dict, case: dict):
    rule = case.get("rule", doc.get("rule", "pipeline"))
    locale = case.get("locale", doc.get("locale", "en-US"))
    opts = CleanOptions(**case["options"]) if "options" in case else None
    if rule.startswith("clean"):
        return clean(case["input"], opts)
    lexicon = Lexicon.from_entries(case["lexicon"], locale) if "lexicon" in case else None
    if rule == "lexicon.export":
        return lexicon.export(case["format"], case.get("alphabet", "ipa"))
    if rule.startswith("verbalize"):
        return verbalize(case["input"], locale, options=opts)
    if rule == "chunk.sentences":
        return split_sentences(case["input"], locale)
    if rule == "chunk.pack":
        return pack(split_sentences(case["input"], locale), case.get("limit"), case.get("unit", "chars"))
    if rule == "chunk.stream":
        seg = Segmenter(locale=locale, max_buffer=case.get("max_buffer"))
        out = []
        for piece in case["stream"]:
            out.extend(seg.push(piece))
        out.extend(seg.flush())
        return out
    profile = load_profile(case.get("profile", doc.get("profile", "plain")))
    result = prepare(case["input"], profile=profile, model=case.get("model"), locale=locale,
                     limit=case.get("limit"), options=opts, lexicon=lexicon)
    if rule == "pipeline.chunks":
        return result.chunks
    return result.text


@pytest.mark.parametrize("doc,case", list(_cases()))
def test_fixture(doc, case):
    if case.get("skip"):
        pytest.skip(case["skip"])
    assert _run(doc, case) == case["expect"]
