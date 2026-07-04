"""Helpers ReportLab compartidos por los reportes PDF (estilo corporativo TechRepair)."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# ── PALETA CORPORATIVA ─────────────────────────────────────────
AZUL       = colors.HexColor('#1F3864')
LIGHT      = colors.HexColor('#EBF3FB')
GRIS       = colors.HexColor('#f5f5f5')
GRIS_BORDE = colors.HexColor('#CCCCCC')

# Ancho útil de página A4 con márgenes de 2cm
ANCHO_UTIL = 17 * cm


def crear_doc_pdf(buffer, pagesize=A4, margins=(2 * cm, 2 * cm, 2 * cm, 2 * cm)):
    """Crea el SimpleDocTemplate estándar. margins = (right, left, top, bottom)."""
    right, left, top, bottom = margins
    return SimpleDocTemplate(
        buffer, pagesize=pagesize,
        rightMargin=right, leftMargin=left,
        topMargin=top, bottomMargin=bottom,
    )


def estilos_base():
    """Retorna dict con ParagraphStyles estándar: titulo, subtitulo, seccion."""
    return {
        'titulo':    ParagraphStyle('t', fontSize=16, textColor=AZUL,
                                    fontName='Helvetica-Bold'),
        'subtitulo': ParagraphStyle('s', fontSize=9, textColor=colors.grey,
                                    fontName='Helvetica'),
        'seccion':   ParagraphStyle('sec', fontSize=8, textColor=colors.grey,
                                    fontName='Helvetica-Bold', spaceAfter=4),
    }


def formato_periodo(fecha_inicio, fecha_fin):
    """Sufijo de subtítulo con el período filtrado ('' si no hay filtro)."""
    if fecha_inicio and fecha_fin:
        return f' | Período: {fecha_inicio.strftime("%d/%m/%Y")} — {fecha_fin.strftime("%d/%m/%Y")}'
    if fecha_inicio:
        return f' | Desde: {fecha_inicio.strftime("%d/%m/%Y")}'
    if fecha_fin:
        return f' | Hasta: {fecha_fin.strftime("%d/%m/%Y")}'
    return ''


def tabla_base(data, col_widths, align_right_cols=None, extra_style=None):
    """Retorna un Table de ReportLab con el estilo corporativo TechRepair.

    align_right_cols: lista de índices de columna a alinear a la derecha.
    extra_style: lista de comandos TableStyle adicionales (p.ej. ALIGN).
    """
    t = Table(data, colWidths=col_widths)
    style = [
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('BACKGROUND',    (0, 0), (-1, 0),  AZUL),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS]),
        ('GRID',          (0, 0), (-1, -1), 0.4, GRIS_BORDE),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    if align_right_cols:
        for col in align_right_cols:
            style.append(('ALIGN', (col, 0), (col, -1), 'RIGHT'))
    if extra_style:
        style.extend(extra_style)
    t.setStyle(TableStyle(style))
    return t
