"""The "just prompt the LLM" baseline: ask a chat model to prepare the text for speech.

The harness runs this as a third variant (`--variants raw,processed,llm`) beside the
raw text and speechready's output. The prompt is what a careful developer would
write without a library: strip markdown, write out the things voices misread, keep
the content. It knows nothing about the provider, since a prompt cannot (a break tag
for ElevenLabs is a comma for OpenAI). Rewrites are cached in eval/out/rewrites.jsonl
so a rerun or a second voice does not call the model again.

Needs OPENAI_API_KEY.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "out"
CACHE = OUT / "rewrites.jsonl"
DEFAULT_MODEL = "gpt-6-luna"

LANGUAGE = {"en": "English", "tr": "Turkish"}

SYSTEM = (
    "You prepare text for a text-to-speech engine. Rewrite the user's message so that a TTS voice reads it "
    "correctly and naturally in {language}. Remove markdown and formatting symbols, emoji and anything else that "
    "should not be spoken; for a URL say only the site name; leave out code blocks. Write out everything a voice might "
    "misread the way a native speaker would say it: numbers, dates, times, prices, percentages, phone numbers, "
    "identifiers, units, abbreviations and acronyms. Keep every piece of information and the original order; do not "
    "add, shorten, summarize or explain anything. Output only the rewritten text, as plain text."
)

_lock = threading.Lock()
_cache: dict[str, str] | None = None


def _key(text: str, locale: str, model: str) -> str:
    return hashlib.sha1(f"{model}|{locale}|{text}".encode()).hexdigest()[:16]


def _load() -> dict[str, str]:
    global _cache
    if _cache is None:
        _cache = {}
        if CACHE.exists():
            for l in CACHE.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    r = json.loads(l)
                    _cache[r["key"]] = r["text"]
    return _cache


def rewrite(text: str, locale: str, model: str = DEFAULT_MODEL) -> str:
    """The model's spoken-form rewrite of `text`, from the cache when it has been asked before."""
    k = _key(text, locale, model)
    with _lock:
        cache = _load()
        if k in cache:
            return cache[k]
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set; the llm variant needs it")
    r = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model,
              "messages": [{"role": "system", "content": SYSTEM.format(language=LANGUAGE.get(locale.split("-")[0], locale))},
                           {"role": "user", "content": text}]},
        timeout=120,
    )
    r.raise_for_status()
    out = r.json()["choices"][0]["message"]["content"].strip()
    with _lock:
        cache[k] = out
        OUT.mkdir(parents=True, exist_ok=True)
        with CACHE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": k, "model": model, "locale": locale, "raw": text, "text": out}, ensure_ascii=False) + "\n")
    return out
