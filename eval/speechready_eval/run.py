"""Run the evaluation.

    python -m speechready_eval.run --locales en --providers openai --stt openai --limit 20

Each corpus line is synthesized twice per voice (raw and preprocessed), both
audios are transcribed, and the transcripts are scored against the intended
words. Results accumulate in eval/out/results.jsonl, so a rerun skips what is
done and a crash loses nothing. Providers run in parallel, one worker each, so
no provider ever sees more than one request at a time. `report` renders the
tables and the page.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from speechready import prepare

from . import corpus, metrics, synth, transcribe

OUT = Path(__file__).resolve().parents[1] / "out"


def _key(line_id: str, voice: synth.Voice, variant: str) -> str:
    return hashlib.sha1(f"{line_id}|{voice.provider}|{voice.model}|{voice.voice}|{variant}".encode()).hexdigest()[:16]


def _load_done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done: set[str] = set()
    for l in path.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            (done.discard if "error" in r else done.add)(r["key"])  # last write wins; an error is retried next run
    return done


def _one(line: corpus.Line, v: synth.Voice, variant: str, text: str, processed, stt: str, synth_only: bool = False) -> dict | None:
    """Synthesize (if the clip is not there yet) and transcribe one variant. With `synth_only`
    the clip is written and None is returned; a later run without the flag transcribes it."""
    key = _key(line.id, v, variant)
    audio = OUT / "audio" / f"{key}.mp3"
    base = {"key": key, "id": line.id, "locale": line.locale, "cls": line.cls, "variant": variant,
            "provider": v.provider, "model": v.model, "voice": v.voice, "text": text, "intended": line.intended}
    try:
        if not audio.exists():
            if not synth.available(v.provider):
                raise RuntimeError(f"no clip on disk and the {v.provider} package or key is not available here")
            audio.write_bytes(synth.synthesize(text, v, preprocessed=(variant == "processed")))
        if synth_only:
            return None
        hyp = transcribe.transcribe(audio, line.locale, stt)
        score = metrics.wer(line.intended, hyp, line.locale)
        return {**base, "transcript": hyp, "wer": round(score, 4), "misread": metrics.is_misread(line.intended, hyp, line.locale),
                "audio": audio.name, "changes": [c.rule for c in processed.changes] if variant == "processed" else [], "ts": time.time()}
    except Exception as exc:  # noqa: BLE001 - record and move on
        return {**base, "error": f"{type(exc).__name__}: {exc}", "ts": time.time()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locales", default="en,tr")
    ap.add_argument("--providers", default="all", help="comma list or 'all'; providers whose keys (hosted) or packages (local) are missing are skipped")
    ap.add_argument("--voice", action="append", default=[], help="provider:model:voice[:locale]; repeatable, replaces the defaults")
    ap.add_argument("--stt", default="whisper", choices=["whisper", "openai"])
    ap.add_argument("--limit", type=int, default=None, help="first N corpus lines per locale")
    ap.add_argument("--ids", default=None, help="regex on line ids; only matching lines run (e.g. '^heldout\\.')")
    ap.add_argument("--dry-run", action="store_true", help="print what would be synthesized and exit")
    ap.add_argument("--synth-only", action="store_true", help="write the audio clips and stop; a later run transcribes them (keeps local TTS models and Whisper in separate processes)")
    ap.add_argument("--redo", default=None, help="'changed' re-synthesizes every processed variant whose text the library now renders differently; otherwise a regex on line ids")
    args = ap.parse_args(argv)

    locales = tuple(args.locales.split(","))
    lines = [l for loc in locales for l in corpus.build((loc,), args.limit)]
    if args.ids:
        lines = [l for l in lines if re.search(args.ids, l.id)]

    voices: list[synth.Voice] = []
    if args.voice:
        for spec in args.voice:
            parts = spec.split(":")
            voices.append(synth.Voice(parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 else "en-US"))
    else:
        wanted = set(synth.ADAPTERS) if args.providers == "all" else set(args.providers.split(","))
        for loc, vs in synth.DEFAULT_VOICES.items():
            if loc.split("-")[0] in locales:
                voices.extend(v for v in vs if v.provider in wanted)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audio").mkdir(exist_ok=True)
    results = OUT / "results.jsonl"
    done = _load_done(results)

    # A provider without its key or package can still be transcribed when its clips are already on disk
    # (a --synth-only pass in another environment); it is skipped only when it has nothing to transcribe.
    def has_clips(provider: str) -> bool:
        return any((OUT / "audio" / f"{_key(l.id, v, var)}.mp3").exists()
                   for l in lines for v in voices if v.provider == provider and v.locale == l.locale for var in ("raw", "processed"))

    missing = sorted({v.provider for v in voices if not synth.available(v.provider) and not has_clips(v.provider)})
    if missing:
        print(f"skipping providers whose keys or packages are missing: {', '.join(missing)}", file=sys.stderr)
        voices = [v for v in voices if v.provider not in missing]

    jobs = [(line, v) for line in lines for v in voices if v.locale == line.locale]
    if args.redo == "changed":
        stored: dict[str, str] = {}
        if results.exists():
            for l in results.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    r = json.loads(l)
                    if r.get("variant") == "processed":
                        stored[r["key"]] = r["text"]
        redo = set()
        for line, v in jobs:
            k = _key(line.id, v, "processed")
            if k in stored and stored[k] != prepare(line.raw, provider=v.provider, model=v.model, locale=line.locale).text:
                redo.add(k)
    elif args.redo:
        pat = re.compile(args.redo)
        redo = {_key(line.id, v, "processed") for line, v in jobs if pat.search(line.id)}
    else:
        redo = set()
    if redo:
        for k in redo:
            (OUT / "audio" / f"{k}.mp3").unlink(missing_ok=True)
        done -= redo
        print(f"redoing {len(redo)} processed variants", file=sys.stderr)
    print(f"{len(lines)} lines x {len(voices)} voices -> {len(jobs)} line/voice pairs, {len(done)} variants already done", file=sys.stderr)
    if args.dry_run:
        for line, v in jobs[:10]:
            print(f"{line.id} [{v.provider}/{v.model}] raw={line.raw!r}")
        return 0

    lock = threading.Lock()
    sink = results.open("a", encoding="utf-8")

    def worker(provider: str) -> int:
        n = 0
        for line, v in jobs:
            if v.provider != provider:
                continue
            processed = prepare(line.raw, provider=v.provider, model=v.model, locale=line.locale)
            for variant, text in (("raw", line.raw), ("processed", processed.text)):
                if _key(line.id, v, variant) in done:
                    continue
                row = _one(line, v, variant, text, processed, args.stt, args.synth_only)
                if row is None:
                    print(f"{line.id} {v.provider}/{v.model} {variant} synthesized", file=sys.stderr)
                    n += 1
                    continue
                with lock:
                    sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                    sink.flush()
                    done.add(row["key"])
                msg = f"ERROR {row['error']}" if "error" in row else f"wer={row['wer']}"
                print(f"{line.id} {v.provider}/{v.model} {variant} {msg}", file=sys.stderr)
                n += 1
        return n

    providers = sorted({v.provider for v in voices})
    with ThreadPoolExecutor(max_workers=max(1, len(providers))) as pool:
        counts = list(pool.map(worker, providers))
    sink.close()
    print(f"done: {sum(counts)} new variants", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
