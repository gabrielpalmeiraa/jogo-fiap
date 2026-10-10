"""Provider de IA generativa (texto): único ponto do projeto que fala com a OpenAI.

O router só conhece `generate_text`. Trocar de serviço (outro modelo ou outro fornecedor)
significa mexer apenas aqui.
"""
from __future__ import annotations

import os

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class ProviderUnavailable(Exception):
    """Serviço externo não configurado (sem chave)."""


class ProviderError(Exception):
    """O serviço externo respondeu com erro, estourou o tempo ou devolveu texto vazio."""


def is_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def generate_text(messages: list[dict], temperature: float, max_tokens: int) -> dict:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ProviderUnavailable("sem OPENAI_API_KEY")
    from openai import OpenAI

    try:
        client = OpenAI(api_key=key, timeout=20.0, max_retries=1)
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # rede, cota, chave inválida, timeout
        raise ProviderError(type(exc).__name__) from exc
    if not text:
        raise ProviderError("resposta vazia")
    return {"text": text, "model": MODEL}
