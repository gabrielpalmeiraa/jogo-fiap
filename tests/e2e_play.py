"""Teste ponta a ponta no navegador (Playwright): joga uma partida inteira até o final.

Uso (com o servidor rodando em http://127.0.0.1:8000):
    python tests/e2e_play.py [pasta_dos_prints]
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/prints")
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://127.0.0.1:8000"


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        page = b.new_page(viewport={"width": 1280, "height": 720})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "404" not in m.text else None)
        page.goto(URL)
        page.wait_for_timeout(9000)  # renderizador por software é lento
        page.screenshot(path=OUT / "01_menu.png")

        page.mouse.click(640, 484)  # NOVO CASO
        page.wait_for_selector("#view-scene.active", timeout=20000)
        page.wait_for_timeout(700)
        page.screenshot(path=OUT / "02_cena.png")
        page.click("[data-collect=log_acesso]")
        page.click("[data-collect=email]")
        assert page.inner_text("#tab-evidence").endswith("3/5") is False
        page.screenshot(path=OUT / "03_cena_coletada.png")

        page.click("[data-view=suspects]")
        page.screenshot(path=OUT / "04_suspeitos.png")
        page.click("[data-talk=beatriz]")
        page.wait_for_selector("#view-interrogation.active")
        page.click("[data-ev=log_acesso]")
        page.fill("#msg", "Beatriz, o log do servidor mostra um acesso às 23h47 com o crachá da sua sala. Como você explica isso?")
        page.click("#btn-send")
        page.wait_for_selector(".msg.npc")
        page.wait_for_timeout(600)
        page.screenshot(path=OUT / "05_interrogatorio.png")

        # aumenta a pressão até Beatriz ceder
        page.click("[data-ev=email]")
        page.click("[data-tone=pressionar]")
        page.fill("#msg", "Quem mais sabia disso? Esse e-mail é seu.")
        page.click("#btn-send")
        page.wait_for_selector(".msg.npc >> nth=1")
        page.wait_for_timeout(900)
        page.screenshot(path=OUT / "06_pressao_alta.png")
        assert int(page.inner_text("#press-val").strip("%")) >= 80

        # Rafael confessa ao ser confrontado com o e-mail e citar Beatriz
        page.click("[data-view=suspects]")
        page.click("[data-talk=rafael]")
        page.click("[data-ev=email]")
        page.fill("#msg", "A Beatriz te mandou esse e-mail, não foi?")
        page.click("#btn-send")
        page.wait_for_selector(".msg.npc")
        page.wait_for_timeout(600)
        page.screenshot(path=OUT / "07_rafael_confessa.png")

        page.click("[data-view=evidence]")
        page.screenshot(path=OUT / "08_evidencias.png")
        assert "Confissão de Rafael" in page.inner_text("#ev-cards")

        page.click("[data-view=state]")
        page.screenshot(path=OUT / "09_estado.png")
        page.click("#btn-to-board")
        page.click("#board-suspects [data-b=rafael]")
        page.click("[data-be=email]")
        page.click("[data-be=confissao]")
        page.screenshot(path=OUT / "10_quadro.png")
        page.click("#btn-close-case")  # pede confirmação
        page.click("#btn-close-case")
        page.wait_for_timeout(9000)
        page.screenshot(path=OUT / "11_final.png")
        b.close()
        assert not errors, errors
        print("OK: partida completa até o final CASO ENCERRADO. Prints em", OUT)


if __name__ == "__main__":
    main()
