"""TTS adapters. Each takes text and returns audio bytes. Keys come from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

TIMEOUT = 120.0


@dataclass(frozen=True)
class Voice:
    provider: str  # elevenlabs | openai | azure
    model: str
    voice: str
    locale: str = "en-US"
    ext: str = "mp3"


def elevenlabs(text: str, v: Voice) -> bytes:
    key = os.environ["ELEVENLABS_API_KEY"]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{v.voice}?output_format=mp3_44100_128"
    body = {"text": text, "model_id": v.model}
    r = httpx.post(url, json=body, headers={"xi-api-key": key}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content


def openai(text: str, v: Voice) -> bytes:
    key = os.environ["OPENAI_API_KEY"]
    body = {"model": v.model, "voice": v.voice, "input": text, "response_format": "mp3"}
    r = httpx.post("https://api.openai.com/v1/audio/speech", json=body, headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content


def azure(text: str, v: Voice, ssml_body: bool = True) -> bytes:
    key = os.environ["AZURE_SPEECH_KEY"]
    region = os.environ["AZURE_SPEECH_REGION"]
    if not ssml_body:
        from xml.sax.saxutils import escape

        text = escape(text)
    ssml = (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{v.locale}">'
        f'<voice name="{v.voice}">{text}</voice></speak>'
    )
    r = httpx.post(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        content=ssml.encode("utf-8"),
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3",
            "User-Agent": "speechready-eval",
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.content


def synthesize(text: str, v: Voice, preprocessed: bool) -> bytes:
    if v.provider == "elevenlabs":
        return elevenlabs(text, v)
    if v.provider == "openai":
        return openai(text, v)
    if v.provider == "azure":
        # raw text is escaped by us; preprocessed text is already an SSML body
        return azure(text, v, ssml_body=preprocessed)
    raise ValueError(f"unknown provider {v.provider!r}")


# Voices used by default. Override with --voice provider:model:voice on the command line.
DEFAULT_VOICES = {
    "en-US": [
        Voice("elevenlabs", "eleven_multilingual_v2", "JBFqnCBsd6RMkjVDRZzb", "en-US"),  # George
        Voice("openai", "gpt-4o-mini-tts", "alloy", "en-US"),
        Voice("azure", "neural", "en-US-AvaMultilingualNeural", "en-US"),
    ],
    "tr-TR": [
        Voice("elevenlabs", "eleven_multilingual_v2", "JBFqnCBsd6RMkjVDRZzb", "tr-TR"),
        Voice("openai", "gpt-4o-mini-tts", "alloy", "tr-TR"),
        Voice("azure", "neural", "tr-TR-EmelNeural", "tr-TR"),
    ],
}
