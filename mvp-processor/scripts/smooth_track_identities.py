"""Apply track smoothing to already-written metadata files.

For metadata produced before the smoothing pass was part of the pipeline. Filled detections get
``match_source = "track"``; frame-level matches are never overwritten.

    python scripts/smooth_track_identities.py ../local_output/metadata
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from track_smoothing import (  # noqa: E402
    rebuild_timeline,
    refresh_summary,
    smooth_track_identities,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata_dir", type=Path)
    parser.add_argument("--min-accepted", type=int, default=2)
    parser.add_argument("--dominance", type=float, default=0.75)
    args = parser.parse_args()

    for path in sorted(args.metadata_dir.glob("*.json")):
        if not path.name[0].isdigit():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        stats = smooth_track_identities(
            doc.get("frame_data", []),
            min_accepted=args.min_accepted,
            dominance=args.dominance,
        )
        doc["contestant_timeline"] = rebuild_timeline(doc.get("frame_data", []))
        refresh_summary(doc)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        print(
            f"{path.name[:2]}: filled {stats['filled']} across "
            f"{stats['tracks_filled']}/{stats['tracks_considered']} tracks"
        )


if __name__ == "__main__":
    main()
