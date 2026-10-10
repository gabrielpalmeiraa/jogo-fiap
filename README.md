# Sinapse: Protocolo Silencioso (MVP, CP5)

Jogo de investigação narrativa em que os suspeitos são NPCs movidos por GPT. Continuação direta da CP4
(NLP, Chatbots e Agentes Virtuais, FIAP). Stack: Phaser.js no navegador, Python + FastAPI no servidor, API da OpenAI.

## Como executar

1. Python 3.10 ou mais novo.
2. `python -m venv .venv` e ativar (`source .venv/bin/activate`, no Windows `.venv\Scripts\activate`).
3. `pip install -r requirements.txt`
4. Copie `.env.example` para `.env` e preencha `OPENAI_API_KEY` e `IA_API_KEY` (não suba o `.env` para o GitHub). A `IA_API_KEY` é a chave que protege a API de IA do grupo; gere uma com `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
5. `python run.py` e abra http://127.0.0.1:8000

Sem chave o jogo roda em modo offline (falas pré-escritas) e avisa na tela.

## Como jogar

Cena do Crime: colete evidências (não gasta ação). Suspeitos: escolha com quem falar. Interrogatório: escreva a
pergunta, escolha o tom (Perguntar, Pressionar, Acolher) e, se quiser, apresente evidências. São 4 ações por dia, 7 dias.
Quando tiver provas, abra Estado do Caso e Montar acusação final.

## API de IA generativa (disciplina de Front-end)

O jogo não chama a OpenAI. Ele chama a API FastAPI do grupo, e só o provider fala com a OpenAI:

```
Navegador -> /api/interrogate (regras do jogo) -> ia_client (requests, X-API-Key)
          -> POST /v1/ia-generativa/texto (router) -> providers/ia_provider.py -> OpenAI
```

- Swagger: http://127.0.0.1:8000/docs (botão **Authorize** para colar a API Key).
- `POST /v1/ia-generativa/texto` gera a fala de um NPC; `GET /v1/ia-generativa/status` diz se o provider está configurado.
- Autenticação por header `X-API-Key` (valor de `IA_API_KEY`): sem header 401, chave errada 403, servidor sem chave configurada 503.
- CORS: `CORS_ORIGINS` (padrão: só `localhost:8000`).
- `IA_API_URL` (opcional) aponta o jogo para a API de IA rodando em outro serviço; o padrão é o próprio servidor.

```
curl -X POST http://127.0.0.1:8000/v1/ia-generativa/texto \
  -H "Content-Type: application/json" -H "X-API-Key: $IA_API_KEY" \
  -d '{"messages":[{"role":"system","content":"Você é Beatriz Konno. Máx. 2 frases."},{"role":"user","content":"Onde você estava?"}]}'
```

Evidências e explicação da arquitetura: `docs/ENTREGA_FRONTEND.md`.

## Estrutura

- `backend/game.py` regras do jogo (sem rede), `backend/llm.py` prompt, filtro de saída e fallback, `backend/main.py` API do jogo.
- `backend/routers/ia_generativa.py` rotas de IA, `backend/providers/ia_provider.py` chamada à OpenAI, `backend/security.py` API Key, `backend/ia_client.py` cliente usado pelo jogo.
- `frontend/` Phaser (`js/main.js`), arte procedural de reserva (`js/art.js`) e imagens opcionais em `assets/`.
- `tests/` testes das regras (`python -m pytest -q`) e partida completa no navegador (`python tests/e2e_play.py`).
- `docs/prints/` capturas de tela da partida automatizada.

## Imagens geradas por IA (opcional)

Salve em `frontend/assets/`: `bg_menu.png`, `bg_room.png`, `portrait_beatriz.png`, `portrait_rafael.png`, `portrait_aurora.png`.
O jogo usa os arquivos que existirem e desenha arte procedural no lugar dos que faltarem.

## Publicar o jogo na web (ponto extra: build público)

Versão publicada: https://jogo-fiap.onrender.com (a primeira abertura pode levar cerca de 1 minuto).

O projeto já tem `Dockerfile` e `render.yaml`. No Render: New > Blueprint, aponte para o repositório do GitHub e
preencha `OPENAI_API_KEY` no painel (nunca no código). A URL pública abre direto no menu do jogo.
Variáveis opcionais: `IA_API_KEY` (obrigatória; no Render o `render.yaml` gera uma), `MAX_GPT_CALLS_PER_SESSION` (padrão 40, depois disso o jogo usa falas pré-escritas),
`MAX_SESSIONS` (300), `SESSION_TTL_SECONDS` (7200), `MAX_GPT_CALLS_PER_IP_DAY` (120), `MAX_GPT_CALLS_GLOBAL_DAY` (1500) e `MAX_NEW_GAMES_PER_IP_HOUR` (20), e `TRUST_PROXY=1` (já definido no Dockerfile, para ler o IP real atrás do proxy do Render). Os tetos por IP e global impedem que abrir várias partidas burle o limite por sessão. Perguntas têm no máximo 300 caracteres.
No plano gratuito o servidor "dorme" e a primeira abertura pode levar cerca de 1 minuto.

## Extras implementados

Testes automatizados (`python -m pytest -q`, 52 testes) e partida completa no navegador (`tests/e2e_play.py`, precisa de
`pip install playwright && playwright install chromium`), fallback quando a API falha, filtro de saída, efeitos sonoros
(botão de som no canto) e limites de custo. Documentação da entrega em `docs/ENTREGA_CP5.md`; prompts de imagem em
`docs/prompts_imagens_nano_banana.md`.
