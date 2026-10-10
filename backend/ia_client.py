"""Cliente (lado do jogo) da API de IA generativa do próprio grupo.

O jogo não chama a OpenAI: ele faz POST em /v1/ia-generativa/texto com `requests`,
enviando a API Key no header X-API-Key. A URL padrão é o próprio servidor; para separar
a API do jogo em outro serviço basta apontar IA_API_URL para ele.
"""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger("uvicorn.error")
ENDPOINT = "/v1/ia-generativa/texto"


class IAError(Exception):
    """Falha ao obter texto. `api_called` diz se a chamada chegou a gastar o serviço externo."""

    def __init__(self, note: str, api_called: bool):
        super().__init__(note)
        self.note = note
        self.api_called = api_called


def base_url() -> str:
    return os.getenv("IA_API_URL") or f"http://127.0.0.1:{os.getenv('PORT', '8000')}"


def is_enabled() -> bool:
    if not os.getenv("IA_API_KEY"):
        return False
    # API embutida: só funciona com a chave da OpenAI; API remota: ela mesma decide.
    return bool(os.getenv("IA_API_URL")) or bool(os.getenv("OPENAI_API_KEY"))


def generate_text(messages: list[dict], temperature: float, max_tokens: int) -> dict:
    key = os.getenv("IA_API_KEY")
    if not key:
        raise IAError("sem IA_API_KEY", api_called=False)
    url = base_url().rstrip("/") + ENDPOINT
    try:
        r = requests.post(
            url,
            json={"messages": messages, "temperature": temperature, "max_tokens": max_tokens},
            headers={"X-API-Key": key},
            timeout=25,
        )
    except requests.RequestException as exc:
        raise IAError(f"API de IA indisponível: {type(exc).__name__}", api_called=False)
    log.info("jogo -> POST %s -> %s", url, r.status_code)
    if r.status_code == 200:
        return r.json()
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except ValueError:
        pass
    # 503 = serviço externo sem chave: nada foi gasto
    raise IAError(str(detail) or f"HTTP {r.status_code}", api_called=r.status_code >= 500 and r.status_code != 503)
