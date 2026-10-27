"""The audit trail: one Change per rewrite the pipeline made."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Change:
    """One rewrite. `rule` is dotted and stable, e.g. `clean.markdown.heading`."""

    stage: str
    rule: str
    before: str
    after: str
    note: str = ""


@dataclass
class Recorder:
    """Collects Changes; stages call `add` whenever they rewrite something."""

    changes: list[Change] = field(default_factory=list)

    def add(self, stage: str, rule: str, before: str, after: str, note: str = "") -> None:
        if before == after:
            return
        self.changes.append(Change(stage, rule, before, after, note))
