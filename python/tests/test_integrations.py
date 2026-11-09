import asyncio

from speechready import Options
from speechready.integrations import livekit, pipecat

TEXT = "**Step 1:** run `npm install`. [pause 1s] Then:\n```bash\nnpm start\n```\nRead https://example.com/docs. Done"


async def _tokens(text: str, size: int = 7):
    for i in range(0, len(text), size):
        yield text[i : i + size]


async def _collect(aiter):
    return [s async for s in aiter]


def test_livekit_stream_is_spoken_sentence_by_sentence():
    transform = livekit.text_transform(provider="elevenlabs", model="eleven_multilingual_v2")
    out = asyncio.run(_collect(transform(_tokens(TEXT))))
    assert out == [s + " " for s in ["Step 1: run npm install.", '<break time="1s" /> Then:', "npm start.", "Read example.com.", "Done."]]


def test_livekit_code_block_spoken_dropped_or_mentioned():
    joined = "".join(asyncio.run(_collect(livekit.text_transform(provider="openai")(_tokens(TEXT)))))
    assert "npm start." in joined  # a one-line block is spoken by default
    dropped = livekit.text_transform(provider="openai", options=Options(code_blocks="drop"))
    assert "npm start" not in "".join(asyncio.run(_collect(dropped(_tokens(TEXT)))))
    mention = livekit.text_transform(provider="openai", options=Options(code_blocks="mention"))
    assert "See the code block." in "".join(asyncio.run(_collect(mention(_tokens(TEXT)))))


def test_livekit_empty_stream():
    assert asyncio.run(_collect(livekit.text_transform()(_tokens("")))) == []


def test_pipecat_sentence_is_compiled_and_whitespace_kept():
    transform = pipecat.text_transform(provider="azure")
    out = asyncio.run(transform(" Wait [pause 500ms] for 3 items. ", "sentence"))
    assert out == ' Wait <break time="500ms" /> for 3 items. '


def test_pipecat_fragments_pass_through():
    transform = pipecat.text_transform(provider="azure")
    assert asyncio.run(transform("**bold", "token")) == "**bold"
    assert asyncio.run(transform("", "sentence")) == ""


def test_pipecat_fence_split_across_pieces_is_one_block():
    transform = pipecat.text_transform(provider="openai", options=Options(code_blocks="mention"))
    assert asyncio.run(transform("Run:\n```bash\nnpm start. Then", "sentence")) == ""
    assert asyncio.run(transform("echo done.\n```\nThat is all.", "sentence")) == "Run:\nSee the code block.\nThat is all."
    assert asyncio.run(transform("Next sentence.", "sentence")) == "Next sentence."


def test_pipecat_dropped_block_returns_empty():
    transform = pipecat.text_transform(provider="openai")
    assert asyncio.run(transform("```\nx = 1\ny = 2\n```", "sentence")) == ""
    assert asyncio.run(transform("```\nx = 1\n```", "sentence")) == "x equals 1."  # a one-line block is spoken by default
