"""The stream route must not serve an unfinalized rendition.

An interrupted encode leaves the MP4 `mdat` and never writes `moov`; the file is unreadable
by every browser. The route prefers `_1080p`, so without a container check the valid `_720p`
is never reached. These tests pin the helper and the skip.
"""

import asyncio
import struct
from pathlib import Path

from src import local_api


def _box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def _finalized(*, faststart: bool) -> bytes:
    ftyp = _box(b"ftyp", b"isom")
    moov = _box(b"moov", b"\x00" * 8)
    mdat = _box(b"mdat", b"\x00" * 32)
    return ftyp + (moov + mdat if faststart else mdat + moov)


def _aborted() -> bytes:
    # What a killed writer leaves: a zero-size `mdat` and no `moov`.
    return _box(b"ftyp", b"isom") + struct.pack(">I", 0) + b"mdat" + b"\x00" * 16


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_faststart_rendition_is_playable(tmp_path):
    assert local_api._rendition_playable(
        _write(tmp_path, "a_1080p.mp4", _finalized(faststart=True))
    )


def test_moov_at_tail_is_playable(tmp_path):
    assert local_api._rendition_playable(
        _write(tmp_path, "b_1080p.mp4", _finalized(faststart=False))
    )


def test_aborted_rendition_is_not_playable(tmp_path):
    assert not local_api._rendition_playable(_write(tmp_path, "c_1080p.mp4", _aborted()))


def test_missing_file_is_not_playable(tmp_path):
    assert not local_api._rendition_playable(tmp_path / "missing_1080p.mp4")


def test_stream_skips_aborted_1080p_for_the_720p(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    source = tmp_path / "source"
    processed.mkdir()
    source.mkdir()

    _write(processed, "reel_1080p.mp4", _aborted())
    good = _write(processed, "reel_720p.mp4", _finalized(faststart=True))

    monkeypatch.setattr(local_api, "PROCESSED_DIR", processed)
    monkeypatch.setattr(local_api, "SOURCE_DIR", source)

    response = asyncio.run(local_api.stream_video("reel"))

    assert Path(response.path) == good


def test_stream_version_tracks_the_rendition(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    target = _write(processed, "reel_1080p.mp4", _finalized(faststart=True))
    monkeypatch.setattr(local_api, "PROCESSED_DIR", processed)

    stat = target.stat()
    assert local_api._stream_version("reel") == f"{stat.st_size:x}-{int(stat.st_mtime):x}"


def test_stream_version_is_absent_without_a_rendition(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    monkeypatch.setattr(local_api, "PROCESSED_DIR", processed)

    assert local_api._stream_version("reel") is None
