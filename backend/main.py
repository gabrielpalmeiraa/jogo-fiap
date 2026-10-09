"""API e servidor estático do MVP Sinapse: Protocolo Silencioso.

Rodar (na pasta raiz do projeto):
    uvicorn backend.main:app --reload   (ou: python run.py)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import llm  # noqa: E402
from game import GameError, GameState, TONES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
ASSETS = FRONTEND / "assets"

app = FastAPI(title="Sinapse: Protocolo Silencioso (MVP)")
SESSIONS: dict[str, GameState] = {}
LAST_SEEN: dict[str, float] = {}

# Proteções para a versão publicada: limitam memória e gasto de API por visitante.
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "300"))
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "7200"))
MAX_GPT_CALLS = int(os.getenv("MAX_GPT_CALLS_PER_SESSION", "40"))  # depois disso, falas pré-escritas

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
    while len(SESSIONS) >= MAX_SESSIONS:
        oldest = min(LAST_SEEN, key=LAST_SEEN.get)
        SESSIONS.pop(oldest, None)
        LAST_SEEN.pop(oldest, None)


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
def new_game():
    purge_sessions()
    st = GameState.new()
    SESSIONS[st.sid] = st
    LAST_SEEN[st.sid] = time.time()
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
def interrogate(body: InterrogateIn):
    st = get_state(body.sid)
    turn = guarded(lambda: st.apply_turn(body.suspect, body.tone, body.evidence_ids, body.message))
    reply = llm.generate_reply(st, body.suspect, turn, body.message, allow_api=st.gpt_calls < MAX_GPT_CALLS)
    if reply["source"] == "gpt":
        st.gpt_calls += 1
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
