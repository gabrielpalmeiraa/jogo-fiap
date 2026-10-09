"""Testes automatizados das mecânicas centrais (sem rede, LLM desligado ou simulado)."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.pop("OPENAI_API_KEY", None)

import llm  # noqa: E402
from game import ACTIONS_PER_DAY, GameError, GameState  # noqa: E402


def turn(gs, suspect, msg="pergunta", tone="perguntar", ev=None):
    return gs.apply_turn(suspect, tone, ev or [], msg)


def test_estado_inicial_bate_com_cp4():
    gs = GameState.new()
    assert gs.day == 1 and gs.actions_left == ACTIONS_PER_DAY
    assert (gs.suspects["beatriz"].trust, gs.suspects["beatriz"].pressure) == (65, 35)


def test_medidores_mudam_conforme_o_tom():
    gs = GameState.new()
    turn(gs, "beatriz", tone="pressionar")
    assert gs.suspects["beatriz"].pressure == 47 and gs.suspects["beatriz"].trust == 57
    turn(gs, "beatriz", tone="acolher")
    assert gs.suspects["beatriz"].pressure == 43 and gs.suspects["beatriz"].trust == 67


def test_medidores_ficam_entre_0_e_100():
    gs = GameState.new()
    gs.actions_left = 99
    for _ in range(20):
        turn(gs, "beatriz", tone="pressionar")
    assert gs.suspects["beatriz"].pressure == 100 and gs.suspects["beatriz"].trust == 0


def test_coleta_de_evidencias_e_bloqueio_do_mandado():
    gs = GameState.new()
    gs.collect("log_acesso")
    gs.collect("email")
    with pytest.raises(GameError):
        gs.collect("log_acesso")  # repetida
    with pytest.raises(GameError):
        gs.collect("autorizacao")  # só a partir do Dia 4
    for _ in range(3):
        gs.end_day()
    assert gs.day == 4
    gs.collect("autorizacao")
    assert "autorizacao" in gs.found


def test_nao_pode_apresentar_evidencia_que_nao_tem():
    gs = GameState.new()
    with pytest.raises(GameError):
        turn(gs, "beatriz", ev=["email"])


def test_evidencia_soma_pressao_uma_unica_vez_por_suspeito():
    gs = GameState.new()
    gs.collect("log_acesso")
    turn(gs, "beatriz", ev=["log_acesso"])
    assert gs.suspects["beatriz"].pressure == 35 + 3 + 15
    turn(gs, "beatriz", ev=["log_acesso"])
    assert gs.suspects["beatriz"].pressure == 35 + 3 + 15 + 3  # só o tom


def test_beatriz_revela_rafael_com_pressao_80():
    gs = GameState.new()
    gs.collect("log_acesso")
    gs.collect("email")
    t = turn(gs, "beatriz", tone="pressionar", ev=["log_acesso", "email"])
    assert gs.suspects["beatriz"].pressure == 35 + 12 + 15 + 20 == 82
    assert t["just_unlocked"] and gs.suspects["beatriz"].unlocked


def test_rafael_confessa_citando_beatriz_com_evidencia():
    gs = GameState.new()
    gs.collect("email")
    t = turn(gs, "rafael", msg="A Beatriz mandou isso, certo?", ev=["email"])
    assert t["just_unlocked"]
    assert "confissao" in gs.found  # confissão vira evidência


def test_rafael_nao_confessa_so_citando_beatriz_sem_prova():
    gs = GameState.new()
    t = turn(gs, "rafael", msg="Conte sobre a Beatriz")
    assert not t["just_unlocked"]


def test_rafael_confessa_por_pressao_70():
    gs = GameState.new()
    gs.suspects["rafael"].pressure = 60
    t = turn(gs, "rafael", tone="pressionar")  # 60 + 12 = 72
    assert t["just_unlocked"]


def test_aurora_depende_do_mandado_e_nao_da_pressao():
    gs = GameState.new()
    for _ in range(3):
        turn(gs, "aurora", tone="pressionar")
    assert not gs.suspects["aurora"].unlocked
    for _ in range(3):
        gs.end_day()
    gs.collect("autorizacao")
    t = turn(gs, "aurora", ev=["autorizacao"])
    assert t["just_unlocked"] and "logs_aurora" in gs.found


def test_acoes_por_dia_acabam_e_dia_renova_e_pressao_cai():
    gs = GameState.new()
    for _ in range(ACTIONS_PER_DAY):
        turn(gs, "beatriz", tone="pressionar")
    with pytest.raises(GameError):
        turn(gs, "beatriz")
    before = gs.suspects["beatriz"].pressure
    gs.end_day()
    assert gs.day == 2 and gs.actions_left == ACTIONS_PER_DAY
    assert gs.suspects["beatriz"].pressure == before - 10


def test_prazo_esgotado_no_dia_7():
    gs = GameState.new()
    for _ in range(6):
        gs.end_day()
    assert gs.day == 7
    gs.end_day()
    assert gs.ending == "prazo_esgotado"
    with pytest.raises(GameError):
        gs.end_day()


def _com_provas(*ids):
    gs = GameState.new()
    gs.found = list(ids)
    return gs


def test_final_correto_e_fundamentado():
    gs = _com_provas("email", "confissao")
    gs.accuse("rafael", ["email", "confissao"])
    assert gs.ending == "caso_encerrado"


def test_final_acusacao_fragil_por_falta_de_provas():
    gs = _com_provas("email", "log_acesso")
    gs.accuse("rafael", ["email", "log_acesso"])  # o log aponta Beatriz, só 1 prova forte
    assert gs.ending == "acusacao_fragil"


@pytest.mark.parametrize("suspeito", ["beatriz", "aurora"])
def test_final_incorreto(suspeito):
    gs = _com_provas("email", "confissao")
    gs.accuse(suspeito, ["email", "confissao"])
    assert gs.ending == "investigacao_erro"


# ----- integração com o LLM (sem rede) -------------------------------------
def test_sem_chave_usa_fallback_e_avisa():
    gs = GameState.new()
    t = turn(gs, "beatriz")
    r = llm.generate_reply(gs, "beatriz", t, "pergunta")
    assert r["source"] == "fallback" and r["text"]


def test_prompt_traz_estado_e_persona():
    gs = GameState.new()
    gs.collect("email")
    t = turn(gs, "beatriz", ev=["email"])
    p = llm.build_system_prompt(gs, "beatriz", t["unlocked"], t["presented_now"])
    assert "Beatriz Konno" in p and "Dia 1 de 7" in p and "E-mail interceptado" in p
    assert "NÃO revele o nome" in p  # ainda bloqueada


def test_prompt_muda_quando_desbloqueia():
    gs = GameState.new()
    gs.suspects["beatriz"].pressure = 90
    t = turn(gs, "beatriz")
    p = llm.build_system_prompt(gs, "beatriz", t["unlocked"], [])
    assert "CEDE" in p


def test_filtro_barra_spoiler_antes_do_limiar():
    _, blocked = llm.filter_output("Foi o Rafael, ele que fez tudo.", "beatriz", False, "quem foi?")
    assert blocked
    _, ok = llm.filter_output("Foi o Rafael, ele que fez tudo.", "beatriz", True, "quem foi?")
    assert not ok


def test_filtro_barra_fuga_de_personagem():
    _, blocked = llm.filter_output("Como modelo de linguagem, não posso.", "rafael", False, "x")
    assert blocked


def test_chamada_gpt_simulada(monkeypatch):
    """Simula a resposta da API para provar o fluxo prompt -> resposta -> filtro."""
    seen = {}

    class FakeResp:
        class _C:
            class _M:
                content = "Não tenho nada a declarar sobre isso."

            message = _M()

        choices = [_C()]

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    seen.update(kw)
                    return FakeResp()

    monkeypatch.setattr(llm, "_client", lambda: FakeClient())
    gs = GameState.new()
    t = turn(gs, "beatriz")
    r = llm.generate_reply(gs, "beatriz", t, "pergunta")
    assert r["source"] == "gpt" and r["text"].startswith("Não tenho")
    assert seen["messages"][0]["role"] == "system" and seen["temperature"] == llm.TEMPERATURE


def test_erro_da_api_cai_no_fallback(monkeypatch):
    class Boom:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    raise TimeoutError("rede fora")

    monkeypatch.setattr(llm, "_client", lambda: Boom())
    gs = GameState.new()
    t = turn(gs, "beatriz")
    r = llm.generate_reply(gs, "beatriz", t, "pergunta")
    assert r["source"] == "fallback" and "TimeoutError" in r["note"]
