import assert from "node:assert/strict";
import test from "node:test";

import { textTransform } from "../dist/integrations/livekit.js";

async function* tokens(text, size = 7) {
  for (let i = 0; i < text.length; i += size) yield text.slice(i, i + size);
}

async function collect(iter) {
  const out = [];
  for await (const s of iter) out.push(s);
  return out;
}

const TEXT = "**Step 1:** run `npm install`. [pause 1s] Then:\n```bash\nnpm start\n```\nRead https://example.com/docs. Done";

test("stream is spoken sentence by sentence in provider syntax", async () => {
  const out = await collect(textTransform({ provider: "elevenlabs", model: "eleven_multilingual_v2" })(tokens(TEXT)));
  assert.deepEqual(out, ["Step 1: run npm install.", '<break time="1s" /> Then:', "Read example.com.", "Done."].map((s) => s + " "));
});

test("code block is dropped by default and mentioned on request", async () => {
  const joined = (await collect(textTransform({ provider: "openai" })(tokens(TEXT)))).join("");
  assert.ok(!joined.includes("npm start"));
  const mentioned = (await collect(textTransform({ provider: "openai", options: { code_blocks: "mention" } })(tokens(TEXT)))).join("");
  assert.ok(mentioned.includes("See the code block."));
});

test("empty stream yields nothing", async () => {
  assert.deepEqual(await collect(textTransform()(tokens(""))), []);
});
