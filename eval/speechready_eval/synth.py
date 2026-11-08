"""TTS adapters. Each takes text and returns MP3 bytes.

Hosted providers take their keys from the environment. Local models (Kokoro, Piper,
Chatterbox, XTTS v2, Orpheus) need their Python package installed and ffmpeg on the
path to encode MP3; Piper also needs its voice files under eval/models/piper. A
provider whose package or keys are missing is skipped by the run.

Raw text goes to each provider the way a developer would send it: plain text.
Preprocessed text goes the way the profile says: an SSML body wrapped in
<speak> for SSML profiles, plain text otherwise.
"""

from __future__ import annotations

import base64
import importlib.util
import io
import os
import subprocess
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
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


# Local models: the module whose presence means the provider can run here.
LOCAL = {"kokoro": "kokoro", "piper": "piper", "chatterbox": "chatterbox", "xtts": "TTS", "orpheus": "orpheus_tts"}
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"  # downloaded voice files, gitignored


def available(provider: str) -> bool:
    """True when the provider can run here: its package is importable (local models) or its keys are set."""
    if provider in LOCAL:
        return importlib.util.find_spec(LOCAL[provider]) is not None
    return all(any(os.environ.get(n) for n in group) for group in ENV[provider])


has_keys = available  # the earlier name


@dataclass(frozen=True)
class Voice:
    provider: str  # a key of ADAPTERS: elevenlabs | openai | azure | google | polly | cartesia | deepgram | kokoro | piper | chatterbox | xtts | orpheus
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


# --- local models ----------------------------------------------------------------------
# Each returns MP3 like the hosted adapters, so the results file and the listening page
# need no special case. Models are loaded once per process and kept.


def _wav_bytes(samples, rate: int) -> bytes:
    """Mono float or int16 samples to WAV bytes."""
    import numpy as np

    a = np.asarray(samples)
    if a.dtype.kind == "f":
        a = (np.clip(a, -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(a.astype("<i2").tobytes())
    return buf.getvalue()


def _mp3(wav: bytes) -> bytes:
    r = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-codec:a", "libmp3lame", "-q:a", "2", "-f", "mp3", "pipe:1"],
        input=wav, capture_output=True, check=True,
    )
    return r.stdout


@lru_cache(maxsize=4)
def _kokoro(lang_code: str):
    from kokoro import KPipeline

    return KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")


def kokoro(text: str, v: Voice, preprocessed: bool) -> bytes:
    import numpy as np

    lang = {"en-GB": "b", "es": "e", "fr": "f", "hi": "h", "it": "i", "pt": "p"}.get(v.locale, {"en": "a"}.get(v.locale.split("-")[0], "a"))
    pieces = [np.asarray(audio) for _, _, audio in _kokoro(lang)(text, voice=v.voice)]
    return _mp3(_wav_bytes(np.concatenate(pieces) if pieces else np.zeros(2400, dtype="float32"), 24000))


@lru_cache(maxsize=4)
def _piper(name: str):
    from piper import PiperVoice

    path = MODELS_DIR / "piper" / f"{name}.onnx"
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing; download it with: python -m piper.download_voices {name} --data-dir {path.parent}")
    return PiperVoice.load(str(path))


def piper(text: str, v: Voice, preprocessed: bool) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        _piper(v.voice).synthesize_wav(text, w)
    return _mp3(buf.getvalue())


def _device() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=2)
def _chatterbox(model: str):
    if model == "chatterbox-multilingual":
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        return ChatterboxMultilingualTTS.from_pretrained(device=_device())
    from chatterbox.tts import ChatterboxTTS

    return ChatterboxTTS.from_pretrained(device=_device())


def chatterbox(text: str, v: Voice, preprocessed: bool) -> bytes:
    """`voice` is "default" for the built-in voice or the path of a reference clip to clone."""
    m = _chatterbox(v.model)
    kw: dict = {}
    if v.model == "chatterbox-multilingual":
        kw["language_id"] = v.locale.split("-")[0]
    if v.voice != "default":
        kw["audio_prompt_path"] = v.voice
    wav = m.generate(text, **kw)
    return _mp3(_wav_bytes(wav.squeeze(0).cpu().numpy(), m.sr))


@lru_cache(maxsize=1)
def _xtts():
    from TTS.api import TTS

    return TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(_device())


def xtts(text: str, v: Voice, preprocessed: bool) -> bytes:
    """`voice` is one of the model's built-in speakers, e.g. "Ana Florence"."""
    import numpy as np

    wav = _xtts().tts(text=text, speaker=v.voice, language=v.locale.split("-")[0])
    return _mp3(_wav_bytes(np.asarray(wav, dtype="float32"), 24000))


# canopylabs gates its weights behind a Hugging Face login; unsloth republishes them openly, same tensors.
ORPHEUS_REPOS = {"orpheus-3b-0.1-ft": "unsloth/orpheus-3b-0.1-ft"}
# About 86 audio tokens a second: the package default of 1,200 cuts a clip at 14 s, these allow about 80 s.
ORPHEUS_CONTEXT, ORPHEUS_MAX_TOKENS = 8192, 7000


@lru_cache(maxsize=1)
def _orpheus(model: str):
    from orpheus_tts import OrpheusModel
    from vllm import AsyncEngineArgs, AsyncLLMEngine

    class Engine(OrpheusModel):
        def _setup_engine(self):  # the package takes no engine options; short prompts need neither the 128k context nor 90% of the card
            return AsyncLLMEngine.from_engine_args(AsyncEngineArgs(
                model=self.model_name, dtype=self.dtype, max_model_len=ORPHEUS_CONTEXT,
                gpu_memory_utilization=float(os.environ.get("SPEECHREADY_EVAL_VLLM_MEM", "0.8"))))

    return Engine(model_name=ORPHEUS_REPOS.get(model, f"canopylabs/{model}"))


def orpheus(text: str, v: Voice, preprocessed: bool) -> bytes:
    pcm = b"".join(_orpheus(v.model).generate_speech(prompt=text, voice=v.voice, max_tokens=ORPHEUS_MAX_TOKENS))
    import numpy as np

    return _mp3(_wav_bytes(np.frombuffer(pcm, dtype="<i2"), 24000))


ADAPTERS = {
    "elevenlabs": elevenlabs, "openai": openai, "azure": azure, "google": google,
    "polly": polly, "cartesia": cartesia, "deepgram": deepgram,
    "kokoro": kokoro, "piper": piper, "chatterbox": chatterbox, "xtts": xtts, "orpheus": orpheus,
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
        # local models; run when the package is installed (eval[local] covers Kokoro and Piper)
        Voice("kokoro", "kokoro-82m", "af_heart", "en-US"),
        Voice("piper", "piper", "en_US-lessac-medium", "en-US"),
        Voice("chatterbox", "chatterbox-multilingual", "default", "en-US"),
        Voice("xtts", "xtts-v2", "Ana Florence", "en-US"),
        Voice("orpheus", "orpheus-3b-0.1-ft", "tara", "en-US"),
    ],
    "tr-TR": [
        Voice("elevenlabs", "eleven_multilingual_v2", "JBFqnCBsd6RMkjVDRZzb", "tr-TR"),
        Voice("openai", "gpt-4o-mini-tts", "alloy", "tr-TR"),
        Voice("azure", "neural", "tr-TR-EmelNeural", "tr-TR"),
        Voice("google", "chirp3-hd", "tr-TR-Chirp3-HD-Aoede", "tr-TR"),
        Voice("google", "wavenet", "tr-TR-Wavenet-A", "tr-TR"),
        Voice("polly", "neural", "Burcu", "tr-TR"),
        Voice("cartesia", "sonic-3.6", _CARTESIA_VOICE, "tr-TR"),
        Voice("piper", "piper", "tr_TR-dfki-medium", "tr-TR"),
        Voice("chatterbox", "chatterbox-multilingual", "default", "tr-TR"),
        Voice("xtts", "xtts-v2", "Ana Florence", "tr-TR"),
    ],
}
