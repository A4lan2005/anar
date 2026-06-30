import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src import db
from src.app_state import (
    apply_and_save,
    app_url,
    bootstrap_local_workbook,
    bootstrap_workspace,
    get_candidates_cache,
    get_phrase_index,
    get_phrases,
    get_replacements,
    init_app_state,
    refresh_shared_state,
    render_downloads,
    render_upload,
    resolve_session,
    save_progress_index,
)
from src.gemini_rewrite import suggest_replacements
from src.session_store import save_candidates, save_replacements


def phrase_context(meta: dict | None) -> str:
    if not meta:
        return ""
    parts = []
    if meta.get("pairs"):
        parts.append(f"Пара листов: {', '.join(meta['pairs'])}")
    if meta.get("is_duplicate_across_pair"):
        parts.append("Фраза повторяется на сводном листе и на листе рабочего дня")
    if meta.get("in_summary") and not meta.get("in_workday"):
        parts.append("Только сводная хронометражная карта (Лист N)")
    if meta.get("in_workday") and not meta.get("in_summary"):
        parts.append("Только рабочий день (вкладка N)")
    return ". ".join(parts)


def get_candidates(phrase: str, cache: dict, context: str, paths) -> dict:
    if phrase in cache and cache[phrase].get("candidates"):
        return cache[phrase]
    with st.spinner("Запрос к Gemini..."):
        result = suggest_replacements(phrase, context)
    cache[phrase] = result
    st.session_state.candidates = cache
    save_candidates(paths, cache, persist_db=False)
    return result


def pick_replacement(paths, replacements, phrase, value, phrases, global_idx):
    replacements[phrase] = value
    st.session_state.replacements = replacements
    save_replacements(paths, replacements)
    if global_idx < len(phrases) - 1:
        global_idx += 1
        st.session_state.global_idx = global_idx
        save_progress_index(paths, global_idx)


def main():
    st.set_page_config(page_title="Редактор операций", layout="wide")
    st.title("Замена абстрактных операций")

    init_app_state()
    paths = resolve_session()
    bootstrap_local_workbook(paths)

    with st.sidebar:
        st.header("Рабочая область")
        if db.db_enabled():
            st.caption("Общая сессия · Neon PostgreSQL")
            if st.button("Обновить с сервера"):
                refresh_shared_state(paths)
                st.rerun()
            st.caption("Только по кнопке — не при каждом клике.")
        else:
            st.warning("DATABASE_URL не задан — данные только на этом сервере.")

        url = app_url()
        if url:
            st.markdown(f"[Открыть приложение]({url})")

        if st.session_state.get("db_error"):
            st.error(f"БД: {st.session_state.db_error}")

    if not render_upload(paths):
        return

    bootstrap_workspace(paths)

    phrases = get_phrases()
    phrase_index = get_phrase_index()
    replacements = get_replacements()
    cache = get_candidates_cache()

    if not phrases:
        st.warning("Не удалось прочитать фразы из Excel.")
        return

    if "global_idx" not in st.session_state:
        st.session_state.global_idx = 0
    st.session_state.global_idx = max(0, min(st.session_state.global_idx, len(phrases) - 1))

    done = sum(1 for p in phrases if p in replacements)
    st.progress(done / max(len(phrases), 1), text=f"Выбрано: {done} / {len(phrases)}")

    pending = [p for p in phrases if p not in replacements]

    if paths.revised.exists() or replacements:
        with st.expander("Скачать файлы", expanded=bool(paths.revised.exists())):
            render_downloads(paths, replacements)

    if not pending:
        st.success("Все фразы обработаны!")
        if st.button("Применить замены к Excel", type="primary"):
            count = apply_and_save(paths, replacements)
            st.success(f"Готово: {count} ячеек обновлено.")
            render_downloads(paths, replacements)
        return

    phrase = phrases[st.session_state.global_idx]
    meta = phrase_index.get(phrase)
    current_num = st.session_state.global_idx + 1

    nav_prev, nav_title, nav_next = st.columns([1, 8, 1])
    with nav_prev:
        if st.button("←", key="nav_prev", use_container_width=True, disabled=current_num <= 1):
            st.session_state.global_idx -= 1
            save_progress_index(paths, st.session_state.global_idx)
            st.rerun()
    with nav_title:
        st.markdown(f"### Фраза {current_num} из {len(phrases)}")
    with nav_next:
        if st.button("→", key="nav_next", use_container_width=True, disabled=current_num >= len(phrases)):
            st.session_state.global_idx += 1
            save_progress_index(paths, st.session_state.global_idx)
            st.rerun()

    if phrase in replacements:
        if replacements[phrase] == phrase:
            st.success("Оставлено без изменений")
        else:
            st.success(f"Выбрано: {replacements[phrase]}")
    st.info(phrase)

    data = get_candidates(phrase, cache, phrase_context(meta), paths)
    candidates = data["candidates"]
    recommended = data.get("recommended", 0)

    st.markdown("**Выберите вариант:**")
    cols = st.columns(min(len(candidates), 3))
    for i, cand in enumerate(candidates):
        label = f"{'★ ' if i == recommended else ''}{cand}"
        col = cols[i % len(cols)]
        with col:
            if st.button(label, key=f"pick_{current_num}_{i}", use_container_width=True):
                pick_replacement(
                    paths,
                    replacements,
                    phrase,
                    cand,
                    phrases,
                    st.session_state.global_idx,
                )
                st.rerun()

    if st.button("Пропустить — оставить как есть", use_container_width=True):
        pick_replacement(
            paths,
            replacements,
            phrase,
            phrase,
            phrases,
            st.session_state.global_idx,
        )
        st.rerun()

    st.divider()
    custom = st.text_area(
        "Свой вариант",
        value=phrase,
        key=f"custom_{st.session_state.global_idx}",
        height=120,
    )
    if st.button("Сохранить свой вариант", disabled=not custom.strip() or custom.strip() == phrase):
        pick_replacement(
            paths,
            replacements,
            phrase,
            custom.strip(),
            phrases,
            st.session_state.global_idx,
        )
        st.rerun()

    st.divider()
    st.markdown("**Применить выбранные замены**")
    if st.button(f"Применить {len(replacements)} замен"):
        count = apply_and_save(paths, replacements)
        st.success(f"Обновлено {count} ячеек")
        render_downloads(paths, replacements)

    with st.sidebar:
        st.divider()
        st.header("Навигация")
        st.write(f"Осталось: {len(pending)}")

        if meta:
            st.subheader("Листы")
            if meta.get("pairs"):
                for pair in meta["pairs"]:
                    st.write(pair)
            st.write(f"Вхождений: {meta.get('count', 0)}")
            if meta.get("is_duplicate_across_pair"):
                st.warning("Дубль: есть и на сводном листе (Лист N), и на рабочем дне (N)")
            elif meta.get("in_summary"):
                st.info("Только сводная карта")
            elif meta.get("in_workday"):
                st.info("Только рабочий день")


if __name__ == "__main__":
    main()
