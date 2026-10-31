/** The pipeline: clean -> verbalize -> compile -> chunk, with a change log. */

import { Change, Recorder } from "./changes.js";
import { pack, splitSentences } from "./chunk.js";
import { Options, clean } from "./clean.js";
import { compileText } from "./compile.js";
import { Intent, extract, sentinelPattern } from "./intents.js";
import { EntryInput, Lexicon } from "./lexicon.js";
import { Profile, resolveProfile } from "./profiles/index.js";
import { sub } from "./util.js";
import { verbalize } from "./verbalize/index.js";
import "./verbalize/en.js";
import "./verbalize/tr.js";

export interface Prepared {
  /** The full compiled text. */
  text: string;
  /** The same text split under the model's request limit. */
  chunks: string[];
  /** Every rewrite: rule, before, after, note. */
  changes: Change[];
  profile: Profile;
  locale: string;
}

export interface PrepareInit {
  provider?: string | null;
  model?: string | null;
  /** A profile picked directly; overrides provider and model. */
  profile?: Profile | null;
  locale?: string;
  /** Overrides the profile's request limit (null = no limit, undefined = the profile's). */
  limit?: number | null;
  options?: Partial<Options> | null;
  /** A Lexicon, or its entries; its words are pronounced as it says. */
  lexicon?: Lexicon | EntryInput[] | null;
}

/** Prepare `text` for the given provider and model.
 *
 * Returns the full compiled text, the request-sized chunks, and every change made.
 */
export function prepare(text: string, init: PrepareInit = {}): Prepared {
  const locale = init.locale ?? "en-US";
  const lex = Array.isArray(init.lexicon) ? Lexicon.fromEntries(init.lexicon, locale) : init.lexicon ?? null;
  const prof = init.profile ?? resolveProfile(init.provider ?? null, init.model ?? null);
  const rec = new Recorder();

  let [work, intents] = extract(text);
  work = clean(work, init.options, rec, locale);
  [work, intents] = extract(work, intents);
  if (lex) {
    const before = work;
    work = lex.apply(work, intents);
    rec.add("lexicon", "lexicon.apply", before, work, "lexicon words marked for pronunciation");
  }
  work = verbalize(work, locale, rec, init.options);
  work = compileText(work, intents, prof, rec);

  const maxSize = init.limit !== undefined ? init.limit : prof.limitFor(init.model ?? null);
  const sentences = splitSentences(work, locale);
  const chunks = pack(sentences, maxSize, prof.limitUnit, " ");
  return { text: work, chunks, changes: readable(rec.changes, intents), profile: prof, locale };
}

function intentTag(intent: Intent): string {
  if (intent.kind === "pause") return `[pause ${intent.ms}ms]`;
  if (intent.kind === "phoneme") return `[ipa ${intent.text} ${intent.ipa || intent.say}]`;
  return `[${intent.kind} ${intent.text}]`;
}

/** Show intents in the change log as the tags the developer wrote, not as sentinels. */
function readable(changes: Change[], intents: Intent[]): Change[] {
  const pattern = sentinelPattern();
  const fix = (text: string): string => sub(pattern, text, (m) => intentTag(intents[parseInt(m[1], 10)]));
  return changes.map((c) => ({ ...c, before: fix(c.before), after: fix(c.after) }));
}
