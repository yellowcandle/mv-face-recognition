"""Resolve embedding filenames to 編號.

ADR 0001 makes the contestant number the identity everywhere: the reference manifest
is keyed by it and `scripts/publish` joins on it. The `.npy` files predate that rule
and are still named after the person — `{暱稱}_embedding.npy`, sometimes
`contestant_<編號>_embedding.npy`. This module is the one place that maps a filename
back to the number, and it also absorbs the `3 妹` / `3\\xa0妹` duplicate: two files
that name the same contestant resolve to the same id, so the loader sees one.

Nothing here imports ChromaDB or numpy, so the mapping can be checked without the
face-recognition stack installed.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTESTANT_CSV = REPO_ROOT / "metadata/contestant_info.csv"

# `contestant_17_embedding`, `contestant_17`, and (after the loader strips the suffix)
# `contestant_17`. The 編號 is normalised so `017` and `17` are one person.
_CONTESTANT_FILE = re.compile(r"^contestant_(\d+)(?:_embedding)?$")


@dataclass(frozen=True)
class Roster:
    """`編號 -> (姓名, 暱稱)` plus the reverse lookups embedding filenames need."""

    by_id: dict[str, tuple[str, str]]
    by_nickname: dict[str, str]
    by_name: dict[str, str]

    @classmethod
    def from_csv(cls, path: Path = CONTESTANT_CSV) -> "Roster":
        """Load the cast sheet; `utf-8-sig` strips the BOM Excel writes."""
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        by_id: dict[str, tuple[str, str]] = {}
        by_nickname: dict[str, str] = {}
        by_name: dict[str, str] = {}
        for row in rows:
            cid = str(int(row["編號"].strip()))
            name = row["姓名"].strip()
            nickname = row["暱稱"].strip()
            by_id[cid] = (name, nickname)
            by_nickname[nickname] = cid
            by_name[name] = cid
        return cls(by_id=by_id, by_nickname=by_nickname, by_name=by_name)

    def id_for_embedding_stem(self, stem: str) -> str | None:
        """The 編號 behind an embedding filename stem, or None if it names nobody.

        Accepts `{暱稱}`, `{姓名}`, `contestant_<編號>` and their `_embedding` forms.
        Whitespace is normalised first: the same contestant's files exist as `3 妹`
        (space) and `3\\xa0妹` (no-break space), and ADR 0001 says those are one id.
        """
        stem = " ".join(stem.replace("\xa0", " ").replace("\u3000", " ").split())
        match = _CONTESTANT_FILE.match(stem)
        if match:
            cid = str(int(match.group(1)))
            return cid if cid in self.by_id else None
        return self.by_nickname.get(stem) or self.by_name.get(stem)

    def label(self, contestant_id: str) -> str:
        """`編號 暱稱` for logs and the database-status page."""
        name, nickname = self.by_id.get(contestant_id, ("?", "?"))
        return f"{contestant_id} {nickname}" if nickname != name else f"{contestant_id} {name}"
