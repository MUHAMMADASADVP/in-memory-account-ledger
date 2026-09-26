"""Render the reviewed Markdown into a three-page submission PDF."""

from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/architecture-trade-offs.pdf"


def inline(text):
    safe = escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    if safe.startswith("https://"):
        return f'<link href="{safe}" color="#146476">{safe}</link>'
    return safe


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("LedgerBody", fontName="Helvetica", fontSize=10, leading=14,
                          spaceAfter=9, textColor=colors.HexColor("#263642"))
    bullet = ParagraphStyle("LedgerBullet", parent=body, fontSize=9, leading=13,
                            leftIndent=10, firstLineIndent=-8, spaceAfter=7)
    title = ParagraphStyle("LedgerTitle", parent=body, fontName="Helvetica-Bold",
                           fontSize=22, leading=26, spaceAfter=12, textColor=colors.HexColor("#143547"))
    heading = ParagraphStyle("LedgerHeading", parent=body, fontName="Helvetica-Bold",
                             fontSize=14, leading=18, spaceBefore=10, spaceAfter=9, keepWithNext=True)
    subheading = ParagraphStyle("LedgerSubheading", parent=heading, fontSize=11, leading=15)
    small = ParagraphStyle("LedgerSmall", parent=body, fontSize=8, leading=11,
                           spaceAfter=6, splitLongWords=True)
    story = []
    in_references = False
    for block in (ROOT / "ARCHITECTURE.md").read_text().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block == "<!-- pagebreak -->":
            story.append(PageBreak())
        elif block.startswith("# "):
            story.append(Paragraph(inline(block[2:]), title))
        elif block.startswith("## "):
            in_references = block == "## Primary references"
            story.append(Paragraph(inline(block[3:]), heading))
        elif block.startswith("### "):
            story.append(Paragraph(inline(block[4:]), subheading))
        elif block.startswith("- "):
            for item in re.split(r"\n(?=- )", block):
                story.append(Paragraph("- " + inline(" ".join(item[2:].splitlines())), bullet))
        else:
            lines = block.splitlines()
            urls = [line for line in lines if line.startswith("https://")]
            text = " ".join(line for line in lines if not line.startswith("https://"))
            story.append(Paragraph(inline(text), small if in_references else body))
            for url in urls:
                story.append(Paragraph(inline(url), small))

    def decorate(canvas, doc):
        width, height = A4
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#B9CCD3"))
        canvas.line(48, height - 32, width - 48, height - 32)
        canvas.setFillColor(colors.HexColor("#526D78"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(48, height - 25, "ACCOUNT LEDGER / ARCHITECTURE REVIEW")
        canvas.drawString(48, 27, "Implementation-specific decisions and production gaps")
        canvas.drawRightString(width - 48, 27, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=48, rightMargin=48,
                            topMargin=48, bottomMargin=48, title="Account Ledger - Architecture & Trade-offs",
                            author="Muhammad Asad VP", subject="Implementation-specific architecture and trade-offs")
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    print(OUTPUT)


if __name__ == "__main__":
    main()
