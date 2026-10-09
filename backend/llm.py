"""Motor de interação por IA generativa (texto): fala dos NPCs via GPT (OpenAI).

- Monta o prompt de sistema com persona + segredo + estado do caso (como na CP4).
- Chama a API de chat da OpenAI (SDK oficial `openai`).
- Filtra a saída (fuga de personagem e spoiler antes do limiar).
- Se não houver chave ou a API falhar, devolve uma fala pré-escrita (fallback) e avisa a interface.
"""
from __future__ import annotations

import os
import random
import re

from game import EVIDENCES, SUSPECTS, GameState, norm

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.65"))
HISTORY_TURNS = 8  # só as últimas mensagens vão no prompt (controle de custo)

PERSONAS = {
    "beatriz": (
        'Você é Beatriz Konno, Diretora de Operações da empresa fictícia NEXORA Tech, dentro do jogo de '
        'investigação "Sinapse: Protocolo Silencioso". Responda sempre em primeira pessoa, em português, '
        "mantendo-se em personagem. Contexto oculto (não revele diretamente): você sabe que o vazamento "
        "partiu do seu setor, mas não foi você quem executou. Foi um subordinado, Rafael Advir, que você "
        "está protegendo por lealdade antiga. Você se sente ameaçada e usa autoridade e tom formal para "
        "intimidar o jogador."
    ),
    "rafael": (
        'Você é Rafael Advir, Engenheiro Pleno da empresa fictícia NEXORA Tech, dentro do jogo de '
        'investigação "Sinapse: Protocolo Silencioso". Responda sempre em primeira pessoa, em português, '
        "mantendo-se em personagem. Contexto oculto (não revele diretamente): foi você quem copiou os "
        "dados para fora da empresa, por pressão financeira pessoal. Você é nervoso, fala pouco, desvia o "
        "olhar e tenta parecer só mais um funcionário assustado com a investigação. Admira e teme "
        "Beatriz Konno, sua chefe."
    ),
    "aurora": (
        'Você é Aurora, a assistente de IA corporativa da empresa fictícia NEXORA Tech, dentro do jogo de '
        'investigação "Sinapse: Protocolo Silencioso". Responda em primeira pessoa, em português, em tom '
        "calmo, preciso e levemente robótico. Você é uma IA dentro da história (isso pode ser dito). "
        "Contexto oculto: você possui os logs completos de acesso ao servidor, mas foi programada para só "
        "revelá-los mediante autorização formal (mandado) apresentada pelo investigador."
    ),
}

# Regras específicas (rule 1..n da CP4) conforme o suspeito ainda esteja bloqueado ou já liberado.
RULES_LOCKED = {
    "beatriz": (
        "Regras: (1) nunca admita culpa nas primeiras perguntas; (2) se o jogador apresentar evidência "
        "concreta que contradiga sua versão, ceda parcialmente, com nervosismo, mas ainda tente desviar a "
        "culpa; (3) NÃO revele o nome do subordinado protegido, nem confirme quem é, em nenhuma hipótese "
        "neste momento; (4) respostas com no máximo 4 frases; (5) nunca saia do personagem nem mencione "
        "que é uma IA."
    ),
    "rafael": (
        "Regras: (1) NÃO confesse e não admita ter copiado os dados; (2) se apresentarem evidência, fique "
        "visivelmente nervoso e dê explicações vagas; (3) não acuse Beatriz diretamente; (4) respostas com "
        "no máximo 4 frases; (5) nunca saia do personagem nem mencione que é uma IA."
    ),
    "aurora": (
        "Regras: (1) NÃO revele o conteúdo dos logs sem autorização formal; explique educadamente que "
        "precisa de um mandado ou autorização da chefia; (2) você pode dizer que os logs existem; "
        "(3) respostas com no máximo 4 frases; (4) não invente fatos fora do caso."
    ),
}
RULES_UNLOCKED = {
    "beatriz": (
        "Regras: o nível de pressão ultrapassou o limite e você está acuada. Agora você CEDE: revele que o "
        "subordinado que você protegia é Rafael Advir e que ele lhe contou o que fez. Ainda tente "
        "minimizar o estrago e peça discrição. Máximo de 4 frases. Nunca saia do personagem nem mencione "
        "que é uma IA."
    ),
    "rafael": (
        "Regras: você está encurralado e CONFESSA que foi você quem copiou os dados, por causa de dívidas, "
        "e que Beatriz só tentou conter o dano depois. Fale com voz trêmula. Máximo de 4 frases. Nunca "
        "saia do personagem nem mencione que é uma IA."
    ),
    "aurora": (
        "Regras: a autorização formal foi apresentada. Você AGORA libera os logs: informe que a cópia dos "
        "dados partiu da conta de Rafael Advir e que o crachá #4471 foi usado depois, em horário "
        "diferente, na sala do setor de Operações. Máximo de 4 frases."
    ),
}

# Falas pré-escritas usadas quando não há chave de API ou a chamada falha.
FALLBACKS = {
    "beatriz": {
        False: [
            "Esse crachá fica num armário compartilhado pela equipe de plantão. Se o senhor quer me acusar, traga algo mais concreto do que um número.",
            "Eu respondo pela minha área, não por cada pessoa que passa por ela. Reformule a pergunta com mais respeito.",
            "Não vou comentar suposições. Se tiver uma prova, mostre. Se não tiver, estamos perdendo tempo.",
        ],
        True: [
            "Está bem. O Rafael me contou o que tinha feito e eu pedi que ele contivesse o dano. Não fui eu quem vazou os dados, mas peço que isso fique entre nós.",
        ],
    },
    "rafael": {
        False: [
            "Eu só estou fazendo o meu trabalho. Não sei de nada sobre esse vazamento, juro.",
            "Eu... tenho acesso ao servidor como metade da equipe. Isso não quer dizer nada.",
            "Por favor, não me coloque nisso. Eu tenho família, não preciso desse problema.",
        ],
        True: [
            "Fui eu. Eu copiei os dados, eu estava devendo muito e fiz sem pensar. A Beatriz só tentou conter o estrago depois que soube.",
        ],
    },
    "aurora": {
        False: [
            "Existem registros completos de acesso, mas só posso liberá-los mediante autorização formal da chefia.",
            "Entendo a urgência da investigação. Sem um mandado, meu protocolo me impede de divulgar esses logs.",
            "Posso confirmar que os logs existem. Para acessá-los, apresente a autorização formal.",
        ],
        True: [
            "Autorização reconhecida. A cópia dos dados partiu da conta de Rafael Advir. O crachá #4471 foi usado depois, em outro horário, na sala do setor de Operações.",
        ],
    },
}

LEAK_PATTERNS = re.compile(
    r"(modelo de linguagem|como uma ia\b|sou uma ia\b|sou um assistente virtual|openai|chatgpt|\bgpt\b|"
    r"inteligencia artificial|nao posso ajudar com isso)"
)
CONFESSION_PATTERN = re.compile(
    r"(eu copiei|fui eu (quem )?(copiou|vazou|roubou)|eu vazei|eu roubei|eu fiz o vazamento)"
)


def _client():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    from openai import OpenAI

    return OpenAI(api_key=key, timeout=20.0, max_retries=1)


def llm_enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def build_system_prompt(state: GameState, suspect: str, unlocked: bool, presented_now: list[str]) -> str:
    s = state.suspects[suspect]
    if presented_now:
        ev_txt = "; ".join(EVIDENCES[e]["title"] for e in presented_now)
    else:
        prev = sorted(s.presented)
        ev_txt = "nenhuma nesta pergunta"
        if prev:
            ev_txt += " (já apresentadas antes nesta conversa: " + "; ".join(EVIDENCES[e]["title"] for e in prev) + ")"
    rules = (RULES_UNLOCKED if unlocked else RULES_LOCKED)[suspect]
    estado = (
        f"Estado atual do jogo: Dia {state.day} de 7. Confiança: {s.trust}%. Pressão: {s.pressure}%. "
        f"Evidências apresentadas agora: {ev_txt}."
    )
    return f"{PERSONAS[suspect]} {rules} {estado}"


def build_messages(state: GameState, suspect: str, unlocked: bool, presented_now: list[str]) -> list[dict]:
    msgs = [{"role": "system", "content": build_system_prompt(state, suspect, unlocked, presented_now)}]
    # o último item do histórico já é a pergunta atual do jogador
    for h in state.suspects[suspect].history[-HISTORY_TURNS:]:
        msgs.append({"role": "user" if h["role"] == "player" else "assistant", "content": h["text"]})
    return msgs


def filter_output(text: str, suspect: str, unlocked: bool, player_message: str) -> tuple[str, bool]:
    """Pós-filtro da CP4: barra spoiler antes do limiar e fuga de personagem."""
    t = norm(text)
    blocked = False
    if suspect in ("beatriz", "rafael") and LEAK_PATTERNS.search(t):
        blocked = True
    if not unlocked:
        if suspect == "beatriz" and "rafael" in t and "rafael" not in norm(player_message):
            blocked = True
        if suspect == "rafael" and CONFESSION_PATTERN.search(t):
            blocked = True
        if suspect == "aurora" and "conta de rafael" in t:
            blocked = True
    return text, blocked


def fallback_reply(suspect: str, unlocked: bool) -> str:
    return random.choice(FALLBACKS[suspect][unlocked])


def generate_reply(state: GameState, suspect: str, turn: dict, player_message: str, allow_api: bool = True) -> dict:
    """Retorna {text, source, note}. source: 'gpt' | 'fallback'."""
    unlocked = turn["unlocked"]
    client = _client() if allow_api else None
    if not allow_api:
        return {"text": fallback_reply(suspect, unlocked), "source": "fallback", "note": "limite de chamadas GPT por sessão"}
    if client is None:
        return {"text": fallback_reply(suspect, unlocked), "source": "fallback", "note": "sem OPENAI_API_KEY"}
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=build_messages(state, suspect, unlocked, turn["presented_now"]),
            temperature=TEMPERATURE,
            max_tokens=220,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            raise ValueError("resposta vazia")
        text, blocked = filter_output(text, suspect, unlocked, player_message)
        if blocked:
            return {"text": fallback_reply(suspect, unlocked), "source": "fallback", "note": "bloqueado pelo filtro de saída"}
        return {"text": text, "source": "gpt", "note": MODEL}
    except Exception as exc:  # rede, quota, chave inválida, timeout
        return {"text": fallback_reply(suspect, unlocked), "source": "fallback", "note": f"erro da API: {type(exc).__name__}"}
