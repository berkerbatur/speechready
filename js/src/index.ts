/** speechready: prepare text for text-to-speech.
 *
 * Clean LLM output, verbalize ambiguous tokens, compile pacing intents to a
 * provider's own syntax, and chunk under the model's request limit. Deterministic,
 * no network calls, every rewrite reported as a Change.
 */

export type { Change } from "./changes.js";
export { Segmenter, pack, splitSentences } from "./chunk.js";
export { DEFAULT_OPTIONS, clean, options } from "./clean.js";
export type { Options } from "./clean.js";
export { Lexicon } from "./lexicon.js";
export type { Entry, EntryInput } from "./lexicon.js";
export { prepare } from "./pipeline.js";
export type { Prepared, PrepareInit } from "./pipeline.js";
export { listProfiles, loadProfile, resolveProfile } from "./profiles/index.js";
export type { Profile } from "./profiles/index.js";
export { verbalize } from "./verbalize/index.js";
import "./verbalize/en.js";
import "./verbalize/tr.js";

export const version = "0.1.0-dev.0";
