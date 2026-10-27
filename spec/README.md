# Shared spec

This folder is the single source of truth for both runtimes. The Python and the JavaScript package must produce the same output for every fixture here, and every provider profile is a data file both packages load unchanged.

## fixtures/

One YAML file per language and rule family, for example `en/clean-markdown.yaml`. Each file holds a list of cases:

```yaml
rule: clean.markdown        # the rule family under test
locale: en-US
cases:
  - id: bold-and-code
    input: "**Step 1:** run `npm install`"
    expect: "Step 1: run npm install"
  - id: heading
    input: "## Pricing\nTwo plans."
    expect: "Pricing. Two plans."
    note: a heading ends with a full stop so TTS pauses after it
```

Optional keys per case: `provider` and `model` when the expected output depends on a profile, `stream` as a list of chunks when the input arrives as a token stream, and `skip` with a reason while a case is known to fail.

## profiles/

One YAML file per provider model family, for example `elevenlabs-v2.yaml`. A profile states which intents the model accepts (pause, emphasis, spell-out, say-as, phoneme), how each is rendered, the request character limit, and the escaping rules. The schema is defined in `profiles/README.md` once the first three profiles exist.
