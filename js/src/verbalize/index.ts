/** Stage 2: verbalize. Rewrite only the tokens a TTS model is likely to misread.
 *
 * Each language has an ordered list of rules. A rule is a regex and a function
 * that returns the spoken form; it fires only on the pattern, so ordinary prose
 * and ordinary numbers are left for the model, which reads them well.
 * Sentinels from the intent stage are never touched.
 */

import { Recorder } from "../changes.js";
import { Options } from "../clean.js";
import { SENTINEL_CLOSE, SENTINEL_OPEN } from "../intents.js";
import { Match, finditer, re, sub } from "../util.js";

const STAGE = "verbalize";

export interface Rule {
  id: string;
  pattern: RegExp;
  /** (match, locale) -> replacement, or null to leave the match alone */
  render: (m: Match, locale: string) => string | null;
  note: string;
}

export function rule(id: string, pattern: RegExp, render: Rule["render"], note = ""): Rule {
  return { id, pattern, render, note };
}

const SENTINEL = re(`${SENTINEL_OPEN}\\d+${SENTINEL_CLOSE}`);

let currentOptions: Partial<Options> | null | undefined = null;

/** Read a field of the Options the current verbalize() call runs with. */
export function option<K extends keyof Options>(name: K, fallback: Options[K]): Options[K] {
  const o = currentOptions as Record<string, unknown> | null | undefined;
  return o && o[name] !== undefined ? (o[name] as Options[K]) : fallback;
}

let rulesEn: Rule[] | null = null;
let rulesTr: Rule[] | null = null;

export function registerRules(lang: string, rules: Rule[]): void {
  if (lang === "en") rulesEn = rules;
  else if (lang === "tr") rulesTr = rules;
}

function rulesFor(locale: string): Rule[] {
  const lang = (locale || "en").split("-")[0].split("_")[0].toLowerCase();
  if (lang === "en") return rulesEn ?? [];
  if (lang === "tr") return rulesTr ?? [];
  return [];
}

export function verbalize(text: string, locale = "en-US", recorder?: Recorder, opts?: Partial<Options> | null): string {
  const rec = recorder ?? new Recorder();
  const rules = rulesFor(locale);
  if (!rules.length) return text;
  const previous = currentOptions;
  currentOptions = opts;
  try {
    return run(text, rules, locale, rec);
  } finally {
    currentOptions = previous;
  }
}

function run(text: string, rules: Rule[], locale: string, rec: Recorder): string {
  const sentinels = finditer(SENTINEL, text).map((m) => m[0]);
  const parts = text.split(SENTINEL);
  const out: string[] = [];
  parts.forEach((segment, i) => {
    out.push(apply(segment, rules, locale, rec));
    if (i < sentinels.length) out.push(sentinels[i]);
  });
  return out.join("");
}

function apply(segment: string, rules: Rule[], locale: string, rec: Recorder): string {
  let work = segment;
  for (const r of rules) {
    work = sub(r.pattern, work, (m) => {
      const next = r.render(m, locale);
      if (next === null || next === undefined || next === m[0]) return m[0];
      rec.add(STAGE, r.id, m[0], next, r.note);
      return next;
    });
  }
  return work;
}
