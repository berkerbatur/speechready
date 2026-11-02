"""Lexicons bundled with the package, from spec/lexicons.

    from speechready import load_lexicon, prepare
    prepare("API'yi çağır.", locale="tr-TR", lexicon=load_lexicon("tr-tech")).text
    prepare("API'yi çağır.", locale="tr-TR", lexicon="tr-tech").text   # the same, by name

When running from the repository the files are read from spec/lexicons; in an
installed wheel they are copied into speechready/lexicons/data at build time.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..lexicon import Lexicon


def _candidate_dirs() -> list[Path]:
    here = Path(__file__).resolve().parent
    return [here / "data", here.parents[3] / "spec" / "lexicons"]


def lexicons_dir() -> Path:
    for d in _candidate_dirs():
        if d.is_dir() and any(d.glob("*.yaml")):
            return d
    raise FileNotFoundError("no bundled lexicons found; expected speechready/lexicons/data or spec/lexicons")


@lru_cache(maxsize=1)
def list_lexicons() -> list[str]:
    """Names of the bundled lexicons, e.g. ["tr-tech"]."""
    return sorted(p.stem for p in lexicons_dir().glob("*.yaml"))


def load_lexicon(name: str) -> Lexicon:
    """A bundled lexicon by name; a new object each call, so it can be extended."""
    path = lexicons_dir() / f"{name}.yaml"
    if not path.is_file():
        raise KeyError(f"unknown bundled lexicon {name!r}; known: {list_lexicons()}")
    return Lexicon.load(path)


__all__ = ["lexicons_dir", "list_lexicons", "load_lexicon"]
