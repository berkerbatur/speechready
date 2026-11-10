"""The `speechready` command.

    speechready lexicon scan FILE...                 candidate words in text files, most frequent first
    speechready lexicon build GLOSSARY -o FILE       ask a model once, write (or extend) a lexicon file
    speechready lexicon check FILE                   every entry through the pipeline; problems to stderr
    speechready lexicon export FILE --format pls     the upload file for a vendor
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import builder
from .lexicon import Lexicon
from .profiles import load_profile


def _read(paths: list[str]) -> str:
    return "\n".join(sys.stdin.read() if p == "-" else Path(p).read_text(encoding="utf-8") for p in paths)


def cmd_scan(args: argparse.Namespace) -> int:
    for word, n in builder.scan(_read(args.files), min_count=args.min_count):
        print(f"{word}\t# {n}" if args.counts else word)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    words = builder.read_glossary(_read([args.glossary]))
    out = Path(args.out)
    existing = Lexicon.load(out) if out.exists() else None
    if existing and existing.locale.lower() != args.locale.lower():
        print(f"{out} is a {existing.locale} lexicon; pass --locale {existing.locale} or another --out", file=sys.stderr)
        return 2
    model = args.model or builder.DEFAULT_MODELS[args.provider]
    new = [w for w, _ in words if not existing or w.lower() not in {e.word.lower() for e in existing.entries}]
    if args.dry_run:
        print(f"{len(words)} words in the glossary, {len(new)} to ask {args.provider}/{model} about"
              + (f", {len(words) - len(new)} already in {out}" if existing else ""), file=sys.stderr)
        for w in new:
            print(w)
        return 0
    if not new:
        print(f"nothing to do: every word of the glossary is in {out}", file=sys.stderr)
        return 0
    result = builder.build(words, args.locale, lexicon=existing, ipa=args.ipa, provider=args.provider,
                           model=model, base_url=args.base_url, batch=args.batch)
    header = builder.header_of(out) if existing else builder.default_header(args.locale, model)
    builder.write(result.lexicon, out, header)
    print(f"{out}: {len(result.added)} entries added, {len(result.kept)} words the model says the voice reads as written, "
          f"{len(result.skipped)} already there", file=sys.stderr)
    for word, note in result.kept:
        print(f"  kept as written: {word}" + (f"  ({note})" if note else ""), file=sys.stderr)
    for word, note in result.notes:
        print(f"  note on {word}: {note}", file=sys.stderr)
    if result.usage:
        print("  tokens: " + ", ".join(f"{k} {v}" for k, v in result.usage.items()), file=sys.stderr)
    problems = builder.check(result.lexicon)
    for word, problem in problems:
        print(f"  check {word}: {problem}", file=sys.stderr)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    lex = Lexicon.load(args.file)
    problems = builder.check(lex)
    for word, problem in problems:
        print(f"{word}: {problem}", file=sys.stderr)
    print(f"{args.file}: {len(lex.entries)} entries, {len(problems)} problems", file=sys.stderr)
    return 1 if problems else 0


def cmd_export(args: argparse.Namespace) -> int:
    lex = Lexicon.load(args.file)
    if args.profile:
        text = lex.export_for(load_profile(args.profile))
        if text is None:
            print(f"profile {args.profile} takes no lexicon file; its entries are applied in the text instead", file=sys.stderr)
            return 1
    else:
        text = lex.export(args.format, args.alphabet)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="speechready", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    lex = sub.add_parser("lexicon", help="build, check and export pronunciation lexicons").add_subparsers(dest="action", required=True)

    p = lex.add_parser("scan", help="candidate lexicon words in text files: acronyms, mixed-case names, names with inner punctuation")
    p.add_argument("files", nargs="+", help="text files, or - for stdin")
    p.add_argument("--min-count", type=int, default=1)
    p.add_argument("--counts", action="store_true", help="append the count as a comment")
    p.set_defaults(run=cmd_scan)

    p = lex.add_parser("build", help="ask a model how the glossary's words are said and write a lexicon file")
    p.add_argument("glossary", help="one word per line, optionally a tab and a hint; # starts a comment; - for stdin")
    p.add_argument("-o", "--out", required=True, help=".yaml or .json; an existing file is extended with the words it lacks")
    p.add_argument("--locale", default="en-US")
    p.add_argument("--provider", choices=["openai", "anthropic"], default="openai",
                   help="openai (OPENAI_API_KEY; OPENAI_BASE_URL for a compatible server) or anthropic (ANTHROPIC_API_KEY)")
    p.add_argument("--model", default=None, help=f"default {builder.DEFAULT_MODELS}")
    p.add_argument("--base-url", default=None)
    p.add_argument("--ipa", action="store_true", help="also ask for an IPA transcription (phoneme tags on Azure, Google, Polly)")
    p.add_argument("--batch", type=int, default=builder.BATCH, help="words per model call")
    p.add_argument("--dry-run", action="store_true", help="list the words that would be asked about and exit")
    p.set_defaults(run=cmd_build)

    p = lex.add_parser("check", help="run every entry through the pipeline and report what a voice would still misread")
    p.add_argument("file")
    p.set_defaults(run=cmd_check)

    p = lex.add_parser("export", help="the upload file for a vendor")
    p.add_argument("file")
    p.add_argument("--format", choices=["pls", "google", "json"], default="pls")
    p.add_argument("--alphabet", default="ipa")
    p.add_argument("--profile", default=None, help="pick the format from a profile id instead (elevenlabs-v2, azure-neural, google-ssml, amazon-polly)")
    p.add_argument("-o", "--out", default=None)
    p.set_defaults(run=cmd_export)

    args = ap.parse_args(argv)
    try:
        return args.run(args)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"speechready: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
