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

32 pairs got better, 42 worse, 166 did not change. Of the 42 worse: 14 are code blocks that speechready dropped by default while the narration kept the command (the default now speaks a block of one line, which is the command in every one of these answers; re-measured on Kokoro and Piper, the three English command answers went from WER 0.13, 0.16 and 0.36 to 0.02, 0.09 and 0.25 on Kokoro and from 0.12, 0.27 and 0.31 to 0.00, 0.13 and 0.07 on Piper, the hosted voices are not re-measured yet); 8 are convention differences between the library and the narration (lira and kuruş against "virgül", "dokuzda beş" against "beş bölü dokuz"); 6 are two bugs this run found, fixed in the next release (a dotted Turkish time with a suffix, `14.00'teki`, and a spaced minus in an equation read as a range); 18 differ by a word or two of transcription noise. The reading: concise assistant answers contain few of the constructs the library targets, so on them it changes little either way. The gain in the tables above is on inputs that do contain markdown, prices, phone numbers, dates and code, which is where voice agents fail audibly. The corpus is in `eval/corpus/heldout.*.yaml`, `summary.md` reports it in its own section, and the numbers here are as measured before the two fixes.

**Local models.** Measured on 2026-11-08, no API calls: the same corpus (grown to 89 English and 63 Turkish lines by then) through five open-weight models, Kokoro and Piper on a laptop CPU, Chatterbox, XTTS v2 and Orpheus on a rented RTX 4090, all transcribed with faster-whisper large-v3 instead of the hosted transcription model. The rows are comparable with each other and with the trend above, not digit for digit with the hosted table. None of these models has a text normalizer of its own, so their profiles also write every remaining number out in words.

| Model | Locale | Pairs | Misread as written | Misread with speechready |
| --- | --- | --- | --- | --- |
| Kokoro 82M | English | 89 | 38% | 11% |
| Piper (lessac-medium) | English | 89 | 42% | 12% |
| Piper (dfki-medium) | Turkish | 63 | 43% | 14% |
| Chatterbox multilingual | English | 89 | 60% | 27% |
| Chatterbox multilingual | Turkish | 63 | 86% | 21% |
| XTTS v2 | English | 89 | 49% | 25% |
| XTTS v2 | Turkish | 63 | 52% | 22% |
| Orpheus 3B | English | 89 | 43% | 8% |

Local models fail on the same inputs as the hosted voices, more often: a raw ISO date, a markdown table or an inline code span comes out as noise, and written-out text fixes most of it. What remains after preprocessing for Chatterbox and XTTS is largely the model itself: given a very short sentence, both tend to keep talking past the end of the text, and the transcript then carries a few seconds of invented words. Orpheus is a streaming model that expects a sentence at a time; the harness sends whole lines, and its package stops a clip after 14 seconds unless told otherwise, which the harness now does. The held-out assistant answers behaved as they did for the hosted voices (Kokoro 3% misread either way, Piper 10% as written and 13% processed, 10% after one-line code blocks became spoken, Chatterbox 30% and 17%, XTTS 17% and 13%, Orpheus 20% and 10%, each over 60 pairs or 30 for the English-only models; the differences are mostly code blocks the library drops). Their pairs are in the listening page under their own headings.

**Prompting the LLM instead.** The question every reader asks: why not tell the language model to write for speech? Measured on 2026-11-09: every line of the corpus was rewritten by gpt-6-luna with the prompt a careful developer would write without a library (strip markdown, say only a site's name for a URL, leave out code blocks, write every number, date, time, price, phone number, identifier, unit and acronym out as a native speaker would, keep everything else; the prompt is in `eval/speechready_eval/rewrite.py`), then spoken by the same four hosted voices as the held-out check (transcribed with gpt-4o-transcribe) and by Kokoro and Piper on a laptop (local Whisper), so the three versions of each line are scored on the same voice.

| | Pairs | Misread as written | Misread with speechready | Misread with the LLM rewrite |
| --- | --- | --- | --- | --- |
| Four hosted voices, main corpus | 608 | 34% | 7% | 17% |
| English | 356 | 30% | 6% | 13% |
| Turkish | 252 | 38% | 9% | 23% |
| Four hosted voices, held-out answers | 240 | 10% | 8% | 11% |
| Kokoro, main corpus (English) | 89 | 38% | 11% | 17% |
| Piper, main corpus, English | 89 | 42% | 12% | 18% |
| Piper, main corpus, Turkish | 63 | 43% | 14% | 27% |
| Kokoro and Piper, held-out answers | 90 | 8% | 10% | 6% |

About half of the rewrite's misreads on the main corpus are readings the reference does not accept but a listener would not mind ("example dot com" for a link, "twenty U.S. dollars", "dört buçuk" for `4,5`). The other half are real: the model spoke a hidden `<think>` block aloud, read a code block it was told to leave out, narrated checkbox markup as "Checked: done. Unchecked: to do", and read an order number as "forty-eight million two hundred nineteen thousand". On the held-out answers the rewrite changed nothing on the hosted voices (mean WER identical to the raw text) and the three versions are within a few pairs of each other on the local ones, while it did find one thing the rules leave alone: a lone number before a sentence end (`Puan 3.`) that the voices read as an ordinal. It also costs a model call on every turn: in this run the rewrite took a median 2.3 seconds per answer with gpt-6-luna and 1.2 seconds with gpt-4.1-mini before the first byte of audio could be requested, against microseconds for the library, and no prompt can put a break tag in for ElevenLabs and a comma for OpenAI. The full tables are in `summary.md` under "Prompting the LLM instead".

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

Everything a caller may want to decide differently is an `Options` field (code blocks spoken when they are one line, dropped, kept or replaced by one spoken sentence; list numbers kept or dropped; fractions spoken or read as a division; URLs reduced to their domain, dropped or kept). The defaults are what the evaluation above ran with. See `python/README.md`.

## Status

Version 0.4.0 is on [PyPI](https://pypi.org/project/speechready/) and [npm](https://www.npmjs.com/package/speechready). Both packages have all four stages, the streaming segmenter, English and Turkish verbalization rules, the lexicon, and profiles for ElevenLabs (v2 and v3/v4 families), OpenAI, Azure, Google (Chirp 3 HD and the SSML voices), Amazon Polly, Cartesia and Deepgram, and for the open-weight models Kokoro, Piper, Chatterbox, XTTS v2 and Orpheus. The Python package has been through the evaluation above; the TypeScript package passes the same 233 fixtures, so it produces the same text. Changes are listed in `CHANGELOG.md`. The public API may still move before 1.0; anything that does will be called out there.

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
