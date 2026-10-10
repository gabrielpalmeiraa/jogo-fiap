"""Testes da API de IA generativa (rota -> provider), da autenticação e do consumo pelo jogo."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.pop("OPENAI_API_KEY", None)
os.environ["IA_API_KEY"] = "chave-de-teste"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import ia_client  # noqa: E402
from main import app  # noqa: E402
from providers import ia_provider  # noqa: E402

c = TestClient(app)
URL = "/v1/ia-generativa/texto"
BODY = {"messages": [{"role": "system", "content": "Você é Beatriz."}, {"role": "user", "content": "Oi?"}]}
AUTH = {"X-API-Key": "chave-de-teste"}


@pytest.fixture(autouse=True)
def chave(monkeypatch):
    monkeypatch.setenv("IA_API_KEY", "chave-de-teste")


def test_sem_chave_401_e_chave_errada_403():
    assert c.post(URL, json=BODY).status_code == 401
    assert c.post(URL, json=BODY, headers={"X-API-Key": "errada"}).status_code == 403
    assert c.get("/v1/ia-generativa/status").status_code == 401


def test_servidor_sem_ia_api_key_falha_fechado(monkeypatch):
    monkeypatch.delenv("IA_API_KEY")
    assert c.post(URL, json=BODY, headers=AUTH).status_code == 503


def test_rota_chama_o_provider(monkeypatch):
    seen = {}

    def fake(messages, temperature, max_tokens):
        seen.update(messages=messages, t=temperature, m=max_tokens)
        return {"text": "Resposta gerada.", "model": "fake-1"}

    monkeypatch.setattr(ia_provider, "generate_text", fake)
    r = c.post(URL, json={**BODY, "temperature": 0.2, "max_tokens": 50}, headers=AUTH)
    assert r.status_code == 200 and r.json() == {"text": "Resposta gerada.", "model": "fake-1"}
    assert seen["messages"][1] == {"role": "user", "content": "Oi?"} and seen["t"] == 0.2 and seen["m"] == 50


def test_provider_sem_chave_openai_vira_503(monkeypatch):
    r = c.post(URL, json=BODY, headers=AUTH)
    assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["detail"]


def test_erro_do_servico_externo_vira_502(monkeypatch):
    def boom(*a, **kw):
        raise ia_provider.ProviderError("RateLimitError")

    monkeypatch.setattr(ia_provider, "generate_text", boom)
    r = c.post(URL, json=BODY, headers=AUTH)
    assert r.status_code == 502 and "RateLimitError" in r.json()["detail"]


@pytest.mark.parametrize("body", [
    {"messages": []},
    {"messages": [{"role": "hacker", "content": "x"}]},
    {"messages": [{"role": "user", "content": "x" * 4001}]},
    {**BODY, "max_tokens": 5000},
    {**BODY, "temperature": 9},
])
def test_entrada_invalida_422(body):
    assert c.post(URL, json=body, headers=AUTH).status_code == 422


def test_swagger_e_openapi_expoem_a_rota_com_api_key():
    assert c.get("/docs").status_code == 200
    spec = c.get("/openapi.json").json()
    assert URL in spec["paths"]
    assert "APIKeyHeader" in spec["components"]["securitySchemes"]


def test_cors_preflight_libera_so_origem_configurada():
    h = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-api-key,content-type"}
    ok = c.options(URL, headers={**h, "Origin": "http://localhost:8000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:8000"
    ruim = c.options(URL, headers={**h, "Origin": "http://site-malicioso.com"})
    assert "access-control-allow-origin" not in ruim.headers


def test_jogo_consome_a_api_do_grupo_de_ponta_a_ponta(monkeypatch):
    """Interrogatório -> ia_client (requests) -> POST /v1/ia-generativa/texto com X-API-Key -> provider."""
    chamadas = []

    def requests_post(url, json, headers, timeout):
        chamadas.append((url, headers))
        r = c.post(url.replace("http://testserver", ""), json=json, headers=headers)
        r.status_code  # TestClient devolve um objeto compatível com requests.Response
        return r

    monkeypatch.setattr(ia_client.requests, "post", requests_post)
    monkeypatch.setenv("IA_API_URL", "http://testserver")
    monkeypatch.setattr(ia_provider, "generate_text", lambda m, t, n: {"text": "Não tenho nada a declarar.", "model": "fake-1"})
    sid = c.post("/api/new").json()["sid"]
    r = c.post("/api/interrogate", json={"sid": sid, "suspect": "beatriz", "message": "Onde você estava?"}).json()
    assert r["reply"]["source"] == "gpt" and r["reply"]["via"] == URL
    assert chamadas and chamadas[0][0].endswith(URL) and chamadas[0][1]["X-API-Key"] == "chave-de-teste"


def test_jogo_cai_no_fallback_se_a_api_de_ia_estiver_fora(monkeypatch):
    monkeypatch.setenv("IA_API_URL", "http://127.0.0.1:1")  # porta fechada
    sid = c.post("/api/new").json()["sid"]
    r = c.post("/api/interrogate", json={"sid": sid, "suspect": "aurora", "message": "Oi"}).json()
    assert r["reply"]["source"] == "fallback" and "indisponível" in r["reply"]["note"]
    assert r["state"]["suspects"]["aurora"]  # a partida continua
