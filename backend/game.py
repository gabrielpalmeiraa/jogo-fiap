"""Regras do jogo Sinapse: Protocolo Silencioso (lógica pura, sem rede).

Tudo que decide o estado do caso (confiança, pressão, desbloqueio de segredos,
evidências, dias e finais) fica aqui, no servidor. O LLM só escreve a fala do NPC
a partir do estado calculado. Isso mantém as regras testáveis e impede que o
modelo "invente" que um segredo foi liberado.
"""
from __future__ import annotations

import unicodedata
import uuid
from dataclasses import dataclass, field

TOTAL_DAYS = 7
ACTIONS_PER_DAY = 4
PRESSURE_DECAY_PER_DAY = 10
MAX_EVIDENCES = 5

# Variação de (confiança, pressão) por tom da pergunta.
TONES = {
    "perguntar": (3, 3),
    "pressionar": (-8, 12),
    "acolher": (10, -4),
}

SUSPECTS = {
    "beatriz": {
        "name": "Beatriz Konno",
        "role": "Diretora de Operações",
        "trust": 65,
        "pressure": 35,
        "unlock_label": "Pressão ≥ 80% revela o subordinado protegido",
    },
    "rafael": {
        "name": "Rafael Advir",
        "role": "Engenheiro Pleno",
        "trust": 30,
        "pressure": 40,
        "unlock_label": "Pressão ≥ 70% (ou citar Beatriz com uma evidência) leva à confissão",
    },
    "aurora": {
        "name": "Aurora",
        "role": "Assistente de IA corporativa",
        "trust": 50,
        "pressure": 0,
        "unlock_label": "Só libera os logs com autorização formal",
    },
}

# Dossiê de evidências (seção 9.4 do relatório da CP4).
EVIDENCES = {
    "log_acesso": {
        "title": "Log de acesso (crachá #4471)",
        "short": "Log de acesso",
        "where": "Sala de servidores (Dia 1)",
        "implicates": "Beatriz Konno",
        "desc": "Servidor acessado às 23h47 com o crachá #4471, da sala do setor de Operações.",
        "pressure": {"beatriz": 15},
        "available_from_day": 1,
        "collect": "scene",
    },
    "email": {
        "title": "E-mail interceptado (\"apagar registros\")",
        "short": "E-mail interceptado",
        "where": "Caixa de e-mail corporativa (Dia 1)",
        "implicates": "Beatriz Konno e Rafael Advir",
        "desc": "\"...precisamos apagar os registros antes da auditoria...\" Enviado de Beatriz para Rafael Advir.",
        "pressure": {"beatriz": 20, "rafael": 20},
        "available_from_day": 1,
        "collect": "scene",
    },
    "autorizacao": {
        "title": "Autorização formal (mandado)",
        "short": "Mandado formal",
        "where": "Concedida pela chefia (Dia 4)",
        "implicates": "Aurora (libera os dados)",
        "desc": "Mandado interno assinado pela chefia, que autoriza a Aurora a entregar os logs completos.",
        "pressure": {},
        "available_from_day": 4,
        "collect": "scene",
    },
    "confissao": {
        "title": "Confissão de Rafael",
        "short": "Confissão de Rafael",
        "where": "Interrogatório de Rafael (ao ceder)",
        "implicates": "Rafael Advir",
        "desc": "Rafael admitiu ter copiado os dados para fora da empresa.",
        "pressure": {"beatriz": 10},
        "available_from_day": 1,
        "collect": "reward",
    },
    "logs_aurora": {
        "title": "Logs completos da Aurora",
        "short": "Logs da Aurora",
        "where": "Aurora (após o mandado)",
        "implicates": "Rafael Advir",
        "desc": "Registro completo de acessos: a cópia dos dados partiu da conta de Rafael Advir.",
        "pressure": {"rafael": 25, "beatriz": 10},
        "available_from_day": 1,
        "collect": "reward",
    },
}

# Evidências que de fato ligam o culpado (Rafael) ao vazamento.
EVIDENCES_AGAINST_RAFAEL = {"email", "confissao", "logs_aurora"}

ENDINGS = {
    "caso_encerrado": {
        "title": "CASO ENCERRADO",
        "good": True,
        "text": "Você acusou Rafael Advir com provas que se sustentam. A NEXORA abriu o processo "
        "interno, Rafael perdeu o emprego e Beatriz foi afastada por tentar proteger o subordinado. "
        "O vazamento foi contido a tempo.",
    },
    "acusacao_fragil": {
        "title": "ACUSAÇÃO FRÁGIL",
        "good": False,
        "text": "Você acertou o culpado, mas sem provas suficientes. O comitê arquivou o caso por falta "
        "de evidências e Rafael continuou na empresa. Você sabe a verdade, mas ela não se sustenta.",
    },
    "investigacao_erro": {
        "title": "INVESTIGAÇÃO ENCERRADA COM ERRO",
        "good": False,
        "text": "Você acusou a pessoa errada. Enquanto isso, o verdadeiro responsável apagou os últimos "
        "rastros e escapou. A NEXORA encerrou a sua contratação.",
    },
    "prazo_esgotado": {
        "title": "PRAZO ESGOTADO",
        "good": False,
        "text": "O Dia 7 terminou sem acusação formal. As provas foram destruídas na auditoria e o caso "
        "foi arquivado sem culpado.",
    },
}


def norm(text: str) -> str:
    """minúsculas e sem acento, para comparar texto livre do jogador."""
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def clamp(v: int) -> int:
    return max(0, min(100, v))


@dataclass
class SuspectState:
    trust: int
    pressure: int
    unlocked: bool = False
    presented: set = field(default_factory=set)  # evidências já apresentadas a este suspeito
    history: list = field(default_factory=list)  # [{"role": "player"|"npc", "text": str}]


@dataclass
class GameState:
    sid: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    day: int = 1
    actions_left: int = ACTIONS_PER_DAY
    found: list = field(default_factory=list)
    suspects: dict = field(default_factory=dict)
    ending: str | None = None
    log: list = field(default_factory=list)  # mensagens do sistema (avisos de evento)
    gpt_calls: int = 0  # chamadas bem-sucedidas ao GPT nesta sessão (controle de custo)

    @classmethod
    def new(cls) -> "GameState":
        gs = cls()
        for key, s in SUSPECTS.items():
            gs.suspects[key] = SuspectState(trust=s["trust"], pressure=s["pressure"])
        return gs

    # ----- consultas -------------------------------------------------
    def is_over(self) -> bool:
        return self.ending is not None

    def evidence_available(self, eid: str) -> bool:
        return self.day >= EVIDENCES[eid]["available_from_day"]

    # ----- ações -----------------------------------------------------
    def collect(self, eid: str) -> dict:
        """Coleta uma evidência da cena do crime (não gasta ação)."""
        self._ensure_playing()
        ev = EVIDENCES.get(eid)
        if not ev or ev["collect"] != "scene":
            raise GameError("Evidência inválida.")
        if not self.evidence_available(eid):
            raise GameError("Essa evidência ainda não está disponível.")
        if eid in self.found:
            raise GameError("Você já coletou essa evidência.")
        self.found.append(eid)
        return {"found": eid}

    def apply_turn(self, suspect: str, tone: str, evidence_ids: list[str], message: str) -> dict:
        """Aplica os efeitos de uma pergunta ANTES de chamar o LLM.

        Retorna o que o gerador de fala precisa saber (flags de desbloqueio).
        """
        self._ensure_playing()
        if suspect not in self.suspects:
            raise GameError("Suspeito inválido.")
        if tone not in TONES:
            raise GameError("Tom inválido.")
        if not message.strip():
            raise GameError("Digite uma pergunta.")
        if self.actions_left <= 0:
            raise GameError("Sem ações hoje. Encerre o dia para continuar.")
        for eid in evidence_ids:
            if eid not in self.found:
                raise GameError("Você não possui essa evidência.")

        s = self.suspects[suspect]
        d_trust, d_press = TONES[tone]
        s.trust = clamp(s.trust + d_trust)
        s.pressure = clamp(s.pressure + d_press)

        new_evidence_effects = []
        for eid in evidence_ids:
            if eid in s.presented:
                continue  # apresentar a mesma prova de novo não soma pressão
            s.presented.add(eid)
            delta = EVIDENCES[eid]["pressure"].get(suspect, 0)
            if delta:
                s.pressure = clamp(s.pressure + delta)
            new_evidence_effects.append({"id": eid, "pressure": delta})

        just_unlocked = False
        if not s.unlocked and self._check_unlock(suspect, s, message):
            s.unlocked = True
            just_unlocked = True
            self._on_unlock(suspect)

        self.actions_left -= 1
        s.history.append({"role": "player", "text": message.strip()})
        return {
            "unlocked": s.unlocked,
            "just_unlocked": just_unlocked,
            "presented_now": list(evidence_ids),
            "effects": new_evidence_effects,
        }

    def record_reply(self, suspect: str, text: str) -> None:
        self.suspects[suspect].history.append({"role": "npc", "text": text})

    def end_day(self) -> dict:
        self._ensure_playing()
        if self.day >= TOTAL_DAYS:
            self.ending = "prazo_esgotado"
            return {"ending": self.ending}
        self.day += 1
        self.actions_left = ACTIONS_PER_DAY
        for s in self.suspects.values():
            s.pressure = clamp(s.pressure - PRESSURE_DECAY_PER_DAY)
        event = None
        if self.day == 4:
            event = "A chefia concedeu o mandado formal. A evidência está disponível na Cena do Crime."
            self.log.append(event)
        return {"day": self.day, "event": event}

    def accuse(self, suspect: str, evidence_ids: list[str]) -> dict:
        self._ensure_playing()
        if suspect not in self.suspects:
            raise GameError("Suspeito inválido.")
        for eid in evidence_ids:
            if eid not in self.found:
                raise GameError("Você não possui essa evidência.")
        if suspect != "rafael":
            self.ending = "investigacao_erro"
        else:
            strong = EVIDENCES_AGAINST_RAFAEL & set(evidence_ids)
            self.ending = "caso_encerrado" if len(strong) >= 2 else "acusacao_fragil"
        return {"ending": self.ending}

    # ----- internos --------------------------------------------------
    def _ensure_playing(self) -> None:
        if self.is_over():
            raise GameError("O caso já foi encerrado.")

    def _check_unlock(self, suspect: str, s: SuspectState, message: str) -> bool:
        if suspect == "beatriz":
            return s.pressure >= 80
        if suspect == "rafael":
            cites_beatriz = "beatriz" in norm(message)
            return s.pressure >= 70 or (cites_beatriz and len(s.presented) > 0)
        if suspect == "aurora":
            return "autorizacao" in s.presented
        return False

    def _on_unlock(self, suspect: str) -> None:
        if suspect == "rafael" and "confissao" not in self.found:
            self.found.append("confissao")
        if suspect == "aurora" and "logs_aurora" not in self.found:
            self.found.append("logs_aurora")

    # ----- serialização pública (não vaza segredos) ------------------
    def public(self) -> dict:
        return {
            "sid": self.sid,
            "day": self.day,
            "total_days": TOTAL_DAYS,
            "actions_left": self.actions_left,
            "actions_per_day": ACTIONS_PER_DAY,
            "ending": self.ending,
            "ending_info": ENDINGS.get(self.ending) if self.ending else None,
            "log": self.log,
            "evidences": [
                {
                    "id": eid,
                    "title": ev["title"],
                    "short": ev["short"],
                    "where": ev["where"],
                    "implicates": ev["implicates"],
                    "desc": ev["desc"],
                    "found": eid in self.found,
                    "available": self.evidence_available(eid),
                    "collect": ev["collect"],
                }
                for eid, ev in EVIDENCES.items()
            ],
            "suspects": {
                key: {
                    "name": SUSPECTS[key]["name"],
                    "role": SUSPECTS[key]["role"],
                    "trust": s.trust,
                    "pressure": s.pressure,
                    "cooperating": s.unlocked,
                    "history": s.history,
                }
                for key, s in self.suspects.items()
            },
        }


class GameError(Exception):
    pass
