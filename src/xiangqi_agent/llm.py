"""通用 OpenAI 兼容客户端（GLM / DeepSeek 共用）。"""
from __future__ import annotations

import base64
import json

import requests


class LLMError(RuntimeError):
    pass


def _image_data_url(img) -> str:
    import io

    from PIL import Image

    if isinstance(img, Image.Image):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()
        mime = "image/png"
    else:  # 路径
        with open(img, "rb") as f:
            data = f.read()
        mime = "image/png" if str(img).lower().endswith(".png") else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def chat(base_url: str, api_key: str, model: str, messages: list[dict],
         timeout: int = 60, temperature: float = 0.2, max_tokens: int | None = None) -> str:
    """调用 OpenAI 兼容 chat/completions，返回文本内容。

    max_tokens=None 时不传该字段：glm-4.6v 系列是推理模型，
    该参数是「推理+正文」总预算，设小了会把正文挤空，交给服务端默认更稳。
    """
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    try:
        r = requests.post(
            base_url,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise LLMError(f"请求失败: {e}") from e
    if r.status_code != 200:
        raise LLMError(f"API {r.status_code}: {r.text[:300]}")
    d = r.json()
    try:
        return d["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"响应格式异常: {json.dumps(d, ensure_ascii=False)[:300]}") from e


def chat_vision(base_url: str, api_key: str, model: str, image, prompt: str,
                timeout: int = 90, temperature: float = 0.0,
                max_tokens: int | None = None) -> str:
    """带一张图的视觉对话。image 为 PIL Image 或路径。"""
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": _image_data_url(image)}},
        ],
    }]
    return chat(base_url, api_key, model, messages, timeout=timeout,
                temperature=temperature, max_tokens=max_tokens)
