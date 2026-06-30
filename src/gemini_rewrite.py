import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .config import GEMINI_MODEL, ROOT

load_dotenv(ROOT / ".env")

SYSTEM_PROMPT = """Ты редактор хронометражных карт для методистов образования Казахстана.
Перепиши абстрактное название операции в конкретное наблюдаемое действие — так, чтобы его можно было засечь секундомером.

Правила:
- Глагол в неопределённой форме или отглагольное существительное с конкретным объектом
- Сохраняй термины: ТУПр, ГОСО, названия разделов (Тыңдалым, Айтылым, Оқылым, Жазылым и т.д.)
- Не меняй смысл и объём работы
- Варианты на русском языке
- 3–5 вариантов, от более детального к более краткому
- recommended — индекс (0-based) лучшего варианта для хронометража

Ответ — только JSON, без markdown:
{"candidates": ["...", "..."], "recommended": 0, "reason": "одно предложение почему"}"""


def _client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=api_key)


def _parse_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError("No candidates in response")
    recommended = int(data.get("recommended", 0))
    recommended = max(0, min(recommended, len(candidates) - 1))
    return {
        "candidates": candidates[:5],
        "recommended": recommended,
        "reason": data.get("reason", ""),
    }


def suggest_replacements(phrase: str, context: str = "") -> dict:
    client = _client()
    user_text = f"Оригинал: {phrase}"
    if context:
        user_text += f"\nКонтекст работы: {context}"

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.4,
            response_mime_type="application/json",
        ),
    )
    return _parse_response(response.text)


def suggest_replacements_batch(phrases: list[str], context: str = "") -> dict[str, dict]:
    if not phrases:
        return {}

    client = _client()
    items = [{"id": i, "phrase": p} for i, p in enumerate(phrases)]
    user_text = json.dumps({"phrases": items, "context": context}, ensure_ascii=False)

    batch_prompt = SYSTEM_PROMPT + """

Для каждой фразы из массива phrases верни объект с тем же id.
Ответ — JSON:
{"results": [{"id": 0, "candidates": [...], "recommended": 0, "reason": "..."}, ...]}"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_text,
        config=types.GenerateContentConfig(
            system_instruction=batch_prompt,
            temperature=0.4,
            response_mime_type="application/json",
        ),
    )
    data = json.loads(response.text.strip())
    out: dict[str, dict] = {}
    for item in data.get("results", []):
        idx = int(item["id"])
        if 0 <= idx < len(phrases):
            candidates = item.get("candidates") or []
            recommended = int(item.get("recommended", 0))
            recommended = max(0, min(recommended, len(candidates) - 1)) if candidates else 0
            out[phrases[idx]] = {
                "candidates": candidates[:5],
                "recommended": recommended,
                "reason": item.get("reason", ""),
            }
    return out


def best_replacement(phrase: str, context: str = "") -> str:
    result = suggest_replacements(phrase, context)
    return result["candidates"][result["recommended"]]
