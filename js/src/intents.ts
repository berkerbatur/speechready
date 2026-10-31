/** Pacing intents written inline in the input and carried through the pipeline.
 *
 * Developers write `[pause 500ms]`, `[spell AB12]` or `[em really]` in their text,
 * or an SSML `<break time="500ms"/>` they already had. `extract` replaces each one
 * with a private-use sentinel so cleaning and verbalizing leave it alone; the
 * compile stage renders every sentinel in the target provider's own syntax.
 */

import { Match, fullmatch, partition, re, roundHalfEven, sub } from "./util.js";

export const SENTINEL_OPEN = "";
export const SENTINEL_CLOSE = "";

const INTENT_TAG = re(String.raw`\[(?<kind>pause|spell|em|ipa)(?:\s+(?<arg>[^\]]*?))?\s*\](?!\()`, "i");
const SSML_BREAK = re(String.raw`<break\s+(?:time\s*=\s*["'](?<time>[^"']+)["']|strength\s*=\s*["'](?<strength>[^"']+)["'])[^>]*/?>`, "i");
const SENTINEL = re(`${SENTINEL_OPEN}(\\d+)${SENTINEL_CLOSE}`);
const DURATION = re(String.raw`(\d+(?:\.\d+)?)\s*(ms|s)?`);

const STRENGTH_MS: Record<string, number> = { "x-weak": 250, weak: 500, medium: 750, strong: 1000, "x-strong": 1250 };
export const DEFAULT_PAUSE_MS = 500;

export interface Intent {
  kind: "pause" | "spell" | "em" | "phoneme";
  /** pause only */
  ms: number;
  /** spell, em and phoneme: the words as written */
  text: string;
  /** phoneme: IPA transcription */
  ipa: string;
  /** phoneme: respelling fallback for providers without phoneme tags */
  say: string;
}

export function intent(kind: Intent["kind"], fields: Partial<Omit<Intent, "kind">> = {}): Intent {
  return { kind, ms: 0, text: "", ipa: "", say: "", ...fields };
}

/** '1.5s', '500ms', '2' (seconds) -> milliseconds. Unparseable -> the default. */
export function parseDurationMs(value: string | undefined | null): number {
  if (!value) return DEFAULT_PAUSE_MS;
  const v = value.trim().toLowerCase();
  const m = fullmatch(DURATION, v);
  if (!m) return DEFAULT_PAUSE_MS;
  const number = parseFloat(m[1]);
  const unit = m[2];
  if (unit === "ms") return roundHalfEven(number);
  return roundHalfEven(number * 1000);
}

/** Replace every inline intent with a sentinel; return the text and the intents in order.
 *
 * Pass an existing list to append to it (the pipeline runs a second pass after
 * cleaning, because the cleaner can turn markdown emphasis into `[em ...]`).
 */
export function extract(text: string, intents?: Intent[]): [string, Intent[]] {
  const list = intents ?? [];

  const add = (it: Intent): string => {
    list.push(it);
    return `${SENTINEL_OPEN}${list.length - 1}${SENTINEL_CLOSE}`;
  };

  const ssml = (m: Match): string => {
    const g = m.groups ?? {};
    if (g.time) return add(intent("pause", { ms: parseDurationMs(g.time) }));
    return add(intent("pause", { ms: STRENGTH_MS[(g.strength ?? "").toLowerCase()] ?? DEFAULT_PAUSE_MS }));
  };

  const tag = (m: Match): string => {
    const g = m.groups ?? {};
    const kind = (g.kind ?? "").toLowerCase();
    const arg = (g.arg ?? "").trim();
    if (kind === "pause") return add(intent("pause", { ms: parseDurationMs(arg) }));
    if (!arg) return "";
    if (kind === "ipa") {
      const [word, , transcription] = partition(arg, " ");
      if (!transcription) return word;
      return add(intent("phoneme", { text: word, ipa: transcription.trim() }));
    }
    return add(intent(kind as "spell" | "em", { text: arg }));
  };

  let out = sub(SSML_BREAK, text, ssml);
  out = sub(INTENT_TAG, out, tag);
  return [out, list];
}

/** Split text into [segment, intentIndex] pairs; plain text has index null. */
export function splitOnSentinels(text: string): [string, number | null][] {
  const parts: [string, number | null][] = [];
  let pos = 0;
  SENTINEL.lastIndex = 0;
  for (const m of text.matchAll(SENTINEL)) {
    const start = m.index ?? 0;
    if (start > pos) parts.push([text.slice(pos, start), null]);
    parts.push(["", parseInt(m[1], 10)]);
    pos = start + m[0].length;
  }
  if (pos < text.length) parts.push([text.slice(pos), null]);
  return parts;
}

export function stripSentinels(text: string): string {
  return sub(SENTINEL, text, () => "");
}

export function sentinelPattern(): RegExp {
  return re(`${SENTINEL_OPEN}(\\d+)${SENTINEL_CLOSE}`);
}
