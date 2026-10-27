# speechready

Prepare text for text-to-speech. `speechready` takes text, especially LLM output, plus a target provider and model, and returns text that provider reads correctly, split into request-sized chunks.

It is deterministic and makes no network calls. Every rewrite is reported back as a diff so you can audit and override it.

## What it does

1. **Cleans** markdown, code fences, tables, emoji, URLs, emails and invisible Unicode out of LLM output.
2. **Verbalizes only the ambiguous tokens**: phone numbers, IDs, dates in a stated locale, years, currency decimals, units, ranges and acronyms from a lexicon. Ordinary numbers are left to the model, which reads them well.
3. **Compiles** pacing intents such as a pause or emphasis into each vendor's own syntax: an SSML break where the model accepts it, punctuation where it does not, the vendor's tag elsewhere. Escapes SSML characters where needed.
4. **Chunks** at sentence and clause boundaries under the model's character limit, on whole strings and on streaming token feeds.
5. **Exports one lexicon** to each vendor's pronunciation format.

English and Turkish ship with full rule sets. Other languages get the language-independent stages plus a labelled number fallback, and each new language is one rules file plus one fixture file.

## Status

Version 0.0.1 on [PyPI](https://pypi.org/project/speechready/) and [npm](https://www.npmjs.com/package/speechready) is a placeholder that reserves the name. The first working release is in progress.

## Layout

| Folder | Holds |
| --- | --- |
| `spec/` | The shared fixture corpus and provider profiles. Both runtimes must pass every fixture. |
| `python/` | The Python package. |
| `js/` | The JavaScript package. |

## Licence

MIT.
