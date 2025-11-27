import json
import logging
from typing import List, Dict
from langchain_openai import ChatOpenAI
from edms_assistant.core.settings import settings

logger = logging.getLogger(__name__)


async def route_question_to_file(
        question: str,
        chat_history: List[Dict],
        available_files_info: List[Dict]
) -> str:
    """
    Маршрутизирует вопрос к наиболее релевантному документу на основе его описания.

    Args:
        question: Текущий вопрос пользователя.
        chat_history: История диалога.
        available_files_info: Список документов с метаданными.

    Returns:
        Имя выбранного файла (str).
    """
    if not available_files_info:
        raise ValueError("Нет доступных документов для маршрутизации")

    if len(available_files_info) == 1:
        return available_files_info[0]["filename"]

    # Формируем контекст из истории (только вопросы пользователя)
    history = " ".join(
        msg["content"] for msg in chat_history if msg["role"] == "user"
    ) if chat_history else ""
    context = f"История вопросов: {history}\nТекущий вопрос: {question}" if history else question

    # Формируем строку с файлами и описаниями для промпта
    files_list_str = "\n".join(
        f"- {f['filename']}: {f['description']}"
        for f in available_files_info
    )

    # Инициализируем LLM
    llm = ChatOpenAI(
        api_key="not-needed",
        base_url=str(settings.vllm.generative_base_url),
        model=settings.vllm.generative_model,
        temperature=0.0,
        max_tokens=128
    )

    logger.info(f"Доступные документы:{available_files_info}")

    # Системная инструкция
    system_prompt = (
        "Ты — маршрутизатор запросов в корпоративной системе документооборота (СЭД). "
        "Твоя задача — выбрать ОДИН файл из списка, в котором НАИБОЛЕЕ ВЕРОЯТНО содержится ответ на вопрос. "
        "Используй описания файлов для принятия решения."
    )

    # Пользовательский промпт
    user_prompt = f"""Инструкция:
1. Проанализируй вопрос и доступные файлы (с описаниями).
2. Выбери файл, наиболее релевантный по ТЕМАТИКЕ и КОНТЕКСТУ.
3. Верни ТОЛЬКО валидный JSON без пояснений.

Формат ответа:
{{"filename": "точное_имя_файла_с_расширением", "reason": "1-3 слова"}}

Пример:
Доступные документы:
- Руководство_по_EDMS.docx: Описание работы со справочниками СЭД, классификаторами и настройками...
- Приказы_2024.pdf: Архив приказов за 2024 год...

Контекст:
Текущий вопрос: Кто согласовывает приказы в отделе продаж?
Ответ:
{{"filename": "Таблица_ответственных.xlsx", "reason": "согласование ответственных"}}

Теперь твоя очередь:

Доступные документы:
{files_list_str}

Контекст:
{context}

Ответ:"""

    try:
        # Вызываем LLM
        resp = await llm.ainvoke([
            ("system", system_prompt),
            ("user", user_prompt)
        ])

        raw_content = resp.content.strip()
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]

        data = json.loads(raw_content)
        fname = data.get("filename", "").strip()
        reason = data.get("reason", "no reason")

        valid_filenames = {f["filename"] for f in available_files_info}
        if fname in valid_filenames:
            logger.debug(f"✅ Маршрутизация: {fname} (причина: {reason})")
            return fname
        else:
            logger.warning(f"⚠️ Неверное имя файла в ответе LLM: '{fname}'. Доступны: {list(valid_filenames)}")

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(
            f"⚠️ Ошибка парсинга JSON от LLM: {e}. Ответ был: {resp.content if 'resp' in locals() else 'N/A'}"
        )
    except Exception as e:
        logger.error(f"❌ Критическая ошибка маршрутизации: {e}")

    fallback = available_files_info[0]["filename"]
    logger.debug(f"🔀 Fallback маршрутизации: {fallback}")
    return fallback
