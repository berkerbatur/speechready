// Run every fixture in ../../spec/fixtures against the JavaScript implementation.
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve, dirname, basename } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

import { Lexicon, Segmenter, clean, loadProfile, pack, prepare, splitSentences, verbalize } from "../dist/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const SPEC = resolve(here, "..", "..", "spec", "fixtures");

function* yamlFiles(dir) {
  for (const name of readdirSync(dir).sort()) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* yamlFiles(p);
    else if (name.endsWith(".yaml")) yield p;
  }
}

function run(doc, c) {
  const rule = c.rule ?? doc.rule ?? "pipeline";
  const locale = c.locale ?? doc.locale ?? "en-US";
  const opts = c.options ?? null;
  if (rule.startsWith("clean")) return clean(c.input, opts, undefined, locale);
  const lexicon = c.lexicon ? Lexicon.fromEntries(c.lexicon, locale) : null;
  if (rule === "lexicon.export") return lexicon.export(c.format, c.alphabet ?? "ipa");
  if (rule.startsWith("verbalize")) return verbalize(c.input, locale, undefined, opts);
  if (rule === "chunk.sentences") return splitSentences(c.input, locale);
  if (rule === "chunk.pack") return pack(splitSentences(c.input, locale), c.limit ?? null, c.unit ?? "chars");
  if (rule === "chunk.stream") {
    const seg = new Segmenter({ locale, maxBuffer: c.max_buffer ?? null });
    const out = [];
    for (const piece of c.stream) out.push(...seg.push(piece));
    out.push(...seg.flush());
    return out;
  }
  const profile = loadProfile(c.profile ?? doc.profile ?? "plain");
  const result = prepare(c.input, { profile, model: c.model, locale, limit: c.limit, options: opts, lexicon });
  return rule === "pipeline.chunks" ? result.chunks : result.text;
}

let count = 0;
for (const path of yamlFiles(SPEC)) {
  const doc = parse(readFileSync(path, "utf-8"));
  const group = `${basename(dirname(path))}/${basename(path, ".yaml")}`;
  for (const c of doc.cases ?? []) {
    count++;
    test(`${group}::${c.id}`, { skip: c.skip || false }, () => {
      assert.deepEqual(run(doc, c), c.expect);
    });
  }
}

test("fixture corpus found", () => {
  assert.ok(count > 100, `only ${count} fixture cases found under ${SPEC}`);
});
