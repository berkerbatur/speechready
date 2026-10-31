/** Small helpers that make the TypeScript port line up with the Python reference.
 *
 * Python's `re` is Unicode-aware by default: `\w` matches letters in any script
 * and `\b` is a boundary next to them. JavaScript's `\w` and `\b` are ASCII only,
 * so every pattern in this package is written with `W` and `B` instead and
 * compiled with the `u` flag.
 */

/** Python's `\w` under Unicode: letters, digits, underscore. Use inside a character class. */
export const W = "\\p{L}\\p{N}_";
/** Python's `\b` under Unicode. */
export const B = `(?:(?<=[${W}])(?![${W}])|(?<![${W}])(?=[${W}]))`;

/** Compile a pattern with the `u` flag (plus `g`, which every helper here expects). */
export function re(source: string, flags = ""): RegExp {
  let f = flags;
  if (!f.includes("u")) f += "u";
  if (!f.includes("g")) f += "g";
  return new RegExp(source, f);
}

/** A match as the Python-style callbacks see it: `m[0]`, `m[1]`..., `m.index`, `m.groups`. */
export type Match = RegExpExecArray;

/** `pattern.sub(fn, text)`: every match replaced by `fn(match)`. */
export function sub(pattern: RegExp, text: string, fn: (m: Match) => string): string {
  pattern.lastIndex = 0;
  return text.replace(pattern, (...args: unknown[]) => {
    const groups = typeof args[args.length - 1] === "object" ? (args.pop() as Record<string, string | undefined>) : undefined;
    args.pop(); // the whole string
    const index = args.pop() as number;
    const m = args as unknown as RegExpExecArray;
    m.index = index;
    m.groups = groups as Record<string, string> | undefined;
    return fn(m);
  });
}

/** `pattern.sub(repl, text)` with a plain string replacement (no `$` expansion). */
export function subs(pattern: RegExp, text: string, repl: string): string {
  return sub(pattern, text, () => repl);
}

/** First match anywhere, or null. Safe on global patterns. */
export function search(pattern: RegExp, text: string): Match | null {
  pattern.lastIndex = 0;
  const m = pattern.exec(text);
  pattern.lastIndex = 0;
  return m;
}

/** `pattern.match(text)`: a match anchored at the start, or null. */
export function matchStart(pattern: RegExp, text: string): Match | null {
  const m = search(pattern, text);
  return m && m.index === 0 ? m : null;
}

/** `re.fullmatch(pattern, text)`. */
export function fullmatch(pattern: RegExp, text: string): Match | null {
  const anchored = new RegExp(`^(?:${pattern.source})$`, pattern.flags.replace("g", ""));
  return anchored.exec(text);
}

export function test(pattern: RegExp, text: string): boolean {
  return search(pattern, text) !== null;
}

/** All matches, in order. */
export function finditer(pattern: RegExp, text: string): Match[] {
  pattern.lastIndex = 0;
  const out: Match[] = [];
  for (const m of text.matchAll(pattern)) out.push(m as RegExpExecArray);
  return out;
}

export function findall(pattern: RegExp, text: string): string[] {
  return finditer(pattern, text).map((m) => m[0]);
}

/** `re.escape`: escape what is special in a pattern (letters are left alone, which the `u` flag requires). */
export function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
}

export function group(m: Match, i: number): string | undefined {
  return m[i] === undefined ? undefined : m[i];
}

// --- strings -----------------------------------------------------------------

export function strip(s: string, chars?: string): string {
  return rstrip(lstrip(s, chars), chars);
}

export function lstrip(s: string, chars?: string): string {
  let i = 0;
  while (i < s.length && (chars === undefined ? /\s/u.test(s[i]) : chars.includes(s[i]))) i++;
  return s.slice(i);
}

export function rstrip(s: string, chars?: string): string {
  let j = s.length;
  while (j > 0 && (chars === undefined ? /\s/u.test(s[j - 1]) : chars.includes(s[j - 1]))) j--;
  return s.slice(0, j);
}

export function partition(s: string, sep: string): [string, string, string] {
  const i = s.indexOf(sep);
  return i < 0 ? [s, "", ""] : [s.slice(0, i), sep, s.slice(i + sep.length)];
}

export function rpartition(s: string, sep: string): [string, string, string] {
  const i = s.lastIndexOf(sep);
  return i < 0 ? ["", "", s] : [s.slice(0, i), sep, s.slice(i + sep.length)];
}

export function isDigit(s: string): boolean {
  return s.length > 0 && /^\p{Nd}+$/u.test(s);
}

export function isUpper(ch: string): boolean {
  return /\p{Lu}/u.test(ch);
}

export function isAlpha(s: string): boolean {
  return s.length > 0 && /^\p{L}+$/u.test(s);
}

export function isSpace(ch: string): boolean {
  return /\s/u.test(ch);
}

export function chars(s: string): string[] {
  return Array.from(s);
}

/** Python's `round()`: ties go to the even neighbour. */
export function roundHalfEven(x: number): number {
  const f = Math.floor(x);
  const diff = x - f;
  if (diff > 0.5) return f + 1;
  if (diff < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}

/** Python's `divmod` for non-negative integers. */
export function divmod(n: number, d: number): [number, number] {
  return [Math.floor(n / d), n % d];
}

/** `str.format` for the small templates in provider profiles: `{ms}`, `{s}`, `{text}`, `{ipa}`. */
export function format(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (whole, key: string) => (key in values ? String(values[key]) : whole));
}

export function escapeXml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** `len(text.encode("utf-8"))`. */
export function utf8Length(text: string): number {
  return new TextEncoder().encode(text).length;
}

/** `len(text)` in code points, as Python counts. */
export function codePoints(text: string): number {
  let n = 0;
  for (const _ of text) n++;
  return n;
}
