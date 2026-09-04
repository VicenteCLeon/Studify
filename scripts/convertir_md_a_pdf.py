"""Convierte los archivos Markdown de prueba (.md) a documentos PDF (.pdf)

Utiliza ReportLab para compilar los Markdown de `data/documentos_prueba_md/`
en archivos PDF listos para ingestar desde la interfaz docente de Studify.
"""

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

DIR_MD = Path("data/documentos_prueba_md")
DIR_PDF = Path("data/documentos_prueba_pdf")


def clean_text_for_xml(text: str) -> str:
    """Escapa caracteres especiales y convierte formato Markdown básico (**bold**, *italic*, `code`)."""
    # 1. Escapar HTML/XML primero
    text = html.escape(text)
    # 2. Reemplazar negritas **texto**
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    # 3. Reemplazar cursivas *texto*
    text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
    # 4. Reemplazar código inline `texto`
    text = re.sub(r"`(.*?)`", r'<font face="Courier">\1</font>', text)
    return text


def parsear_lineas_md(texto: str):
    """Parsea contenido de Markdown para construir elementos Flowable de ReportLab."""
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1E3A8A"),
        spaceAfter=12,
    )

    h2_style = ParagraphStyle(
        "DocH2",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#2563EB"),
        spaceBefore=12,
        spaceAfter=8,
    )

    h3_style = ParagraphStyle(
        "DocH3",
        parent=styles["Heading3"],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1E40AF"),
        spaceBefore=8,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=6,
    )

    code_style = ParagraphStyle(
        "DocCode",
        parent=styles["Code"],
        fontSize=9,
        leading=12,
        backColor=colors.HexColor("#F3F4F6"),
        borderColor=colors.HexColor("#E5E7EB"),
        borderWidth=1,
        borderPadding=6,
        spaceBefore=6,
        spaceAfter=8,
    )

    flowables = []
    lineas = texto.splitlines()
    i = 0

    in_code_block = False
    code_lines = []

    while i < len(lineas):
        linea = lineas[i]
        stripped = linea.strip()

        if stripped.startswith("```"):
            if in_code_block:
                code_text = "\n".join(code_lines)
                flowables.append(Preformatted(code_text, code_style))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_lines.append(linea)
            i += 1
            continue

        if stripped.startswith("# "):
            flowables.append(Paragraph(clean_text_for_xml(stripped[2:]), title_style))
        elif stripped.startswith("## "):
            flowables.append(Paragraph(clean_text_for_xml(stripped[3:]), h2_style))
        elif stripped.startswith("### "):
            flowables.append(Paragraph(clean_text_for_xml(stripped[4:]), h3_style))
        elif stripped.startswith("---"):
            flowables.append(
                HRFlowable(
                    width="100%",
                    thickness=1,
                    color=colors.HexColor("#CBD5E1"),
                    spaceAfter=10,
                    spaceBefore=10,
                )
            )
        elif stripped.startswith("|") and "|" in stripped[1:]:
            tabla_lineas = []
            while i < len(lineas) and lineas[i].strip().startswith("|"):
                tabla_lineas.append(lineas[i].strip())
                i += 1
            i -= 1

            filas_datos = []
            for t_lin in tabla_lineas:
                if ":---" in t_lin or "---" in t_lin:
                    continue
                celdas = [c.strip() for c in t_lin.split("|")[1:-1]]
                if celdas:
                    filas_datos.append(
                        [Paragraph(clean_text_for_xml(c), body_style) for c in celdas]
                    )

            if filas_datos:
                t = Table(filas_datos, spaceBefore=8, spaceAfter=8)
                t.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ]
                    )
                )
                flowables.append(t)
        elif stripped.startswith("* ") or stripped.startswith("- "):
            flowables.append(Paragraph(f"• {clean_text_for_xml(stripped[2:])}", body_style))
        elif re.match(r"^\d+\.\s", stripped):
            texto_bullet = re.sub(r"^\d+\.\s", "", stripped)
            num = stripped.split(".")[0]
            flowables.append(Paragraph(f"{num}. {clean_text_for_xml(texto_bullet)}", body_style))
        elif stripped:
            flowables.append(Paragraph(clean_text_for_xml(stripped), body_style))

        i += 1

    return flowables


def convertir_todas():
    DIR_PDF.mkdir(parents=True, exist_ok=True)
    archivos_md = sorted(list(DIR_MD.glob("*.md")))
    print(f"Encontrados {len(archivos_md)} archivos Markdown en {DIR_MD}")

    for ruta_md in archivos_md:
        ruta_pdf = DIR_PDF / f"{ruta_md.stem}.pdf"
        print(f"Convirtiendo {ruta_md.name} -> {ruta_pdf.name}...")

        contenido = ruta_md.read_text(encoding="utf-8")
        doc = SimpleDocTemplate(
            str(ruta_pdf),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )
        flowables = parsear_lineas_md(contenido)
        doc.build(flowables)
        print(f"  [OK] {ruta_pdf.name} generado con exito.")


if __name__ == "__main__":
    convertir_todas()
