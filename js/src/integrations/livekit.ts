/** speechready as a LiveKit Agents text transform.
 *
 * LiveKit Agents for Node passes the LLM's text stream through `ttsTextTransforms`
 * before synthesis. Each transform is `(AsyncIterable<string>) => AsyncIterable<string>`.
 * This one segments the stream into sentences as they are confirmed, runs each
 * through `prepare`, and yields the result.
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

export function textTransform(init: TextTransformInit = {}): (text: AsyncIterable<string>) => AsyncIterable<string> {
  const { maxBuffer = null, ...prepareInit } = init;
  const locale = prepareInit.locale ?? "en-US";
  const spoken = (piece: string): string => prepare(piece, prepareInit).text;
  return async function* transform(text: AsyncIterable<string>): AsyncIterable<string> {
    const seg = new Segmenter({ locale, maxBuffer });
    for await (const chunk of text) {
      for (const piece of seg.push(chunk)) {
        const out = spoken(piece);
        if (out) yield out + " ";
      }
    }
    for (const piece of seg.flush()) {
      const out = spoken(piece);
      if (out) yield out + " ";
    }
  };
}
