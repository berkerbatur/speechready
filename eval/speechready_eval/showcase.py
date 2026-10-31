"""Pick the clearest before/after examples and write a self-contained showcase folder.

    python -m speechready_eval.showcase [--per-voice 3]

Writes eval/out/showcase/index.html plus the audio it references, small enough
to publish as a page. Examples are the pairs where the raw text was misread and
the processed text was heard right, spread across providers and locales.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from html import escape
from pathlib import Path

from . import report

OUT = report.OUT
SHOW = OUT / "showcase"

PROVIDER_NAMES = {
    "elevenlabs": "ElevenLabs", "openai": "OpenAI", "azure": "Azure AI Speech", "google": "Google Cloud TTS",
    "polly": "Amazon Polly", "cartesia": "Cartesia", "deepgram": "Deepgram",
}


def pick(ps, per_voice: int):
    by_voice = defaultdict(list)
    for a, b in ps:
        if a["wer"] > report.MISREAD and b["wer"] <= 0.1 and a["cls"].split("/")[0] != "control":
            by_voice[(a["provider"], a["model"], a["locale"])].append((a, b))
    chosen = []
    seen_ids: set[str] = set()
    for key in sorted(by_voice):
        cands = sorted(by_voice[key], key=lambda ab: (ab[0]["id"] in seen_ids, -(ab[0]["wer"] - ab[1]["wer"])))
        take = cands[:per_voice]
        chosen.extend(take)
        seen_ids.update(a["id"] for a, _ in take)
    return chosen


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-voice", type=int, default=3)
    args = ap.parse_args(argv)
    ps = report.pairs(report.load())
    chosen = pick(ps, args.per_voice)
    SHOW.mkdir(parents=True, exist_ok=True)
    (SHOW / "audio").mkdir(exist_ok=True)
    for a, b in chosen:
        for r in (a, b):
            shutil.copyfile(OUT / "audio" / r["audio"], SHOW / "audio" / r["audio"])
    stats = report.by_provider(ps)
    data = {
        "pairs": [{
            "id": a["id"], "provider": a["provider"], "providerName": PROVIDER_NAMES.get(a["provider"], a["provider"]),
            "model": a["model"], "voice": a["voice"], "locale": a["locale"], "cls": a["cls"],
            "raw": {"text": a["text"], "heard": a["transcript"], "wer": a["wer"], "audio": a["audio"]},
            "processed": {"text": b["text"], "heard": b["transcript"], "wer": b["wer"], "audio": b["audio"], "rules": sorted(set(b.get("changes", [])))},
            "intended": a["intended"],
        } for a, b in chosen],
        "stats": [{"provider": p, "providerName": PROVIDER_NAMES.get(p, p), "model": m, "locale": loc, **s}
                  for (p, m, loc), s in sorted(stats.items()) if p != "all" and loc != "all"],
        "overall": {loc: stats[("all", "all", loc)] for loc in ("all", "en-US", "tr-TR") if ("all", "all", loc) in stats},
    }
    (SHOW / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    template = (Path(__file__).with_name("showcase.html")).read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (SHOW / "index.html").write_text(template.replace("/*DATA*/", payload), encoding="utf-8")
    print(f"{len(chosen)} pairs, {sum(f.stat().st_size for f in (SHOW / 'audio').iterdir()) / 1e6:.1f} MB of audio -> {SHOW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
