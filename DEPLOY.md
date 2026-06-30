# Деплой: Streamlit Cloud + Neon ($0)

Рекомендуемый бесплатный стек:

| Компонент | Сервис | Free-tier |
|-----------|--------|-----------|
| Приложение | [Streamlit Community Cloud](https://streamlit.io/cloud) | $0, публичный GitHub-репо |
| База данных | [Neon](https://neon.tech) | ~500 MB Postgres, scale-to-zero |
| AI | Google Gemini API | pay-as-you-go (копейки на сессию) |

> **Vercel не подходит** — Streamlit требует постоянный Python-процесс.

---

## Что понадобится

- Аккаунт [GitHub](https://github.com)
- Аккаунт [Streamlit Cloud](https://share.streamlit.io) (вход через GitHub)
- Аккаунт [Neon](https://neon.tech)
- Ключ [Gemini API](https://aistudio.google.com/apikey)

---

## Шаг 1. Подготовить репозиторий

1. Создайте **публичный** репозиторий на GitHub и запушьте код проекта.

2. **Не коммитьте** (они уже в `.gitignore`):
   - `.env` — секреты
   - `*.xlsx` — большие Excel-файлы
   - `candidates_cache.json`, `replacements.json` — локальный кэш

3. В репозитории должны быть:
   - `app.py`
   - `requirements.txt`
   - `schema.sql`
   - папка `src/`

---

## Шаг 2. Neon — база данных

### Вариант A: уже есть проекты в Neon (ваш случай)

Не обязательно создавать новый проект — **достаточно одной пустой базы** в существующем:

1. [console.neon.tech](https://console.neon.tech) → выберите проект (у вас, например, `neon-cerulean-yacht`).

2. На **Project dashboard** нажмите чёрную кнопку **Connect** (справа вверху).
   - Вкладка **Connection string**
   - Режим: **Pooled connection** (не Direct)
   - Скопируйте строку — в конце будет `/neondb?sslmode=require`  
     Это **дефолтная база `neondb`** — отдельно создавать database **не нужно**.

3. **SQL Editor** — иконка в левом сайдбаре (лист с символом SQL) → вставьте содержимое `schema.sql` из репозитория → **Run**.

   Если таблицы уже есть — ничего страшного, `CREATE TABLE IF NOT EXISTS` их не сломает.

> **Где «Databases»?** В новом UI Neon этого пункта часто нет. Проект = одна Postgres-инстанция, база по умолчанию — `neondb`. Для этого app этого достаточно.

Для одной общей сессии и одного Excel ~1 MB хватит **нескольких мегабайт** — ваш **0.17 GB** более чем достаточно.

### Вариант B: кнопка «New project» недоступна (Neon через Vercel)

Если при «+ New project» видите подсказку *«use the Neon Postgres integration in Vercel»* — аккаунт привязан к **Vercel Marketplace**. Это нормально:

| Что делать | Как |
|------------|-----|
| **Проще всего** | Использовать **существующий** проект/БД (вариант A) |
| Новая БД через Vercel | Vercel → Project → **Storage** → **Neon** → Create database → скопировать `DATABASE_URL` |
| Отдельный Neon без Vercel | Зарегистрироваться на [neon.tech](https://neon.tech) **другим email** или отвязать интеграцию — только если нужен чистый standalone-аккаунт |

> **Важно:** приложение крутится на **Streamlit Cloud**, не на Vercel. Neon из Vercel — это просто способ получить `DATABASE_URL`; строка подключения работает откуда угодно (Streamlit, локально).

### Connection string

Формат (pooled):
```
postgresql://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
```

### Free-tier

- ~**0.5 GB** на проект — для одной общей книги и кэша более чем достаточно
- проект «засыпает» при неактивности — первый запрос после паузы может быть медленнее

---

## Шаг 3. Streamlit Cloud — деплой приложения

1. [share.streamlit.io](https://share.streamlit.io) → **Create app**.

2. Выберите репозиторий, ветку `main`, main file: **`app.py`**.

3. Перед деплоем откройте **Advanced settings** → **Secrets** и вставьте:

   ```toml
   GEMINI_API_KEY = "ваш-ключ-gemini"

   DATABASE_URL = "postgresql://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require"

   APP_BASE_URL = "https://YOUR-APP-NAME.streamlit.app"
   ```

   - `DATABASE_URL` — pooled-строка из Neon (шаг 2)
   - `APP_BASE_URL` — URL приложения Streamlit (после деплоя; для ссылки в сайдбаре)

4. Нажмите **Deploy**. Streamlit установит зависимости из `requirements.txt` и запустит `app.py`.

---

## Шаг 4. Проверка

1. Откройте URL приложения.
2. В сайдбаре: **«Общая сессия · Neon PostgreSQL»**.
3. Загрузите `.xlsx` (один раз — файл общий для всех).
4. Откройте приложение во второй вкладке / у коллеги — те же фразы и прогресс.
5. После изменений коллеги нажмите **«Обновить с сервера»**.
6. **Применить** → скачайте `manual.xlsx` и `Книга2_revised.xlsx`.

---

## Как это работает

```
Пользователь → Streamlit Cloud (app.py)
                    ↓
              Neon Postgres
              ├── user_sessions   (id, global_idx, имя файла)
              └── session_blobs   (Excel, replacements, candidates)
```

- **Одна общая сессия** для всех пользователей (1–2 человека работают с одной книгой).
- Excel, выборы, позиция в списке и кэш Gemini — в Neon, переживают рестарт Streamlit Cloud.
- Диск Streamlit Cloud **временный**; Neon — источник правды.
- Кнопка **«Обновить с сервера»** подтягивает изменения коллеги.

---

## Лимиты free-tier и когда думать об апгрейде

| Ресурс | Лимит | Ориентир |
|--------|-------|----------|
| Neon storage | ~500 MB | одна книга + кэш — более чем достаточно |
| Neon compute | 100 CU-hours/мес | обычно хватает для личного/командного использования |
| Streamlit Cloud | 1 частное app на free* | нужен **публичный** репо |
| Gemini API | по тарифу Google | ~$0.01–0.10 на сотню фраз (flash) |

\* Актуальные лимиты Streamlit Cloud: [streamlit.io/pricing](https://streamlit.io/pricing)

Когда понадобится начать заново — удалите данные общей сессии в SQL Editor:
```sql
DELETE FROM session_blobs WHERE session_id = '00000000-0000-4000-8000-000000000001';
UPDATE user_sessions SET global_idx = 0 WHERE id = '00000000-0000-4000-8000-000000000001';
```

---

## Локальная разработка

```bash
pip install -r requirements.txt
cp .env.example .env
# заполните GEMINI_API_KEY и DATABASE_URL
streamlit run app.py
```

Без `DATABASE_URL` — локальный режим: подхватывается `Книга2.xlsx` из папки, без upload.

---

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| «DATABASE_URL не задан» | Добавьте secret в Streamlit Cloud → Reboot |
| Ошибка подключения к Neon | Используйте **pooled** URL + `?sslmode=require` |
| «Сессия не найдена» | Ссылка устарела или сессия удалена из Neon |
| Долгий первый запрос | Neon «проснулся» после паузы — нормально для free-tier |
| Gemini 404 / 403 | Проверьте `GEMINI_API_KEY` в Secrets |

---

## Альтернативы (не нужны для старта)

- **Railway / Render + Docker** — если нужен приватный репо или свой домен; см. `Dockerfile`
- **Supabase** — если Neon storage кончится (1 GB file storage на free-tier)
- **Vercel** — потребует переписать UI на Next.js; текущий код — Streamlit-only
