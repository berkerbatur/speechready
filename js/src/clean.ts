/** Stage 1: clean. Turn markdown, code, emoji, URLs and invisible Unicode into plain prose.
 *
 * Block structure is preserved as one block per line: headings, paragraphs,
 * list items and table rows each become a line, and a block that ends without
 * terminal punctuation gets a full stop so the model pauses after it. Hard-wrapped
 * lines inside a paragraph are joined with a space.
 */

import { Recorder } from "./changes.js";
import { SENTINEL_CLOSE } from "./intents.js";
import { Match, W, escapeRe, isDigit, matchStart, re, rstrip, sub, test } from "./util.js";

const STAGE = "clean";

/** Everything a caller can change about how text is prepared. Defaults are what the evaluation ran with.
 *
 * Field names are the same as in the Python package and the shared fixtures (snake_case).
 */
export interface Options {
  // clean stage
  /** drop | keep | mention (one spoken sentence stands in for the block) */
  code_blocks: "drop" | "keep" | "mention";
  /** the sentence `mention` speaks; null = the locale's default */
  code_block_mention: string | null;
  tables: "rows" | "drop";
  urls: "domain" | "drop" | "keep";
  emails: "keep" | "drop";
  emoji: "drop" | "keep";
  emphasis: "strip" | "intent";
  /** keep ("1. Open the app") | drop ("Open the app") */
  list_numbers: "keep" | "drop";
  strip_tags: string[];
  terminal_punctuation: string;
  html: "strip" | "keep";
  // verbalize stage
  /** spoken ("one half", "yarım") | division ("one over two", "bir bölü iki") */
  fractions: "spoken" | "division";
  /** Turkish: lowercase vowel-less tokens like npm, css read with English letter names */
  foreign_acronyms: boolean;
  extra: Record<string, unknown>;
}

export const DEFAULT_OPTIONS: Options = Object.freeze({
  code_blocks: "drop",
  code_block_mention: null,
  tables: "rows",
  urls: "domain",
  emails: "keep",
  emoji: "drop",
  emphasis: "strip",
  list_numbers: "keep",
  strip_tags: ["think", "thinking", "reasoning"],
  terminal_punctuation: ".",
  html: "strip",
  fractions: "spoken",
  foreign_acronyms: true,
  extra: {},
}) as Options;

/** Fill in defaults. Unknown keys throw, so a camelCase typo is not silently ignored. */
export function options(partial?: Partial<Options> | null): Options {
  if (!partial) return DEFAULT_OPTIONS;
  for (const key of Object.keys(partial)) {
    if (!(key in DEFAULT_OPTIONS)) {
      throw new TypeError(`unknown option ${JSON.stringify(key)}; options use the same snake_case names as the Python package: ${Object.keys(DEFAULT_OPTIONS).join(", ")}`);
    }
  }
  return { ...DEFAULT_OPTIONS, ...partial };
}

// what `code_blocks: "mention"` says in place of a fenced block, by language
const MENTION: Record<string, string> = { en: "See the code block.", tr: "Kod bloğuna bakın." };

const TERMINAL = ".!?…:;,";
const CLOSERS = "\"'”’)]»";

const ZERO_WIDTH = re("[​‌‍⁠﻿­]");
const SPACES = re("[           　]");
const CONTROL = re("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f]");

const FENCE = re(String.raw`^\s*(${"```"}|~~~)`);
const HEADING = re(String.raw`^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$`);
const SETEXT = re(String.raw`^\s{0,3}(=+|-+)\s*$`);
const HR = re(String.raw`^\s{0,3}([-*_])(\s*\1){2,}\s*$`);
const LIST = re(String.raw`^(\s*)([-*+•]|\d{1,3}[.)])\s+(.*)$`);
const TASK = re(String.raw`^\[( |x|X)\]\s+`);
const QUOTE = re(String.raw`^\s{0,3}>\s?`);
const TABLE_SEP = re(String.raw`^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$`);
const TABLE_ROW = re(String.raw`^\s*\|.*\|\s*$`);

const IMAGE = re(String.raw`!\[([^\]]*)\]\([^)]*\)`);
const LINK = re(String.raw`\[([^\]]+)\]\(\s*<?([^)\s>]*)>?(?:\s+"[^"]*")?\s*\)`);
const AUTOLINK = re(String.raw`<((?:https?|mailto):[^>\s]+)>`);
const REF_LINK = re(String.raw`\[([^\]]+)\]\[[^\]]*\]`);
const CODE_SPAN = re(String.raw`(${"`"}+)(.+?)\1`);
const BOLD = re(String.raw`(\*\*|__)(?=\S)(.+?)(?<=\S)\1`);
const ITALIC = re(String.raw`(?<![${W}*])(\*|_)(?=\S)(.+?)(?<=\S)\1(?![${W}*])`);
const STRIKE = re(String.raw`~~(?=\S)(.+?)(?<=\S)~~`);
const ESCAPE = re(String.raw`\\([\\${"`"}*_{}\[\]()#+\-.!>~|])`);
const HTML_TAG = re(String.raw`</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>`);
const URL = re(String.raw`(?<![${W}@/])(?:https?://|www\.)([^\s<>()"']+)`);
const EMAIL = re(String.raw`[${W}.+-]+@[${W}-]+(?:\.[${W}-]+)+`);
const FOOTNOTE = re(String.raw`\[\^[^\]]+\]`);
// a backslash-escaped marker is swapped for a private-use character while the
// markdown rules run, so it can never be read as markdown, and swapped back after
const ESCAPABLE = "\\`*_{}[]()#+-.!>~|";
const ESC_TO_PUA = new Map(Array.from(ESCAPABLE).map((c, i) => [c, String.fromCharCode(0xe100 + i)]));
const PUA_TO_ESC = new Map(Array.from(ESC_TO_PUA.entries()).map(([k, v]) => [v, k]));
const PUA_RANGE = re("[-]");

// Emoji and pictographs: symbols (So), variation selectors, ZWJ, skin tones, keycaps, flags.
const EMOJI = re(
  "(?:[\\u{1F000}-\\u{1FAFF}\\u2600-\\u27BF\\u2B00-\\u2BFF\\u{1F1E6}-\\u{1F1FF}\\uFE0F\\u200D\\u20E3\\u{1F3FB}-\\u{1F3FF}]|[\\u2190-\\u21FF])+",
);
// Other pictographic symbols in the U+2000-U+32FF blocks, except letterlike symbols (U+2100-U+214F).
const SYMBOLS = re("(?:(?=[\\u2000-\\u20FF\\u2150-\\u32FF])\\p{So})+");

/** Run the clean stage on `text`; returns the cleaned text and records changes.
 *
 * `locale` only picks the sentence that `{code_blocks: "mention"}` speaks.
 */
export function clean(text: string, opts?: Partial<Options> | null, recorder?: Recorder, locale = "en-US"): string {
  const o = options(opts);
  const rec = recorder ?? new Recorder();

  let work = unicode(text, rec);
  work = stripReasoning(work, o, rec);
  const blocks = splitBlocks(work, o, rec, locale);
  let lines = blocks.map((b) => inline(b, o, rec));
  lines = lines.filter((l) => l.trim()).map((l) => terminate(l, o, rec));
  return lines.join("\n");
}

// --- character level ---------------------------------------------------------

function unicode(text: string, rec: Recorder): string {
  let out = text.normalize("NFC");
  out = out.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  out = sub(ZERO_WIDTH, out, () => "");
  out = sub(SPACES, out, () => " ");
  out = sub(CONTROL, out, () => "");
  if (out !== text) rec.add(STAGE, "clean.unicode.invisible", text, out, "removed invisible or non-standard whitespace characters");
  return out;
}

function stripReasoning(text: string, o: Options, rec: Recorder): string {
  let work = text;
  for (const tag of o.strip_tags) {
    const pattern = re(`<${escapeRe(tag)}${B_WORD}[^>]*>[\\s\\S]*?</${escapeRe(tag)}\\s*>`, "i");
    const next = sub(pattern, work, () => "");
    if (next !== work) {
      rec.add(STAGE, `clean.tags.${tag}`, work, next, `dropped <${tag}> block`);
      work = next;
    }
  }
  return work;
}

const B_WORD = `(?![${W}])`; // `\b` right after a tag name

// --- block level ---------------------------------------------------------------

/** Split markdown into blocks: one string per heading, paragraph, list item, table row. */
function splitBlocks(text: string, o: Options, rec: Recorder, locale: string): string[] {
  const blocks: string[] = [];
  let para: string[] = [];
  let inFence = false;
  let lastWasList = false;
  let fenceLines: string[] = [];
  const lines = text.split("\n");

  const flush = (): void => {
    if (para.length) {
      blocks.push(para.map((s) => s.trim()).join(" "));
      para = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    let line = raw;
    if (matchStart(FENCE, line)) {
      if (inFence) {
        inFence = false;
        const body = fenceLines.join("\n");
        if (o.code_blocks === "keep") {
          blocks.push(...fenceLines.filter((s) => s.trim()));
          rec.add(STAGE, "clean.markdown.code_block", "```\n" + body + "\n```", body, "kept code block as plain lines");
        } else if (o.code_blocks === "mention") {
          const said = o.code_block_mention || MENTION[locale.split("-")[0].toLowerCase()] || MENTION.en;
          blocks.push(said);
          rec.add(STAGE, "clean.markdown.code_block", "```\n" + body + "\n```", said, "code block replaced by a mention");
        } else {
          rec.add(STAGE, "clean.markdown.code_block", "```\n" + body + "\n```", "", "dropped code block");
        }
        fenceLines = [];
      } else {
        flush();
        inFence = true;
      }
      continue;
    }
    if (inFence) {
      fenceLines.push(line);
      continue;
    }

    const quoted = matchStart(QUOTE, line);
    if (quoted) {
      line = line.slice(quoted[0].length);
      rec.add(STAGE, "clean.markdown.blockquote", raw, line, "removed blockquote marker");
    }

    if (!line.trim()) {
      flush();
      continue;
    }
    if (matchStart(HR, line)) {
      flush();
      rec.add(STAGE, "clean.markdown.rule", line, "", "dropped horizontal rule");
      continue;
    }
    if (matchStart(SETEXT, line) && para.length) {
      // underline under a paragraph line = setext heading
      const heading = para.map((s) => s.trim()).join(" ");
      para = [];
      blocks.push(heading);
      rec.add(STAGE, "clean.markdown.heading", `${heading}\n${line}`, heading, "setext heading to plain line");
      continue;
    }
    const h = matchStart(HEADING, line);
    if (h) {
      flush();
      blocks.push(h[2]);
      rec.add(STAGE, "clean.markdown.heading", line, h[2], "heading marker removed");
      continue;
    }
    if (matchStart(TABLE_SEP, line)) {
      flush();
      rec.add(STAGE, "clean.markdown.table", line, "", "dropped table separator row");
      continue;
    }
    if (matchStart(TABLE_ROW, line)) {
      flush();
      if (o.tables === "drop") {
        rec.add(STAGE, "clean.markdown.table", line, "", "dropped table row");
        continue;
      }
      const inner = line.trim().replace(/^\|+/, "").replace(/\|+$/, "");
      const cells = inner.split("|").map((c) => c.trim());
      const row = cells.filter((c) => c).join(", ");
      blocks.push(row);
      rec.add(STAGE, "clean.markdown.table", line, row, "table row read as a comma list");
      continue;
    }
    let li = matchStart(LIST, line);
    if (li && isDigit(li[2].slice(0, -1)) && li[2].slice(0, -1) !== "1" && !lastWasList) {
      // "3. madde" at the start of a text is an ordinal, not a list that begins at three:
      // a numbered item counts as a list only when it starts at 1, continues a list,
      // or is followed by another numbered item.
      const nxt = lines.slice(i + 1).find((l) => l.trim()) ?? "";
      const m2 = matchStart(LIST, nxt);
      if (!(m2 && isDigit(m2[2].slice(0, -1)))) li = null;
    }
    if (li) {
      flush();
      lastWasList = true;
      let item = li[3];
      const task = matchStart(TASK, item);
      if (task) item = item.slice(task[0].length);
      const marker = li[2];
      if (isDigit(marker.slice(0, -1)) && o.list_numbers === "keep") {
        item = `${marker.slice(0, -1)}. ${item}`;
        rec.add(STAGE, "clean.markdown.list", line, item, "numbered item kept with its number");
      } else {
        rec.add(STAGE, "clean.markdown.list", line, item, "list marker removed");
      }
      blocks.push(item);
      continue;
    }
    para.push(line);
    lastWasList = false;
  }
  flush();
  if (inFence && fenceLines.length) {
    // unterminated fence: treat as dropped code
    rec.add(STAGE, "clean.markdown.code_block", fenceLines.join("\n"), "", "dropped unterminated code block");
  }
  return blocks;
}

// --- inline level ---------------------------------------------------------------

function inline(block: string, o: Options, rec: Recorder): string {
  let text = block;

  const apply = (pattern: RegExp, repl: (m: Match) => string, rule: string, note: string): void => {
    const next = sub(pattern, text, repl);
    if (next !== text) {
      rec.add(STAGE, rule, text, next, note);
      text = next;
    }
  };

  // protect backslash escapes so an escaped marker is never read as markdown
  text = sub(ESCAPE, text, (m) => ESC_TO_PUA.get(m[1]) ?? m[0]);
  apply(IMAGE, (m) => m[1], "clean.markdown.image", "image replaced by its alt text");
  apply(LINK, (m) => m[1], "clean.markdown.link", "link replaced by its text");
  apply(REF_LINK, (m) => m[1], "clean.markdown.link", "reference link replaced by its text");
  apply(AUTOLINK, (m) => m[1], "clean.markdown.link", "autolink brackets removed");
  apply(FOOTNOTE, () => "", "clean.markdown.footnote", "footnote marker removed");
  apply(CODE_SPAN, (m) => m[2], "clean.markdown.code_span", "inline code backticks removed");
  apply(STRIKE, (m) => m[1], "clean.markdown.emphasis", "strikethrough markers removed");
  if (o.emphasis === "intent") {
    apply(BOLD, (m) => `[em ${m[2]}]`, "clean.markdown.emphasis", "bold turned into an emphasis intent");
    apply(ITALIC, (m) => `[em ${m[2]}]`, "clean.markdown.emphasis", "italic turned into an emphasis intent");
  } else {
    apply(BOLD, (m) => m[2], "clean.markdown.emphasis", "bold markers removed");
    apply(ITALIC, (m) => m[2], "clean.markdown.emphasis", "italic markers removed");
  }
  if (test(PUA_RANGE, text)) {
    const next = sub(PUA_RANGE, text, (m) => PUA_TO_ESC.get(m[0]) ?? m[0]);
    rec.add(STAGE, "clean.markdown.escape", block, next, "backslash escape removed");
    text = next;
  }
  if (o.html === "strip") apply(HTML_TAG, () => "", "clean.html.tag", "HTML tag removed");
  if (o.emails === "drop") apply(EMAIL, () => "", "clean.email", "email address dropped");
  if (o.urls === "domain") apply(URL, domainOf, "clean.url", "URL reduced to its domain");
  else if (o.urls === "drop") apply(URL, () => "", "clean.url", "URL dropped");
  if (o.emoji === "drop") {
    apply(EMOJI, () => "", "clean.emoji", "emoji removed");
    apply(SYMBOLS, () => "", "clean.emoji", "pictographic symbol removed");
  }
  text = whitespace(text);
  return text;
}

function domainOf(m: Match): string {
  const rest = m[1];
  let host = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0];
  const at = host.split("@");
  host = at[at.length - 1].split(":")[0];
  return host;
}

function whitespace(text: string): string {
  let t = text.replace(/[ \t]+/g, " ");
  t = t.replace(/ ([,.;:!?])(?!\d)/gu, "$1"); // "word ." -> "word."
  t = t.replace(/\( /g, "(");
  t = t.replace(/ \)/g, ")");
  return t.trim();
}

/** A block that ends without punctuation gets a full stop so the model pauses after it. */
function terminate(line: string, o: Options, rec: Recorder): string {
  if (!o.terminal_punctuation) return line;
  const stripped = rstrip(line, CLOSERS + " ");
  if (!stripped) return line;
  const last = stripped[stripped.length - 1];
  if (TERMINAL.includes(last) || last === SENTINEL_CLOSE) return line;
  if ("-–—".includes(last)) return line;
  const next = line + o.terminal_punctuation;
  rec.add(STAGE, "clean.block.terminal", line, next, "added a full stop at the end of a block");
  return next;
}

