"""speechready as a Pipecat text transform.

Pipecat (1.14+) runs a TTS service's `text_transforms` on each aggregated piece
of LLM text, normally one sentence, right before synthesis. A transform is an
async `(text, text_type) -> text`. Register this one on the TTS service, not on
`LLMTextProcessor`, so provider syntax such as SSML reaches the voice only and
the conversation context keeps the text as the LLM wrote it.

    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
    from speechready.integrations.pipecat import text_transform

    tts = ElevenLabsTTSService(
        ...,
        text_transforms=[("*", text_transform(provider="elevenlabs", model="eleven_turbo_v2_5"))],
    )

Use it with sentence aggregation (Pipecat's default). In token mode the
transform would see fragments, so it passes `token` and `word` text through
unchanged. A fenced code block that Pipecat's aggregator splits across pieces
is held back until its closing fence arrives and then handled as one block.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from ..clean import Options
from ..lexicon import Lexicon
from ..pipeline import prepare
from ..profiles import Profile

_FENCE_LINE = re.compile(r"^\s*(```|~~~)", re.MULTILINE)
_MAX_HELD = 8000  # characters of an unclosed fence to hold before giving up on it

#: Text types the transform leaves alone: fragments and non-speech markers.
PASS_THROUGH = frozenset({"token", "word", "expression_sound", "expression_pause"})


def text_transform(
    *,
    provider: str | None = None,
    model: str | None = None,
    profile: Profile | None = None,
    locale: str = "en-US",
    options: Options | None = None,
    lexicon: Lexicon | str | Path | None = None,
    pass_through: frozenset[str] | set[str] = PASS_THROUGH,
) -> Callable[[str, str], Awaitable[str]]:
    """Build a transform for a TTS service's `text_transforms=[("*", ...)]`.

    The arguments are those of `prepare`. `pass_through` names the Pipecat text
    types returned unchanged. Leading and trailing whitespace of each piece is
    kept, since Pipecat uses it for word-by-word streaming. A piece that
    becomes empty (a dropped code block) returns "" and Pipecat skips it.
    """
    lex = Lexicon.load(lexicon) if isinstance(lexicon, (str, Path)) else lexicon
    held: list[str] = []  # pieces of a fenced block still waiting for its closing fence

    def _spoken(piece: str) -> str:
        return prepare(
            piece, provider=provider, model=model, profile=profile, locale=locale, options=options, lexicon=lex
        ).text

    async def transform(text: str, text_type: str = "sentence") -> str:
        if str(text_type) in pass_through:
            return text
        body = text.strip()
        if not body:
            return text
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()) :]
        if held:
            held.append(body)
            unclosed = len(_FENCE_LINE.findall("\n".join(held))) % 2 == 1
            if unclosed and sum(map(len, held)) <= _MAX_HELD:
                return ""
            body, held[:] = "\n".join(held), []
        elif len(_FENCE_LINE.findall(body)) % 2 == 1:
            held.append(body)
            return ""
        spoken = _spoken(body)
        return lead + spoken + trail if spoken else ""

    return transform
