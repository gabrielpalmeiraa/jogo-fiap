"""Rotas da modalidade de IA generativa do MVP (texto). Protegidas por X-API-Key."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from providers import ia_provider
from security import require_api_key

router = APIRouter(
    prefix="/v1/ia-generativa",
    tags=["IA generativa"],
    dependencies=[Depends(require_api_key)],
)


class Mensagem(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class TextoIn(BaseModel):
    messages: list[Mensagem] = Field(min_length=1, max_length=20, description="Contexto da conversa (persona no system).")
    temperature: float = Field(0.65, ge=0, le=1.5)
    max_tokens: int = Field(220, ge=1, le=400)

    model_config = {
        "json_schema_extra": {
            "example": {
                "messages": [
                    {"role": "system", "content": "Você é Beatriz Konno, diretora da NEXORA Tech. Responda em até 3 frases."},
                    {"role": "user", "content": "Onde você estava na noite do vazamento?"},
                ],
                "temperature": 0.65,
                "max_tokens": 220,
            }
        }
    }


class TextoOut(BaseModel):
    text: str
    model: str


@router.post("/texto", response_model=TextoOut, summary="Gera a fala de um NPC")
def texto(body: TextoIn) -> TextoOut:
    try:
        out = ia_provider.generate_text([m.model_dump() for m in body.messages], body.temperature, body.max_tokens)
    except ia_provider.ProviderUnavailable as exc:
        raise HTTPException(503, str(exc))
    except ia_provider.ProviderError as exc:
        raise HTTPException(502, f"erro da API: {exc}")
    return TextoOut(**out)


@router.get("/status", summary="Informa se o serviço externo está configurado")
def status() -> dict:
    return {"provider_configured": ia_provider.is_configured(), "model": ia_provider.MODEL}
