/** speechready as a LiveKit Agents text transform.
 *
 * LiveKit Agents for Node passes the LLM's text stream through `ttsTextTransforms`
 * before synthesis. Each transform is `(text: ReadableStream<string>) => ReadableStream<string>`
 * (`TextTransform` in `@livekit/agents`), and the transforms are chained, so the
 * return value has to be a real `ReadableStream`. This one segments the stream into
 * sentences as they are confirmed, runs each through `prepare`, and streams the result.
 * It also accepts any async iterable of strings as input.
 *
 *     import { textTransform } from "speechready/livekit";
 *     const session = new voice.AgentSession({
 *       ...,
 *       ttsTextTransforms: [textTransform({ provider: "elevenlabs", model: "eleven_turbo_v2_5" })],
 *     });
 */

import { Segmenter } from "../chunk.js";
import { prepare } from "../pipeline.js";
import type { PrepareInit } from "../pipeline.js";

export interface TextTransformInit extends Omit<PrepareInit, "limit"> {
  /** Release a long sentence at a clause boundary once the buffer holds this many characters. */
  maxBuffer?: number | null;
}

export type TextInput = ReadableStream<string> | AsyncIterable<string>;

export function textTransform(init: TextTransformInit = {}): (text: TextInput) => ReadableStream<string> {
  const { maxBuffer = null, ...prepareInit } = init;
  const locale = prepareInit.locale ?? "en-US";
  const spoken = (piece: string): string => prepare(piece, prepareInit).text;

  async function* run(text: TextInput): AsyncGenerator<string> {
    const seg = new Segmenter({ locale, maxBuffer });
    for await (const chunk of iterate(text)) {
      for (const piece of seg.push(chunk)) {
        const out = spoken(piece);
        if (out) yield out + " ";
      }
    }
    for (const piece of seg.flush()) {
      const out = spoken(piece);
      if (out) yield out + " ";
    }
  }

  return function transform(text: TextInput): ReadableStream<string> {
    const gen = run(text);
    return new ReadableStream<string>({
      async pull(controller) {
        const { value, done } = await gen.next();
        if (done) controller.close();
        else controller.enqueue(value);
      },
      async cancel() {
        await gen.return(undefined);
      },
    });
  };
}

/** Read a ReadableStream (which browsers do not make async-iterable) or any async iterable. */
async function* iterate(text: TextInput): AsyncGenerator<string> {
  if (typeof (text as AsyncIterable<string>)[Symbol.asyncIterator] === "function") {
    yield* text as AsyncIterable<string>;
    return;
  }
  const reader = (text as ReadableStream<string>).getReader();
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return;
      yield value;
    }
  } finally {
    reader.releaseLock();
  }
}
