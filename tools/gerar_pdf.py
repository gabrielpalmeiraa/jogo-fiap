"""Gera docs/Entrega_CP5_Sinapse.pdf a partir de docs/ENTREGA_CP5.md e README.md.

Uso: pip install reportlab && python tools/gerar_pdf.py
"""
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "Entrega_CP5_Sinapse.pdf"
NAVY = colors.HexColor("#0b1730")
YELLOW = colors.HexColor("#e9b800")

ss = getSampleStyleSheet()
body = ParagraphStyle("body", parent=ss["Normal"], fontName="Helvetica", fontSize=9.5, leading=13.5, spaceAfter=5)
small = ParagraphStyle("small", parent=body, fontSize=7.8, leading=10, spaceAfter=0)
h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=16, textColor=NAVY, spaceBefore=6, spaceAfter=8)
h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12, textColor=NAVY, spaceBefore=8, spaceAfter=5)
h3 = ParagraphStyle("h3", parent=ss["Heading3"], fontName="Helvetica-Bold", fontSize=10.5, textColor=NAVY, spaceBefore=6, spaceAfter=3)
code = ParagraphStyle("code", parent=body, fontName="Courier", fontSize=8, leading=10.5, backColor=colors.HexColor("#f0f2f6"), borderPadding=4, spaceAfter=7)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2, spaceAfter=2)
cap = ParagraphStyle("cap", parent=body, fontSize=8, textColor=colors.HexColor("#555555"), alignment=TA_CENTER)


def inline(t: str) -> str:
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r'<font face="Courier" size="8.3">\1</font>', t)
    t = re.sub(r"(https?://[^\s<)]+[^\s<).,])", r'<link href="\1" color="#1a4fd6">\1</link>', t)
    return t


def table(rows, widths):
    head = ParagraphStyle("head", parent=small, textColor=colors.white, fontName="Helvetica-Bold")
    data = [[Paragraph(inline(c), head) for c in rows[0]]] + [[Paragraph(inline(c), small) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8bfcc")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fb")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def md_to_flow(md: str, avail: float, skip_h1=True):
    flow, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            j = i + 1
            blk = []
            while j < len(lines) and not lines[j].startswith("```"):
                blk.append(lines[j]); j += 1
            flow.append(Paragraph("<br/>".join(inline(x).replace(" ", "&nbsp;") for x in blk), code))
            i = j + 1; continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(set(c) <= set("-: ") for c in cells):
                    rows.append(cells)
                i += 1
            n = len(rows[0])
            if n == 4 and rows[0][0].startswith("Item"):
                w = [0.14, 0.2, 0.26, 0.40]
            elif n == 4 and rows[0][1].startswith("Prompt"):
                w = [0.04, 0.24, 0.32, 0.40]
            elif n == 3 and rows[0][0] == "#":
                w = [0.04, 0.27, 0.69]
            else:
                w = [1 / n] * n
            flow.append(table(rows, [avail * x for x in w])); flow.append(Spacer(1, 6)); continue
        if ln.startswith("# "):
            if not skip_h1:
                flow.append(Paragraph(inline(ln[2:]), h1))
        elif ln.startswith("## "):
            flow.append(Paragraph(inline(ln[3:]), h1 if skip_h1 else h2))
        elif ln.startswith("### "):
            flow.append(Paragraph(inline(ln[4:]), h2 if skip_h1 else h3))
        elif re.match(r"^\d+\. ", ln):
            m = re.match(r"^(\d+)\. (.*)", ln)
            flow.append(Paragraph(inline(m.group(2)), bullet, bulletText=m.group(1) + "."))
        elif ln.startswith("- "):
            flow.append(Paragraph(inline(ln[2:]), bullet, bulletText="•"))
        elif ln.startswith("> "):
            pass
        elif ln.strip():
            para = [ln.strip()]
            while (i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^(#|\||- |> |```|\d+\. )", lines[i + 1])):
                i += 1
                para.append(lines[i].strip())
            flow.append(Paragraph(inline(" ".join(para)), body))
        i += 1
    return flow


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5); canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(18 * mm, 10 * mm, "Sinapse: Protocolo Silencioso | CP5 | FIAP 2TIAPY")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {doc.page}")
    canvas.restoreState()


def main():
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                            title="CP5 Sinapse: Protocolo Silencioso", author="Gabriel Palmeira e Mayara Mota")
    avail = A4[0] - 36 * mm
    s = []
    # capa
    s += [Spacer(1, 30 * mm), Paragraph("CHECKPOINT 5: VIBE CODING E MVP", ParagraphStyle("k", parent=body, fontSize=11, textColor=YELLOW, alignment=TA_CENTER)),
          Spacer(1, 6 * mm),
          Paragraph("SINAPSE", ParagraphStyle("t", parent=h1, fontSize=40, alignment=TA_CENTER, leading=44, textColor=NAVY)),
          Paragraph("PROTOCOLO SILENCIOSO", ParagraphStyle("t2", parent=h1, fontSize=18, alignment=TA_CENTER, textColor=NAVY)),
          Spacer(1, 5 * mm),
          Paragraph("MVP jogável de um jogo de investigação narrativa com suspeitos movidos por IA generativa (GPT) e arte gerada no Nano Banana", ParagraphStyle("d", parent=body, alignment=TA_CENTER, fontSize=11, leading=15)),
          Spacer(1, 12 * mm)]
    img = ROOT / "docs" / "prints" / "01_menu.png"
    if img.exists():
        s += [Image(str(img), width=avail * 0.8, height=avail * 0.8 * 720 / 1280, hAlign="CENTER"), Paragraph("Menu principal do MVP", cap)]
    s += [Spacer(1, 12 * mm),
          Paragraph("<b>Integrantes</b><br/>Gabriel Palmeira (RM 563522)<br/>Mayara Mota (RM 563887)", ParagraphStyle("i", parent=body, alignment=TA_CENTER, fontSize=11, leading=16)),
          Spacer(1, 4 * mm),
          Paragraph("FIAP, turma 2TIAPY<br/>NLP, Chatbots e Agentes Virtuais<br/>São Paulo, outubro de 2026", ParagraphStyle("i2", parent=body, alignment=TA_CENTER, leading=14)),
          Spacer(1, 6 * mm),
          Paragraph("Jogo online: https://jogo-fiap.onrender.com<br/>Código: https://github.com/gabrielpalmeiraa/jogo-fiap", ParagraphStyle("l", parent=body, alignment=TA_CENTER)),
          PageBreak()]
    md = (ROOT / "docs" / "ENTREGA_CP5.md").read_text(encoding="utf-8")
    md = md.replace("Veja `README.md`. ", "O README completo está no Apêndice A. ")
    s += md_to_flow(md, avail, skip_h1=True)
    # capturas
    s.append(PageBreak()); s.append(Paragraph("6. Capturas de tela do MVP", h1))
    caps = [("02_cena.png", "Cena do Crime: coleta de evidências (sem gastar ação)"),
            ("06_pressao_alta.png", "Interrogatório: resposta da Beatriz gerada pelo GPT, com o rótulo de texto em tempo real, retrato do Nano Banana e medidores"),
            ("10_quadro.png", "Quadro de Investigação (acusação final)"), ("11_final.png", "Final: Caso Encerrado")]
    for name, text in caps:
        f = ROOT / "docs" / "prints" / name
        if f.exists():
            w = avail * 0.78
            s.append(KeepTogether([Image(str(f), width=w, height=w * 720 / 1280, hAlign="CENTER"), Paragraph(text, cap), Spacer(1, 4 * mm)]))
    # apêndice README
    s.append(PageBreak()); s.append(Paragraph("Apêndice A: README do projeto", h1))
    s += md_to_flow((ROOT / "README.md").read_text(encoding="utf-8"), avail, skip_h1=True)
    doc.build(s, onFirstPage=lambda c, d: None, onLaterPages=footer)
    print("PDF gerado:", OUT)


if __name__ == "__main__":
    main()
