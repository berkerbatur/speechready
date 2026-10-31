"""TTS adapters. Each takes text and returns MP3 bytes. Keys come from the environment.

Raw text goes to each provider the way a developer would send it: plain text.
Preprocessed text goes the way the profile says: an SSML body wrapped in
<speak> for SSML profiles, plain text otherwise.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from xml.sax.saxutils import escape as xml_escape

import httpx

from speechready import resolve_profile

TIMEOUT = 120.0

# Accepted environment variable names per provider; the first one set wins.
ENV = {
    "elevenlabs": [("ELEVENLABS_API_KEY",)],
    "openai": [("OPENAI_API_KEY",)],
    "azure": [("AZURE_SPEECH_KEY",), ("AZURE_SPEECH_REGION",)],
    "google": [("GOOGLE_TTS_API_KEY", "GOOGLE_CLOUD_PROJECT_API_KEY")],
    "polly": [("AWS_ACCESS_KEY_ID", "AWS_POLLY_USER_AWS_CLI_ACCESS_KEY"), ("AWS_SECRET_ACCESS_KEY", "AWS_POLLY_USER_AWS_CLI_ACCESS_SECRET")],
    "cartesia": [("CARTESIA_API_KEY",)],
    "deepgram": [("DEEPGRAM_API_KEY",)],
}


def _env(*names: str) -> str:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    raise KeyError(f"none of {names} is set")


def has_keys(provider: str) -> bool:
    return all(any(os.environ.get(n) for n in group) for group in ENV[provider])


@dataclass(frozen=True)
class Voice:
    provider: str  # elevenlabs | openai | azure | google | polly | cartesia | deepgram
    model: str
    voice: str
    locale: str = "en-US"
    ext: str = "mp3"


def _ssml_mode(v: Voice, preprocessed: bool) -> bool:
    return preprocessed and resolve_profile(v.provider, v.model).syntax == "ssml"


def elevenlabs(text: str, v: Voice, preprocessed: bool) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{v.voice}?output_format=mp3_44100_128"
    body = {"text": text, "model_id": v.model}
    r = httpx.post(url, json=body, headers={"xi-api-key": _env("ELEVENLABS_API_KEY")}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content


def openai(text: str, v: Voice, preprocessed: bool) -> bytes:
    body = {"model": v.model, "voice": v.voice, "input": text, "response_format": "mp3"}
    r = httpx.post("https://api.openai.com/v1/audio/speech", json=body,
                   headers={"Authorization": f"Bearer {_env('OPENAI_API_KEY')}"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content


def azure(text: str, v: Voice, preprocessed: bool) -> bytes:
    region = _env("AZURE_SPEECH_REGION")
    body = text if _ssml_mode(v, preprocessed) else xml_escape(text)
    ssml = (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{v.locale}">'
        f'<voice name="{v.voice}">{body}</voice></speak>'
    )
    r = httpx.post(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        content=ssml.encode("utf-8"),
        headers={
            "Ocp-Apim-Subscription-Key": _env("AZURE_SPEECH_KEY"),
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3",
            "User-Agent": "speechready-eval",
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.content


def google(text: str, v: Voice, preprocessed: bool) -> bytes:
    key = _env("GOOGLE_TTS_API_KEY", "GOOGLE_CLOUD_PROJECT_API_KEY")
    inp = {"ssml": f"<speak>{text}</speak>"} if _ssml_mode(v, preprocessed) else {"text": text}
    body = {"input": inp, "voice": {"languageCode": v.locale, "name": v.voice}, "audioConfig": {"audioEncoding": "MP3"}}
    r = httpx.post(f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}", json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return base64.b64decode(r.json()["audioContent"])


def polly(text: str, v: Voice, preprocessed: bool) -> bytes:
    import boto3  # only needed for this provider

    client = boto3.client(
        "polly",
        region_name=os.environ.get("AWS_POLLY_REGION") or os.environ.get("AWS_REGION") or "eu-central-1",
        aws_access_key_id=_env("AWS_ACCESS_KEY_ID", "AWS_POLLY_USER_AWS_CLI_ACCESS_KEY"),
        aws_secret_access_key=_env("AWS_SECRET_ACCESS_KEY", "AWS_POLLY_USER_AWS_CLI_ACCESS_SECRET"),
    )
    ssml = _ssml_mode(v, preprocessed)
    resp = client.synthesize_speech(
        Engine=v.model, OutputFormat="mp3", VoiceId=v.voice, LanguageCode=v.locale,
        Text=f"<speak>{text}</speak>" if ssml else text, TextType="ssml" if ssml else "text",
    )
    return resp["AudioStream"].read()


def cartesia(text: str, v: Voice, preprocessed: bool) -> bytes:
    body = {
        "model_id": v.model,
        "transcript": text,
        "voice": {"id": v.voice},
        "language": v.locale.split("-")[0],
        "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000},
    }
    r = httpx.post("https://api.cartesia.ai/tts/bytes", json=body,
                   headers={"Authorization": f"Bearer {_env('CARTESIA_API_KEY')}", "Cartesia-Version": "2026-08-14"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content


def deepgram(text: str, v: Voice, preprocessed: bool) -> bytes:
    r = httpx.post(f"https://api.deepgram.com/v1/speak?model={v.voice}&encoding=mp3", json={"text": text},
                   headers={"Authorization": f"Token {_env('DEEPGRAM_API_KEY')}"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content


ADAPTERS = {
    "elevenlabs": elevenlabs, "openai": openai, "azure": azure, "google": google,
    "polly": polly, "cartesia": cartesia, "deepgram": deepgram,
}


def synthesize(text: str, v: Voice, preprocessed: bool) -> bytes:
    try:
        fn = ADAPTERS[v.provider]
    except KeyError:
        raise ValueError(f"unknown provider {v.provider!r}; known: {sorted(ADAPTERS)}") from None
    return fn(text, v, preprocessed)


# Voices used by default. Override with --voice provider:model:voice[:locale] on the command line.
# Model names are the ones the profiles in spec/profiles list, so `prepare` picks the right dialect.
_CARTESIA_VOICE = "f786b574-daa5-4673-aa0c-cbe3e8534c02"  # Katie, a public multilingual voice
DEFAULT_VOICES = {
    "en-US": [
        Voice("elevenlabs", "eleven_multilingual_v2", "JBFqnCBsd6RMkjVDRZzb", "en-US"),  # George
        Voice("openai", "gpt-4o-mini-tts", "alloy", "en-US"),
        Voice("azure", "neural", "en-US-AvaMultilingualNeural", "en-US"),
        Voice("google", "chirp3-hd", "en-US-Chirp3-HD-Aoede", "en-US"),
        Voice("google", "neural2", "en-US-Neural2-F", "en-US"),
        Voice("polly", "neural", "Joanna", "en-US"),
        Voice("polly", "generative", "Ruth", "en-US"),
        Voice("cartesia", "sonic-3.6", _CARTESIA_VOICE, "en-US"),
        Voice("deepgram", "aura-2", "aura-2-thalia-en", "en-US"),
    ],
    "tr-TR": [
        Voice("elevenlabs", "eleven_multilingual_v2", "JBFqnCBsd6RMkjVDRZzb", "tr-TR"),
        Voice("openai", "gpt-4o-mini-tts", "alloy", "tr-TR"),
        Voice("azure", "neural", "tr-TR-EmelNeural", "tr-TR"),
        Voice("google", "chirp3-hd", "tr-TR-Chirp3-HD-Aoede", "tr-TR"),
        Voice("google", "wavenet", "tr-TR-Wavenet-A", "tr-TR"),
        Voice("polly", "neural", "Burcu", "tr-TR"),
        Voice("cartesia", "sonic-3.6", _CARTESIA_VOICE, "tr-TR"),
    ],
}
