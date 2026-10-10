"""Autenticação por API Key (header X-API-Key) das rotas de IA generativa."""
from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

# auto_error=False para devolvermos 401 com mensagem própria; o esquema aparece no Swagger (botão Authorize).
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Chave definida em IA_API_KEY")


def require_api_key(key: str | None = Security(api_key_header)) -> None:
    expected = os.getenv("IA_API_KEY")
    if not expected:  # falha fechada: sem chave configurada a rota não funciona para ninguém
        raise HTTPException(503, "IA_API_KEY não configurada no servidor.")
    if not key:
        raise HTTPException(401, "Envie a chave no header X-API-Key.")
    if not secrets.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(403, "API Key inválida.")
