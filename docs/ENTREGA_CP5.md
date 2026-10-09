# Sinapse: Protocolo Silencioso, CP5 (Gabriel Palmeira RM 563522 e Mayara Mota RM 563887)

> Consolide este arquivo (mais o README) em um único PDF ou Word para a entrega. Complete os campos marcados com [PREENCHER].

## 1. README resumido
Veja `README.md`. Executar: `python -m venv .venv && source .venv/bin/activate`, `pip install -r requirements.txt`,
`cp .env.example .env` (colocar OPENAI_API_KEY), `python run.py`, abrir http://127.0.0.1:8000.
Versão pública (build web): [PREENCHER link do Render]. Vídeo: [PREENCHER link].

## 2. Continuidade com a CP4
Mesmo título, gênero, premissa, elenco, dossiê de evidências e finais da CP4. Mecânicas implementadas (CP4, seção 1.5): interrogatório
dinâmico por GPT, medidores de Confiança e Pressão injetados no prompt, coleta e cruzamento de evidências, contador de 7 dias
e dedução final. Telas: menu, interrogatório (HUD) e Quadro de Investigação.
Extras além do mínimo: 4 mecânicas da CP4, testes automatizados, fallback offline, filtro de saída, efeitos sonoros, limites
de custo, build público.

## 3. Diário de Mudanças CP4 x CP5
| Item alterado | O que estava na CP4 | O que foi implementado | Justificativa técnica |
|---|---|---|---|
| Persistência do estado | PostgreSQL ou SQLite (seção 4.2) | Dicionário em memória no FastAPI (`SESSIONS`), com limite de sessões e TTL | Partida curta e sem contas de usuário; um banco só traria migração e configuração sem benefício no MVP. Impacto: reiniciar o servidor apaga as partidas em andamento. |
| Medidores iniciais | Todos os suspeitos começando em 65/35 (seção 9.2) | Beatriz 65/35, Rafael 30/40, Aurora 50/0 | A CP4 usou 65/35 só como exemplo da Beatriz. Rafael precisa de confiança baixa e pressão média para a confissão fazer sentido; Aurora não depende de pressão. |
| Tons de pergunta | Pergunta livre ou menu de tópicos, sem tons | Perguntar, Pressionar e Acolher alteram confiança e pressão por valores fixos no servidor | A CP4 dizia que cada pergunta altera os medidores, mas sem regra. Tons discretos tornam isso determinístico e testável. |
| Ações por dia | Não definido | 4 ações por dia, pressão cai 10 por dia | Sem um custo por turno, os 7 dias não teriam peso e a pressão cruzaria o limiar sem escolha. |
| Dia 7 | Dia de montar a acusação | Final extra "Prazo Esgotado" se o Dia 7 acabar sem acusação | Todo jogo precisa de condição de derrota por tempo; a CP4 só tinha três finais. |
| Histórico no prompt | Resumir o histórico a cada turno (seção 2.1) | Envia só as últimas 8 mensagens do suspeito | Resumo exigiria uma 2ª chamada ao modelo por turno (mais custo e latência). A janela fixa resolve o limite de contexto no MVP. |
| Cache de perguntas repetidas | Cache planejado (seção 2.1) | Não implementado | Como o estado muda a cada turno, quase nenhuma pergunta se repete com o mesmo contexto, então o cache quase não acertaria. |
| Moderação de saída | Filtro de termos proibidos | Filtro por regex (fuga de personagem, spoiler antes do limiar) com fallback para fala pré-escrita | Cobre os dois riscos descritos na CP4 sem chamar uma API de moderação extra. |
| Evidência "mandado" | "Autorização/mandado formal" | Nome exibido: "Autorização formal (mandado)" | Apenas padronização do nome. Comportamento igual ao da CP4. |
| Tecnologia do cliente | Phaser com HUD | Phaser nas cenas e HUD em DOM/HTML sobre o canvas | Texto longo, campo de entrada e rolagem são muito mais simples em DOM do que em Phaser. |
| Arquitetura do backend | FastAPI com chamadas ao GPT | Igual, com rota separada para cada ação (`/api/collect`, `/api/interrogate` etc.) | Regras ficam em `game.py` (sem rede) para serem testadas sem chamar a API. |
| Limites de custo | Custo por token citado como risco | Máx. 300 caracteres por pergunta e 40 chamadas ao GPT por sessão (depois, falas pré-escritas) | Necessário para publicar o jogo com chave real sem risco de gasto descontrolado. |
| Prompts e forma de uso do Nano Banana | P-IMG-01 a 03 | Acrescentados P-IMG-04 (Rafael) e P-IMG-05 (Aurora) | A CP4 listava 3 retratos/cenários para 3 suspeitos e 2 cenários; faltavam dois retratos. As 5 imagens foram geradas no Nano Banana (interface do Gemini, camada gratuita, pois a cota da Gemini API para imagem não estava disponível na conta) e integradas ao jogo. |

## 4. Checklist de testes manuais
Preencha "obtido" depois de jogar. Os testes automáticos (`python -m pytest -q`, 30 testes) e o `tests/e2e_play.py` cobrem os itens 1 a 14.

| # | Mecânica | Esperado | Obtido |
|---|---|---|---|
| 1 | Menu: Novo Caso | Abre a Cena do Crime no Dia 1 | [PREENCHER] |
| 2 | Coletar log e e-mail | Evidências aparecem na aba, sem gastar ação | [PREENCHER] |
| 3 | Mandado antes do Dia 4 | Bloqueado | [PREENCHER] |
| 4 | Perguntar a Beatriz | Resposta do GPT com rótulo "gerado em tempo real" | [PREENCHER] |
| 5 | Pressionar | Confiança cai 8, pressão sobe 12 | [PREENCHER] |
| 6 | Acolher | Confiança sobe 10, pressão cai 4 | [PREENCHER] |
| 7 | Apresentar evidência | Pressão sobe uma única vez por prova | [PREENCHER] |
| 8 | Beatriz com pressão >= 80 | Revela Rafael | [PREENCHER] |
| 9 | Rafael com pressão >= 70 ou citando Beatriz com prova | Confessa e ganha a evidência | [PREENCHER] |
| 10 | Aurora sem mandado | Recusa | [PREENCHER] |
| 11 | Aurora com mandado (Dia 4+) | Libera logs | [PREENCHER] |
| 12 | 4 ações por dia | Na 5ª, pede para encerrar o dia | [PREENCHER] |
| 13 | Encerrar dia | Dia +1, pressão -10 | [PREENCHER] |
| 14 | Acusar Rafael com 2 provas fortes | Final Caso Encerrado | [PREENCHER] |
| 15 | Acusar Rafael com menos provas | Acusação Frágil | [PREENCHER] |
| 16 | Acusar Beatriz ou Aurora | Investigação Encerrada com Erro | [PREENCHER] |
| 17 | Dia 7 encerrado sem acusar | Prazo Esgotado (pede confirmação) | [PREENCHER] |
| 18 | Sem chave ou com a API fora do ar | Fala pré-escrita e aviso na tela | [PREENCHER] |
| 19 | Botão de som | Liga e desliga os efeitos | [PREENCHER] |

## 5. Diário de Vibe Coding
Ferramenta: Claude Code (terminal), conduzido por Gabriel Palmeira. Os prompts abaixo são os que foram realmente enviados nesta etapa final do projeto, copiados do histórico da conversa. Os dados sensíveis (chaves de API) foram omitidos como [chave omitida].

| # | Prompt enviado | O que a IA gerou | O que o grupo ajustou ou rejeitou |
|---|---|---|---|
| 1 | "pode tocar o restante do projeto. Só quero que atenta TODOS os critérios para que eu tire 10" | Limites para a versão pública (300 caracteres por pergunta, 300 sessões com expiração e 40 chamadas ao GPT por sessão), Dockerfile e render.yaml, efeitos sonoros com WebAudio e botão de som, 3 testes novos (27 para 30), Diário de Mudanças e checklist. | O botão de som cobria o texto "v1.0 MVP" no menu e foi movido. A IA escreveu as linhas do Diário de Mudanças a partir do código, e o grupo conferiu cada uma contra o jogo (por exemplo, o cache de perguntas realmente não foi implementado). |
| 2 | "Vc n pode acessar o nano banana e gerar essas imagens? Se precisar rodar algo no terminal, me avisa" | Um script (`tools/gerar_imagens.py`) que chama a Gemini API (Nano Banana) e usa o retrato da Beatriz como referência de estilo para os outros retratos. | A primeira execução falhou por chave inválida (o texto de exemplo foi colado no lugar da chave). Com a chave real, a API devolveu erro 429 de cota (sem cota gratuita de imagem pela API nessa conta). O grupo desistiu da API e gerou as imagens pela interface do Gemini, o que foi registrado no Diário de Mudanças. O script ficou no projeto como ferramenta. |
| 3 | "me mande os prompts que vc gostaria que gerasse a imagem para vc colocar no projeto" | Os 5 prompts de imagem: três da CP4 e dois novos (Rafael e Aurora), com nomes de arquivo e formato 16:9 ou 1:1. | O grupo colou os 5 prompts de uma vez, com os títulos, e o Gemini gerou só uma imagem. Passou a mandar um prompt por mensagem, sem título, e a anexar o retrato de referência. No retrato do Rafael, o crachá saiu com "ENGINEZR" em vez de "ENGINEER". Como o texto é minúsculo e o retrato é recortado no painel, foi mantido. |
| 4 | "Coloque a chave da openIA no .env: [chave omitida]" | Criou o `.env` (que está no `.gitignore`), subiu o servidor e fez duas chamadas reais ao `/api/interrogate`. | O teste confirmou `source: gpt` com `gpt-4o-mini`, e a Beatriz não revelou o nome do Rafael com a pressão baixa, como a CP4 pede. Como a chave ficou exposta na conversa, o grupo vai trocar e revogar a chave depois do vídeo. |
| 5 | "Vou te mandar o escopo do projeto todo também" (relatório da CP4 e enunciado da CP5) | Leitura dos dois documentos e uma lista de divergências entre o jogo e a CP4 (banco de dados, medidores iniciais, tons de pergunta, ações por dia, final Prazo Esgotado, janela de contexto, cache). | O grupo checou a lista com o código e registrou todas no Diário de Mudanças. O RM da Mayara foi corrigido para 563887. |

Nota: a construção inicial do jogo (regras, backend, interface, testes) foi feita em conversas anteriores. Se o grupo quiser, pode acrescentar aqui os prompts daquela fase, copiando do histórico.

### Como o código funciona (texto do grupo)
O jogo tem três partes: o servidor com as regras, a integração com o GPT e a tela no navegador. As regras ficam todas em `backend/game.py`, em Python puro, sem rede. É lá que se calculam a confiança e a pressão de cada suspeito, os desbloqueios, as evidências, os dias e os finais. Decidimos assim para que o GPT só escreva a fala do personagem. Se deixássemos o modelo decidir, ele poderia "inventar" que o segredo foi revelado cedo demais. O estado é sempre calculado pelo servidor.

Cada turno de interrogatório segue o mesmo caminho. A tela chama `/api/interrogate` com o suspeito, o tom (perguntar, pressionar ou acolher), as evidências apresentadas e a pergunta. O servidor aplica as regras primeiro: muda confiança e pressão pelo tom, soma a pressão de cada prova apresentada (só uma vez por suspeito) e confere o gatilho do suspeito (Beatriz com pressão de 80% ou mais, Rafael com 70% ou mais ou citando a Beatriz junto de uma prova, Aurora só com o mandado). Só depois disso `backend/llm.py` monta o prompt de sistema com a persona, o segredo, as regras de "bloqueado" ou "liberado" e o estado do caso, que inclui o dia, a confiança, a pressão e as evidências. É assim que os medidores influenciam o GPT, porque entram no texto do prompt a cada turno. O histórico enviado é só o das últimas 8 mensagens para controlar o custo.

Depois da resposta, passa por um filtro de saída que barra fuga de personagem e spoiler antes do limiar (por exemplo, Rafael confessando antes da hora). Se o filtro bloquear, se não houver chave ou se a API falhar, o jogo usa uma fala pré-escrita (fallback) e avisa na tela. O servidor também limita o gasto: 300 caracteres por pergunta e 40 chamadas ao GPT por partida.

A tela usa Phaser nas cenas (menu, atmosfera do interrogatório e finais) e HTML por cima do canvas para o HUD e o diálogo, porque texto longo e campo de digitação são mais simples em HTML. As imagens geradas no Nano Banana ficam em `frontend/assets/` e o jogo detecta os arquivos sozinho, usando arte procedural se alguma faltar. Os testes automáticos (`python -m pytest -q`) cobrem as regras e a API, e `tests/e2e_play.py` joga uma partida inteira no navegador.
