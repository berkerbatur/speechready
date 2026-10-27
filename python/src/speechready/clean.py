"""Stage 1: clean. Turn markdown, code, emoji, URLs and invisible Unicode into plain prose.

Block structure is preserved as one block per line: headings, paragraphs,
list items and table rows each become a line, and a block that ends without
terminal punctuation gets a full stop so the model pauses after it. Hard-wrapped
lines inside a paragraph are joined with a space.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .changes import Recorder
from .intents import SENTINEL_CLOSE, SENTINEL_OPEN

STAGE = "clean"


@dataclass(frozen=True)
class CleanOptions:
    code_blocks: str = "drop"  # drop | keep
    tables: str = "rows"  # rows | drop
    urls: str = "domain"  # domain | drop | keep
    emails: str = "keep"  # keep | drop
    emoji: str = "drop"  # drop | keep
    emphasis: str = "strip"  # strip | intent
    strip_tags: tuple[str, ...] = ("think", "thinking", "reasoning")
    terminal_punctuation: str = "."
    html: str = "strip"  # strip | keep
    extra: dict = field(default_factory=dict)


_TERMINAL = ".!?…:;,"
_CLOSERS = "\"'”’)]»"

_ZERO_WIDTH = re.compile("[​‌‍⁠﻿­]")
_SPACES = re.compile("[           　]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_SETEXT = re.compile(r"^\s{0,3}(=+|-+)\s*$")
_HR = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
_LIST = re.compile(r"^(\s*)([-*+•]|\d{1,3}[.)])\s+(.*)$")
_TASK = re.compile(r"^\[( |x|X)\]\s+")
_QUOTE = re.compile(r"^\s{0,3}>\s?")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")

_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\(\s*<?([^)\s>]*)>?(?:\s+\"[^\"]*\")?\s*\)")
_AUTOLINK = re.compile(r"<((?:https?|mailto):[^>\s]+)>")
_REF_LINK = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
_CODE_SPAN = re.compile(r"(`+)(.+?)\1")
_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_ITALIC = re.compile(r"(?<![\w*])(\*|_)(?=\S)(.+?)(?<=\S)\1(?![\w*])")
_STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!>~|])")
_HTML_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")
_URL = re.compile(r"(?<![\w@/])(?:https?://|www\.)([^\s<>()\"']+)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_FOOTNOTE = re.compile(r"\[\^[^\]]+\]")
# a backslash-escaped marker is swapped for a private-use character while the
# markdown rules run, so it can never be read as markdown, and swapped back after
_ESCAPABLE = "\\`*_{}[]()#+-.!>~|"
_ESC_TO_PUA = {c: chr(0xE100 + i) for i, c in enumerate(_ESCAPABLE)}
_PUA_TO_ESC = {v: k for k, v in _ESC_TO_PUA.items()}
_PUA_RANGE = re.compile("[\ue100-\ue11f]")

# Emoji and pictographs: symbols (So), variation selectors, ZWJ, skin tones, keycaps, flags.
_EMOJI = re.compile(
    "(?:[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF\U0001F1E6-\U0001F1FF"
    "\U0000FE0F\U0000200D\U000020E3\U0001F3FB-\U0001F3FF]|[←-⇿])+"
)


def clean(text: str, options: CleanOptions | None = None, recorder: Recorder | None = None) -> str:
    """Run the clean stage on `text`; returns the cleaned text and records changes."""
    opts = options or CleanOptions()
    rec = recorder or Recorder()

    text = _unicode(text, rec)
    text = _strip_reasoning(text, opts, rec)
    blocks = _blocks(text, opts, rec)
    lines = [_inline(block, opts, rec) for block in blocks]
    lines = [_terminate(line, opts, rec) for line in lines if line.strip()]
    return "\n".join(lines)


# --- character level ---------------------------------------------------------


def _unicode(text: str, rec: Recorder) -> str:
    out = unicodedata.normalize("NFC", text)
    out = out.replace("\r\n", "\n").replace("\r", "\n")
    out = _ZERO_WIDTH.sub("", out)
    out = _SPACES.sub(" ", out)
    out = _CONTROL.sub("", out)
    if out != text:
        rec.add(STAGE, "clean.unicode.invisible", text, out, "removed invisible or non-standard whitespace characters")
    return out


def _strip_reasoning(text: str, opts: CleanOptions, rec: Recorder) -> str:
    for tag in opts.strip_tags:
        pattern = re.compile(rf"<{tag}\b[^>]*>.*?</{tag}\s*>", re.DOTALL | re.IGNORECASE)
        new = pattern.sub("", text)
        if new != text:
            rec.add(STAGE, f"clean.tags.{tag}", text, new, f"dropped <{tag}> block")
            text = new
    return text


# --- block level ---------------------------------------------------------------


def _blocks(text: str, opts: CleanOptions, rec: Recorder) -> list[str]:
    """Split markdown into blocks: one string per heading, paragraph, list item, table row."""
    blocks: list[str] = []
    para: list[str] = []
    in_fence = False
    fence_lines: list[str] = []
    lines = text.split("\n")

    def flush() -> None:
        if para:
            blocks.append(" ".join(s.strip() for s in para))
            para.clear()

    for i, raw in enumerate(lines):
        line = raw
        if _FENCE.match(line):
            if in_fence:
                in_fence = False
                body = "\n".join(fence_lines)
                if opts.code_blocks == "keep":
                    blocks.extend(s for s in fence_lines if s.strip())
                    rec.add(STAGE, "clean.markdown.code_block", f"```\n{body}\n```", body, "kept code block as plain lines")
                else:
                    rec.add(STAGE, "clean.markdown.code_block", f"```\n{body}\n```", "", "dropped code block")
                fence_lines = []
            else:
                flush()
                in_fence = True
            continue
        if in_fence:
            fence_lines.append(line)
            continue

        quoted = _QUOTE.match(line)
        if quoted:
            line = line[quoted.end() :]
            rec.add(STAGE, "clean.markdown.blockquote", raw, line, "removed blockquote marker")

        if not line.strip():
            flush()
            continue
        if _HR.match(line):
            flush()
            rec.add(STAGE, "clean.markdown.rule", line, "", "dropped horizontal rule")
            continue
        if _SETEXT.match(line) and para:
            # underline under a paragraph line = setext heading
            heading = " ".join(s.strip() for s in para)
            para.clear()
            blocks.append(heading)
            rec.add(STAGE, "clean.markdown.heading", f"{heading}\n{line}", heading, "setext heading to plain line")
            continue
        h = _HEADING.match(line)
        if h:
            flush()
            blocks.append(h.group(2))
            rec.add(STAGE, "clean.markdown.heading", line, h.group(2), "heading marker removed")
            continue
        if _TABLE_SEP.match(line):
            flush()
            rec.add(STAGE, "clean.markdown.table", line, "", "dropped table separator row")
            continue
        if _TABLE_ROW.match(line):
            flush()
            if opts.tables == "drop":
                rec.add(STAGE, "clean.markdown.table", line, "", "dropped table row")
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            row = ", ".join(c for c in cells if c)
            blocks.append(row)
            rec.add(STAGE, "clean.markdown.table", line, row, "table row read as a comma list")
            continue
        li = _LIST.match(line)
        if li:
            flush()
            item = li.group(3)
            task = _TASK.match(item)
            if task:
                item = item[task.end() :]
            blocks.append(item)
            rec.add(STAGE, "clean.markdown.list", line, item, "list marker removed")
            continue
        para.append(line)
    flush()
    if in_fence and fence_lines:
        # unterminated fence: treat as dropped code
        rec.add(STAGE, "clean.markdown.code_block", "\n".join(fence_lines), "", "dropped unterminated code block")
    return blocks


# --- inline level ---------------------------------------------------------------


def _inline(block: str, opts: CleanOptions, rec: Recorder) -> str:
    text = block

    def sub(pattern: re.Pattern[str], repl, rule: str, note: str) -> None:
        nonlocal text
        new = pattern.sub(repl, text)
        if new != text:
            rec.add(STAGE, rule, text, new, note)
            text = new

    # protect backslash escapes so an escaped marker is never read as markdown
    text = _ESCAPE.sub(lambda m: _ESC_TO_PUA[m.group(1)], text)
    sub(_IMAGE, lambda m: m.group(1), "clean.markdown.image", "image replaced by its alt text")
    sub(_LINK, lambda m: m.group(1), "clean.markdown.link", "link replaced by its text")
    sub(_REF_LINK, lambda m: m.group(1), "clean.markdown.link", "reference link replaced by its text")
    sub(_AUTOLINK, lambda m: m.group(1), "clean.markdown.link", "autolink brackets removed")
    sub(_FOOTNOTE, "", "clean.markdown.footnote", "footnote marker removed")
    sub(_CODE_SPAN, lambda m: m.group(2), "clean.markdown.code_span", "inline code backticks removed")
    sub(_STRIKE, lambda m: m.group(1), "clean.markdown.emphasis", "strikethrough markers removed")
    if opts.emphasis == "intent":
        sub(_BOLD, lambda m: f"[em {m.group(2)}]", "clean.markdown.emphasis", "bold turned into an emphasis intent")
        sub(_ITALIC, lambda m: f"[em {m.group(2)}]", "clean.markdown.emphasis", "italic turned into an emphasis intent")
    else:
        sub(_BOLD, lambda m: m.group(2), "clean.markdown.emphasis", "bold markers removed")
        sub(_ITALIC, lambda m: m.group(2), "clean.markdown.emphasis", "italic markers removed")
    if _PUA_RANGE.search(text):
        new = _PUA_RANGE.sub(lambda m: _PUA_TO_ESC[m.group(0)], text)
        rec.add(STAGE, "clean.markdown.escape", block, new, "backslash escape removed")
        text = new
    if opts.html == "strip":
        sub(_HTML_TAG, "", "clean.html.tag", "HTML tag removed")
    if opts.emails == "drop":
        sub(_EMAIL, "", "clean.email", "email address dropped")
    if opts.urls == "domain":
        sub(_URL, _domain_of, "clean.url", "URL reduced to its domain")
    elif opts.urls == "drop":
        sub(_URL, "", "clean.url", "URL dropped")
    if opts.emoji == "drop":
        sub(_EMOJI, "", "clean.emoji", "emoji removed")
        sub(_SYMBOLS, "", "clean.emoji", "pictographic symbol removed")
    text = _whitespace(text)
    return text


_SYMBOLS_CHARS = "".join(
    chr(c) for c in range(0x2000, 0x3300) if unicodedata.category(chr(c)) == "So" and not (0x2100 <= c <= 0x214F)
)
_SYMBOLS = re.compile(f"[{re.escape(_SYMBOLS_CHARS)}]+") if _SYMBOLS_CHARS else re.compile(r"(?!x)x")


def _domain_of(m: re.Match[str]) -> str:
    rest = m.group(1)
    host = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    host = host.split("@")[-1].split(":")[0]
    return host


def _whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ([,.;:!?])(?!\d)", r"\1", text)  # "word ." -> "word."
    text = re.sub(r"\( ", "(", text)
    text = re.sub(r" \)", ")", text)
    return text.strip()


def _terminate(line: str, opts: CleanOptions, rec: Recorder) -> str:
    """A block that ends without punctuation gets a full stop so the model pauses after it."""
    if not opts.terminal_punctuation:
        return line
    stripped = line.rstrip(_CLOSERS + " ")
    if not stripped:
        return line
    last = stripped[-1]
    if last in _TERMINAL or last == SENTINEL_CLOSE:
        return line
    if last in "-–—":
        return line
    new = line + opts.terminal_punctuation
    rec.add(STAGE, "clean.block.terminal", line, new, "added a full stop at the end of a block")
    return new


__all__ = ["CleanOptions", "clean", "SENTINEL_OPEN"]
