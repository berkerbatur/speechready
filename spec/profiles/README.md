# Provider profiles

One YAML file per provider model family. Both runtimes load these files unchanged, so a vendor changing its syntax is a change here, not in code.

```yaml
id: elevenlabs-v2            # what `load_profile()` takes
provider: elevenlabs         # what `prepare(provider=...)` takes
models: [eleven_multilingual_v2, eleven_flash_v2_5]
default: true                # picked when a provider is given without a model
syntax: plain                # plain | ssml: what the output text is
escape: none                 # none | xml: escape & < > in text segments
audio_tags: false            # pass unknown [bracket tags] through (ElevenLabs v3/v4 style)
limit:
  unit: chars                # chars | bytes
  max: 10000                 # default per request; null = no limit
  per_model: {eleven_flash_v2_5: 40000}
intents:
  pause: {render: '<break time="{s}s" />', min_ms: 100, max_ms: 3000}   # or render: punctuation
  spell: {render: spaced}    # spaced = "A B 1 2", or a template with {text}
  emphasis: {render: '{text}'}
  phoneme: {render: '<phoneme alphabet="ipa" ph="{ipa}">{text}</phoneme>'}  # omit when the model takes no phoneme tag
lexicon: {format: pls, alphabet: ipa}   # how a lexicon is uploaded to this provider: pls | google | none
notes: free text for maintainers
sources: [urls the numbers were taken from]
verified: 2026-10-27         # the day someone last checked the sources
```

Render templates take `{ms}` and `{s}` (seconds, shortest form) for pauses, `{text}` for spell and emphasis, and `{text}` plus `{ipa}` for phoneme. A lexicon entry with IPA becomes a phoneme tag only where `intents.phoneme` is set; elsewhere its `say` respelling is used.
