import base64
import json
import os
import sys
import time
from io import BytesIO

import mss
import requests
from PIL import Image


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(_base_dir(), "config.json")
KNOWLEDGE_PATH = os.path.join(_base_dir(), "knowledge.md")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_knowledge():
    if not os.path.exists(KNOWLEDGE_PATH):
        return ""
    with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def capture_screen(monitor_index=1, resize_w=1280, resize_h=720):
    with mss.mss() as sct:
        monitors = sct.monitors
        if monitor_index >= len(monitors):
            monitor_index = 1
        monitor = monitors[monitor_index]
        screenshot = sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        img = img.resize((resize_w, resize_h), Image.LANCZOS)
        return img


def image_to_base64(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def analyze_screen(on_progress=None) -> dict:
    config = load_config()
    knowledge = load_knowledge()

    ollama_url = config.get("ollama_url", "http://localhost:11434")
    model = config.get("model", "llava")
    timeout = config["analysis"].get("timeout_seconds", 60)
    max_tokens = config["analysis"].get("max_tokens", 300)
    cap_cfg = config.get("capture", {})

    if on_progress:
        on_progress("Захватываю экран...")

    try:
        img = capture_screen(
            monitor_index=cap_cfg.get("monitor", 1),
            resize_w=cap_cfg.get("resize_width", 1280),
            resize_h=cap_cfg.get("resize_height", 720),
        )
    except Exception as e:
        return {"error": f"Ошибка захвата экрана: {e}"}

    if on_progress:
        on_progress("Отправляю в Ollama...")

    img_b64 = image_to_base64(img)

    system_prompt = f"""Ты — ИИ-аналитик для PvP-дуэлей в Minecraft на сервере Crystalix (режим Custom Steve House).
Твоя задача: смотреть на скриншот экрана игрока и давать быстрый вердикт о шансах победы.

БАЗА ЗНАНИЙ ОБ ИГРЕ:
{knowledge}

ПРАВИЛА АНАЛИЗА:
1. Определи что видно на экране (инвентарь игрока, его шмот, класс, статистика)
2. Оцени угрозу противника по его снаряжению и статистике
3. Дай вердикт СТРОГО в формате ниже — коротко и по делу
4. Отвечай ТОЛЬКО на русском языке
5. Если на экране нет данных для анализа — скажи об этом

ФОРМАТ ОТВЕТА (строго):
🎯 ВЕРДИКТ: [Ты победишь / Противник победит / Примерно равно]
📊 ШАНС ПОБЕДЫ: [число]%
⚠️ УГРОЗА: [Низкая / Средняя / Высокая / Критическая]
🔍 АНАЛИЗ: [1-2 предложения что увидел]
💡 СОВЕТ: [конкретная тактика]"""

    payload = {
        "model": model,
        "prompt": "Проанализируй этот скриншот игры и дай вердикт о дуэли. Смотри на снаряжение, класс и статистику игроков.",
        "images": [img_b64],
        "system": system_prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.2,
        },
    }

    try:
        start = time.time()
        response = requests.post(
            f"{ollama_url}/api/generate",
            json=payload,
            timeout=timeout,
        )
        elapsed = time.time() - start
        response.raise_for_status()
        data = response.json()
        text = data.get("response", "").strip()
        return {"text": text, "elapsed": round(elapsed, 1), "error": None}
    except requests.exceptions.ConnectionError:
        return {"error": "Ollama не запущена! Запусти Ollama и попробуй снова."}
    except requests.exceptions.Timeout:
        return {"error": f"Ollama не ответила за {timeout} сек. Попробуй меньшую модель."}
    except Exception as e:
        return {"error": f"Ошибка запроса: {e}"}


def check_ollama(ollama_url: str) -> tuple[bool, str]:
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=5)
        data = r.json()
        models = [m["name"] for m in data.get("models", [])]
        return True, models
    except requests.exceptions.ConnectionError:
        return False, []
    except Exception as e:
        return False, []


def check_vision_model(ollama_url: str, model: str) -> bool:
    ok, models = check_ollama(ollama_url)
    if not ok:
        return False
    return any(model in m for m in models)
