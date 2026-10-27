"""Run the evaluation.

    python -m speechready_eval.run --locales en --providers openai --stt openai --limit 20

Each corpus line is synthesized twice per voice (raw and preprocessed), both
audios are transcribed, and the transcripts are scored against the intended
words. Results accumulate in eval/out/results.jsonl, so a rerun skips what is
done and a crash loses nothing. `report` renders the tables and the page.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from speechready import prepare

from . import corpus, metrics, synth, transcribe

OUT = Path(__file__).resolve().parents[1] / "out"


def _key(line_id: str, voice: synth.Voice, variant: str) -> str:
    return hashlib.sha1(f"{line_id}|{voice.provider}|{voice.model}|{voice.voice}|{variant}".encode()).hexdigest()[:16]


def _load_done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(l)["key"] for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locales", default="en,tr")
    ap.add_argument("--providers", default="elevenlabs,openai,azure")
    ap.add_argument("--voice", action="append", default=[], help="provider:model:voice[:locale]; repeatable, replaces the defaults")
    ap.add_argument("--stt", default="whisper", choices=["whisper", "openai"])
    ap.add_argument("--limit", type=int, default=None, help="first N corpus lines")
    ap.add_argument("--dry-run", action="store_true", help="print what would be synthesized and exit")
    args = ap.parse_args(argv)

    locales = tuple(args.locales.split(","))
    providers = set(args.providers.split(","))
    lines = corpus.build(locales, args.limit)

    voices: list[synth.Voice] = []
    if args.voice:
        for spec in args.voice:
            parts = spec.split(":")
            voices.append(synth.Voice(parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 else "en-US"))
    else:
        for loc, vs in synth.DEFAULT_VOICES.items():
            if loc.split("-")[0] in locales:
                voices.extend(v for v in vs if v.provider in providers)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audio").mkdir(exist_ok=True)
    results = OUT / "results.jsonl"
    done = _load_done(results)

    jobs = [(line, v) for line in lines for v in voices if v.locale == line.locale]
    print(f"{len(lines)} lines x {len(voices)} voices -> {len(jobs)} line/voice pairs, {len(done)} variants already done", file=sys.stderr)
    if args.dry_run:
        for line, v in jobs[:10]:
            print(f"{line.id} [{v.provider}/{v.model}] raw={line.raw!r}")
        return 0

    with results.open("a", encoding="utf-8") as sink:
        for line, v in jobs:
            processed = prepare(line.raw, provider=v.provider, model=v.model, locale=line.locale)
            for variant, text in (("raw", line.raw), ("processed", processed.text)):
                key = _key(line.id, v, variant)
                if key in done:
                    continue
                audio = OUT / "audio" / f"{key}.mp3"
                try:
                    if not audio.exists():
                        audio.write_bytes(synth.synthesize(text, v, preprocessed=(variant == "processed")))
                    hyp = transcribe.transcribe(audio, line.locale, args.stt)
                    score = metrics.wer(line.intended, hyp, line.locale)
                    row = {
                        "key": key, "id": line.id, "locale": line.locale, "cls": line.cls, "variant": variant,
                        "provider": v.provider, "model": v.model, "voice": v.voice,
                        "text": text, "intended": line.intended, "transcript": hyp,
                        "wer": round(score, 4), "misread": metrics.is_misread(line.intended, hyp, line.locale),
                        "audio": audio.name, "changes": [c.rule for c in processed.changes] if variant == "processed" else [],
                        "ts": time.time(),
                    }
                except Exception as exc:  # noqa: BLE001 - record and move on
                    row = {"key": key, "id": line.id, "locale": line.locale, "cls": line.cls, "variant": variant,
                           "provider": v.provider, "model": v.model, "voice": v.voice, "text": text,
                           "intended": line.intended, "error": f"{type(exc).__name__}: {exc}", "ts": time.time()}
                    print(f"ERROR {line.id} {v.provider} {variant}: {exc}", file=sys.stderr)
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                sink.flush()
                done.add(key)
                print(f"{line.id} {v.provider} {variant} wer={row.get('wer')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
