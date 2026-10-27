# Shared spec

This folder is the single source of truth for both runtimes. The Python and the JavaScript package must produce the same output for every fixture here, and every provider profile is a data file both packages load unchanged.

## fixtures/

One YAML file per language and rule family, for example `en/clean-markdown.yaml`. A file sets defaults (`rule`, `locale`, `profile`) and holds a list of cases:

```yaml
rule: clean.markdown
locale: en-US
cases:
  - id: bold-and-inline-code
    input: "**Step 1:** run `npm install`"
    expect: "Step 1: run npm install."
    note: a block that ends without punctuation gets a full stop
```

`rule` picks what the runner calls and what `expect` is:

| rule | runs | expect |
| --- | --- | --- |
| `clean.*` | the clean stage only | string |
| `verbalize.*` | the verbalize stage only, for `locale` | string |
| `chunk.sentences` | sentence splitting | list of sentences |
| `chunk.stream` | the streaming segmenter over `stream` (a list of pushes), then flush | list of sentences |
| `chunk.pack` | split then pack under `limit` (`unit` chars or bytes) | list of chunks |
| `pipeline` | the whole pipeline with `profile` | the compiled text |
| `pipeline.chunks` | the whole pipeline with `profile` and `limit` | list of chunks |

Optional keys per case: `rule` and `locale` (override the file), `profile` (a profile id), `model` (for per-model limits), `limit`, `unit`, `options` (clean options as a map), `stream`, `max_buffer`, `note`, and `skip` with a reason while a case is known to fail.

Expected strings are exact. Blocks are separated by `\n` in cleaned text; chunks are joined with a space.

## profiles/

One YAML file per provider model family. See `profiles/README.md` for the schema. Every number in a profile carries a `sources` link and a `verified` date.
