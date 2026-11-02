# Changelog

Both packages share one version number and one fixture corpus, so an entry here applies to Python and JavaScript alike unless it says otherwise.

## 0.1.0 (2026-11-02)

First release. The 0.0.1 versions on PyPI and npm were name placeholders with no code.

- **Pipeline:** `prepare(text, provider=..., model=...)` runs clean, verbalize, compile and chunk and reports every rewrite as a `Change`. Stages are also usable on their own.
- **Clean:** Markdown and LLM artefacts (headings, emphasis, links, fenced code, tables, emoji, URLs, emails) with an `Options` switch for each judgment call. Code blocks are dropped by default; `code_blocks="mention"` replaces one with a spoken sentence.
- **Verbalize:** English and Turkish rules for numbers, ordinals, decimals, fractions, percentages, currencies, dates, times, phone numbers, units, abbreviations and acronyms. Turkish applies vowel harmony to suffixes and, by default, reads foreign tech acronyms with English letter names.
- **Compile:** pause, spell and emphasis intents (`[pause 1s]`, `[spell ...]`, bold with `emphasis="intent"`) rendered to each provider's syntax: SSML, ElevenLabs break tags and v3 audio tags, Cartesia and Deepgram plain-text conventions.
- **Chunk:** sentence splitting for both locales, packing under each model's request limit in characters or bytes, and a streaming `Segmenter` that releases sentences from an LLM token stream as boundaries are confirmed.
- **Profiles:** ElevenLabs (v2 and v3/v4 families), OpenAI, Azure Neural, Google (Chirp 3 HD and the SSML voices), Amazon Polly, Cartesia, Deepgram, and `plain`. Profiles are YAML in `spec/profiles` and are bundled into both packages.
- **Lexicon:** one pronunciation file (IPA, respelling or spell-out per word) applied inline as phoneme tags where the provider supports them, exported as PLS for ElevenLabs, Azure and Polly, and as Google custom pronunciations.
- **Evaluation:** 1180 raw-versus-processed audio pairs across 7 providers and 16 voices, transcribed back with speech-to-text. Misreads on the targeted classes fell from 33% to 10% (English 30% to 8%, Turkish 39% to 13%). Listen at https://berkerbatur.github.io/speechready/.
- **JavaScript:** ESM package with type declarations, Node 20+, no runtime dependencies; passes the same 210 fixtures as the Python package.
