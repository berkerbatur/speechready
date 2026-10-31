/** Turkish verbalization rules, in the order they run.
 *
 * Turkish text carries case and possessive suffixes on numerals with an
 * apostrophe (3'te, 1990'da, %50'si) and uses a dot for thousands and a comma
 * for decimals. Foreign TTS models get all of these wrong, so they are the
 * first things this module rewrites.
 */

import { B, Match, W, escapeRe, findall, fullmatch, group, isDigit, partition, re } from "../util.js";
import { Rule, option, registerRules, rule } from "./index.js";
import { attach, cardinal, decimal, digits, locative, ordinal, reharmonize } from "./numbers_tr.js";

const MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
const APOS = "['’]";
const LOWER = "a-zçğıöşü";
const UPPER = "A-ZÇĞİÖŞÜ";

// English letter names as Turkish speakers say them, for foreign tech acronyms (npm, css, sql).
const EN_LETTERS: Record<string, string> = Object.fromEntries(
  Array.from("abcdefghijklmnopqrstuvwxyz").map((ch, i) => [ch, ["ey", "bi", "si", "di", "i", "ef", "ci", "eyç", "ay", "cey", "key", "el", "em", "en", "o", "pi", "kyu", "ar", "es", "ti", "yu", "vi", "dabılyu", "eks", "vay", "zi"][i]]),
);
const UNIT_ABBREVIATIONS = new Set(["km", "kg", "cm", "mm", "mg", "ml", "lt", "sn", "dk", "hz", "gr", "kw", "mb", "gb", "kb", "tb", "ms", "vb", "vs", "bkz", "yy", "tl", "krş", "tr", "st", "nr", "sk", "mh", "cd", "pk"]);

function foreignAcronym(m: Match): string | null {
  const word = m[0];
  if (!option("foreign_acronyms", true) || UNIT_ABBREVIATIONS.has(word)) return null;
  return Array.from(word).map((ch) => EN_LETTERS[ch]).join(" ");
}

const int = (s: string | undefined): number => parseInt(s ?? "", 10);

function dateWords(y: number, m: number, d: number, suffix = ""): string | null {
  if (!(m >= 1 && m <= 12 && d >= 1 && d <= 31)) return null;
  let yy = y;
  if (yy < 100) yy += yy < 70 ? 2000 : 1900;
  return `${cardinal(d)} ${MONTHS[m - 1]} ${attach(cardinal(yy), suffix)}`;
}

const dateDmy = (m: Match): string | null => dateWords(int(m[3]), int(m[2]), int(m[1]), group(m, 4) ?? "");
const dateIso = (m: Match): string | null => dateWords(int(m[1]), int(m[2]), int(m[3]), group(m, 4) ?? "");

/** How Turkish speakers say one group of a phone number: 0532 -> sıfır beş yüz otuz iki, 00 -> sıfır sıfır, 45 -> kırk beş. */
function groupWords(groupText: string): string {
  const words: string[] = [];
  let g = groupText;
  if (g.startsWith("+")) {
    words.push("artı");
    g = g.slice(1);
  }
  const stripped = g.replace(/^0+/, "");
  for (let i = 0; i < g.length - stripped.length; i++) words.push("sıfır");
  if (stripped) words.push(cardinal(parseInt(stripped, 10)));
  return words.join(" ");
}

function digitGroups(m: Match): string | null {
  const raw = m[1];
  const suffix = group(m, 2) ?? "";
  const count = (raw.match(/\d/g) ?? []).length;
  if (count < 7 || count > 16) return null;
  const groups = raw.split(/[\s.\-()]+/u).filter((g) => g);
  const spoken = groups.map(groupWords);
  spoken[spoken.length - 1] = attach(spoken[spoken.length - 1], suffix);
  return spoken.join(", ");
}

function timeWords(hh: string, mm: string): string {
  const h = parseInt(hh, 10);
  const minute = parseInt(mm, 10);
  const hour = cardinal(h);
  if (minute === 0) return `${hour} sıfır sıfır`;
  return `${hour} ${mm[0] !== "0" ? cardinal(minute) : "sıfır " + cardinal(minute)}`;
}

const time = (m: Match): string => attach(timeWords(m[1], m[2]), group(m, 3) ?? "");
const timeRange = (m: Match): string => `${timeWords(m[1], m[2])} ile ${timeWords(m[3], m[4])}`;

const CURRENCY: Record<string, [string, string]> = {
  "₺": ["lira", "kuruş"], TL: ["lira", "kuruş"], TRY: ["lira", "kuruş"],
  $: ["dolar", "sent"], USD: ["dolar", "sent"],
  "€": ["avro", "sent"], EUR: ["avro", "sent"],
  "£": ["sterlin", "peni"], GBP: ["sterlin", "peni"],
};

function currencyPostfix(m: Match): string {
  const [whole, , frac] = partition(m[1], ",");
  const scale = group(m, 2) ? ` ${m[2]}` : "";
  const [unitWord] = CURRENCY[m[3]];
  return `${decimal(whole, frac || null)}${scale} ${attach(unitWord, reharmonize(unitWord, group(m, 4) ?? ""))}`;
}

function money(symbol: string, whole: string, frac: string | undefined, suffix = ""): string {
  const [unitWord, subWord] = CURRENCY[symbol];
  const amount = cardinal(parseInt(whole.replace(/\./g, ""), 10));
  if (frac) {
    const cents = parseInt(frac.padEnd(2, "0").slice(0, 2), 10);
    if (cents) return `${amount} ${unitWord} ${cardinal(cents)} ${attach(subWord, reharmonize(subWord, suffix))}`;
  }
  return `${amount} ${attach(unitWord, reharmonize(unitWord, suffix))}`;
}

const currencyPrefix = (m: Match): string => money(m[1], m[2], group(m, 3), group(m, 4) ?? "");
const currencySuffix = (m: Match): string => money(m[3].toUpperCase(), m[1], group(m, 2), group(m, 4) ?? "");

function percent(m: Match): string {
  const number = group(m, 1) ?? group(m, 3) ?? "";
  const suffix = group(m, 2) ?? group(m, 4) ?? "";
  const [whole, , frac] = partition(number, ",");
  const words = decimal(whole, frac || null);
  return "yüzde " + attach(words, suffix);
}

const UNITS: Record<string, string> = {
  "km/sa": "kilometre", "km/s": "kilometre", km: "kilometre", cm: "santimetre", mm: "milimetre",
  kg: "kilogram", mg: "miligram", GB: "gigabayt", MB: "megabayt", KB: "kilobayt", TB: "terabayt",
  ms: "milisaniye", sn: "saniye", dk: "dakika", sa: "saat", "°C": "derece", "°": "derece",
};
const UNIT_ALTERNATION = Object.keys(UNITS).sort((a, b) => b.length - a.length).map(escapeRe).join("|");

function unit(m: Match): string {
  const number = m[1];
  const u = m[2];
  const suffix = group(m, 3) ?? "";
  const word = UNITS[u];
  if (u === "km/sa" || u === "km/s") return `saatte ${number} ${attach(word, reharmonize(word, suffix))}`;
  return `${number} ${attach(word, reharmonize(word, suffix))}`;
}

const FRACTION_NAMES: Record<string, string> = { "1/2": "yarım", "1/4": "çeyrek" };

function fraction(m: Match): string | null {
  const num = parseInt(m[1], 10);
  const den = parseInt(m[2], 10);
  const suffix = group(m, 3) ?? "";
  if (num >= den) return null;
  if (option("fractions", "spoken") === "division") return `${cardinal(num)} bölü ${attach(cardinal(den), suffix)}`;
  const named = FRACTION_NAMES[`${num}/${den}`];
  if (named) return attach(named, reharmonize(named, suffix));
  return `${locative(cardinal(den))} ${attach(cardinal(num), suffix)}`;
}

function range(m: Match): string | null {
  const a = m[1];
  const b = m[2];
  if (a.length > 4 || b.length > 4) return null;
  return `${a} ila ${b}`;
}

const thousands = (m: Match): string => attach(decimal(m[1], group(m, 2)), group(m, 3) ?? "");
const decimalComma = (m: Match): string => attach(decimal(m[1], m[2]), group(m, 3) ?? "");

const ORDINAL_SUFFIX = re("(?:[ıiuü]nc[ıiuü]|nc[ıiuü])");

function suffixedNumber(m: Match): string {
  const n = parseInt(m[1], 10);
  const suffix = m[2];
  if (fullmatch(ORDINAL_SUFFIX, suffix)) return ordinal(n);
  return attach(cardinal(n), suffix);
}

const ordinalDot = (m: Match): string => ordinal(parseInt(m[1], 10));

const ABBREVIATIONS: Record<string, string> = {
  vb: "ve benzeri", vs: "vesaire", vd: "ve diğerleri", örn: "örneğin", bkz: "bakınız",
  Dr: "Doktor", Prof: "Profesör", Doç: "Doçent", Av: "Avukat", Sn: "Sayın",
  No: "numara", no: "numara", Tel: "telefon", tel: "telefon", yy: "yüzyıl",
  Cad: "Caddesi", Sok: "Sokak", Mah: "Mahallesi", Apt: "Apartmanı", Bul: "Bulvarı",
  "T.C": "Türkiye Cumhuriyeti", Ltd: "Limited", Şti: "Şirketi", "A.Ş": "Anonim Şirketi",
  Üniv: "Üniversitesi", Fak: "Fakültesi", Böl: "Bölümü", Hst: "Hastanesi", Müh: "Mühendisi",
  Alb: "Albay", Yzb: "Yüzbaşı", Bşk: "Başkanı", Yrd: "Yardımcı", Uzm: "Uzman", Öğr: "Öğretim",
};
const ABBR_ALTERNATION = Object.keys(ABBREVIATIONS).sort((a, b) => b.length - a.length).map(escapeRe).join("|");

const abbreviation = (m: Match): string => ABBREVIATIONS[m[1]];

const VOWELS_UP = new Set("AEIİOÖUÜ");
const RUNS = re(`[${UPPER}]+|\\d+`);

function alnum(m: Match): string | null {
  const token = m[0];
  if (token.replace(/-/g, "").length < 4) return null;
  const runs = findall(RUNS, token);
  const out: string[] = [];
  for (const run of runs) {
    if (isDigit(run)) out.push(runs.length === 2 && run.length <= 2 ? cardinal(parseInt(run, 10)) : digits(run));
    else if (run.length >= 3 && Array.from(run).some((c) => VOWELS_UP.has(c))) out.push(run);
    else out.push(Array.from(run).join(" "));
  }
  return out.join(" ");
}

const SEP = String.raw`(?:[ \-]|\.(?!\s))`;
const SUFFIX = `(?:${APOS}([${LOWER}]+))?`;

export const RULES: Rule[] = [
  rule("verbalize.abbreviation", re(String.raw`(?<![${W}.])(${ABBR_ALTERNATION})\.(?![${LOWER}${UPPER}])`), abbreviation, "abbreviation read in full"),
  rule("verbalize.date.dmy", re(String.raw`${B}(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})${B}${SUFFIX}`), dateDmy, "date read as day, month name, year"),
  rule("verbalize.date.iso", re(String.raw`${B}(\d{4})-(\d{2})-(\d{2})${B}${SUFFIX}`), dateIso, "ISO date read as day, month name, year"),
  rule(
    "verbalize.phone",
    re(String.raw`(?<![${W}.])((?:\+?\d{1,3}${SEP})?(?:\(\d{2,4}\)[ \-]?|\d{2,4}${SEP})(?:\d{2,4}${SEP}){1,4}\d{2,4})${SUFFIX}(?![${W}\-]|[.,]\d)`),
    digitGroups,
    "digit groups read digit by digit with a pause between groups",
  ),
  rule("verbalize.number_sign", re(String.raw`#(?=\d)`), () => "numara ", "number sign read as a word"),
  rule("verbalize.acronym.foreign", re(String.raw`(?<![${W}'’.])[bcdfghjklmnpqrstvwxyz]{2,5}(?![${W}'’])`), foreignAcronym, "lowercase foreign acronym read with English letter names"),
  rule("verbalize.digits.long", re(String.raw`(?<![${W}.,])\d{7,}(?![${W}]|[.,]\d)`), (m) => digits(m[0]), "long digit string read digit by digit"),
  rule("verbalize.time.range", re(String.raw`${B}([01]?\d|2[0-3]):([0-5]\d)\s?[-–]\s?([01]?\d|2[0-3]):([0-5]\d)${B}`), timeRange, "time range read with 'ile'"),
  rule("verbalize.time", re(String.raw`${B}([01]?\d|2[0-3]):([0-5]\d)${B}(?!:)${SUFFIX}`), time, "clock time read as hours and minutes"),
  rule("verbalize.currency.postfix", re(String.raw`(?<![${W}.,])(\d+(?:,\d+)?)\s?(bin|milyon|milyar)?\s?([₺$€£])${SUFFIX}(?![${W}])`), currencyPostfix, "currency symbol after the amount read as words"),
  rule("verbalize.currency", re(String.raw`([₺$€£])\s?(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{1,2}))?${SUFFIX}(?![${W}]|[.,]\d)`), currencyPrefix, "currency amount read as words"),
  rule("verbalize.currency.code", re(String.raw`(?<![${W}.,])(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{1,2}))?\s?(TL|TRY|USD|EUR|GBP)${B}${SUFFIX}`), currencySuffix, "currency code read as words"),
  rule("verbalize.percent", re(String.raw`%\s?(\d+(?:,\d+)?)${SUFFIX}|(?<![${W}.])(\d+(?:,\d+)?)\s?%${SUFFIX}`), percent, "percent read as 'yüzde'"),
  rule("verbalize.unit", re(String.raw`(?<![${W}.,])(\d+(?:,\d+)?)\s?(${UNIT_ALTERNATION})${SUFFIX}(?![${W}/])`), unit, "unit abbreviation read as a word"),
  rule("verbalize.fraction", re(String.raw`(?<![\d/])([1-9])/([2-9]|10)${SUFFIX}(?![\d/])`), fraction, "fraction read as words"),
  rule("verbalize.range", re(String.raw`(?<![${W}.,\-/:])(\d+)\s?[-–]\s?(\d+)(?![${W}\-/:]|[.,]\d)`), range, "number range read with 'ila'"),
  rule("verbalize.thousands", re(String.raw`(?<![${W}.,])(\d{1,3}(?:\.\d{3})+)(?:,(\d+))?${SUFFIX}(?![${W}]|[.,]\d)`), thousands, "dotted thousands read as a number, not a decimal"),
  rule("verbalize.decimal", re(String.raw`(?<![${W}.,])(\d+),(\d+)${SUFFIX}(?![${W}]|[.,]\d)`), decimalComma, "decimal comma read as 'virgül'"),
  rule("verbalize.suffix", re(String.raw`${B}(\d+)${APOS}([${LOWER}]+)${B}`), suffixedNumber, "numeral with a suffix read as one word"),
  rule("verbalize.ordinal", re(String.raw`${B}(\d{1,3})\.(?=\s+[${LOWER}])`), ordinalDot, "numeral with a dot before a lowercase word read as an ordinal"),
  rule("verbalize.minus", re(String.raw`(?<![${W}.)\-–])[-–](?=\d)`), () => "eksi ", "leading minus read as a word"),
  rule("verbalize.alnum", re(String.raw`${B}(?=[${UPPER}0-9-]*\d)(?=[${UPPER}0-9-]*[${UPPER}])[${UPPER}0-9]+(?:-[${UPPER}0-9]+)*${B}`), alnum, "identifier spelled out"),
];

registerRules("tr", RULES);
