import assert from "node:assert/strict";
import test from "node:test";

import { Lexicon, listProfiles, options, prepare, version } from "../dist/index.js";

test("version is set", () => {
  assert.ok(version);
});

test("profiles are bundled", () => {
  const ids = listProfiles().map((p) => p.id);
  assert.ok(ids.includes("plain"));
  assert.ok(ids.includes("elevenlabs-v2"));
});

test("prepare picks a profile from provider and model", () => {
  const r = prepare("**Step 1:** run `npm install`. [pause 1s] Then read https://example.com/docs.", {
    provider: "elevenlabs",
    model: "eleven_multilingual_v2",
  });
  assert.equal(r.text, 'Step 1: run npm install. <break time="1s" /> Then read example.com.');
  assert.equal(r.profile.id, "elevenlabs-v2");
  assert.ok(r.changes.length > 0);
});

test("unknown option names are rejected", () => {
  assert.throws(() => options({ codeBlocks: "keep" }), /snake_case/);
});

test("lexicon export", () => {
  const lex = Lexicon.fromEntries([{ word: "SQL", say: "sequel" }]);
  assert.match(lex.toPls(), /<alias>sequel<\/alias>/);
});
