"""speechready as a LiveKit Agents text transform.

LiveKit Agents (1.8+) passes the LLM's text stream through `tts_text_transforms`
before synthesis. Each transform is `(AsyncIterable[str]) -> AsyncIterable[str]`.
This one segments the stream into sentences as they are confirmed, runs each
through `prepare`, and yields the result, so pauses, numbers, Markdown and
code blocks are handled on the way to the voice without a custom `tts_node`.

    from livekit.agents import AgentSession
    from speechready.integrations.livekit import text_transform

    session = AgentSession(
        ...,
        tts_text_transforms=[text_transform(provider="elevenlabs", model="eleven_turbo_v2_5")],
    )

Setting `tts_text_transforms` replaces LiveKit's defaults (`filter_markdown`,
`filter_emoji`); both are covered by the clean stage, so nothing is lost.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, Callable
from pathlib import Path

from ..chunk import Segmenter
from ..clean import Options
from ..lexicon import Lexicon
from ..pipeline import prepare
from ..profiles import Profile


def text_transform(
    *,
    provider: str | None = None,
    model: str | None = None,
    profile: Profile | None = None,
    locale: str = "en-US",
    options: Options | None = None,
    lexicon: Lexicon | str | Path | None = None,
    max_buffer: int | None = None,
) -> Callable[[AsyncIterable[str]], AsyncIterable[str]]:
    """Build a transform for `AgentSession(tts_text_transforms=[...])`.

    The arguments are those of `prepare`. `max_buffer` releases a long sentence
    at a clause boundary once the buffer holds that many characters, which bounds
    the time to first audio on run-on output.
    """
    lex = Lexicon.load(lexicon) if isinstance(lexicon, (str, Path)) else lexicon

    def _spoken(piece: str) -> str:
        return prepare(
            piece, provider=provider, model=model, profile=profile, locale=locale, options=options, lexicon=lex
        ).text

    async def transform(text: AsyncIterable[str]) -> AsyncIterable[str]:
        seg = Segmenter(locale=locale, max_buffer=max_buffer)
        async for chunk in text:
            for piece in seg.push(chunk):
                if spoken := _spoken(piece):
                    yield spoken + " "
        for piece in seg.flush():
            if spoken := _spoken(piece):
                yield spoken + " "

    return transform
