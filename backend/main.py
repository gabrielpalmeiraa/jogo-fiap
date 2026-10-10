"""API e servidor estático do MVP Sinapse: Protocolo Silencioso.

Rodar (na pasta raiz do projeto):
    uvicorn backend.main:app --reload   (ou: python run.py)
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import llm  # noqa: E402
from game import GameError, GameState, TONES  # noqa: E402
from routers import ia_generativa  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
ASSETS = FRONTEND / "assets"

app = FastAPI(
    title="Sinapse: Protocolo Silencioso (MVP)",
    version="1.1.0",
    description="API do jogo (/api/*) e API de IA generativa do grupo (/v1/ia-generativa/*, protegida por X-API-Key).",
)
# CORS: origens permitidas a chamar a API de IA a partir de um navegador (lista separada por vírgula).
# O jogo publicado é servido pelo mesmo domínio, então o padrão só libera o ambiente local.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)
app.include_router(ia_generativa.router)
SESSIONS: dict[str, GameState] = {}
LAST_SEEN: dict[str, float] = {}

# Proteções para a versão publicada: limitam memória e gasto de API por visitante.
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "300"))
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "7200"))
MAX_GPT_CALLS = int(os.getenv("MAX_GPT_CALLS_PER_SESSION", "40"))  # depois disso, falas pré-escritas
# Tetos que valem mesmo se o visitante abrir várias sessões (evita burlar o limite por sessão).
MAX_GPT_CALLS_PER_IP_DAY = int(os.getenv("MAX_GPT_CALLS_PER_IP_DAY", "120"))
MAX_GPT_CALLS_GLOBAL_DAY = int(os.getenv("MAX_GPT_CALLS_GLOBAL_DAY", "1500"))
MAX_NEW_GAMES_PER_IP_HOUR = int(os.getenv("MAX_NEW_GAMES_PER_IP_HOUR", "20"))
TRUST_PROXY = os.getenv("TRUST_PROXY") == "1"  # só atrás de proxy confiável (Render)
MAX_TRACKED_IPS = 5000
LOCK = threading.Lock()
SID_IP: dict[str, str] = {}
GPT_USAGE: dict[str, list] = {}   # ip -> timestamps das chamadas ao GPT (últimas 24h)
GPT_GLOBAL: list = []             # timestamps de todas as chamadas ao GPT (últimas 24h)
NEW_GAMES: dict[str, list] = {}   # ip -> timestamps de /api/new (última hora)

ASSET_KEYS = {
    "bg_menu": "bg_menu",
    "bg_room": "bg_room",
    "portrait_beatriz": "portrait_beatriz",
    "portrait_rafael": "portrait_rafael",
    "portrait_aurora": "portrait_aurora",
}


class InterrogateIn(BaseModel):
    sid: str
    suspect: str
    message: str = Field(max_length=300)
    tone: str = "perguntar"
    evidence_ids: list[str] = []


class SidIn(BaseModel):
    sid: str


class CollectIn(SidIn):
    evidence_id: str


class AccuseIn(SidIn):
    suspect: str
    evidence_ids: list[str] = []


def purge_sessions() -> None:
    """Remove sessões paradas e, se ainda passar do limite, as mais antigas."""
    now = time.time()
    for sid in [k for k, t in LAST_SEEN.items() if now - t > SESSION_TTL]:
        SESSIONS.pop(sid, None)
        LAST_SEEN.pop(sid, None)
        SID_IP.pop(sid, None)
    while len(SESSIONS) >= MAX_SESSIONS:
        oldest = min(LAST_SEEN, key=LAST_SEEN.get) if LAST_SEEN else next(iter(SESSIONS))
        SESSIONS.pop(oldest, None)
        LAST_SEEN.pop(oldest, None)
        SID_IP.pop(oldest, None)


def client_ip(request: Request) -> str:
    """IP do visitante. Atrás do proxy do Render usa a ÚLTIMA entrada do x-forwarded-for
    (a que o proxy anexou); as anteriores podem ser forjadas pelo cliente."""
    if TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "?"


_last_gc = {"t": 0.0}


def _recent(log: dict, key: str, window: float) -> list:
    now = time.time()
    fresh = [t for t in log.get(key, []) if now - t < window]
    if fresh:
        log[key] = fresh
    else:
        log.pop(key, None)
    return fresh


def _gc(window_by_log: list) -> None:
    """Varre e remove IPs sem atividade recente (no máximo 1x por minuto, custo O(n) amortizado)."""
    now = time.time()
    if now - _last_gc["t"] < 60:
        return
    _last_gc["t"] = now
    for log, window in window_by_log:
        for k in [k for k, v in log.items() if not v or now - v[-1] >= window]:
            log.pop(k, None)


OVERFLOW = "__overflow__"


def _bucket(log: dict, key: str) -> str:
    """Com a tabela cheia, IPs novos dividem um único balde compartilhado (com os mesmos tetos).
    Assim a tabela nunca passa do limite, os contadores dos outros IPs ficam intactos e quem
    chega depois ainda joga, só que dividindo a cota do balde (sem bloqueio total)."""
    return key if key in log or len(log) < MAX_TRACKED_IPS else OVERFLOW


def reserve_gpt_call(sid: str, ip: str) -> bool:
    """Reserva uma vaga de chamada ao GPT ANTES de chamar (evita corrida entre requisições
    simultâneas). Se a chamada não usar o GPT, a vaga é devolvida por release_gpt_call."""
    now = time.time()
    with LOCK:
        st = SESSIONS.get(sid)
        if st is None:  # sessão descartada pela limpeza no meio da requisição
            return False
        _gc([(GPT_USAGE, 86400), (NEW_GAMES, 3600)])
        GPT_GLOBAL[:] = [t for t in GPT_GLOBAL if now - t < 86400]
        ip = _bucket(GPT_USAGE, ip)
        if st.gpt_calls >= MAX_GPT_CALLS:
            return False
        if len(_recent(GPT_USAGE, ip, 86400)) >= MAX_GPT_CALLS_PER_IP_DAY:
            return False
        if len(GPT_GLOBAL) >= MAX_GPT_CALLS_GLOBAL_DAY:
            return False
        st.gpt_calls += 1
        GPT_USAGE.setdefault(ip, []).append(now)
        GPT_GLOBAL.append(now)
        return True


def release_gpt_call(sid: str, ip: str) -> None:
    with LOCK:
        if ip not in GPT_USAGE and OVERFLOW in GPT_USAGE:
            ip = OVERFLOW
        st = SESSIONS.get(sid)
        if st and st.gpt_calls > 0:
            st.gpt_calls -= 1
        if GPT_USAGE.get(ip):
            GPT_USAGE[ip].pop()
        if GPT_GLOBAL:
            GPT_GLOBAL.pop()


def get_state(sid: str) -> GameState:
    st = SESSIONS.get(sid)
    if not st:
        raise HTTPException(404, "Sessão não encontrada. Inicie um novo caso.")
    LAST_SEEN[sid] = time.time()
    return st


def guarded(fn):
    try:
        return fn()
    except GameError as e:
        raise HTTPException(400, str(e))


@app.get("/api/health")
def health():
    return {"ok": True, "llm": llm.llm_enabled(), "model": llm.MODEL, "tones": list(TONES)}


@app.get("/api/assets")
def assets():
    """Lista quais imagens (geradas por IA) existem em frontend/assets. O jogo usa arte
    procedural no lugar das que faltarem."""
    found = {}
    for key in ASSET_KEYS:
        for ext in ("png", "jpg", "jpeg", "webp"):
            if (ASSETS / f"{key}.{ext}").exists():
                found[key] = f"/assets/{key}.{ext}"
                break
    return found


@app.post("/api/new")
def new_game(request: Request):
    ip = client_ip(request)
    with LOCK:
        _gc([(GPT_USAGE, 86400), (NEW_GAMES, 3600)])
        ip = _bucket(NEW_GAMES, ip)
        if len(_recent(NEW_GAMES, ip, 3600)) >= MAX_NEW_GAMES_PER_IP_HOUR:
            raise HTTPException(429, "Muitas partidas novas em pouco tempo. Tente novamente mais tarde.")
        NEW_GAMES.setdefault(ip, []).append(time.time())
        purge_sessions()
        st = GameState.new()
        SESSIONS[st.sid] = st
        LAST_SEEN[st.sid] = time.time()
        SID_IP[st.sid] = ip
    return st.public()


@app.get("/api/state/{sid}")
def state(sid: str):
    return get_state(sid).public()


@app.post("/api/collect")
def collect(body: CollectIn):
    st = get_state(body.sid)
    guarded(lambda: st.collect(body.evidence_id))
    return st.public()


@app.post("/api/interrogate")
def interrogate(body: InterrogateIn, request: Request):
    st = get_state(body.sid)
    turn = guarded(lambda: st.apply_turn(body.suspect, body.tone, body.evidence_ids, body.message))
    ip = client_ip(request)
    reserved = reserve_gpt_call(body.sid, ip)
    try:
        reply = llm.generate_reply(st, body.suspect, turn, body.message, allow_api=reserved)
    except Exception:
        if reserved:
            release_gpt_call(body.sid, ip)
        raise
    if reserved and not reply.get("api_called"):
        release_gpt_call(body.sid, ip)  # nenhuma chamada à API foi feita: devolve a vaga
    st.record_reply(body.suspect, reply["text"])
    return {
        "reply": reply,
        "just_unlocked": turn["just_unlocked"],
        "effects": turn["effects"],
        "state": st.public(),
    }


@app.post("/api/end-day")
def end_day(body: SidIn):
    st = get_state(body.sid)
    result = guarded(st.end_day)
    return {"result": result, "state": st.public()}


@app.post("/api/accuse")
def accuse(body: AccuseIn):
    st = get_state(body.sid)
    guarded(lambda: st.accuse(body.suspect, body.evidence_ids))
    return st.public()


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
