"""Render eval/out/results.jsonl as a markdown summary and a before/after HTML page with audio players.

    python -m speechready_eval.report
"""

from __future__ import annotations

import json
from collections import defaultdict
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "out"


def load() -> list[dict]:
    path = OUT / "results.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    latest: dict[str, dict] = {}
    for r in rows:
        latest[r["key"]] = r  # last write wins
    return [r for r in latest.values() if "error" not in r]


def summarize(rows: list[dict]) -> dict:
    """{(provider, locale, cls): {"raw": (misreads, n, mean_wer), "processed": (...)}}"""
    acc: dict[tuple, dict[str, list[float]]] = defaultdict(lambda: {"raw": [], "processed": []})
    for r in rows:
        acc[(r["provider"], r["locale"], r["cls"])][r["variant"]].append(r["wer"])
        acc[(r["provider"], r["locale"], "ALL")][r["variant"]].append(r["wer"])
    out = {}
    for key, variants in acc.items():
        out[key] = {
            v: (sum(1 for w in ws if w > 0.2), len(ws), (sum(ws) / len(ws)) if ws else 0.0)
            for v, ws in variants.items()
        }
    return out


def markdown(summary: dict) -> str:
    lines = ["| Provider | Locale | Class | n | Misreads raw | Misreads processed | Mean WER raw | Mean WER processed |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for (provider, locale, cls), v in sorted(summary.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] != "ALL", kv[0][2])):
        raw, proc = v["raw"], v["processed"]
        n = max(raw[1], proc[1])
        lines.append(f"| {provider} | {locale} | {cls} | {n} | {raw[0]} | {proc[0]} | {raw[2]:.3f} | {proc[2]:.3f} |")
    return "\n".join(lines) + "\n"


def page(rows: list[dict]) -> str:
    pairs: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        pairs[(r["provider"], r["locale"], r["cls"], r["id"])][r["variant"]] = r
    items = []
    for (provider, locale, cls, line_id), v in sorted(pairs.items()):
        raw, proc = v.get("raw"), v.get("processed")
        if not raw or not proc:
            continue
        verdict = "better" if proc["wer"] < raw["wer"] else ("same" if proc["wer"] == raw["wer"] else "worse")
        items.append(f"""
<section class="pair {verdict}">
  <h3>{escape(line_id)} <small>{escape(provider)} · {escape(locale)} · {escape(cls)} · {verdict}</small></h3>
  <div class="cols">
    <div><h4>Raw text</h4><pre>{escape(raw['text'])}</pre><audio controls preload="none" src="audio/{raw['audio']}"></audio>
      <p class="t">heard: {escape(raw['transcript'])}<br>WER {raw['wer']:.2f}</p></div>
    <div><h4>With speechready</h4><pre>{escape(proc['text'])}</pre><audio controls preload="none" src="audio/{proc['audio']}"></audio>
      <p class="t">heard: {escape(proc['transcript'])}<br>WER {proc['wer']:.2f}</p></div>
  </div>
  <p class="t">intended: {escape(raw['intended'])}</p>
</section>""")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>speechready before and after</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;background:#fff;color:#111}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}} @media (max-width:700px){{.cols{{grid-template-columns:1fr}}}}
pre{{white-space:pre-wrap;background:#f4f4f4;padding:.5rem;border-radius:6px;font-size:.9rem}}
section{{border-left:4px solid #ccc;padding-left:1rem;margin:1.5rem 0}} section.better{{border-color:#2a9d4b}} section.worse{{border-color:#d33}}
.t{{color:#555;font-size:.85rem}} small{{color:#777;font-weight:normal}}
</style></head><body>
<h1>speechready: before and after</h1>
<p>Each line was sent to the provider as written (left) and after <code>speechready.prepare</code> (right). "Heard" is the speech-to-text round trip; WER is against the intended words. Green = the processed version was heard more accurately.</p>
{''.join(items)}
</body></html>"""


def main() -> int:
    rows = load()
    summary = summarize(rows)
    (OUT / "summary.md").write_text(markdown(summary), encoding="utf-8")
    (OUT / "index.html").write_text(page(rows), encoding="utf-8")
    print(markdown(summary))
    print(f"wrote {OUT / 'summary.md'} and {OUT / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
