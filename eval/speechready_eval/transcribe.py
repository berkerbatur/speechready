"""STT adapters: a local faster-whisper model, or OpenAI's transcription API."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import httpx


@lru_cache(maxsize=1)
def _whisper(model_size: str):
    from faster_whisper import WhisperModel

    device = "cuda" if os.environ.get("SPEECHREADY_EVAL_DEVICE", "auto") == "cuda" else "auto"
    return WhisperModel(model_size, device=device, compute_type="int8" if device != "cuda" else "float16")


def whisper_local(path: Path, locale: str, model_size: str = "large-v3") -> str:
    model = _whisper(model_size)
    segments, _ = model.transcribe(str(path), language=locale.split("-")[0], beam_size=5)
    return " ".join(s.text.strip() for s in segments)


def openai_api(path: Path, locale: str, model: str = "gpt-4o-transcribe") -> str:
    key = os.environ["OPENAI_API_KEY"]
    with path.open("rb") as f:
        r = httpx.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {key}"},
            data={"model": model, "language": locale.split("-")[0]},
            files={"file": (path.name, f, "audio/mpeg")},
            timeout=180.0,
        )
    r.raise_for_status()
    return r.json()["text"]


def transcribe(path: Path, locale: str, backend: str = "whisper") -> str:
    if backend == "whisper":
        return whisper_local(path, locale)
    if backend == "openai":
        return openai_api(path, locale)
    raise ValueError(f"unknown STT backend {backend!r}")
