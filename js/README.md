# speechready (JavaScript / TypeScript)

Prepare text for text-to-speech. See the [repository README](https://github.com/berkerbatur/speechready) for the project overview and the evaluation results.

```
npm install speechready
```

(`npm install speechready` still gives the 0.0.1 name placeholder until the first release. Until then: clone the repository, `cd js && npm ci && npm run build && npm link`.)

ESM only, Node 20 or newer, no runtime dependencies. Type declarations are included. The provider profiles from `spec/profiles` are compiled into the package, so it also runs in a browser bundle.

## Usage

```js
import { prepare } from "speechready";

const result = prepare(
  "**Step 1:** run `npm install`. [pause 1s] Then read https://example.com/docs.",
  { provider: "elevenlabs", model: "eleven_multilingual_v2", locale: "en-US" },
);

result.text     // 'Step 1: run npm install. <break time="1s" /> Then read example.com.'
result.chunks   // the same text split under the model's request limit
for (const change of result.changes) {
  console.log(change.rule, JSON.stringify(change.before), "->", JSON.stringify(change.after));
}
```

`provider` and `model` pick a profile; with neither, the `plain` profile renders pauses as punctuation and returns one chunk. Pass `profile: loadProfile("azure-neural")` to pick one directly and `limit` to override the request limit. `locale` is `en-US` by default; `tr-TR` turns on the Turkish rules.

Everything a caller may want to decide differently is an option. The names are the same as in the Python package and in the shared fixtures, so they are snake_case; a name the package does not know throws.

```js
prepare(text, { provider: "openai", options: {
  code_blocks: "mention",     // drop (default) | keep | mention: one sentence stands in for a fenced block
  code_block_mention: null,   // what `mention` says; null = "See the code block." / "Kod bloğuna bakın."
  tables: "rows",             // rows (default, each row a comma list) | drop
  urls: "domain",             // domain (default) | drop | keep
  emails: "keep",             // keep (default) | drop
  emoji: "drop",              // drop (default) | keep
  emphasis: "strip",          // strip (default) | intent: **bold** becomes an emphasis intent
  list_numbers: "keep",       // keep (default, "1. Open the app") | drop
  fractions: "spoken",        // spoken (default: "one half", "yarım") | division ("one over two", "bir bölü iki")
  foreign_acronyms: true,     // Turkish: npm, css, sql read with English letter names (en pi em)
  terminal_punctuation: ".",  // added to a block that ends without one
}});
```

Stages are also exported on their own: `clean(text, options, recorder, locale)`, `verbalize(text, locale, recorder, options)`, `splitSentences(text, locale)`, `pack(sentences, limit, unit)`, and `Segmenter` for streaming token feeds:

```js
import { Segmenter } from "speechready";

const seg = new Segmenter({ locale: "en-US" });
for (const token of llmStream) {
  for (const sentence of seg.push(token)) speak(sentence);   // released once the boundary is confirmed
}
for (const sentence of seg.flush()) speak(sentence);
```

Pronunciation lexicon, one file for every vendor:

```js
import { Lexicon, prepare } from "speechready";

const lex = Lexicon.fromEntries([
  { word: "Nginx", ipa: "ˈɛndʒɪnˈɛks", say: "engine X" },
  { word: "SQL", say: "sequel" },
  { word: "CLI", spell: true },
]);
prepare("Restart Nginx.", { provider: "azure", lexicon: lex }).text;
// 'Restart <phoneme alphabet="ipa" ph="ˈɛndʒɪnˈɛks">Nginx</phoneme>.'
prepare("Restart Nginx.", { provider: "openai", lexicon: lex }).text;
// 'Restart engine X.'            (no phoneme tags on OpenAI, so the respelling is used)

lex.toPls();          // PLS XML for ElevenLabs, Azure and Polly uploads
lex.toGoogleJson();   // Google Cloud TTS custom pronunciations
await Lexicon.load("lexicon.json");   // Node only; .yaml files need the optional `yaml` package
```

## Differences from the Python package

The two packages produce the same text for every fixture in `spec/fixtures`. The API differs only where the languages do: keyword arguments are one options object, methods are camelCase (`limitFor`, `toPls`, `splitSentences`), `Lexicon.load` is async, and `prepare` takes a `Lexicon` or an entries array rather than a file path.

## Development

```
cd js
npm ci
npm test        # builds, then runs every fixture in ../spec/fixtures plus the package tests
```

`npm run build` regenerates `src/profiles/data.ts` from `../spec/profiles` and compiles to `dist/`. Both are build outputs and are not committed.
