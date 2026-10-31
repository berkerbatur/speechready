"""Render eval/out/results.jsonl as a markdown summary and a before/after HTML page with audio players.

    python -m speechready_eval.report

summary.md has three tables: per provider (the go/no-go view), per provider
and class, and per rule family (which rules earn their place). index.html is
the listening page: every line side by side, raw on the left, processed on
the right, with what the speech-to-text engine heard under each.
"""

from __future__ import annotations

import json
from collections import defaultdict
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "out"
MISREAD = 0.2


def load() -> list[dict]:
    """Latest row per key, errors dropped, restricted to lines still in the corpus."""
    from . import corpus, metrics

    ids = {l.id for l in corpus.build()}
    path = OUT / "results.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    latest: dict[str, dict] = {}
    for r in rows:
        latest[r["key"]] = r  # last write wins
    out = []
    for r in latest.values():
        if "error" in r or r["id"] not in ids:
            continue
        r["wer"] = round(metrics.wer(r["intended"], r["transcript"], r["locale"]), 4)  # rescore with the current metric
        r["misread"] = r["wer"] > MISREAD
        out.append(r)
    return out


def pairs(rows: list[dict]) -> list[tuple[dict, dict]]:
    """(raw, processed) for every line/voice with both variants."""
    by: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        by[(r["provider"], r["model"], r["voice"], r["id"])][r["variant"]] = r
    return [(v["raw"], v["processed"]) for v in by.values() if "raw" in v and "processed" in v]


def _stats(ps: list[tuple[dict, dict]]) -> dict:
    n = len(ps)
    raw_mis = sum(1 for a, _ in ps if a["wer"] > MISREAD)
    proc_mis = sum(1 for _, b in ps if b["wer"] > MISREAD)
    return {
        "n": n,
        "raw_misreads": raw_mis, "proc_misreads": proc_mis,
        "raw_wer": sum(a["wer"] for a, _ in ps) / n if n else 0.0,
        "proc_wer": sum(b["wer"] for _, b in ps) / n if n else 0.0,
        "better": sum(1 for a, b in ps if b["wer"] < a["wer"]),
        "worse": sum(1 for a, b in ps if b["wer"] > a["wer"]),
    }


def by_provider(ps) -> dict[tuple, dict]:
    g: dict[tuple, list] = defaultdict(list)
    for a, b in ps:
        g[(a["provider"], a["model"], a["locale"])].append((a, b))
        g[(a["provider"], a["model"], "all")].append((a, b))
        g[("all", "all", a["locale"])].append((a, b))
        g[("all", "all", "all")].append((a, b))
    return {k: _stats(v) for k, v in g.items()}


def by_class(ps) -> dict[tuple, dict]:
    g: dict[tuple, list] = defaultdict(list)
    for a, b in ps:
        g[(a["provider"], a["locale"], a["cls"])].append((a, b))
        g[("all", a["locale"], a["cls"])].append((a, b))
    return {k: _stats(v) for k, v in g.items()}


def by_rule(ps) -> dict[tuple, dict]:
    """Rule family -> stats over the pairs where that family fired. A family is the
    stage plus the first segment of the rule id (verbalize.phone, clean.markdown...)."""
    g: dict[tuple, list] = defaultdict(list)
    for a, b in ps:
        fams = {".".join(r.split(".")[:2]) for r in b.get("changes", [])}
        for f in fams:
            g[(f, a["locale"])].append((a, b))
            g[(f, "all")].append((a, b))
        if not fams:
            g[("(no change)", a["locale"])].append((a, b))
            g[("(no change)", "all")].append((a, b))
    return {k: _stats(v) for k, v in g.items()}


def _pct(x: int, n: int) -> str:
    return f"{100 * x / n:.0f}%" if n else "-"


def markdown(ps: list[tuple[dict, dict]]) -> str:
    out = ["# speechready evaluation\n", f"{len(ps)} line/voice pairs. A misread is WER above {MISREAD}.\n"]
    out += ["## Per provider\n", "| Provider | Model | Locale | n | Misreads raw | Misreads processed | Mean WER raw | Mean WER processed | Better | Worse |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for (p, m, loc), s in sorted(by_provider(ps).items(), key=lambda kv: (kv[0][0] != "all", kv[0])):
        out.append(f"| {p} | {m} | {loc} | {s['n']} | {s['raw_misreads']} ({_pct(s['raw_misreads'], s['n'])}) | {s['proc_misreads']} ({_pct(s['proc_misreads'], s['n'])}) | {s['raw_wer']:.3f} | {s['proc_wer']:.3f} | {s['better']} | {s['worse']} |")
    out += ["\n## Per class (all providers)\n", "| Locale | Class | n | Misreads raw | Misreads processed | Mean WER raw | Mean WER processed | Better | Worse |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for (p, loc, cls), s in sorted(by_class(ps).items()):
        if p != "all":
            continue
        out.append(f"| {loc} | {cls} | {s['n']} | {s['raw_misreads']} | {s['proc_misreads']} | {s['raw_wer']:.3f} | {s['proc_wer']:.3f} | {s['better']} | {s['worse']} |")
    out += ["\n## Per rule family (pairs where the family fired)\n", "| Rule family | Locale | n | Misreads raw | Misreads processed | Mean WER raw | Mean WER processed | Better | Worse |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for (fam, loc), s in sorted(by_rule(ps).items()):
        out.append(f"| {fam} | {loc} | {s['n']} | {s['raw_misreads']} | {s['proc_misreads']} | {s['raw_wer']:.3f} | {s['proc_wer']:.3f} | {s['better']} | {s['worse']} |")
    out += ["\n## Per provider and class\n", "| Provider | Locale | Class | n | Misreads raw | Misreads processed | Mean WER raw | Mean WER processed |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for (p, loc, cls), s in sorted(by_class(ps).items()):
        if p == "all":
            continue
        out.append(f"| {p} | {loc} | {cls} | {s['n']} | {s['raw_misreads']} | {s['proc_misreads']} | {s['raw_wer']:.3f} | {s['proc_wer']:.3f} |")
    return "\n".join(out) + "\n"


def page(ps: list[tuple[dict, dict]]) -> str:
    prov = by_provider(ps)
    head_rows = []
    for (p, m, loc), s in sorted(prov.items(), key=lambda kv: (kv[0][0] != "all", kv[0])):
        if loc == "all" and p != "all":
            continue
        head_rows.append(f"<tr><td>{escape(p)}</td><td>{escape(m)}</td><td>{escape(loc)}</td><td>{s['n']}</td>"
                         f"<td>{s['raw_misreads']} <small>({_pct(s['raw_misreads'], s['n'])})</small></td>"
                         f"<td>{s['proc_misreads']} <small>({_pct(s['proc_misreads'], s['n'])})</small></td>"
                         f"<td class=ok>{s['better']}</td><td class=bad>{s['worse']}</td></tr>")
    items = []
    order = {"better": 0, "worse": 1, "same": 2}
    ranked = sorted(ps, key=lambda ab: (order["better" if ab[1]["wer"] < ab[0]["wer"] else "worse" if ab[1]["wer"] > ab[0]["wer"] else "same"], -(ab[0]["wer"] - ab[1]["wer"]), ab[0]["id"]))
    for raw, proc in ranked:
        verdict = "better" if proc["wer"] < raw["wer"] else ("same" if proc["wer"] == raw["wer"] else "worse")
        items.append(f"""
<section class="pair {verdict}" data-provider="{escape(raw['provider'])}" data-locale="{escape(raw['locale'])}" data-verdict="{verdict}">
  <h3>{escape(raw['id'])} <small>{escape(raw['provider'])}/{escape(raw['model'])} · {escape(raw['locale'])} · {escape(raw['cls'])} · {verdict}</small></h3>
  <div class="cols">
    <div><h4>As written</h4><pre>{escape(raw['text'])}</pre><audio controls preload="none" src="audio/{raw['audio']}"></audio>
      <p class="t">heard: {escape(raw['transcript'])}<br>WER {raw['wer']:.2f}</p></div>
    <div><h4>With speechready</h4><pre>{escape(proc['text'])}</pre><audio controls preload="none" src="audio/{proc['audio']}"></audio>
      <p class="t">heard: {escape(proc['transcript'])}<br>WER {proc['wer']:.2f}</p></div>
  </div>
  <p class="t">intended: {escape(raw['intended'])}</p>
</section>""")
    providers = sorted({a["provider"] for a, _ in ps})
    opts = "".join(f'<option value="{escape(p)}">{escape(p)}</option>' for p in providers)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>speechready before and after</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{{--bg:#fff;--fg:#111;--muted:#555;--box:#f4f4f4;--ok:#2a9d4b;--bad:#d33;--line:#ccc}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#111;--fg:#eee;--muted:#aaa;--box:#1e1e1e;--line:#444}}}}
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 16px;background:var(--bg);color:var(--fg)}}
table{{border-collapse:collapse;font-size:.9rem}} td,th{{padding:.25rem .6rem;border-bottom:1px solid var(--line);text-align:left}}
.ok{{color:var(--ok)}} .bad{{color:var(--bad)}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}} @media (max-width:700px){{.cols{{grid-template-columns:1fr}}}}
pre{{white-space:pre-wrap;background:var(--box);padding:.5rem;border-radius:6px;font-size:.9rem}}
section{{border-left:4px solid var(--line);padding-left:1rem;margin:1.5rem 0}} section.better{{border-color:var(--ok)}} section.worse{{border-color:var(--bad)}}
.t{{color:var(--muted);font-size:.85rem}} small{{color:var(--muted);font-weight:normal}} audio{{width:100%}}
.filters{{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}} .hidden{{display:none}}
</style></head><body>
<h1>speechready: before and after</h1>
<p>Each line was sent to the provider as written (left) and after <code>speechready.prepare</code> (right). "Heard" is the speech-to-text round trip; WER is the word error rate against the intended words; a misread is WER above {MISREAD}. Green sections are lines the processed version got heard more accurately, red ones are regressions.</p>
<table><thead><tr><th>Provider</th><th>Model</th><th>Locale</th><th>n</th><th>Misreads raw</th><th>Misreads processed</th><th>Better</th><th>Worse</th></tr></thead><tbody>{''.join(head_rows)}</tbody></table>
<div class="filters">
  <label>Provider <select id="fp"><option value="">all</option>{opts}</select></label>
  <label>Locale <select id="fl"><option value="">all</option><option>en-US</option><option>tr-TR</option></select></label>
  <label>Show <select id="fv"><option value="">all</option><option value="better">better</option><option value="worse">worse</option><option value="same">same</option></select></label>
  <span id="count" class="t"></span>
</div>
{''.join(items)}
<script>
const sel = ['fp','fl','fv'].map(id => document.getElementById(id));
function apply(){{
  const [p,l,v] = sel.map(s => s.value); let n = 0;
  document.querySelectorAll('section.pair').forEach(s => {{
    const show = (!p || s.dataset.provider===p) && (!l || s.dataset.locale===l) && (!v || s.dataset.verdict===v);
    s.classList.toggle('hidden', !show); if (show) n++;
  }});
  document.getElementById('count').textContent = n + ' lines';
}}
sel.forEach(s => s.addEventListener('change', apply)); apply();
</script>
</body></html>"""


def main() -> int:
    ps = pairs(load())
    md = markdown(ps)
    (OUT / "summary.md").write_text(md, encoding="utf-8")
    (OUT / "index.html").write_text(page(ps), encoding="utf-8")
    print(md.split("## Per class")[0])
    print(f"wrote {OUT / 'summary.md'} and {OUT / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
