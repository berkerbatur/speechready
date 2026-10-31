/** One pronunciation lexicon, applied in the pipeline and exported to each vendor's format.
 *
 * An entry says how a word is pronounced in one of three ways:
 * - `ipa`: an IPA transcription, rendered as a phoneme tag where the provider
 *   accepts one (Azure, Google, Polly) and exported to lexicon files;
 * - `say`: a respelling or alias ("engine X", "sequel") that replaces the word in
 *   the text, which works on every provider;
 * - `spell: true`: the word is read letter by letter.
 *
 * When a provider cannot take a phoneme tag, an entry falls back to `say`, then
 * to `spell`, then leaves the word alone.
 */

import { Intent, SENTINEL_CLOSE, SENTINEL_OPEN, intent } from "./intents.js";
import { Profile } from "./profiles/index.js";
import { W, escapeRe, escapeXml, re, sub } from "./util.js";

export interface Entry {
  word: string;
  ipa: string;
  say: string;
  spell: boolean;
  case_sensitive: boolean;
}

export type EntryInput = Partial<Entry> & { word: string };

export function entry(e: EntryInput): Entry {
  return { ipa: "", say: "", spell: false, case_sensitive: false, ...e };
}

function entryIntent(e: Entry, matched: string): Intent {
  if (e.spell && !e.ipa && !e.say) return intent("spell", { text: matched });
  return intent("phoneme", { text: matched, ipa: e.ipa, say: e.say });
}

export class Lexicon {
  entries: Entry[];
  locale: string;

  constructor(entries: EntryInput[] = [], locale = "en-US") {
    this.entries = entries.map(entry);
    this.locale = locale;
  }

  // --- construction ---------------------------------------------------------------

  static fromEntries(entries: EntryInput[], locale = "en-US"): Lexicon {
    return new Lexicon(entries, locale);
  }

  /** Build from a parsed lexicon document (`{locale, entries}`), e.g. `JSON.parse` of a lexicon file. */
  static fromObject(data: { locale?: string; entries?: EntryInput[] }): Lexicon {
    return new Lexicon(data.entries ?? [], data.locale ?? "en-US");
  }

  /** Read a `.json` lexicon file, or a `.yaml` one when the optional `yaml` package is installed. Node only. */
  static async load(path: string): Promise<Lexicon> {
    const fs = await import("node:fs/promises");
    const text = await fs.readFile(path, "utf-8");
    if (/\.ya?ml$/i.test(path)) {
      let yaml: { parse: (s: string) => unknown };
      try {
        yaml = (await import("yaml")) as unknown as { parse: (s: string) => unknown };
      } catch {
        throw new Error("reading a YAML lexicon needs the `yaml` package (npm install yaml); JSON lexicons need nothing");
      }
      return Lexicon.fromObject(yaml.parse(text) as { locale?: string; entries?: EntryInput[] });
    }
    return Lexicon.fromObject(JSON.parse(text));
  }

  toObject(): { locale: string; entries: Record<string, unknown>[] } {
    return {
      locale: this.locale,
      entries: this.entries.map((e) => {
        const out: Record<string, unknown> = {};
        for (const [k, v] of Object.entries({ word: e.word, ipa: e.ipa, say: e.say, spell: e.spell, case_sensitive: e.case_sensitive })) {
          if (v) out[k] = v;
        }
        return out;
      }),
    };
  }

  // --- applying to text ------------------------------------------------------------

  /** Replace every lexicon word in `text` with an intent sentinel; appends to `intents`. */
  apply(text: string, intents: Intent[]): string {
    if (!this.entries.length) return text;
    let work = text;
    const ordered = [...this.entries].sort((a, b) => b.word.length - a.word.length);
    for (const e of ordered) {
      const flags = e.case_sensitive ? "" : "i";
      const pattern = re(`(?<![${W}${SENTINEL_OPEN}${SENTINEL_CLOSE}])${escapeRe(e.word)}(?![${W}])`, flags);
      work = sub(pattern, work, (m) => {
        intents.push(entryIntent(e, m[0]));
        return `${SENTINEL_OPEN}${intents.length - 1}${SENTINEL_CLOSE}`;
      });
    }
    return work;
  }

  // --- export ----------------------------------------------------------------------------

  /** Pronunciation Lexicon Specification XML, accepted by ElevenLabs, Azure and Amazon Polly. */
  toPls(alphabet = "ipa"): string {
    const lines = [
      '<?xml version="1.0" encoding="UTF-8"?>',
      `<lexicon version="1.0" xmlns="http://www.w3.org/2005/01/pronunciation-lexicon" alphabet="${alphabet}" xml:lang="${this.locale}">`,
    ];
    for (const e of this.entries) {
      lines.push("  <lexeme>");
      lines.push(`    <grapheme>${escapeXml(e.word)}</grapheme>`);
      if (e.ipa) lines.push(`    <phoneme>${escapeXml(e.ipa)}</phoneme>`);
      else if (e.say) lines.push(`    <alias>${escapeXml(e.say)}</alias>`);
      else if (e.spell) lines.push(`    <alias>${escapeXml(Array.from(e.word).join(" "))}</alias>`);
      lines.push("  </lexeme>");
    }
    lines.push("</lexicon>");
    return lines.join("\n") + "\n";
  }

  /** Google Cloud TTS custom pronunciations (v1beta1 `customPronunciations`). IPA entries only. */
  toGoogleJson(): string {
    const items = this.entries
      .filter((e) => e.ipa)
      .map((e) => ({ phrase: e.word, phoneticEncoding: "PHONETIC_ENCODING_IPA", pronunciation: e.ipa }));
    return JSON.stringify({ pronunciations: items }, null, 2) + "\n";
  }

  toJson(): string {
    return JSON.stringify(this.toObject(), null, 2) + "\n";
  }

  /** The upload file for a provider profile, or null when the provider takes no lexicon. */
  exportFor(profile: Profile): string | null {
    if (profile.lexiconFormat === "none") return null;
    return this.export(profile.lexiconFormat, profile.lexiconAlphabet);
  }

  /** `pls`, `google`, or `json`. */
  export(fmt: string, alphabet = "ipa"): string {
    if (fmt === "pls") return this.toPls(alphabet);
    if (fmt === "google") return this.toGoogleJson();
    if (fmt === "json") return this.toJson();
    throw new Error(`unknown lexicon format ${JSON.stringify(fmt)}; use pls, google or json`);
  }
}
