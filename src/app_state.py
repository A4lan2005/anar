"""Shared session, upload, and download helpers for the Streamlit app."""

from __future__ import annotations

import json
import os
import shutil

import streamlit as st

from src import db
from src.config import SOURCE_XLSX, shared_session_id
from src.excel_io import collect_phrase_index, collect_unique_phrases
from src.session_store import (
    BLOB_CANDIDATES,
    BLOB_PHRASES_CACHE,
    SessionPaths,
    ensure_workbook_on_disk,
    has_workbook,
    ingest_upload,
    load_candidates_from_disk,
    load_replacements_from_disk,
    persist_json_file,
    sync_meta_from_db,
    sync_session_to_disk,
)

BOOTSTRAP_KEY = "workspace_bootstrapped"
CATALOG_MTIME_KEY = "catalog_mtime"


def init_app_state() -> None:
    if db.db_enabled():
        try:
            db.init_schema()
        except Exception as exc:
            st.session_state["db_error"] = str(exc)


def invalidate_workspace_cache() -> None:
    st.session_state.pop(BOOTSTRAP_KEY, None)
    st.session_state.pop(CATALOG_MTIME_KEY, None)
    for key in ("phrases", "phrase_index", "replacements", "candidates"):
        st.session_state.pop(key, None)


def resolve_session() -> SessionPaths:
    session_id = shared_session_id()
    if not db.validate_session_id(session_id):
        raise ValueError(f"Invalid SHARED_SESSION_ID: {session_id}")

    paths = SessionPaths.for_session(session_id)
    st.session_state.session_id = session_id
    st.session_state.paths = paths

    if db.db_enabled():
        db.ensure_session(session_id)

    return paths


def bootstrap_workspace(paths: SessionPaths) -> None:
    """Load heavy data once per browser session — not on every arrow click."""
    ensure_workbook_on_disk(paths)

    if not st.session_state.get(BOOTSTRAP_KEY):
        if db.db_enabled():
            sync_session_to_disk(paths)
        elif not has_workbook(paths):
            return

        st.session_state.replacements = load_replacements_from_disk(paths)
        st.session_state.candidates = load_candidates_from_disk(paths)
        if db.db_enabled():
            st.session_state.global_idx = db.get_global_idx(paths.session_id)
        else:
            st.session_state.global_idx = st.session_state.get("global_idx", 0)

        _load_catalog(paths)
        st.session_state[BOOTSTRAP_KEY] = True
        return

    mtime = paths.manual.stat().st_mtime if paths.manual.exists() else 0
    if st.session_state.get(CATALOG_MTIME_KEY) != mtime:
        _load_catalog(paths)


def _load_catalog(paths: SessionPaths) -> None:
    if not paths.manual.exists():
        return
    st.session_state.phrases = collect_unique_phrases(
        paths.manual,
        cache_path=paths.phrases_cache,
    )
    st.session_state.phrase_index = collect_phrase_index(paths.manual)
    st.session_state[CATALOG_MTIME_KEY] = paths.manual.stat().st_mtime
    if paths.phrases_cache.exists() and db.db_enabled():
        persist_json_file(paths.session_id, BLOB_PHRASES_CACHE, paths.phrases_cache)


def refresh_shared_state(paths: SessionPaths) -> None:
    """Pull colleague changes — full re-download from Neon."""
    invalidate_workspace_cache()
    if db.db_enabled():
        sync_session_to_disk(paths)
    bootstrap_workspace(paths)


def refresh_meta_only(paths: SessionPaths) -> None:
    """Light pull — replacements + shared cursor only."""
    if not db.db_enabled():
        return
    replacements, global_idx = sync_meta_from_db(paths)
    st.session_state.replacements = replacements
    st.session_state.global_idx = global_idx


def get_replacements() -> dict:
    return st.session_state.setdefault("replacements", {})


def get_candidates_cache() -> dict:
    return st.session_state.setdefault("candidates", {})


def get_phrases() -> list[str]:
    return st.session_state.get("phrases", [])


def get_phrase_index() -> dict:
    return st.session_state.get("phrase_index", {})


def bootstrap_local_workbook(paths: SessionPaths) -> None:
    if has_workbook(paths):
        return
    if db.db_enabled():
        return
    if SOURCE_XLSX.exists():
        shutil.copy2(SOURCE_XLSX, paths.source)
        shutil.copy2(SOURCE_XLSX, paths.manual)


def app_url() -> str:
    base = os.environ.get("APP_BASE_URL", "").rstrip("/")
    return base or ""


def render_upload(paths: SessionPaths) -> bool:
    if has_workbook(paths):
        return True

    st.subheader("Загрузите Excel")
    st.caption("Один файл на всю команду — все пользователи работают с одной книгой.")
    uploaded = st.file_uploader("Книга Excel", type=["xlsx"], key="workbook_upload")
    if uploaded is not None:
        ingest_upload(paths, uploaded.getvalue(), uploaded.name)
        invalidate_workspace_cache()
        st.session_state.global_idx = 0
        st.success(f"Загружено: {uploaded.name}")
        st.rerun()
    return False


def apply_and_save(paths: SessionPaths, replacements: dict) -> int:
    from src.excel_io import apply_replacements
    from src.session_store import after_apply

    count = apply_replacements(paths.manual, paths.manual, replacements)
    shutil.copy2(paths.manual, paths.revised)
    after_apply(paths)
    st.session_state[CATALOG_MTIME_KEY] = paths.manual.stat().st_mtime
    return count


def render_downloads(paths: SessionPaths, replacements: dict) -> None:
    st.markdown("**Скачать результаты**")
    cols = st.columns(3)

    if paths.manual.exists():
        cols[0].download_button(
            "manual.xlsx",
            paths.manual.read_bytes(),
            file_name="manual.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    if paths.revised.exists():
        cols[1].download_button(
            "Книга2_revised.xlsx",
            paths.revised.read_bytes(),
            file_name="Книга2_revised.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    if replacements:
        cols[2].download_button(
            "replacements.json",
            json.dumps(replacements, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name="replacements.json",
            mime="application/json",
            use_container_width=True,
        )


def save_progress_index(paths: SessionPaths, global_idx: int) -> None:
    if db.db_enabled():
        db.set_global_idx(paths.session_id, global_idx)
