# Sinapse: Protocolo Silencioso, CP5 Front-end (Gabriel Palmeira RM 563522 e Mayara Mota RM 563887)

Repositório (back-end e jogo): https://github.com/gabrielpalmeiraa/jogo-fiap
Versão publicada: https://jogo-fiap.onrender.com (Swagger em `/docs`)
Vídeo: https://www.youtube.com/watch?v=MQ5MEFfc5eQ

## 1. O que mudou
Antes, o servidor do jogo chamava a OpenAI direto em `backend/llm.py`. Agora a modalidade de IA generativa (texto, as falas dos suspeitos) fica atrás de uma API do grupo:

```
Navegador -> /api/interrogate (regras: game.py) -> llm.py monta o prompt
          -> ia_client.py: requests.post(.../v1/ia-generativa/texto, X-API-Key)
          -> routers/ia_generativa.py (valida entrada, exige API Key)
          -> providers/ia_provider.py -> OpenAI
```

| Arquivo | Papel |
|---|---|
| `backend/routers/ia_generativa.py` | Router `/v1/ia-generativa`: `POST /texto` e `GET /status`. Valida o corpo com Pydantic e traduz erros do provider em 503 (sem chave da OpenAI) ou 502 (erro do serviço). |
| `backend/providers/ia_provider.py` | Único ponto que fala com a OpenAI. Trocar de modelo ou fornecedor mexe só aqui. |
| `backend/security.py` | Dependência `require_api_key` (header `X-API-Key`), aplicada ao router inteiro. |
| `backend/ia_client.py` | Cliente do jogo, com `requests`. Manda a chave no header e trata falhas. |
| `backend/main.py` | Registra o router, o CORS e o Swagger (`/docs`). |

O prompt (persona, segredo, medidores) e o filtro de saída continuam no jogo, porque dependem do estado da partida. A API recebe só as mensagens e devolve o texto.

## 2. Requisitos
| Requisito | Como foi atendido |
|---|---|
| FastAPI com router e provider | `routers/ia_generativa.py` e `providers/ia_provider.py` |
| Autenticação | API Key no header `X-API-Key`, comparada com `secrets.compare_digest`. Sem header: 401. Chave errada: 403. Servidor sem `IA_API_KEY`: 503 (falha fechada). |
| Jogo consome a API | `ia_client.py` faz `POST /v1/ia-generativa/texto`. A resposta do jogo traz `via: "/v1/ia-generativa/texto"` e a tela mostra "via API do jogo". |
| Swagger | `/docs` (com botão Authorize para a API Key) e `/openapi.json` |
| CORS | `CORSMiddleware` com origens de `CORS_ORIGINS` (padrão só localhost), métodos GET/POST e headers `Content-Type` e `X-API-Key` |
| Repositório | https://github.com/gabrielpalmeiraa/jogo-fiap |
| Vídeo | ver topo |

A chave fica só no servidor: o navegador nunca vê a `IA_API_KEY`. Quem manda o header é o servidor do jogo.

## 3. Evidência de que o jogo usa a API (log real, 09/10/2026)
Chamadas com `curl` e depois uma pergunta feita pelo jogo (`/api/interrogate`), no log do uvicorn:

```
POST /v1/ia-generativa/texto  sem X-API-Key    -> 401 Unauthorized  {"detail":"Envie a chave no header X-API-Key."}
POST /v1/ia-generativa/texto  X-API-Key errada -> 403 Forbidden     {"detail":"API Key inválida."}
POST /v1/ia-generativa/texto  X-API-Key certa  -> 200 OK            {"text":"Na noite do vazamento, eu estava em uma reunião ...","model":"gpt-4o-mini"}
INFO: 127.0.0.1 - "POST /v1/ia-generativa/texto HTTP/1.1" 200 OK        <- chamada feita pelo jogo
INFO: jogo -> POST http://127.0.0.1:8000/v1/ia-generativa/texto -> 200
```

Resposta do jogo à pergunta da partida: `{'source': 'gpt', 'note': 'gpt-4o-mini', 'api_called': True, 'via': '/v1/ia-generativa/texto'}`.

Código do consumo (`backend/ia_client.py`):

```python
r = requests.post(url, json={"messages": messages, "temperature": temperature, "max_tokens": max_tokens},
                  headers={"X-API-Key": key}, timeout=25)
```

## 4. Testes
`python -m pytest -q`: 53 testes, 15 deles novos em `tests/test_ia_api.py`: 401/403/503, rota chamando o provider, 502 do serviço externo, 5 entradas inválidas (422), Swagger e esquema de segurança no OpenAPI, CORS (origem permitida e origem bloqueada), o jogo chamando a API de ponta a ponta o fallback quando a API de IA está fora do ar e o limite de chamadas simultâneas (evita travar o servidor esperando a própria API).

## 5. Diário de Mudanças (continua valendo o da CP5 de PLN, com este acréscimo)
| Item alterado | O que estava antes | O que foi implementado | Justificativa técnica |
|---|---|---|---|
| Chamada à IA generativa | `llm.py` chamava a OpenAI direto | `llm.py` chama `POST /v1/ia-generativa/texto` e só o provider chama a OpenAI | Exigência do checkpoint de Front-end. A chave da OpenAI fica isolada no provider e a rota fica protegida por API Key. O comportamento do jogo não mudou: prompt, filtro e fallback são os mesmos. Impacto: cada fala passa por uma requisição HTTP a mais (a API roda no mesmo processo, então o custo é pequeno). |
| Nova variável `IA_API_KEY` | Não existia | Obrigatória; no Render é gerada por `generateValue` no `render.yaml` | Sem ela a rota responde 503 (falha fechada) e o jogo cai nas falas pré-escritas, avisando na tela. |
| Dependência `requests` | Não usada | Adicionada em `requirements.txt` | É a biblioteca de consumo pedida no enunciado. |

Limites de custo por sessão, por IP e global continuam no jogo (`main.py`). A rota `/v1/ia-generativa/texto` não tem esses limites: quem tem a chave tem acesso livre, e por isso a chave não vai para o navegador.
