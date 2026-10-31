/** Stage 3: compile. Render pacing intents in the target provider's syntax and escape text. */

import { Recorder } from "./changes.js";
import { Intent, splitOnSentinels } from "./intents.js";
import { Profile } from "./profiles/index.js";
import { Match, escapeXml, format, fullmatch, isSpace, re, rstrip, sub } from "./util.js";

const STAGE = "compile";

const UNKNOWN_TAG = re(String.raw`\[([^\[\]\n]{1,60})\]`);
const WORDY = re("[A-Za-zÀ-ÿĞğİıŞşÇçÖöÜü ,'\\-]+");

type Spec = Record<string, unknown>;

function spec(profile: Profile, name: string): Spec {
  return (profile.intents[name] ?? {}) as Spec;
}

/** Render a pause as punctuation. `prev` is the text so far (used to avoid doubling). */
function punctuationPause(prev: string, ms: number): string {
  const tail = rstrip(prev);
  if (!tail) return ""; // a pause before any text: nothing to pause after
  const last = tail[tail.length - 1];
  if (ms <= 300) {
    if (".!?,;:…".includes(last)) return " ";
    return ", ";
  }
  if (".!?…".includes(last)) return ms <= 1000 ? " " : "\n";
  if (ms <= 1000) return "... ";
  return "...\n";
}

function renderPause(ms: number, s: Spec, prev: string): string {
  const render = (s.render as string | undefined) ?? "punctuation";
  if (render === "punctuation") return punctuationPause(prev, ms);
  const lo = (s.min_ms as number | undefined) ?? 0;
  const hi = s.max_ms as number | undefined | null;
  let v = Math.max(ms, lo);
  if (hi !== undefined && hi !== null) v = Math.min(v, hi);
  const seconds = String(v / 1000);
  return format(render, { ms: v, s: seconds });
}

function renderSpell(text: string, s: Spec): string {
  const render = (s.render as string | undefined) ?? "spaced";
  if (render === "spaced") return Array.from(text).filter((ch) => !isSpace(ch)).map((ch) => ch.toUpperCase()).join(" ");
  return format(render, { text });
}

function renderEm(text: string, s: Spec): string {
  const render = (s.render as string | undefined) ?? "{text}";
  return format(render, { text });
}

/** Phoneme tag where the provider takes one, else the respelling, else the word. */
function renderPhoneme(intent: Intent, profile: Profile): string {
  const esc = profile.escape === "xml" ? escapeXml : (t: string) => t;
  const s = spec(profile, "phoneme");
  if (intent.ipa && s.render) return format(s.render as string, { text: esc(intent.text), ipa: esc(intent.ipa) });
  if (intent.say) return esc(intent.say);
  return esc(intent.text);
}

export function compileText(text: string, intents: Intent[], profile: Profile, recorder?: Recorder): string {
  const rec = recorder ?? new Recorder();
  const out: string[] = [];
  for (const [segment, idx] of splitOnSentinels(text)) {
    if (idx === null) {
      let seg = unknownTags(segment, profile, rec);
      if (profile.escape === "xml") {
        const esc = escapeXml(seg);
        rec.add(STAGE, "compile.escape.xml", seg, esc, "escaped & < > for SSML");
        seg = esc;
      }
      out.push(seg);
      continue;
    }
    const intent = intents[idx];
    const prev = out.join("");
    let rendered: string;
    if (intent.kind === "pause") {
      rendered = renderPause(intent.ms, spec(profile, "pause"), prev);
      if (out.length && (rendered.startsWith(",") || rendered.startsWith(".")) && prev.endsWith(" ")) {
        out[out.length - 1] = rstrip(out[out.length - 1], " ");
      }
      rec.add(STAGE, "compile.pause", `[pause ${intent.ms}ms]`, rendered, `pause rendered for ${profile.id}`);
    } else if (intent.kind === "phoneme") {
      rendered = renderPhoneme(intent, profile);
      rec.add(STAGE, "compile.phoneme", intent.text, rendered, `pronunciation rendered for ${profile.id}`);
    } else if (intent.kind === "spell") {
      const body = profile.escape === "xml" ? escapeXml(intent.text) : intent.text;
      rendered = renderSpell(body, spec(profile, "spell"));
      rec.add(STAGE, "compile.spell", `[spell ${intent.text}]`, rendered, `spell-out rendered for ${profile.id}`);
    } else {
      const body = profile.escape === "xml" ? escapeXml(intent.text) : intent.text;
      rendered = renderEm(body, spec(profile, "emphasis"));
      rec.add(STAGE, "compile.emphasis", `[em ${intent.text}]`, rendered, `emphasis rendered for ${profile.id}`);
    }
    out.push(rendered);
  }
  let result = out.join("");
  result = result.replace(/[ \t]{2,}/g, " ");
  result = result.replace(/ +\n/g, "\n");
  result = result.replace(/\n +/g, "\n");
  return result.trim();
}

/** Bracket tags the pipeline does not know: pass through on audio-tag models, drop elsewhere. */
function unknownTags(segment: string, profile: Profile, rec: Recorder): string {
  return sub(UNKNOWN_TAG, segment, (m: Match) => {
    const body = m[1].trim();
    const wordy = fullmatch(WORDY, body) !== null;
    if (profile.audioTags && wordy) return m[0];
    rec.add(STAGE, "compile.unknown_tag", m[0], "", "bracket tag removed; this model does not read audio tags");
    return "";
  });
}
