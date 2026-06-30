from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent

SOURCE_XLSX = ROOT / "Книга2.xlsx"
AUTO_XLSX = ROOT / "auto.xlsx"
MANUAL_XLSX = ROOT / "manual.xlsx"
REVISED_XLSX = ROOT / "Книга2_revised.xlsx"
REPLACEMENTS_JSON = ROOT / "replacements.json"
CANDIDATES_JSON = ROOT / "candidates_cache.json"

GEMINI_MODEL = "gemini-2.5-flash"

# Inclusive bounds — prefer catching extra phrases over missing work items.
MIN_PHRASE_LEN = 8
MAX_PHRASE_LEN = 300

# Only skip clear form metadata / labels, not operation-like text.
METADATA_PREFIXES = (
    "наименование организации",
    "наименование подразделения",
    "наименование работы",
    "наименование работы/услуги",
    "наименование работы (услуги)",
    "адрес проведения",
    "дата проведения",
    "дата наблюдения",
    "фамилия",
    "имя",
    "отчество",
    "исполнитель",
    "должность",
    "стаж работы",
    "разряд",
    "образование:",
    "табельный",
    "№ п/п",
    "итого",
    "всего",
    "примечание",
    "подпись",
    "хронометражная карта",
    "сводная хронометражная",
    "(час.мин.сек.)",
)

OPERATION_COLUMN_HEADERS = (
    "наименование операции",
    "наименование работы",
)

ABSTRACT_SUFFIXES = (
    "ение",
    "ание",
    "изация",
    "овка",
    "ировка",
    "из",
    "ка",
    "ство",
)

# Common operation-leading words even when pymorphy tags differ.
OPERATION_LEAD_WORDS = {
    "анализ",
    "определение",
    "разработка",
    "систематизация",
    "уточнение",
    "формирование",
    "проведение",
    "организация",
    "описание",
    "сопоставление",
    "формулирование",
    "выявление",
    "обобщение",
    "корректировка",
    "согласование",
    "оценка",
    "расчет",
    "рассмотрение",
    "изучение",
    "проверка",
    "подготовка",
    "составление",
    "обсуждение",
    "фиксация",
    "внесение",
    "актуализация",
    "структурирование",
    "классификация",
    "верификация",
    "редактирование",
    "доработка",
    "утверждение",
}

PHRASES_CACHE_VERSION = 2

# One shared workspace for all users (1–2 collaborators). Override via env if needed.
DEFAULT_SHARED_SESSION_ID = "00000000-0000-4000-8000-000000000001"


def shared_session_id() -> str:
    return os.environ.get("SHARED_SESSION_ID", DEFAULT_SHARED_SESSION_ID).strip()
