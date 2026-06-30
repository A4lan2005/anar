# Редактор абстрактных операций в хронометраже

## Локально

```bash
pip install -r requirements.txt
cp .env.example .env   # GEMINI_API_KEY обязателен
streamlit run app.py
```

Без `DATABASE_URL` — как раньше: подхватывается `Книга2.xlsx` из папки проекта.

С `DATABASE_URL` (Neon) — загрузка файла через UI, прогресс сохраняется в БД.

## Деплой (бесплатно)

**[DEPLOY.md](DEPLOY.md)** — пошагово: **Streamlit Cloud + Neon** ($0).

Кратко: публичный GitHub → [share.streamlit.io](https://share.streamlit.io) → Secrets (`GEMINI_API_KEY`, `DATABASE_URL`, `APP_BASE_URL`).

## Файлы

| Файл | Описание |
|------|----------|
| `Книга2.xlsx` | Локальный исходник (не нужен в проде) |
| `?session=<uuid>` | Ссылка для восстановления сессии |
| `manual.xlsx` / `Книга2_revised.xlsx` | Скачиваются через UI после «Применить» |

## Авто-обработка (CLI)

```bash
python run_auto.py
```

Локальный скрипт → `auto.xlsx` (не связан с веб-сессиями).
