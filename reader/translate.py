from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from . import db

DEFAULT_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


class TranslationError(RuntimeError):
    pass


def get_llm_settings(mask: bool = True) -> dict[str, Any]:
    raw = db.get_setting("llm")
    cfg: dict[str, Any] = {}
    if raw:
        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError:
            cfg = {}
    env_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    key = cfg.get("api_key") or env_key
    out = {
        "base_url": cfg.get("base_url") or DEFAULT_BASE,
        "model": cfg.get("model") or DEFAULT_MODEL,
        "has_key": bool(key),
        "source": "env" if (env_key and not cfg.get("api_key")) else ("saved" if cfg.get("api_key") else "none"),
    }
    if mask and key:
        out["api_key"] = key[:4] + "…" + key[-4:] if len(key) > 10 else "已配置"
    else:
        out["api_key"] = key
    return out


def save_llm_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = get_llm_settings(mask=False)
    key = (payload.get("api_key") or "").strip()
    if not key or key == current.get("api_key") or key == "已配置" or "…" in key:
        key = current.get("api_key") or ""
    cfg = {
        "base_url": (payload.get("base_url") or DEFAULT_BASE).strip().rstrip("/"),
        "model": (payload.get("model") or DEFAULT_MODEL).strip(),
        "api_key": key,
    }
    db.set_setting("llm", json.dumps(cfg, ensure_ascii=False))
    return get_llm_settings(mask=True)


def _endpoint(base_url: str) -> str:
    base = (base_url or DEFAULT_BASE).rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _clean(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^```(?:text|markdown)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def translate_text(text: str, book: str = "晉書", chapter: str = "") -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise TranslationError("没有可翻译的文本")
    cfg = get_llm_settings(mask=False)
    key = cfg.get("api_key") or ""
    if not key:
        raise TranslationError("尚未配置大模型 API Key。请在「设置 · 今译」中填写 DeepSeek 或 OpenAI 兼容接口。")

    system = (
        "你是中国古代史籍的专业译者，熟悉《晋书》《三国志》等正史的语言、职官、地名与人物关系。"
        "请把用户给出的繁体古文译为准确、通顺、克制的现代汉语。"
        "要求：1. 不添加原文没有的信息；2. 人名、地名、职官保留原貌，必要时用括号略作说明；"
        "3. 保留原文的叙事层次和语气，不用网络流行语；4. 只输出译文，不要解释，不要加标题。"
    )
    user = f"书名：{book}\n篇章：{chapter}\n原文：\n{text}"
    body = {
        "model": cfg.get("model") or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.25,
        "max_tokens": 2000,
        "stream": False,
    }
    req = urllib.request.Request(
        _endpoint(cfg.get("base_url")),
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise TranslationError(f"翻译接口返回 {exc.code}：{detail}") from exc
    except urllib.error.URLError as exc:
        raise TranslationError(f"无法连接翻译接口：{exc.reason}") from exc
    except TimeoutError as exc:
        raise TranslationError("翻译接口超时，请稍后重试") from exc

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TranslationError(f"翻译接口返回格式异常：{payload}") from exc
    return {"translation": _clean(content), "model": cfg.get("model") or DEFAULT_MODEL}
