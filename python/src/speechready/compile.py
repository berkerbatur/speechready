"""Stage 3: compile. Render pacing intents in the target provider's syntax and escape text."""

from __future__ import annotations

import re

from .changes import Recorder
from .intents import Intent, split_on_sentinels
from .profiles import Profile

STAGE = "compile"

_UNKNOWN_TAG = re.compile(r"\[([^\[\]\n]{1,60})\]")
_XML_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}


def _escape_xml(text: str) -> str:
    return "".join(_XML_ESCAPES.get(c, c) for c in text)


def _punctuation_pause(prev: str, ms: int) -> str:
    """Render a pause as punctuation. `prev` is the text so far (used to avoid doubling)."""
    tail = prev.rstrip()
    if not tail:
        return ""  # a pause before any text: nothing to pause after
    last = tail[-1]
    if ms <= 300:
        if last in ".!?,;:…":
            return " "
        return ", "
    if last in ".!?…":
        return " " if ms <= 1000 else "\n"
    if ms <= 1000:
        return "... "
    return "...\n"


def _render_pause(ms: int, spec: dict, prev: str) -> str:
    render = spec.get("render", "punctuation")
    if render == "punctuation":
        return _punctuation_pause(prev, ms)
    lo, hi = spec.get("min_ms", 0), spec.get("max_ms")
    ms = max(ms, lo)
    if hi is not None:
        ms = min(ms, hi)
    seconds = f"{ms / 1000:g}"
    return render.format(ms=ms, s=seconds)


def _render_spell(text: str, spec: dict) -> str:
    render = spec.get("render", "spaced")
    if render == "spaced":
        return " ".join(ch.upper() for ch in text if not ch.isspace())
    return render.format(text=text)


def _render_em(text: str, spec: dict) -> str:
    render = spec.get("render", "{text}")
    return render.format(text=text)


def _render_phoneme(intent: Intent, profile: Profile) -> str:
    """Phoneme tag where the provider takes one, else the respelling, else the word."""
    esc = _escape_xml if profile.escape == "xml" else (lambda t: t)
    spec = profile.intents.get("phoneme", {})
    if intent.ipa and spec.get("render"):
        return spec["render"].format(text=esc(intent.text), ipa=esc(intent.ipa))
    if intent.say:
        return esc(intent.say)
    return esc(intent.text)


def compile_text(text: str, intents: list[Intent], profile: Profile, recorder: Recorder | None = None) -> str:
    rec = recorder or Recorder()
    out: list[str] = []
    for segment, idx in split_on_sentinels(text):
        if idx is None:
            seg = _unknown_tags(segment, profile, rec)
            if profile.escape == "xml":
                esc = _escape_xml(seg)
                rec.add(STAGE, "compile.escape.xml", seg, esc, "escaped & < > for SSML")
                seg = esc
            out.append(seg)
            continue
        intent = intents[idx]
        prev = "".join(out)
        if intent.kind == "pause":
            spec = profile.intents.get("pause", {})
            rendered = _render_pause(intent.ms, spec, prev)
            if out and rendered.startswith((",", ".")) and prev.endswith(" "):
                out[-1] = out[-1].rstrip(" ")
            rec.add(STAGE, "compile.pause", f"[pause {intent.ms}ms]", rendered, f"pause rendered for {profile.id}")
        elif intent.kind == "phoneme":
            rendered = _render_phoneme(intent, profile)
            rec.add(STAGE, "compile.phoneme", intent.text, rendered, f"pronunciation rendered for {profile.id}")
        elif intent.kind == "spell":
            spec = profile.intents.get("spell", {})
            body = _escape_xml(intent.text) if profile.escape == "xml" else intent.text
            rendered = _render_spell(body, spec)
            rec.add(STAGE, "compile.spell", f"[spell {intent.text}]", rendered, f"spell-out rendered for {profile.id}")
        else:
            spec = profile.intents.get("emphasis", {})
            body = _escape_xml(intent.text) if profile.escape == "xml" else intent.text
            rendered = _render_em(body, spec)
            rec.add(STAGE, "compile.emphasis", f"[em {intent.text}]", rendered, f"emphasis rendered for {profile.id}")
        out.append(rendered)
    result = "".join(out)
    result = re.sub(r"[ \t]{2,}", " ", result)
    result = re.sub(r" +\n", "\n", result)
    result = re.sub(r"\n +", "\n", result)
    return result.strip()


def _unknown_tags(segment: str, profile: Profile, rec: Recorder) -> str:
    """Bracket tags the pipeline does not know: pass through on audio-tag models, drop elsewhere."""

    def repl(m: re.Match[str]) -> str:
        body = m.group(1).strip()
        wordy = bool(re.fullmatch(r"[A-Za-zÀ-ÿĞğİıŞşÇçÖöÜü ,'\-]+", body))
        if profile.audio_tags and wordy:
            return m.group(0)
        rec.add(STAGE, "compile.unknown_tag", m.group(0), "", "bracket tag removed; this model does not read audio tags")
        return ""

    new = _UNKNOWN_TAG.sub(repl, segment)
    return new


__all__ = ["compile_text"]
