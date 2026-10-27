# speechready (Python)

Prepare text for text-to-speech. See the [repository README](https://github.com/berkerbatur/speechready) for the project overview.

```
pip install speechready
```

## Usage

```python
from speechready import prepare

result = prepare(
    "**Step 1:** run `npm install`. [pause 1s] Then read https://example.com/docs.",
    provider="elevenlabs",
    model="eleven_multilingual_v2",
    locale="en-US",
)

result.text     # 'Step 1: run npm install. <break time="1s" /> Then read example.com.'
result.chunks   # the same text split under the model's request limit
for change in result.changes:
    print(change.rule, repr(change.before), "->", repr(change.after))
```

Inline intents in the input: `[pause 500ms]`, `[pause 1.5s]`, `[spell AB12]`, `[em really]`. An SSML `<break time="..."/>` you already have is read as a pause intent and re-rendered for the target.

`provider` and `model` pick a profile from `spec/profiles`; with neither, the `plain` profile renders pauses as punctuation and returns one chunk. Pass `profile=load_profile("azure-neural")` to pick one directly, `limit=` to override the request limit, and `options=CleanOptions(...)` to change how markdown, code, tables, URLs, emails and emoji are handled.

Streaming:

```python
from speechready import Segmenter

seg = Segmenter(locale="en-US")
for token in llm_stream:
    for sentence in seg.push(token):
        tts.say(prepare(sentence, provider="openai").text)
for sentence in seg.flush():
    tts.say(prepare(sentence, provider="openai").text)
```

## Development

```
cd python
python -m pip install -e ".[dev]"
pytest
```

Tests run every fixture in `../spec/fixtures`, which the JavaScript package must pass as well.
