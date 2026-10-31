/** Stage 4: chunk. Sentence segmentation, streaming segmentation, and packing under a limit.
 *
 * Rules that keep prosody intact:
 * - a newline is a hard boundary (blocks from the clean stage never merge);
 * - a sentence ends at . ! ? … followed by whitespace and then an uppercase
 *   letter, a digit, an opening quote or bracket, or a tag;
 * - a known abbreviation, a single-letter initial, or a number before the full
 *   stop never ends a sentence;
 * - a sentence that is longer than the limit is split at clause punctuation,
 *   then at spaces, and only as a last resort mid-word.
 */

import { SENTINEL_OPEN } from "./intents.js";
import { Match, codePoints, finditer, fullmatch, isAlpha, isDigit, isUpper, re, rstrip, strip, utf8Length } from "./util.js";

const ABBREVIATIONS: Record<string, Set<string>> = {
  en: new Set(
    `mr mrs ms dr prof sr jr st mt ft vs etc e.g i.e cf no nos inc ltd co corp llc dept est approx
    jan feb mar apr jun jul aug sep sept oct nov dec mon tue wed thu fri sat sun a.m p.m
    u.s u.k e.u ph.d m.d b.a m.a b.sc m.sc fig vol pp ed eds rev gen col lt sgt capt cmdr hon
    ave blvd rd hwy tel ext dept univ assn bros`.split(/\s+/),
  ),
  tr: new Set(
    `dr prof doç yrd av sn vb vs vd örn bkz yy t.c no sok cad apt mah alb yzb bşk müh
    oca şub mar nis haz tem ağu eyl eki kas ara ltd şti a.ş san tic dk sa sn bk ör
    hz sf s c çev der haz üniv fak böl hst bul uzm öğr yrd tel`.split(/\s+/),
  ),
};

const END = re(String.raw`(?<end>[.!?…]+)(?<close>["'”’)\]»]*)(?<space>\s+)(?=(?<next>\S))`);
const WORD_BEFORE = re(String.raw`(\S+)$`);
const CLAUSE = re(String.raw`[,;:—–]\s+|\s+[-]\s+`);
const DOTTED = re("[a-z](\\.[a-z])+");
const LIST_MARKER = re(String.raw`\d{1,3}\.`);

function lang(locale: string): string {
  return (locale || "en").split("-")[0].split("_")[0].toLowerCase();
}

function abbreviations(locale: string): Set<string> {
  return ABBREVIATIONS[lang(locale)] ?? new Set();
}

function isBoundary(text: string, m: Match, abbrs: Set<string>): boolean {
  const g = m.groups ?? {};
  const end = g.end ?? "";
  const nxt = g.next ?? "";
  const before = text.slice(0, m.index);
  const wordM = WORD_BEFORE.exec(before);
  WORD_BEFORE.lastIndex = 0;
  const word = wordM ? wordM[1] : "";
  const core = strip(word, "(\"'“”‘’[").toLowerCase();

  if ((g.space ?? "").includes("\n")) return true;
  if (end.startsWith(".") && !end.includes("…") && !end.includes("!") && !end.includes("?")) {
    if (abbrs.has(core) || abbrs.has(rstrip(core, "."))) return false;
    if (core.length === 1 && isAlpha(core)) return false; // initial: "J. R. R. Tolkien"
    if (isDigit(core) && !isUpper(nxt[0])) return false; // ordinal or list number: "3. madde"
    if (fullmatch(DOTTED, core)) return false; // dotted abbreviation not in the list, e.g. "p.s"
  }
  const first = nxt[0];
  if ("\"'“‘([«<".includes(first) || first === SENTINEL_OPEN) return true;
  if (isUpper(first) || isDigit(first)) return true;
  if ("¿¡".includes(first)) return true;
  return false;
}

/** Split text into sentences. Newlines are hard boundaries. Empty sentences are dropped. */
export function splitSentences(text: string, locale = "en-US"): string[] {
  const abbrs = abbreviations(locale);
  const out: string[] = [];
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (!line) continue;
    let start = 0;
    for (const m of finditer(END, line)) {
      const g = m.groups ?? {};
      const endAll = m.index + m[0].length;
      const endClose = m.index + (g.end ?? "").length + (g.close ?? "").length;
      if (fullmatch(LIST_MARKER, line.slice(start, endAll).trim())) continue; // "1. Open the app": the number is the item's marker, not a sentence
      if (isBoundary(line, m, abbrs)) {
        out.push(line.slice(start, endClose).trim());
        start = endAll;
      }
    }
    const tail = line.slice(start).trim();
    if (tail) out.push(tail);
  }
  return out;
}

/** Streaming sentence segmenter for LLM token feeds.
 *
 * `push(text)` returns the sentences that are now complete; `flush()` returns
 * whatever is left. A boundary is only confirmed once text after it arrives,
 * so a sentence is never cut at "Dr." or "3.14" because the stream paused there.
 */
export class Segmenter {
  locale: string;
  maxBuffer: number | null;
  private buffer = "";

  constructor(init: { locale?: string; maxBuffer?: number | null } = {}) {
    this.locale = init.locale ?? "en-US";
    this.maxBuffer = init.maxBuffer ?? null;
  }

  push(text: string): string[] {
    this.buffer += text;
    const done: string[] = [];
    for (;;) {
      const nl = this.buffer.indexOf("\n");
      if (nl < 0) break;
      const head = this.buffer.slice(0, nl);
      this.buffer = this.buffer.slice(nl + 1);
      done.push(...splitSentences(head, this.locale));
    }
    const sentences = splitSentences(this.buffer, this.locale);
    if (sentences.length > 1) {
      done.push(...sentences.slice(0, -1));
      // keep the unconfirmed tail exactly as it stands (leading spaces dropped)
      const idx = this.buffer.lastIndexOf(sentences[sentences.length - 1]);
      this.buffer = idx >= 0 ? this.buffer.slice(idx) : this.buffer;
    }
    if (this.maxBuffer && this.buffer.length > this.maxBuffer) {
      const cut = lastClauseCut(this.buffer, this.maxBuffer);
      if (cut > 0) {
        done.push(this.buffer.slice(0, cut).trim());
        this.buffer = this.buffer.slice(cut).replace(/^\s+/, "");
      }
    }
    return done.filter((s) => s);
  }

  flush(): string[] {
    const rest = this.buffer;
    this.buffer = "";
    return splitSentences(rest, this.locale);
  }
}

function lastClauseCut(text: string, limit: number): number {
  const window = text.slice(0, limit);
  let best = -1;
  for (const m of finditer(CLAUSE, window)) best = m.index + m[0].length;
  if (best > 0) return best;
  const sp = window.lastIndexOf(" ");
  return sp > 0 ? sp + 1 : limit;
}

function size(text: string, unit: string): number {
  return unit === "bytes" ? utf8Length(text) : codePoints(text);
}

/** Split one over-long sentence at clause marks, then spaces, then hard. */
function splitLong(sentence: string, limit: number, unit: string): string[] {
  if (size(sentence, unit) <= limit) return [sentence];
  const pieces: string[] = [];
  let rest = sentence;
  while (size(rest, unit) > limit) {
    let window = rest;
    while (size(window, unit) > limit) window = window.slice(0, Math.max(1, Math.floor(window.length * 0.9)));
    let cut = -1;
    for (const m of finditer(CLAUSE, window)) cut = m.index + m[0].length;
    if (cut <= 0) cut = window.lastIndexOf(" ") + 1;
    if (cut <= 0) cut = window.length;
    pieces.push(rest.slice(0, cut).trim());
    rest = rest.slice(cut).trim();
  }
  if (rest) pieces.push(rest);
  return pieces;
}

/** Greedily join sentences into chunks no larger than `limit`. null = one chunk. */
export function pack(sentences: string[], limit: number | null | undefined, unit = "chars", joiner = " "): string[] {
  if (limit === null || limit === undefined) return sentences.length ? [sentences.join(joiner)] : [];
  const chunks: string[] = [];
  let current = "";
  for (const s of sentences) {
    for (const piece of splitLong(s, limit, unit)) {
      const candidate = current ? current + joiner + piece : piece;
      if (current && size(candidate, unit) > limit) {
        chunks.push(current);
        current = piece;
      } else {
        current = candidate;
      }
    }
  }
  if (current) chunks.push(current);
  return chunks;
}
