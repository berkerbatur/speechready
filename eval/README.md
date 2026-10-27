# Evaluation: does speechready make the audio better?

This harness answers the plan's go/no-go question. Every corpus line is synthesized twice per provider, as written and after `speechready.prepare`, both audios are transcribed, and the transcripts are scored against the intended words. The output is a table of misread rates per problem class and a before/after page with audio players for listening.

## Corpus

- Every input from the shared fixtures in `spec/fixtures` whose expected output is a spoken form (the verbalize, clean, pipeline and lexicon files), tagged by class.
- `corpus/control.*.yaml`: plain prose that the library must leave alone. Any regression here is a bug.
- `corpus/llm.*.yaml`: realistic assistant answers with markdown, prices, order numbers and phone numbers.

## Run

```
python -m pip install -e python -e "eval[whisper]"     # faster-whisper needs a GPU for large-v3 at a sane speed
export ELEVENLABS_API_KEY=... OPENAI_API_KEY=... AZURE_SPEECH_KEY=... AZURE_SPEECH_REGION=...

python -m speechready_eval.run --dry-run                       # what would be synthesized
python -m speechready_eval.run --locales en --providers openai --stt openai --limit 10   # a cheap first pass
python -m speechready_eval.run                                 # everything: en + tr, three providers, local whisper
python -m speechready_eval.report                              # eval/out/summary.md and eval/out/index.html
```

Results accumulate in `eval/out/results.jsonl`; a rerun skips finished variants, so a crash or a key running out loses nothing. Pass `--voice provider:model:voice:locale` to change voices (defaults are in `synth.py`).

Scoring: word error rate after lowercasing, stripping punctuation and markup, and expanding digits to words. Because an STT engine may write `555` for speech that said "five five five", the hypothesis is expanded both ways and the better score counts. A line is a misread when WER is above 0.2.

## What success looks like

From the plan: the misread rate on the targeted classes at least halves on every provider, with no measurable regression on the control class. Any rule family that does not improve is dropped from the defaults before the first release.

Costs: synthesis is billed per character by each provider at their published rates; the corpus is a few thousand short lines per provider. STT is free with local whisper, or billed per minute with `--stt openai`.
