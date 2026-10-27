"""Provider profiles: data files that say what each TTS model accepts.

The YAML files live in the repository's `spec/profiles` and are copied into the
wheel at build time. Each profile states the intent renderings, the request
limit, the escaping rules and whether unknown bracket tags pass through.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Profile:
    id: str
    provider: str
    models: tuple[str, ...]
    syntax: str  # plain | ssml
    escape: str  # none | xml
    limit_unit: str  # chars | bytes
    limit_max: int | None
    limit_per_model: dict[str, int]
    intents: dict[str, dict]
    audio_tags: bool
    default: bool = False
    notes: str = ""
    sources: tuple[str, ...] = ()
    verified: str = ""
    raw: dict = field(default_factory=dict, compare=False, repr=False)

    def limit_for(self, model: str | None) -> int | None:
        if model and model in self.limit_per_model:
            return self.limit_per_model[model]
        return self.limit_max


def _candidate_dirs() -> list[Path]:
    here = Path(__file__).resolve().parent
    return [here / "data", here.parents[3] / "spec" / "profiles"]


def profiles_dir() -> Path:
    for d in _candidate_dirs():
        if d.is_dir() and any(d.glob("*.yaml")):
            return d
    raise FileNotFoundError("no provider profiles found; expected speechready/profiles/data or spec/profiles")


def _from_dict(data: dict) -> Profile:
    limit = data.get("limit") or {}
    return Profile(
        id=data["id"],
        provider=data["provider"],
        models=tuple(data.get("models") or ()),
        syntax=data.get("syntax", "plain"),
        escape=data.get("escape", "none"),
        limit_unit=limit.get("unit", "chars"),
        limit_max=limit.get("max"),
        limit_per_model=dict(limit.get("per_model") or {}),
        intents=dict(data.get("intents") or {}),
        audio_tags=bool(data.get("audio_tags", False)),
        default=bool(data.get("default", False)),
        notes=data.get("notes", ""),
        sources=tuple(data.get("sources") or ()),
        verified=str(data.get("verified", "")),
        raw=data,
    )


@lru_cache(maxsize=1)
def _all() -> tuple[Profile, ...]:
    out = []
    for path in sorted(profiles_dir().glob("*.yaml")):
        with path.open("r", encoding="utf-8") as f:
            out.append(_from_dict(yaml.safe_load(f)))
    return tuple(out)


def list_profiles() -> list[Profile]:
    return list(_all())


def load_profile(profile_id: str) -> Profile:
    for p in _all():
        if p.id == profile_id:
            return p
    raise KeyError(f"unknown profile {profile_id!r}; known: {[p.id for p in _all()]}")


def resolve_profile(provider: str | None = None, model: str | None = None) -> Profile:
    """Pick the profile for a provider and model. No provider = the `plain` profile."""
    if provider is None and model is None:
        return load_profile("plain")
    matches = [p for p in _all() if provider is None or p.provider == provider]
    if model:
        for p in matches:
            if model in p.models:
                return p
        if provider is None:
            raise KeyError(f"no profile lists model {model!r}")
    for p in matches:
        if p.default:
            return p
    if matches:
        return matches[0]
    raise KeyError(f"no profile for provider {provider!r}; known providers: {sorted({p.provider for p in _all()})}")


__all__ = ["Profile", "list_profiles", "load_profile", "resolve_profile", "profiles_dir"]
