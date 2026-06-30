"""Shared session workspace and Neon sync."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import db

BLOB_SOURCE = "source"
BLOB_MANUAL = "manual"
BLOB_REVISED = "revised"
BLOB_REPLACEMENTS = "replacements"
BLOB_CANDIDATES = "candidates"
BLOB_PHRASES_CACHE = "phrases_cache"

DATA_ROOT = Path(os.environ.get("ANAR_DATA_DIR", tempfile.gettempdir())) / "anar"


@dataclass
class SessionPaths:
    session_id: str
    work_dir: Path
    source: Path
    manual: Path
    revised: Path
    replacements: Path
    candidates: Path
    phrases_cache: Path

    @classmethod
    def for_session(cls, session_id: str) -> SessionPaths:
        work_dir = DATA_ROOT / session_id
        work_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            session_id=session_id,
            work_dir=work_dir,
            source=work_dir / "source.xlsx",
            manual=work_dir / "manual.xlsx",
            revised=work_dir / "revised.xlsx",
            replacements=work_dir / "replacements.json",
            candidates=work_dir / "candidates_cache.json",
            phrases_cache=work_dir / "phrases_cache.json",
        )


def persist_file(session_id: str, blob_key: str, path: Path) -> None:
    if not db.db_enabled() or not path.exists():
        return
    db.save_blob(session_id, blob_key, path.read_bytes())


def persist_json_file(session_id: str, blob_key: str, path: Path) -> None:
    if not db.db_enabled() or not path.exists():
        return
    db.save_blob(session_id, blob_key, path.read_bytes())


def restore_blob_to_path(session_id: str, blob_key: str, path: Path) -> bool:
    if not db.db_enabled():
        return path.exists()
    raw = db.load_blob(session_id, blob_key)
    if raw is None:
        return path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return True


def sync_session_to_disk(paths: SessionPaths) -> None:
    if not db.db_enabled():
        return
    db.ensure_session(paths.session_id)
    restore_blob_to_path(paths.session_id, BLOB_SOURCE, paths.source)
    restore_blob_to_path(paths.session_id, BLOB_MANUAL, paths.manual)
    restore_blob_to_path(paths.session_id, BLOB_REVISED, paths.revised)
    restore_blob_to_path(paths.session_id, BLOB_REPLACEMENTS, paths.replacements)
    restore_blob_to_path(paths.session_id, BLOB_CANDIDATES, paths.candidates)
    restore_blob_to_path(paths.session_id, BLOB_PHRASES_CACHE, paths.phrases_cache)


def ingest_upload(paths: SessionPaths, uploaded_bytes: bytes, filename: str) -> None:
    paths.source.write_bytes(uploaded_bytes)
    shutil.copy2(paths.source, paths.manual)
    paths.revised.unlink(missing_ok=True)
    paths.replacements.unlink(missing_ok=True)
    paths.candidates.unlink(missing_ok=True)
    paths.phrases_cache.unlink(missing_ok=True)

    if db.db_enabled():
        db.ensure_session(paths.session_id, filename)
        db.set_source_filename(paths.session_id, filename)
        db.set_global_idx(paths.session_id, 0)
        persist_file(paths.session_id, BLOB_SOURCE, paths.source)
        persist_file(paths.session_id, BLOB_MANUAL, paths.manual)
        db.delete_blobs(
            paths.session_id,
            [BLOB_REVISED, BLOB_REPLACEMENTS, BLOB_CANDIDATES, BLOB_PHRASES_CACHE],
        )


def save_replacements(paths: SessionPaths, replacements: dict) -> None:
    import json

    paths.replacements.write_text(
        json.dumps(replacements, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if db.db_enabled():
        persist_json_file(paths.session_id, BLOB_REPLACEMENTS, paths.replacements)


def load_replacements(paths: SessionPaths) -> dict:
    import json

    if db.db_enabled():
        data = db.load_json(paths.session_id, BLOB_REPLACEMENTS, None)
        if data is not None:
            paths.replacements.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return data

    if paths.replacements.exists():
        return json.loads(paths.replacements.read_text(encoding="utf-8"))
    return {}


def save_candidates(paths: SessionPaths, cache: dict) -> None:
    import json

    paths.candidates.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    if db.db_enabled():
        persist_json_file(paths.session_id, BLOB_CANDIDATES, paths.candidates)


def load_candidates(paths: SessionPaths) -> dict:
    import json

    if db.db_enabled():
        data = db.load_json(paths.session_id, BLOB_CANDIDATES, None)
        if data is not None:
            paths.candidates.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return data

    if paths.candidates.exists():
        return json.loads(paths.candidates.read_text(encoding="utf-8"))
    return {}


def after_apply(paths: SessionPaths) -> None:
    if db.db_enabled():
        persist_file(paths.session_id, BLOB_MANUAL, paths.manual)
        persist_file(paths.session_id, BLOB_REVISED, paths.revised)


def has_workbook(paths: SessionPaths) -> bool:
    return paths.manual.exists() or paths.source.exists()
