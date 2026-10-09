# Sinapse: Protocolo Silencioso (MVP, CP5)

Jogo de investigação narrativa em que os suspeitos são NPCs movidos por GPT. Continuação direta da CP4
(NLP, Chatbots e Agentes Virtuais, FIAP). Stack: Phaser.js no navegador, Python + FastAPI no servidor, API da OpenAI.

## Como executar

1. Python 3.10 ou mais novo.
2. `python -m venv .venv` e ativar (`source .venv/bin/activate`, no Windows `.venv\Scripts\activate`).
3. `pip install -r requirements.txt`
4. Copie `.env.example` para `.env` e preencha `OPENAI_API_KEY` (não suba o `.env` para o GitHub).
5. `python run.py` e abra http://127.0.0.1:8000

Sem chave o jogo roda em modo offline (falas pré-escritas) e avisa na tela.

## Como jogar

Cena do Crime: colete evidências (não gasta ação). Suspeitos: escolha com quem falar. Interrogatório: escreva a
pergunta, escolha o tom (Perguntar, Pressionar, Acolher) e, se quiser, apresente evidências. São 4 ações por dia, 7 dias.
Quando tiver provas, abra Estado do Caso e Montar acusação final.

## Estrutura

- `backend/game.py` regras do jogo (sem rede), `backend/llm.py` integração com o GPT e filtro de saída, `backend/main.py` API.
- `frontend/` Phaser (`js/main.js`), arte procedural de reserva (`js/art.js`) e imagens opcionais em `assets/`.
- `tests/` testes das regras (`python -m pytest -q`) e partida completa no navegador (`python tests/e2e_play.py`).
- `docs/prints/` capturas de tela da partida automatizada.

## Imagens geradas por IA (opcional)

Salve em `frontend/assets/`: `bg_menu.png`, `bg_room.png`, `portrait_beatriz.png`, `portrait_rafael.png`, `portrait_aurora.png`.
O jogo usa os arquivos que existirem e desenha arte procedural no lugar dos que faltarem.

## Publicar o jogo na web (ponto extra: build público)

O projeto já tem `Dockerfile` e `render.yaml`. No Render: New > Blueprint, aponte para o repositório do GitHub e
preencha `OPENAI_API_KEY` no painel (nunca no código). A URL pública abre direto no menu do jogo.
Variáveis opcionais: `MAX_GPT_CALLS_PER_SESSION` (padrão 40, depois disso o jogo usa falas pré-escritas),
`MAX_SESSIONS` (300), `SESSION_TTL_SECONDS` (7200), `MAX_GPT_CALLS_PER_IP_DAY` (120), `MAX_GPT_CALLS_GLOBAL_DAY` (1500) e `MAX_NEW_GAMES_PER_IP_HOUR` (20), e `TRUST_PROXY=1` (já definido no Dockerfile, para ler o IP real atrás do proxy do Render). Os tetos por IP e global impedem que abrir várias partidas burle o limite por sessão. Perguntas têm no máximo 300 caracteres.
No plano gratuito o servidor "dorme" e a primeira abertura pode levar cerca de 1 minuto.

## Extras implementados

Testes automatizados (`python -m pytest -q`, 36 testes) e partida completa no navegador (`tests/e2e_play.py`, precisa de
`pip install playwright && playwright install chromium`), fallback quando a API falha, filtro de saída, efeitos sonoros
(botão de som no canto) e limites de custo. Documentação da entrega em `docs/ENTREGA_CP5.md`; prompts de imagem em
`docs/prompts_imagens_nano_banana.md`.
