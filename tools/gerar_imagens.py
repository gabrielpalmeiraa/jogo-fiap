"""Gera as 5 imagens do jogo com o Nano Banana (Gemini 2.5 Flash Image) e salva em frontend/assets/.

Uso:
    export GEMINI_API_KEY=sua_chave      # grátis em https://aistudio.google.com/apikey
    python tools/gerar_imagens.py [nome ...]   # sem argumentos gera todas; ou ex.: portrait_rafael

Os prompts P-IMG-01 a 03 são os do relatório da CP4. O 04 e o 05 estão em docs/prompts_imagens_nano_banana.md.
O retrato da Beatriz é enviado como referência de estilo para os retratos de Rafael e Aurora (image-to-image).
Usa só a biblioteca padrão. Para refazer uma imagem, apague o arquivo ou passe o nome dela.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
OUT = Path(__file__).resolve().parent.parent / "frontend" / "assets"

PROMPTS = {
    "bg_menu": "A cinematic wide shot of São Paulo's skyline at night in the year 2041. The city has a cyberpunk noir atmosphere with neon signs glowing in blue and magenta against dark buildings. The lighting is moody, with fog between the skyscrapers. Digital painting style, highly detailed, no text or watermarks anywhere in the image. 16:9 aspect ratio.",
    "bg_room": "The interior of a corporate interrogation room inside a near-future cyberpunk office building. The room has cold fluorescent ceiling lights mixed with subtle neon accents along the walls. The furniture is minimalist: a metal table and two chairs. There is a large one-way mirror on one wall. The atmosphere feels tense and sterile. Digital painting concept art style, wide angle view, no text in the image. 16:9 aspect ratio.",
    "portrait_beatriz": "A front-facing portrait of a corporate executive woman in her early 40s. She wears a sharp dark business suit and has a confident but visibly tense expression, as if she is hiding something. The background is a dimly lit cyberpunk near-future office with subtle neon reflections. Digital painting character concept art style, bust shot framing, no text or watermarks. Square 1:1 aspect ratio.",
    "portrait_rafael": "A front-facing portrait of a male software engineer in his early 30s, thin and tired, wearing a wrinkled shirt with a loosened tie and a company badge. He has a nervous expression and avoids eye contact, as if hiding a heavy secret. The background is a dimly lit cyberpunk near-future office with subtle blue neon reflections. Same digital painting character concept art style as the reference image, bust shot framing, no text or watermarks. Square 1:1 aspect ratio.",
    "portrait_aurora": "A front-facing portrait of a corporate artificial intelligence assistant shown as a calm, elegant humanoid hologram made of translucent blue light with subtle circuit patterns across the face. The expression is neutral and precise. The background is a dark server room with glowing cyan lines. Same digital painting character concept art style as the reference image, bust shot framing, no text or watermarks. Square 1:1 aspect ratio.",
}
USES_REFERENCE = {"portrait_rafael", "portrait_aurora"}


def generate(prompt: str, key: str, reference: bytes | None = None) -> bytes:
    parts = [{"text": prompt}]
    if reference:
        parts.append({"inline_data": {"mime_type": "image/png", "data": base64.b64encode(reference).decode()}})
    body = json.dumps({"contents": [{"parts": parts}]}).encode()
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline:
                return base64.b64decode(inline["data"])
    raise RuntimeError("A resposta não trouxe imagem: " + json.dumps(data)[:400])


def main() -> None:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        sys.exit("Defina GEMINI_API_KEY (grátis em https://aistudio.google.com/apikey).")
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = sys.argv[1:] or list(PROMPTS)
    for name in wanted:
        if name not in PROMPTS:
            sys.exit(f"Nome inválido: {name}. Opções: {', '.join(PROMPTS)}")
        path = OUT / f"{name}.png"
        if path.exists() and not sys.argv[1:]:
            print(f"- {name}: já existe, pulando")
            continue
        ref = None
        if name in USES_REFERENCE:
            beatriz = OUT / "portrait_beatriz.png"
            ref = beatriz.read_bytes() if beatriz.exists() else None
        print(f"- gerando {name} ...", flush=True)
        try:
            path.write_bytes(generate(PROMPTS[name], key, ref))
            print(f"  salvo em {path}")
        except urllib.error.HTTPError as e:
            print(f"  erro HTTP {e.code}: {e.read().decode()[:300]}")
        except Exception as e:  # noqa: BLE001
            print(f"  erro: {e}")


if __name__ == "__main__":
    main()
