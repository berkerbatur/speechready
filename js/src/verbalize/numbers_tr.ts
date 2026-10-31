/** Turkish number words and suffix helpers (vowel harmony, consonant softening). */

import { divmod, rpartition } from "../util.js";

const ONES = ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"];
const TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"];
const SCALES: [number, string][] = [[1e9, "milyar"], [1e6, "milyon"], [1e3, "bin"]];

const VOWELS = "aeıioöuü";
const BACK = new Set("aıou");
const ROUND = new Set("oöuü");
const VOICELESS = new Set("çfhkpsşt");

export function cardinal(n: number): string {
  if (n < 0) return "eksi " + cardinal(-n);
  if (n === 0) return "sıfır";
  const parts: string[] = [];
  let rest = n;
  for (const [value, name] of SCALES) {
    if (rest >= value) {
      const [head, r] = divmod(rest, value);
      rest = r;
      parts.push(head === 1 && value === 1000 ? name : `${cardinal(head)} ${name}`);
    }
  }
  if (rest >= 100) {
    const [head, r] = divmod(rest, 100);
    rest = r;
    parts.push(head === 1 ? "yüz" : `${ONES[head]} yüz`);
  }
  if (rest >= 10) {
    const [head, r] = divmod(rest, 10);
    rest = r;
    parts.push(TENS[head]);
  }
  if (rest > 0) parts.push(ONES[rest]);
  return parts.join(" ");
}

export function lastVowel(word: string): string {
  const lower = Array.from(word.toLowerCase());
  for (let i = lower.length - 1; i >= 0; i--) {
    if (VOWELS.includes(lower[i])) return lower[i];
  }
  return "e";
}

/** Four-way harmony vowel (ı i u ü) for the last vowel of `word`. */
export function harmonyI(word: string): string {
  const v = lastVowel(word);
  if (BACK.has(v)) return ROUND.has(v) ? "u" : "ı";
  return ROUND.has(v) ? "ü" : "i";
}

/** Two-way harmony vowel (a e). */
export function harmonyA(word: string): string {
  return BACK.has(lastVowel(word)) ? "a" : "e";
}

function vowelCount(word: string): number {
  let n = 0;
  for (const ch of word) if (VOWELS.includes(ch)) n++;
  return n;
}

/** Final consonant softening before a vowel-initial suffix: dört -> dörd, çeyrek -> çeyreğ. */
export function soften(word: string): string {
  if (word.endsWith("dört")) return word.slice(0, -1) + "d";
  if (word.endsWith("k") && vowelCount(word) >= 2) return word.slice(0, -1) + "ğ";
  return word;
}

/** Join a spoken word and the suffix the writer attached to the numeral or abbreviation.
 *
 * The writer harmonised the suffix against what they wrote (3'te -> üçte works
 * as is), but a buffer consonant may be wrong for the spoken word: yarım + sı
 * -> yarımı, kilometre + i -> kilometreyi.
 */
export function attach(word: string, suffix: string): string {
  if (!suffix) return word;
  let w = word;
  let s = suffix;
  const endsInVowel = VOWELS.includes(w[w.length - 1]);
  if ("sy".includes(s[0]) && s.length > 1 && VOWELS.includes(s[1]) && !endsInVowel) {
    s = s.slice(1); // drop the buffer consonant after a consonant
  } else if (VOWELS.includes(s[0]) && endsInVowel) {
    s = "y" + s; // insert a buffer consonant between two vowels
  }
  if (VOWELS.includes(s[0])) w = soften(w);
  return w + s;
}

/** Re-harmonise a suffix written against an abbreviation (TL'ye, 1/4'ü) for the spoken word (liraya, çeyreği). */
export function reharmonize(word: string, suffix: string): string {
  if (!suffix) return suffix;
  const two = harmonyA(word);
  const four = harmonyI(word);
  return Array.from(suffix).map((ch) => ("ae".includes(ch) ? two : "ıiuü".includes(ch) ? four : ch)).join("");
}

/** üçüncü, dördüncü, yirmi birinci. */
export function ordinal(n: number): string {
  const words = cardinal(n);
  let [head, , last] = rpartition(words, " ");
  const v = harmonyI(last);
  if (VOWELS.includes(last[last.length - 1])) last = last + "nc" + v;
  else last = soften(last) + v + "nc" + v;
  return (head ? head + " " : "") + last;
}

/** üç -> üçte, dört -> dörtte, on -> onda, beş -> beşte. */
export function locative(word: string): string {
  const a = harmonyA(word);
  const consonant = VOICELESS.has(word[word.length - 1]) ? "t" : "d";
  return word + consonant + a;
}

export function digits(s: string): string {
  const out: string[] = [];
  for (const ch of s) {
    if (/\d/.test(ch)) out.push(ONES[parseInt(ch, 10)]);
    else if (ch === "+") out.push("artı");
  }
  return out.join(" ");
}

export function decimal(whole: string, frac: string | null | undefined): string {
  let text = cardinal(parseInt(whole.replace(/\./g, ""), 10));
  if (frac) text += " virgül " + (frac.startsWith("0") ? digits(frac) : cardinal(parseInt(frac, 10)));
  return text;
}
