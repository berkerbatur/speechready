/** Lexicons bundled with the package, from the repository's `spec/lexicons`.
 *
 *     prepare("API'yi çağır.", { locale: "tr-TR", lexicon: loadLexicon("tr-tech") }).text
 *     prepare("API'yi çağır.", { locale: "tr-TR", lexicon: "tr-tech" }).text   // the same, by name
 */

import { EntryInput, Lexicon } from "../lexicon.js";
import { LEXICON_DATA } from "./data.js";

/** Names of the bundled lexicons, e.g. ["tr-tech"]. */
export function listLexicons(): string[] {
  return Object.keys(LEXICON_DATA).sort();
}

/** A bundled lexicon by name; a new object each call, so it can be extended. */
export function loadLexicon(name: string): Lexicon {
  const data = LEXICON_DATA[name];
  if (!data) throw new Error(`unknown bundled lexicon ${JSON.stringify(name)}; known: ${listLexicons().join(", ")}`);
  return Lexicon.fromObject({ locale: data.locale, entries: (data.entries ?? []) as EntryInput[] });
}
