# Prompts para o Nano Banana (mesmo estilo dos P-IMG da CP4)

Use o P-IMG-01, P-IMG-02 e P-IMG-03 do relatório da CP4 sem alterar. Gere os dois abaixo no mesmo chat, anexando o
retrato aprovado da Beatriz como referência de estilo (image-to-image), como a CP4 previu na seção 2.2.

**P-IMG-04 (retrato, Rafael Advir):**
"A front-facing portrait of a male software engineer in his early 30s, thin and tired, wearing a wrinkled shirt with a
loosened tie and a company badge. He has a nervous expression and avoids eye contact, as if hiding a heavy secret.
The background is a dimly lit cyberpunk near-future office with subtle blue neon reflections. Same digital painting
character concept art style as the reference image, bust shot framing, no text or watermarks."

**P-IMG-05 (retrato, Aurora):**
"A front-facing portrait of a corporate artificial intelligence assistant shown as a calm, elegant humanoid hologram
made of translucent blue light with subtle circuit patterns across the face. The expression is neutral and precise.
The background is a dark server room with glowing cyan lines. Same digital painting character concept art style as
the reference image, bust shot framing, no text or watermarks."

## Onde salvar (nomes exatos)
frontend/assets/bg_menu.png (P-IMG-01, 1280x720), bg_room.png (P-IMG-02, 1280x720),
portrait_beatriz.png (P-IMG-03), portrait_rafael.png (P-IMG-04), portrait_aurora.png (P-IMG-05).
O jogo detecta os arquivos sozinho (confira em http://127.0.0.1:8000/api/assets).

## Se as imagens entrarem no jogo
- Remova a última linha do Diário de Mudanças (a que diz que a arte é procedural).
- Cite no Diário que P-IMG-04 e P-IMG-05 são novos em relação à CP4 (a CP4 só listou 3 prompts) e use as imagens no vídeo.
- Isso conta como a 2ª modalidade de IA generativa (ponto extra da rubrica 6.2).
