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

The verbalize stage rewrites only what models misread: phone numbers and long digit strings (digit by digit), numeric dates in the locale's order, 24-hour times, currency amounts, percent and unit abbreviations, small fractions, number ranges, years in context, decades, ordinals, and identifiers such as `AB12X9`. Ordinary numbers, decimals and pronounceable names like `COVID-19` are left alone.

Turkish (`locale="tr-TR"`) adds what foreign models get wrong in Turkish: suffixes on numerals and abbreviations are joined to the spoken word with vowel harmony and buffer consonants (`3'te` → üçte, `1990'da` → bin dokuz yüz doksanda, `100 TL'ye` → yüz liraya, `1/4'ü` → çeyreği), `%50` → yüzde elli, dotted thousands `1.250` → bin iki yüz elli, decimal commas `3,14` → üç virgül on dört, `3. madde` → üçüncü madde, dates `27.10.2026` → yirmi yedi Ekim iki bin yirmi altı, and abbreviations such as `vb.`, `Dr.`, `Üniv.`, `Cad.` read in full.

Inline intents in the input: `[pause 500ms]`, `[pause 1.5s]`, `[spell AB12]`, `[em really]`. An SSML `<break time="..."/>` you already have is read as a pause intent and re-rendered for the target.

`provider` and `model` pick a profile from `spec/profiles`; with neither, the `plain` profile renders pauses as punctuation and returns one chunk. Pass `profile=load_profile("azure-neural")` to pick one directly, `limit=` to override the request limit, and `options=CleanOptions(...)` to change how markdown, code, tables, URLs, emails and emoji are handled.

Pronunciation lexicon, one file for every vendor:

```python
from speechready import Lexicon, prepare, load_profile

lex = Lexicon.load("examples/lexicon.en.yaml")      # entries with ipa, say or spell
prepare("Restart Nginx.", provider="azure", lexicon=lex).text
# 'Restart <phoneme alphabet="ipa" ph="ˈɛndʒɪnˈɛks">Nginx</phoneme>.'
prepare("Restart Nginx.", provider="openai", lexicon=lex).text
# 'Restart engine X.'            (no phoneme tags on OpenAI, so the respelling is used)

lex.to_pls()                                         # PLS XML for ElevenLabs, Azure and Polly uploads
lex.to_google_json()                                 # Google Cloud TTS custom pronunciations
lex.export_for(load_profile("elevenlabs-v2"))        # the right one for a profile, or None
```

An inline `[ipa Nginx ˈɛndʒɪnˈɛks]` tag does the same for one word without a file.

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
