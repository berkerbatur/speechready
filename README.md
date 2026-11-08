# speechready

Prepare text for text-to-speech. `speechready` takes text, especially LLM output, plus a target provider and model, and returns text that provider reads correctly, split into request-sized chunks.

It is deterministic and makes no network calls. Every rewrite is reported back as a diff so you can audit and override it.

## What it does

1. **Cleans** markdown, code fences, tables, emoji, URLs, emails and invisible Unicode out of LLM output.
2. **Verbalizes only the ambiguous tokens**: phone numbers, IDs, dates in a stated locale, years, currency decimals, units, ranges and acronyms from a lexicon. Ordinary numbers are left to hosted models, which read them well; for local models without a text normalizer (Kokoro, Piper, Chatterbox, XTTS, Orpheus) the profile switches to writing every number out.
3. **Compiles** pacing intents such as a pause or emphasis into each vendor's own syntax: an SSML break where the model accepts it, punctuation where it does not, the vendor's tag elsewhere. Escapes SSML characters where needed.
4. **Chunks** at sentence and clause boundaries under the model's character limit, on whole strings and on streaming token feeds.
5. **Applies one pronunciation lexicon** everywhere: phoneme tags where the vendor takes them, respellings elsewhere, and exports it as PLS (ElevenLabs, Azure, Polly) or Google custom pronunciations.

English and Turkish ship with full rule sets. Other languages get the language-independent stages plus a labelled number fallback, and each new language is one rules file plus one fixture file.

## Quick look

```python
from speechready import prepare

r = prepare("**Step 1:** run `npm install`. [pause 1s] Then read https://example.com/docs.",
            provider="elevenlabs", model="eleven_multilingual_v2")
r.text      # 'Step 1: run npm install. <break time="1s" /> Then read example.com.'
r.chunks    # the same text split under the model's request limit
r.changes   # every rewrite: rule, before, after, note
```

The same call with `provider="openai"` renders the pause as punctuation and chunks at 4,096 characters; with `provider="azure"` it renders SSML with `&`, `<` and `>` escaped. Switching vendors is one argument.

## Does it help?

Measured on 2026-10-30 with the harness in `eval/` (scorer updated 2026-11-02): 145 lines of English and Turkish (LLM answers, markdown, dates, phone numbers, prices, URLs, identifiers, plus control prose that should pass untouched), 16 voices across 7 providers. Every line was synthesized twice, as written and after `prepare`, and both recordings were transcribed back with OpenAI gpt-4o-transcribe. A misread is a transcript that differs from the intended words by more than a fifth.

| | Line/voice pairs | Misread as written | Misread with speechready |
| --- | --- | --- | --- |
| All | 1180 | 32% | 8% |
| English | 774 | 29% | 7% |
| Turkish | 406 | 37% | 10% |

| Provider | Model | Pairs | As written | With speechready |
| --- | --- | --- | --- | --- |
| ElevenLabs | eleven_multilingual_v2 | 144 | 41% | 8% |
| OpenAI | gpt-4o-mini-tts | 144 | 33% | 6% |
| Azure AI Speech | neural | 144 | 27% | 6% |
| Google Cloud TTS | Chirp 3 HD | 144 | 34% | 6% |
| Google Cloud TTS | Neural2 (en) / WaveNet (tr) | 144 | 31% | 6% |
| Amazon Polly | neural | 144 | 26% | 8% |
| Amazon Polly | generative (en) | 86 | 30% | 6% |
| Cartesia | sonic-3.6 | 144 | 33% | 16% |
| Deepgram | aura-2 (en) | 86 | 30% | 9% |

Every voice improved and the control prose did not regress. Cartesia's Turkish is the weakest result: its voice speaks Turkish with an English accent, so the transcription model misses words that were rendered correctly.

**Held-out check.** The corpus above is mostly the fixture inputs the rules were written against, so on 2026-11-02 we added an independent set: 60 answers (30 English, 30 Turkish) that gpt-4.1-mini gave to typical voice-agent questions as a chat assistant, with no instruction about speech, generated after the rules were written and not edited. The same model wrote the narration a reader would speak for each answer in a separate call, and that narration is the reference for both recordings. Four voices (ElevenLabs, OpenAI, Azure, Google Chirp 3 HD), 240 pairs:

| | Pairs | Misread as written | Misread with speechready | Mean WER as written | Mean WER with speechready |
| --- | --- | --- | --- | --- | --- |
| All | 240 | 10% | 8% | 0.058 | 0.061 |
| English | 120 | 6% | 3% | 0.030 | 0.033 |
| Turkish | 120 | 14% | 13% | 0.087 | 0.088 |

32 pairs got better, 42 worse, 166 did not change. Of the 42 worse: 14 are code blocks that speechready drops by default while the narration kept the command (`code_blocks="keep"` or `"mention"` changes that); 8 are convention differences between the library and the narration (lira and kuruş against "virgül", "dokuzda beş" against "beş bölü dokuz"); 6 are two bugs this run found, fixed in the next release (a dotted Turkish time with a suffix, `14.00'teki`, and a spaced minus in an equation read as a range); 18 differ by a word or two of transcription noise. The reading: concise assistant answers contain few of the constructs the library targets, so on them it changes little either way. The gain in the tables above is on inputs that do contain markdown, prices, phone numbers, dates and code, which is where voice agents fail audibly. The corpus is in `eval/corpus/heldout.*.yaml`, `summary.md` reports it in its own section, and the numbers here are as measured before the two fixes.

**Local models.** Measured on 2026-11-08 on a laptop CPU, no API calls: the same corpus (grown to 89 English and 63 Turkish lines by then) through Kokoro 82M and Piper, transcribed with faster-whisper large-v3 instead of the hosted transcription model, so the rows are comparable with each other and with the trend above, not digit for digit with the hosted table. These models have no text normalizer of their own, so their profiles also write every remaining number out in words.

| Model | Locale | Pairs | Misread as written | Misread with speechready |
| --- | --- | --- | --- | --- |
| Kokoro 82M | English | 89 | 38% | 11% |
| Piper (lessac-medium) | English | 89 | 42% | 12% |
| Piper (dfki-medium) | Turkish | 63 | 43% | 14% |

Small local models fail on the same inputs as the hosted voices, more often: a raw ISO date, a markdown table or an inline code span comes out as noise, and written-out text fixes most of it. The held-out assistant answers behaved as they did for the hosted voices (Kokoro 3% misread either way, Piper 10% as written and 13% processed over 60 pairs, the difference being code blocks the library drops). Their pairs are in the listening page under their own headings.

- **Listen:** [berkerbatur.github.io/speechready](https://berkerbatur.github.io/speechready/) plays the clearest before/after pairs for every voice, with what the speech-to-text model heard under each.
- **Try your own text:** [berkerbatur.github.io/speechready/play](https://berkerbatur.github.io/speechready/play/) runs the JavaScript package in your browser (35 kB) and shows the output, the chunks and every rewrite. Nothing you type leaves the page.
- **Reproduce:** `eval/README.md` explains the keys, the scorer and the commands. The results in this table are also in `eval/out/summary.md` after a run.

## Try it

```
pip install speechready      # Python 3.10+, depends only on PyYAML
npm install speechready      # Node 20+, ESM, no runtime dependencies
```

In a voice agent, drop it between the LLM and the TTS: `speechready.integrations.livekit.text_transform(...)` goes in LiveKit's `tts_text_transforms`, `speechready.integrations.pipecat.text_transform(...)` in a Pipecat TTS service's `text_transforms`, and `speechready/livekit` does the same for LiveKit's Node SDK. Runnable agents for all three are in [`examples/`](examples/README.md).

For Turkish developer vocabulary there is a bundled lexicon: `prepare(text, locale="tr-TR", lexicon="tr-tech")` reads `API` as "ey pi ay" and `JSON` as "ceyson", and refits an apostrophe suffix to the spoken form (`API'yi` → `ey pi ay'ı`).

Everything a caller may want to decide differently is an `Options` field (code blocks dropped, kept or replaced by one spoken sentence; list numbers kept or dropped; fractions spoken or read as a division; URLs reduced to their domain, dropped or kept). The defaults are what the evaluation above ran with. See `python/README.md`.

## Status

Version 0.3.0 is on [PyPI](https://pypi.org/project/speechready/) and [npm](https://www.npmjs.com/package/speechready). Both packages have all four stages, the streaming segmenter, English and Turkish verbalization rules, the lexicon, and profiles for ElevenLabs (v2 and v3/v4 families), OpenAI, Azure, Google (Chirp 3 HD and the SSML voices), Amazon Polly, Cartesia and Deepgram, and for the open-weight models Kokoro, Piper, Chatterbox, XTTS v2 and Orpheus. The Python package has been through the evaluation above; the TypeScript package passes the same 233 fixtures, so it produces the same text. Changes are listed in `CHANGELOG.md`. The public API may still move before 1.0; anything that does will be called out there.

### Releasing

A release is a pull request that bumps `__version__` in `python/src/speechready/__init__.py` and `version` in `js/package.json` to the same number and dates the `CHANGELOG.md` entry. Merging it is the release: the `release` workflow runs the tests, publishes to PyPI and npm through trusted publishing (no registry tokens are stored anywhere), then tags the commit `vX.Y.Z` and creates the GitHub release with the changelog entry as its notes. A merge whose versions differ, or whose changelog entry is missing, fails the workflow instead of publishing.

## Layout

| Folder | Holds |
| --- | --- |
| `spec/` | The shared fixture corpus, provider profiles and bundled lexicons. Both runtimes must pass every fixture. |
| `python/` | The Python package. |
| `js/` | The TypeScript package, compiled to ESM with type declarations. Same API, same fixtures. |
| `eval/` | The evaluation harness: raw vs preprocessed audio per provider, STT round trip, before/after page. |
| `docs/` | The GitHub Pages site: the listening page written by the harness, and the browser playground. |
| `examples/` | Runnable LiveKit (Python and Node) and Pipecat agents, and a sample lexicon. |

## Licence

MIT.
