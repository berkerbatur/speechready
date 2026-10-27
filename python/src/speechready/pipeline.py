"""The pipeline: clean -> verbalize -> compile -> chunk, with a change log."""

from __future__ import annotations

from dataclasses import dataclass, field

from .changes import Change, Recorder
from .chunk import pack, split_sentences
from .clean import CleanOptions, clean
from .compile import compile_text
from .intents import Intent, extract, SENTINEL_CLOSE, SENTINEL_OPEN
import re
from .profiles import Profile, resolve_profile
from .verbalize import verbalize


@dataclass
class Prepared:
    text: str
    chunks: list[str]
    changes: list[Change] = field(default_factory=list)
    profile: Profile | None = None
    locale: str = "en-US"

    def __str__(self) -> str:
        return self.text


def prepare(
    text: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    profile: Profile | None = None,
    locale: str = "en-US",
    limit: int | None = None,
    options: CleanOptions | None = None,
) -> Prepared:
    """Prepare `text` for the given provider and model.

    Returns the full compiled text, the request-sized chunks, and every change made.
    `limit` overrides the profile's request limit (None = use the profile's).
    """
    prof = profile or resolve_profile(provider, model)
    rec = Recorder()

    work, intents = extract(text)
    work = clean(work, options, rec)
    work, intents = extract(work, intents)
    work = verbalize(work, locale, rec)
    work = compile_text(work, intents, prof, rec)

    max_size = limit if limit is not None else prof.limit_for(model)
    sentences = split_sentences(work, locale)
    chunks = pack(sentences, max_size, prof.limit_unit, joiner=" ")
    return Prepared(text=work, chunks=chunks, changes=_readable(rec.changes, intents), profile=prof, locale=locale)


_SENTINEL = re.compile(f"{SENTINEL_OPEN}(\\d+){SENTINEL_CLOSE}")


def _intent_tag(intent: Intent) -> str:
    if intent.kind == "pause":
        return f"[pause {intent.ms}ms]"
    return f"[{intent.kind} {intent.text}]"


def _readable(changes: list[Change], intents: list[Intent]) -> list[Change]:
    """Show intents in the change log as the tags the developer wrote, not as sentinels."""

    def fix(text: str) -> str:
        return _SENTINEL.sub(lambda m: _intent_tag(intents[int(m.group(1))]), text)

    return [Change(c.stage, c.rule, fix(c.before), fix(c.after), c.note) for c in changes]


__all__ = ["Prepared", "prepare"]
