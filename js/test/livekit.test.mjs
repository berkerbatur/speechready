import assert from "node:assert/strict";
import test from "node:test";

import { textTransform } from "../dist/integrations/livekit.js";

async function* tokens(text, size = 7) {
  for (let i = 0; i < text.length; i += size) yield text.slice(i, i + size);
}

/** What LiveKit hands a transform: a ReadableStream of text chunks. */
function stream(text, size = 7) {
  return new ReadableStream({
    start(controller) {
      for (let i = 0; i < text.length; i += size) controller.enqueue(text.slice(i, i + size));
      controller.close();
    },
  });
}

async function collect(readable) {
  assert.ok(readable instanceof ReadableStream, "a transform must return a ReadableStream, as @livekit/agents chains them");
  const out = [];
  const reader = readable.getReader();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return out;
    out.push(value);
  }
}

const TEXT = "**Step 1:** run `npm install`. [pause 1s] Then:\n```bash\nnpm start\n```\nRead https://example.com/docs. Done";
const EXPECTED = ["Step 1: run npm install.", '<break time="1s" /> Then:', "npm start.", "Read example.com.", "Done."].map((s) => s + " ");

test("a ReadableStream is spoken sentence by sentence in provider syntax, as a ReadableStream", async () => {
  const out = await collect(textTransform({ provider: "elevenlabs", model: "eleven_multilingual_v2" })(stream(TEXT)));
  assert.deepEqual(out, EXPECTED);
});

test("an async iterable is accepted as input too", async () => {
  const out = await collect(textTransform({ provider: "elevenlabs", model: "eleven_multilingual_v2" })(tokens(TEXT)));
  assert.deepEqual(out, EXPECTED);
});

test("a one-line code block is spoken by default, dropped or mentioned on request", async () => {
  const joined = (await collect(textTransform({ provider: "openai" })(stream(TEXT)))).join("");
  assert.ok(joined.includes("npm start."));
  const dropped = (await collect(textTransform({ provider: "openai", options: { code_blocks: "drop" } })(stream(TEXT)))).join("");
  assert.ok(!dropped.includes("npm start"));
  const mentioned = (await collect(textTransform({ provider: "openai", options: { code_blocks: "mention" } })(stream(TEXT)))).join("");
  assert.ok(mentioned.includes("See the code block."));
});

test("empty stream yields nothing", async () => {
  assert.deepEqual(await collect(textTransform()(stream(""))), []);
});
