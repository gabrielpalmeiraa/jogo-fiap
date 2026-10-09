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


def test_abrir_varias_sessoes_nao_burla_o_teto_por_ip(monkeypatch):
    import main
    import time
    main.GPT_USAGE.clear(); main.GPT_GLOBAL.clear()
    monkeypatch.setattr(main, "MAX_GPT_CALLS_PER_IP_DAY", 2)
    monkeypatch.setattr(main, "MAX_GPT_CALLS_GLOBAL_DAY", 1000)
    main.GPT_USAGE["1.2.3.4"] = [time.time(), time.time()]
    sid = c.post("/api/new").json()["sid"]
    assert main.reserve_gpt_call(sid, "1.2.3.4") is False


def test_reserva_e_atomica_sob_concorrencia(monkeypatch):
    import threading
    import main
    main.GPT_USAGE.clear(); main.GPT_GLOBAL.clear()
    monkeypatch.setattr(main, "MAX_GPT_CALLS", 5)
    sid = c.post("/api/new").json()["sid"]
    results = []
    def worker():
        results.append(main.reserve_gpt_call(sid, "9.9.9.9"))
    ts = [threading.Thread(target=worker) for _ in range(40)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sum(results) == 5


def test_vaga_devolvida_quando_cai_no_fallback(monkeypatch):
    import main
    main.GPT_USAGE.clear(); main.GPT_GLOBAL.clear()
    sid = c.post("/api/new").json()["sid"]
    assert main.reserve_gpt_call(sid, "8.8.8.8")
    main.release_gpt_call(sid, "8.8.8.8")
    assert main.SESSIONS[sid].gpt_calls == 0 and not main.GPT_GLOBAL


def test_x_forwarded_for_so_vale_com_proxy_confiavel(monkeypatch):
    import main
    class Req:
        headers = {"x-forwarded-for": "6.6.6.6, 10.0.0.1"}
        class client: host = "5.5.5.5"
    monkeypatch.setattr(main, "TRUST_PROXY", False)
    assert main.client_ip(Req) == "5.5.5.5"
    monkeypatch.setattr(main, "TRUST_PROXY", True)
    assert main.client_ip(Req) == "10.0.0.1"   # última entrada, a do proxy


def test_tabela_cheia_falha_fechada_sem_apagar_outros_ips(monkeypatch):
    import time
    import main
    main.GPT_USAGE.clear(); main.GPT_GLOBAL.clear()
    monkeypatch.setattr(main, "MAX_TRACKED_IPS", 3)
    sid = c.post("/api/new").json()["sid"]
    for ip in ("a", "b", "c"):
        assert main.reserve_gpt_call(sid, ip)
    antes = {k: list(v) for k, v in main.GPT_USAGE.items()}
    assert main.reserve_gpt_call(sid, "novo") is False      # IP novo, tabela cheia
    assert main.GPT_USAGE == antes                          # contadores dos outros IPs intactos
    assert len(main.GPT_USAGE) == 3


def test_sessao_descartada_no_meio_nao_derruba(monkeypatch):
    import main
    assert main.reserve_gpt_call("sessao-que-nao-existe", "1.1.1.1") is False


def test_purge_com_last_seen_vazio_nao_quebra(monkeypatch):
    import main
    monkeypatch.setattr(main, "MAX_SESSIONS", 1)
    sid = c.post("/api/new").json()["sid"]
    main.LAST_SEEN.clear()
    main.purge_sessions()
    assert len(main.SESSIONS) < 1 or sid not in main.SESSIONS


def test_limite_de_partidas_novas_por_ip(monkeypatch):
    import main
    main.NEW_GAMES.clear()
    monkeypatch.setattr(main, "MAX_NEW_GAMES_PER_IP_HOUR", 2)
    assert c.post("/api/new").status_code == 200
    assert c.post("/api/new").status_code == 200
    assert c.post("/api/new").status_code == 429
    main.NEW_GAMES.clear()
