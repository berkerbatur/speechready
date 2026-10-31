/** English number words: cardinals, ordinals, years, digit strings. */

import { divmod, rpartition } from "../util.js";

const ONES = [
  "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
  "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
];
const TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];
const SCALES: [number, string][] = [[1e9, "billion"], [1e6, "million"], [1e3, "thousand"], [100, "hundred"]];
const ORDINAL_IRREGULAR: Record<string, string> = {
  one: "first", two: "second", three: "third", five: "fifth", eight: "eighth", nine: "ninth", twelve: "twelfth",
};

export function cardinal(n: number): string {
  if (n < 0) return "minus " + cardinal(-n);
  if (n < 20) return ONES[n];
  if (n < 100) {
    const [tens, ones] = divmod(n, 10);
    return TENS[tens] + (ones ? "-" + ONES[ones] : "");
  }
  for (const [value, name] of SCALES) {
    if (n >= value) {
      const [head, rest] = divmod(n, value);
      let words = cardinal(head) + " " + name;
      if (rest) words += " " + cardinal(rest);
      return words;
    }
  }
  return String(n);
}

export function ordinal(n: number): string {
  const words = cardinal(n);
  let [head, sep, last] = words.includes(" ") ? rpartition(words, " ") : ["", "", words];
  if (last.includes("-")) {
    const [tens, , ones] = rpartition(last, "-");
    last = tens + "-" + ordinalWord(ones);
  } else {
    last = ordinalWord(last);
  }
  return head + sep + last;
}

function ordinalWord(word: string): string {
  if (word in ORDINAL_IRREGULAR) return ORDINAL_IRREGULAR[word];
  if (word.endsWith("y")) return word.slice(0, -1) + "ieth";
  return word + "th";
}

/** Spoken year: 1999 -> nineteen ninety-nine, 2005 -> two thousand five, 2026 -> twenty twenty-six. */
export function year(n: number): string {
  if (n < 1000 || n > 9999) return cardinal(n);
  const [high, low] = divmod(n, 100);
  if (low === 0) {
    if (high % 10 === 0) return cardinal(n); // 2000, 3000
    return cardinal(high) + " hundred"; // 1900, 2100
  }
  if (n >= 2000 && n <= 2009) return "two thousand " + cardinal(low);
  if (low < 10) return cardinal(high) + " oh " + cardinal(low); // 1905 -> nineteen oh five
  return cardinal(high) + " " + cardinal(low);
}

/** Each digit as a word; non-digits pass through as their spoken form where known. */
export function digits(s: string): string {
  const out: string[] = [];
  for (const ch of s) {
    if (/\d/.test(ch)) out.push(ONES[parseInt(ch, 10)]);
    else if (ch === "+") out.push("plus");
  }
  return out.join(" ");
}

export function decimal(whole: string, frac: string | null | undefined): string {
  let text = cardinal(parseInt(whole.replace(/,/g, ""), 10));
  if (frac) text += " point " + Array.from(frac).map((c) => ONES[parseInt(c, 10)]).join(" ");
  return text;
}
