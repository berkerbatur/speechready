/** English verbalization rules, in the order they run. */

import { B, Match, W, escapeRe, findall, fullmatch, group, isDigit, re, rpartition } from "../util.js";
import { Rule, option, registerRules, rule } from "./index.js";
import { cardinal, decimal, digits, ordinal, year } from "./numbers_en.js";

const MONTHS = [
  "January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December",
];
const DAY_FIRST_LOCALES = new Set(["en-GB", "en-AU", "en-NZ", "en-IE", "en-IN", "en-ZA"]);

const dayFirst = (locale: string): boolean => DAY_FIRST_LOCALES.has(locale);

function dateWords(y: number, m: number, d: number): string | null {
  if (!(m >= 1 && m <= 12 && d >= 1 && d <= 31)) return null;
  let yy = y;
  if (yy < 100) yy += yy < 70 ? 2000 : 1900;
  return `${MONTHS[m - 1]} ${ordinal(d)}, ${year(yy)}`;
}

const int = (s: string | undefined): number => parseInt((s ?? "").replace(/,/g, ""), 10);

// --- dates -----------------------------------------------------------------------

const dateIso = (m: Match): string | null => dateWords(int(m[1]), int(m[2]), int(m[3]));

function dateSlash(m: Match, locale: string): string | null {
  const a = int(m[1]);
  const b = int(m[2]);
  const y = int(m[3]);
  if (dayFirst(locale)) return dateWords(y, b, a);
  return dateWords(y, a, b);
}

const dateDot = (m: Match): string | null => dateWords(int(m[3]), int(m[2]), int(m[1]));

// --- digit strings ---------------------------------------------------------------

function digitGroups(m: Match): string | null {
  const raw = m[0];
  const count = (raw.match(/\d/g) ?? []).length;
  if (count < 7 || count > 16) return null;
  const groups = raw.split(/[\s.\-()]+/u).filter((g) => g);
  return groups.map(digits).join(", ");
}

const longDigits = (m: Match): string => digits(m[0]);

// --- time ----------------------------------------------------------------------------

function time(m: Match): string | null {
  const hour = m[1];
  const minute = m[2];
  const suffix = group(m, 3);
  if (suffix) return null; // "2:30 pm" is read correctly as it stands
  const h = parseInt(hour, 10);
  if (h >= 13) return `${h - 12}:${minute} PM`;
  if (h === 0) return `12:${minute} AM`;
  if (hour.startsWith("0")) return `${h}:${minute} AM`;
  return null;
}

// --- currency --------------------------------------------------------------------------

const CURRENCY: Record<string, [string, string, string | null, string | null]> = {
  $: ["dollar", "dollars", "cent", "cents"],
  "€": ["euro", "euros", "cent", "cents"],
  "£": ["pound", "pounds", "penny", "pence"],
  "¥": ["yen", "yen", null, null],
  "₺": ["lira", "lira", "kuruş", "kuruş"],
  USD: ["dollar", "dollars", "cent", "cents"],
  EUR: ["euro", "euros", "cent", "cents"],
  GBP: ["pound", "pounds", "penny", "pence"],
  TRY: ["lira", "lira", "kuruş", "kuruş"],
  TL: ["lira", "lira", "kuruş", "kuruş"],
};
const MAGNITUDE: Record<string, string> = {
  k: "thousand", m: "million", bn: "billion", b: "billion", thousand: "thousand", million: "million", billion: "billion",
};

function moneyWords(symbol: string, whole: string, frac: string | undefined, magnitude: string | undefined): string {
  const [one, many, centOne, centMany] = CURRENCY[symbol];
  const amount = int(whole);
  if (magnitude) return `${decimal(whole, frac)} ${MAGNITUDE[magnitude.toLowerCase()]} ${many}`;
  if (frac !== undefined && centOne) {
    const cents = parseInt(frac.padEnd(2, "0").slice(0, 2), 10);
    const main = amount === 0 ? "" : `${cardinal(amount)} ${amount === 1 ? one : many}`;
    if (cents === 0) return main || `zero ${many}`;
    const tail = `${cardinal(cents)} ${cents === 1 ? centOne : centMany}`;
    return main ? `${main} and ${tail}` : tail;
  }
  if (frac !== undefined) return `${decimal(whole, frac)} ${many}`;
  return `${cardinal(amount)} ${amount === 1 ? one : many}`;
}

function currencyRange(m: Match): string {
  const [, many] = CURRENCY[m[1]];
  return `${cardinal(int(m[2]))} to ${cardinal(int(m[3]))} ${many}`;
}

const currencyPrefix = (m: Match): string => moneyWords(m[1], m[2], group(m, 3), group(m, 4));
const currencyCode = (m: Match): string => moneyWords(m[3].toUpperCase(), m[1], group(m, 2), undefined);

// --- percent, units, fractions, ranges ----------------------------------------------------

const UNITS: Record<string, [string, string]> = {
  "km/h": ["kilometer per hour", "kilometers per hour"],
  km: ["kilometer", "kilometers"],
  cm: ["centimeter", "centimeters"],
  mm: ["millimeter", "millimeters"],
  kg: ["kilogram", "kilograms"],
  mg: ["milligram", "milligrams"],
  lbs: ["pound", "pounds"],
  lb: ["pound", "pounds"],
  oz: ["ounce", "ounces"],
  mph: ["mile per hour", "miles per hour"],
  mi: ["mile", "miles"],
  ft: ["foot", "feet"],
  GB: ["gigabyte", "gigabytes"],
  MB: ["megabyte", "megabytes"],
  KB: ["kilobyte", "kilobytes"],
  TB: ["terabyte", "terabytes"],
  ms: ["millisecond", "milliseconds"],
  min: ["minute", "minutes"],
  hrs: ["hour", "hours"],
  hr: ["hour", "hours"],
  kWh: ["kilowatt hour", "kilowatt hours"],
  kHz: ["kilohertz", "kilohertz"],
  MHz: ["megahertz", "megahertz"],
  GHz: ["gigahertz", "gigahertz"],
  Hz: ["hertz", "hertz"],
  fps: ["frame per second", "frames per second"],
  "°C": ["degree Celsius", "degrees Celsius"],
  "°F": ["degree Fahrenheit", "degrees Fahrenheit"],
  "°": ["degree", "degrees"],
};
const UNIT_ALTERNATION = Object.keys(UNITS).sort((a, b) => b.length - a.length).map(escapeRe).join("|");

function unit(m: Match): string {
  const number = m[1];
  const [one, many] = UNITS[m[2]];
  const isOne = number === "1" || number === "1.0";
  return `${number} ${isOne ? one : many}`;
}

const FRACTIONS: Record<number, [string, string]> = {
  2: ["half", "halves"], 3: ["third", "thirds"], 4: ["quarter", "quarters"],
  5: ["fifth", "fifths"], 8: ["eighth", "eighths"], 10: ["tenth", "tenths"],
};

function fraction(m: Match): string | null {
  const num = parseInt(m[1], 10);
  const den = parseInt(m[2], 10);
  if (num >= den) return null;
  if (option("fractions", "spoken") === "division") return `${cardinal(num)} over ${cardinal(den)}`;
  if (!(den in FRACTIONS)) return null;
  const [one, many] = FRACTIONS[den];
  return `${cardinal(num)} ${num === 1 ? one : many}`;
}

const YEAR_LIKE = re(String.raw`(19|20)\d\d`);

function range(m: Match): string | null {
  const a = m[1];
  const b = m[2];
  const short = a.replace(/\./g, "").length <= 3 && b.replace(/\./g, "").length <= 3;
  const years = fullmatch(YEAR_LIKE, a) && fullmatch(YEAR_LIKE, b);
  if (!(short || years)) return null;
  return `${a} to ${b}`;
}

// --- years and ordinals -----------------------------------------------------------------------

const yearInContext = (m: Match): string => `${m[1]} ${year(parseInt(m[2], 10))}`;

function decade(m: Match): string {
  const words = year(parseInt(m[1], 10));
  const [head, , last] = rpartition(words, " ");
  const plural = last.endsWith("y") ? last.slice(0, -1) + "ies" : last + "s";
  return (head ? head + " " : "") + plural;
}

const ordinalRule = (m: Match): string => ordinal(parseInt(m[1], 10));

// --- alphanumeric identifiers ------------------------------------------------------------------

const VOWELS = new Set("AEIOUY");
const RUNS = re("[A-Z]+|\\d+");

function alnum(m: Match): string | null {
  const token = m[0];
  if (token.replace(/-/g, "").length < 4) return null;
  const out: string[] = [];
  const runs = findall(RUNS, token);
  for (const run of runs) {
    if (isDigit(run)) out.push(runs.length === 2 && run.length <= 2 ? cardinal(parseInt(run, 10)) : digits(run));
    else if (run.length >= 3 && Array.from(run).some((c) => VOWELS.has(c))) out.push(run);
    else out.push(Array.from(run).join(" "));
  }
  return out.join(" ");
}

// a separator inside a phone number: space, dash, or a dot that is not followed by whitespace
const SEP = String.raw`(?:[ \-]|\.(?!\s))`;

const timeRange = (m: Match): string => `${m[1]} to ${m[2]}`;

const PER: Record<string, string> = {
  mo: "month", month: "month", yr: "year", year: "year", hr: "hour", hour: "hour",
  min: "minute", minute: "minute", day: "day", week: "week", wk: "week",
};

export const RULES: Rule[] = [
  rule("verbalize.date.iso", re(String.raw`${B}(\d{4})-(\d{2})-(\d{2})${B}`), dateIso, "ISO date read as month, day, year"),
  rule("verbalize.date.slash", re(String.raw`${B}(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})${B}`), dateSlash, "numeric date read in the locale's order"),
  rule("verbalize.date.dot", re(String.raw`${B}(\d{1,2})\.(\d{1,2})\.(\d{4})${B}`), dateDot, "dotted date read as day, month, year"),
  rule(
    "verbalize.phone",
    re(String.raw`(?<![${W}.])(?:\+?\d{1,3}${SEP})?(?:\(\d{2,4}\)[ \-]?|\d{2,4}${SEP})(?:\d{2,4}${SEP}){1,4}\d{2,4}(?![${W}\-]|[.,]\d)`),
    digitGroups,
    "digit groups read digit by digit with a pause between groups",
  ),
  rule("verbalize.number_sign", re(String.raw`#(?=\d)`), () => "number ", "number sign read as a word"),
  rule("verbalize.digits.long", re(String.raw`(?<![${W}.,])\d{7,}(?![${W}]|[.,]\d)`), longDigits, "long digit string read digit by digit"),
  rule("verbalize.time.range", re(String.raw`${B}(\d{1,2}:\d{2})\s?[-–]\s?(\d{1,2}:\d{2})${B}`), timeRange, "time range read with 'to'"),
  rule("verbalize.time", re(String.raw`${B}([01]?\d|2[0-3]):([0-5]\d)${B}(?!:)(?:\s?(am|pm|AM|PM|a\.m\.|p\.m\.))?`), time, "24-hour time read as 12-hour"),
  rule("verbalize.currency.range", re(String.raw`([$€£¥₺])\s?(\d[\d,]*)\s?[-–]\s?[$€£¥₺]?\s?(\d[\d,]*)(?![\d]|[.,]\d)`), currencyRange, "currency range read as words"),
  rule(
    "verbalize.currency",
    re(String.raw`([$€£¥₺])\s?(\d[\d,]*)(?:\.(\d{1,2}))?\s?(k|K|m|M|bn|B|thousand|million|billion)?(?![${W}]|[.,]\d)`),
    currencyPrefix,
    "currency amount read as words",
  ),
  rule("verbalize.currency.code", re(String.raw`(?<![${W}.])(\d[\d,]*)(?:\.(\d{1,2}))?\s?(USD|EUR|GBP|TRY|TL)${B}`), currencyCode, "currency code read as words"),
  rule(
    "verbalize.per",
    re(String.raw`${B}(dollars?|cents?|euros?|pounds?|\d)/(mo|month|yr|year|hr|hour|min|minute|day|week|wk)${B}`),
    (m) => `${m[1]} per ${PER[m[2]]}`,
    "slash before a period read as 'per'",
  ),
  rule("verbalize.percent", re(String.raw`(?<![${W}.])(\d+(?:\.\d+)?)\s?%|%\s?(\d+(?:\.\d+)?)`), (m) => `${group(m, 1) ?? group(m, 2)} percent`, "percent sign read as a word"),
  rule("verbalize.unit", re(String.raw`(?<![${W}.])(\d+(?:\.\d+)?)\s?(${UNIT_ALTERNATION})(?![${W}/])`), unit, "unit abbreviation read as a word"),
  rule("verbalize.fraction", re(String.raw`(?<![\d/])([1-9])/([2-9]|10)(?![\d/])`), fraction, "fraction read as words"),
  rule("verbalize.range", re(String.raw`(?<![${W}.,\-/:])(\d+(?:\.\d+)?)\s?[-–]\s?(\d+(?:\.\d+)?)(?![${W}\-/:]|[.,]\d)`), range, "number range read with 'to'"),
  rule("verbalize.year", re(String.raw`${B}(in|In|since|Since|by|from|until|till|before|after|during|circa|year|est\.|©)\s+(1[1-9]\d\d|20\d\d)${B}(?![${W}.,]?\d)`), yearInContext, "year read as a year"),
  rule("verbalize.decade", re(String.raw`${B}(1[1-9]\d0|20\d0)s${B}`), decade, "decade read as a year"),
  rule("verbalize.ordinal", re(String.raw`${B}(\d{1,4})(?:st|nd|rd|th)${B}`), ordinalRule, "ordinal read as words"),
  rule("verbalize.minus", re(String.raw`(?<![${W}.)\-–])[-–](?=\d)`), () => "minus ", "leading minus read as a word"),
  rule("verbalize.alnum", re(String.raw`${B}(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9]+(?:-[A-Z0-9]+)*${B}`), alnum, "identifier spelled out"),
];

registerRules("en", RULES);
