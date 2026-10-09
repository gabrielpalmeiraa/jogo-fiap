"""Teste de integração da API: partida completa até o final correto (LLM em fallback)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.pop("OPENAI_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

c = TestClient(app)


def test_health_e_pagina_inicial():
    assert c.get("/api/health").json()["ok"] is True
    assert c.get("/").status_code == 200


def test_partida_completa_final_correto():
    st = c.post("/api/new").json()
    sid = st["sid"]
    assert st["day"] == 1
    for eid in ("log_acesso", "email"):
        st = c.post("/api/collect", json={"sid": sid, "evidence_id": eid}).json()
    r = c.post("/api/interrogate", json={
        "sid": sid, "suspect": "rafael", "tone": "perguntar",
        "message": "A Beatriz te mandou esse e-mail, não foi?", "evidence_ids": ["email"],
    }).json()
    assert r["just_unlocked"] and r["reply"]["source"] == "fallback"
    found = [e["id"] for e in r["state"]["evidences"] if e["found"]]
    assert "confissao" in found
    st = c.post("/api/accuse", json={"sid": sid, "suspect": "rafael", "evidence_ids": ["email", "confissao"]}).json()
    assert st["ending"] == "caso_encerrado"
    # depois do fim, nada mais acontece
    assert c.post("/api/end-day", json={"sid": sid}).status_code == 400


def test_erros_de_regra_viram_400():
    sid = c.post("/api/new").json()["sid"]
    r = c.post("/api/interrogate", json={"sid": sid, "suspect": "beatriz", "message": "oi", "evidence_ids": ["email"]})
    assert r.status_code == 400
    assert c.get("/api/state/naoexiste").status_code == 404


def test_mensagem_longa_e_rejeitada():
    sid = c.post("/api/new").json()["sid"]
    r = c.post("/api/interrogate", json={"sid": sid, "suspect": "beatriz", "message": "x" * 301})
    assert r.status_code == 422


def test_limite_de_sessoes_descarta_a_mais_antiga(monkeypatch):
    import main
    monkeypatch.setattr(main, "MAX_SESSIONS", 3)
    first = c.post("/api/new").json()["sid"]
    for _ in range(5):
        c.post("/api/new")
    assert len(main.SESSIONS) <= 3
    assert c.get(f"/api/state/{first}").status_code == 404


def test_limite_de_chamadas_gpt_cai_no_fallback(monkeypatch):
    import main
    import llm
    monkeypatch.setattr(main, "MAX_GPT_CALLS", 0)
    sid = c.post("/api/new").json()["sid"]
    r = c.post("/api/interrogate", json={"sid": sid, "suspect": "aurora", "message": "Oi"}).json()
    assert r["reply"]["source"] == "fallback"
    assert "limite" in r["reply"]["note"]
