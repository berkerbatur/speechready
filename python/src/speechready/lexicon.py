"""One pronunciation lexicon, applied in the pipeline and exported to each vendor's format.

An entry says how a word is pronounced in one of three ways:
- `ipa`: an IPA transcription, rendered as a phoneme tag where the provider
  accepts one (Azure, Google, Polly) and exported to lexicon files;
- `say`: a respelling or alias ("engine X", "sequel") that replaces the word in
  the text, which works on every provider;
- `spell: true`: the word is read letter by letter.

When a provider cannot take a phoneme tag, an entry falls back to `say`, then
to `spell`, then leaves the word alone.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

from .intents import SENTINEL_CLOSE, SENTINEL_OPEN, Intent


@dataclass(frozen=True)
class Entry:
    word: str
    ipa: str = ""
    say: str = ""
    spell: bool = False
    case_sensitive: bool = False

    def intent(self, matched: str) -> Intent:
        if self.spell and not self.ipa and not self.say:
            return Intent("spell", text=matched)
        return Intent("phoneme", text=matched, ipa=self.ipa, say=self.say)


@dataclass
class Lexicon:
    entries: list[Entry] = field(default_factory=list)
    locale: str = "en-US"

    # --- construction ---------------------------------------------------------------

    @classmethod
    def from_entries(cls, entries: list[dict], locale: str = "en-US") -> Lexicon:
        return cls([Entry(**e) for e in entries], locale)

    @classmethod
    def load(cls, path: str | Path) -> Lexicon:
        path = Path(path)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.suffix in (".yaml", ".yml") else json.loads(path.read_text(encoding="utf-8"))
        return cls.from_entries(data.get("entries", []), data.get("locale", "en-US"))

    def to_dict(self) -> dict:
        return {
            "locale": self.locale,
            "entries": [
                {k: v for k, v in {"word": e.word, "ipa": e.ipa, "say": e.say, "spell": e.spell,
                                   "case_sensitive": e.case_sensitive}.items() if v}
                for e in self.entries
            ],
        }

    # --- applying to text ------------------------------------------------------------

    def apply(self, text: str, intents: list[Intent]) -> str:
        """Replace every lexicon word in `text` with an intent sentinel; appends to `intents`."""
        if not self.entries:
            return text
        for entry in sorted(self.entries, key=lambda e: len(e.word), reverse=True):
            flags = 0 if entry.case_sensitive else re.IGNORECASE
            pattern = re.compile(rf"(?<![\w{SENTINEL_OPEN}{SENTINEL_CLOSE}]){re.escape(entry.word)}(?![\w])", flags)

            def repl(m: re.Match[str], entry=entry) -> str:
                intents.append(entry.intent(m.group(0)))
                return f"{SENTINEL_OPEN}{len(intents) - 1}{SENTINEL_CLOSE}"

            text = pattern.sub(repl, text)
        return text

    # --- export ----------------------------------------------------------------------------

    def to_pls(self, alphabet: str = "ipa") -> str:
        """Pronunciation Lexicon Specification XML, accepted by ElevenLabs, Azure and Amazon Polly."""
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<lexicon version="1.0" xmlns="http://www.w3.org/2005/01/pronunciation-lexicon" alphabet="{alphabet}" xml:lang="{self.locale}">',
        ]
        for e in self.entries:
            lines.append("  <lexeme>")
            lines.append(f"    <grapheme>{escape(e.word)}</grapheme>")
            if e.ipa:
                lines.append(f"    <phoneme>{escape(e.ipa)}</phoneme>")
            elif e.say:
                lines.append(f"    <alias>{escape(e.say)}</alias>")
            elif e.spell:
                lines.append(f"    <alias>{escape(' '.join(e.word))}</alias>")
            lines.append("  </lexeme>")
        lines.append("</lexicon>")
        return "\n".join(lines) + "\n"

    def to_google_json(self) -> str:
        """Google Cloud TTS custom pronunciations (v1beta1 `customPronunciations`). IPA entries only."""
        items = [
            {"phrase": e.word, "phoneticEncoding": "PHONETIC_ENCODING_IPA", "pronunciation": e.ipa}
            for e in self.entries if e.ipa
        ]
        return json.dumps({"pronunciations": items}, ensure_ascii=False, indent=2) + "\n"

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"

    def export_for(self, profile) -> str | None:
        """The upload file for a provider profile, or None when the provider takes no lexicon."""
        if profile.lexicon_format == "none":
            return None
        return self.export(profile.lexicon_format, profile.lexicon_alphabet)

    def export(self, fmt: str, alphabet: str = "ipa") -> str:
        """`pls`, `google`, or `json`."""
        if fmt == "pls":
            return self.to_pls(alphabet)
        if fmt == "google":
            return self.to_google_json()
        if fmt == "json":
            return self.to_json()
        raise ValueError(f"unknown lexicon format {fmt!r}; use pls, google or json")


__all__ = ["Entry", "Lexicon"]
