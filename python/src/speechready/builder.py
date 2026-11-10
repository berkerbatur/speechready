"""Build a pronunciation lexicon offline: glossary in, one model call, lexicon file out.

The runtime library makes no network calls. This module is the one place that does,
and it runs once, at development time, from the `speechready lexicon build` command:

    speechready lexicon scan transcripts.txt > glossary.txt    # candidate words, no model
    speechready lexicon build glossary.txt --locale tr-TR -o lexicon.yaml
    speechready lexicon check lexicon.yaml                      # every entry through the pipeline

The model is asked, for every word, how speakers of the locale actually say it, as a
respelling a TTS voice of that locale reads correctly (`say`), whether the voice
already reads the word fine with no entry (`keep`), and whether the lowercase form is
an ordinary word that must not be matched (`case_sensitive`). The answer is a draft
the developer reviews; the file then loads in both packages like any other lexicon.
A rerun asks only for the words the file does not have yet.

OpenAI-compatible chat endpoints (`OPENAI_API_KEY`, `OPENAI_BASE_URL` for a local or
third-party server) and the Anthropic Messages API (`ANTHROPIC_API_KEY`) are supported
with the standard library alone.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

from .lexicon import Entry, Lexicon

DEFAULT_MODELS = {"openai": "gpt-4.1-mini", "anthropic": "claude-sonnet-5-5"}
BATCH = 100
EXAMPLES = 40  # existing entries shown to the model as the file's conventions

LANGUAGE = {"en": "English", "tr": "Turkish", "de": "German", "fr": "French", "es": "Spanish", "it": "Italian",
            "pt": "Portuguese", "nl": "Dutch", "pl": "Polish", "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
            "ar": "Arabic", "ru": "Russian", "hi": "Hindi", "sv": "Swedish", "da": "Danish", "fi": "Finnish", "nb": "Norwegian"}

SYSTEM = """You write entries for a text-to-speech pronunciation lexicon in {language}.

For every word you receive, say how {language} speakers actually pronounce it, as a respelling that a {language} TTS voice reads correctly when it meets it in {language} text:
- Use only letters of the {language} alphabet, spaces and apostrophes. No IPA, no digits, no hyphens, no punctuation.
- Spell every sound the way a native {language} reader would spell it; a foreign name keeps the pronunciation {language} speakers use for it, not the dictionary one.
- For an acronym, write the letter names speakers actually use (in Turkish, foreign tech acronyms take English letter names: API becomes "ey pi ay"; everyday ones take Turkish letter names: TV becomes "te ve"), one letter name per word, separated by spaces.
- Separate syllables with spaces only where the voice would otherwise merge them wrongly.
- A hint beside a word says what it is; use it to pick the right pronunciation.

Reply with JSON only, in this shape, one entry per word in the order received, with "word" copied exactly:
{{"entries": [{{"word": "...", "say": "...", "keep": false, "case_sensitive": false, "note": "..."}}]}}
- "keep": true when a {language} TTS voice reads the word correctly as written, so it needs no entry; "say" may then be empty.
- "case_sensitive": true when the word in lowercase is an ordinary {language} word that must not be matched (IT in Turkish, since "it" is a word).
- "note": one short clause only when something is worth the developer's attention, else an empty string.{ipa}"""

FOREIGN_LETTERS = {"tr": re.compile(r"[qwxQWX]")}

IPA = """
- Also give "ipa": an IPA transcription of that same pronunciation, for voices that accept phoneme tags."""


@dataclass
class Build:
    """What `build` produced: the lexicon with the new entries added, and what was left out and why."""
    lexicon: Lexicon
    added: list[Entry] = field(default_factory=list)
    kept: list[tuple[str, str]] = field(default_factory=list)      # (word, note): the model says the voice reads it fine
    skipped: list[str] = field(default_factory=list)                # already in the lexicon
    notes: list[tuple[str, str]] = field(default_factory=list)      # (word, note) on added entries
    usage: dict = field(default_factory=dict)                       # token counts summed over the calls


# --- glossary -------------------------------------------------------------------------------


def read_glossary(text: str) -> list[tuple[str, str]]:
    """`word`, optionally a tab or two spaces and a hint, one per line; `#` starts a comment; blank lines are skipped."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        parts = re.split(r"\t+| {2,}", line.strip(), maxsplit=1)
        word, hint = parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")
        if word and word.lower() not in seen:
            seen.add(word.lower())
            out.append((word, hint))
    return out


_TOKEN = re.compile(r"[^\W\d_][\w.+#'’-]*", re.UNICODE)
_TR_SUFFIX = re.compile(r"['’][^\W\d_]*$")


def scan(text: str, *, min_count: int = 1) -> list[tuple[str, int]]:
    """Candidate lexicon words in `text`, most frequent first: acronyms (API, S3), mixed-case names
    (GitHub, iOS, PostgreSQL) and names with inner punctuation (Node.js, C++, C#). Plain lowercase
    words (nginx, kubectl) cannot be told from ordinary words without a dictionary; add those by hand."""
    counts: Counter[str] = Counter()
    for tok in _TOKEN.findall(text):
        tok = _TR_SUFFIX.sub("", tok).rstrip(".'’-")
        if len(tok) < 2 or not any(c.isalpha() for c in tok):
            continue
        letters = [c for c in tok if c.isalpha()]
        upper = sum(c.isupper() for c in letters)
        acronym = upper == len(letters) and (upper >= 2 or any(c.isdigit() for c in tok)) and len(tok) <= 8
        mixed = upper >= 1 and any(c.islower() for c in letters) and any(c.isupper() for c in tok[1:])
        inner = any(c in ".+#" for c in tok[1:]) and tok[0].isalpha()
        if acronym or mixed or inner:
            counts[tok] += 1
    return [(w, n) for w, n in counts.most_common() if n >= min_count]


# --- the model call ---------------------------------------------------------------------------


def _ssl_context() -> ssl.SSLContext:
    # A python.org build on macOS ships without a CA bundle for urllib; certifi's is used when it is installed.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _post(url: str, headers: dict, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"{url} answered {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{url}: {exc.reason}") from None


def chat(system: str, user: str, *, provider: str = "openai", model: str | None = None,
         base_url: str | None = None, timeout: float = 180) -> tuple[str, dict]:
    """One chat completion; returns the text and the usage dict. Keys come from the environment only."""
    model = model or DEFAULT_MODELS[provider]
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        base = (base_url or os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")
        data = _post(f"{base}/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"},
                     {"model": model, "max_tokens": 8192, "system": system, "messages": [{"role": "user", "content": user}]},
                     timeout)
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return text, data.get("usage", {})
    if provider != "openai":
        raise ValueError(f"unknown provider {provider!r}; use openai or anthropic")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    base = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    body: dict = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if "api.openai.com" in base:
        body["response_format"] = {"type": "json_object"}
    data = _post(f"{base}/chat/completions", {"Authorization": f"Bearer {key}"}, body, timeout)
    return data["choices"][0]["message"]["content"], data.get("usage", {})


def _parse(text: str) -> list[dict]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start = text.find("{")
    if start < 0:
        raise ValueError(f"the model did not answer with JSON: {text[:120]!r}")
    data = json.loads(text[start:])
    entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise ValueError("the model's JSON has no 'entries' list")
    return entries


# --- build --------------------------------------------------------------------------------------


Asker = Callable[[str, str], "tuple[str, dict]"]


def build(words: list[tuple[str, str]], locale: str, *, lexicon: Lexicon | None = None, ipa: bool = False,
          ask: Asker | None = None, batch: int = BATCH, **chat_kw) -> Build:
    """Ask the model for the words not yet in `lexicon` and return the lexicon with them added.

    `ask(system, user)` replaces the network call (tests, other clients)."""
    lex = lexicon or Lexicon([], locale)
    result = Build(lex)
    have = {e.word.lower() for e in lex.entries}
    todo = []
    for word, hint in words:
        if word.lower() in have:
            result.skipped.append(word)
        else:
            todo.append((word, hint))
    language = LANGUAGE.get(locale.split("-")[0].lower(), locale)
    system = SYSTEM.format(language=language, ipa=IPA if ipa else "")
    examples = [e for e in lex.entries if e.say][:EXAMPLES]
    if examples:
        system += "\n\nEntries already in this lexicon; follow their conventions:\n" + "\n".join(
            f"{e.word} -> {e.say}" for e in examples)
    ask = ask or (lambda s, u: chat(s, u, **chat_kw))
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        user = json.dumps([{"word": w, **({"hint": h} if h else {})} for w, h in chunk], ensure_ascii=False)
        text, usage = ask(system, user)
        for k, v in (usage or {}).items():
            if isinstance(v, (int, float)):
                result.usage[k] = result.usage.get(k, 0) + v
        answers = {str(a.get("word", "")).lower(): a for a in _parse(text) if isinstance(a, dict)}
        for word, _ in chunk:
            a = answers.get(word.lower())
            if a is None:
                raise ValueError(f"the model's answer has no entry for {word!r}")
            say = re.sub(r"\s+", " ", str(a.get("say") or "")).strip()
            note = str(a.get("note") or "").strip()
            if a.get("keep") or not say or say.lower() == word.lower():
                result.kept.append((word, note))
                continue
            entry = Entry(word=word, say=say, ipa=str(a.get("ipa") or "").strip() if ipa else "",
                          case_sensitive=bool(a.get("case_sensitive")))
            lex.entries.append(entry)
            result.added.append(entry)
            if note:
                result.notes.append((word, note))
    return result


# --- check ------------------------------------------------------------------------------------


def check(lexicon: Lexicon) -> list[tuple[str, str]]:
    """Problems a developer should look at before shipping: a `say` with digits, symbols or letters the
    locale's alphabet lacks, which the voice will read its own way, and a word the pipeline does not
    replace (split by the cleaner or matched by an earlier entry). (word, problem) pairs; empty is good."""
    from .pipeline import prepare

    problems: list[tuple[str, str]] = []
    lang = lexicon.locale.split("-")[0].lower()
    foreign = FOREIGN_LETTERS.get(lang)
    for e in lexicon.entries:
        if e.say and re.search(r"[\d_]|[^\w\s'’-]", e.say):
            problems.append((e.word, f"say {e.say!r} has digits or symbols; a voice reads those its own way"))
        elif e.say and foreign and foreign.search(e.say):
            problems.append((e.word, f"say {e.say!r} has letters the {LANGUAGE.get(lang, lang)} alphabet lacks; a voice reads those its own way"))
        if not (e.say or e.ipa or e.spell):
            problems.append((e.word, "entry has no say, ipa or spell"))
            continue
        plain = f"{e.word} burada." if lexicon.locale.lower().startswith("tr") else f"{e.word} here."
        out = prepare(plain, provider="openai", locale=lexicon.locale, lexicon=lexicon).text
        if (e.say and e.say not in out) or (not e.say and out == plain):
            problems.append((e.word, f"not replaced in a sentence: {out!r}"))
    return problems


# --- the file -------------------------------------------------------------------------------------


def _yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def to_yaml(lexicon: Lexicon, header: list[str] | None = None) -> str:
    """The flow-style YAML the bundled lexicons use, one entry per line, with an optional comment header."""
    lines = [f"# {h}" if h else "#" for h in (header or [])]
    lines += [f"locale: {lexicon.locale}", "entries:"]
    for e in lexicon.entries:
        fields = [f"word: {_yaml_str(e.word)}"]
        if e.ipa:
            fields.append(f"ipa: {_yaml_str(e.ipa)}")
        if e.say:
            fields.append(f"say: {_yaml_str(e.say)}")
        if e.spell:
            fields.append("spell: true")
        if e.case_sensitive:
            fields.append("case_sensitive: true")
        lines.append(f"  - {{{', '.join(fields)}}}")
    return "\n".join(lines) + "\n"


def header_of(path: Path) -> list[str]:
    """The comment lines at the top of an existing lexicon file, kept when it is rewritten."""
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            out.append(line[1:].strip())
        elif line.strip():
            break
    return out


def default_header(locale: str, model: str) -> list[str]:
    return [f"Pronunciation lexicon drafted by `speechready lexicon build` on {date.today().isoformat()} with {model}.",
            "Review every entry: a model's respelling is a draft, not a measurement. Load it with",
            f'prepare(text, locale="{locale}", lexicon="path/to/this/file") in Python or JavaScript.']


def write(lexicon: Lexicon, path: Path, header: list[str] | None = None) -> None:
    if path.suffix == ".json":
        path.write_text(lexicon.to_json(), encoding="utf-8")
    else:
        path.write_text(to_yaml(lexicon, header), encoding="utf-8")


__all__ = ["Build", "build", "chat", "check", "read_glossary", "scan", "to_yaml", "write"]
