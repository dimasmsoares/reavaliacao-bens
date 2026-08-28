import os
import re
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                 Image as RLImage, KeepTogether, HRFlowable)

import database as db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOTS_DIR = os.path.join(BASE_DIR, 'screenshots')

METODOLOGIA_LABELS = {
    'M1': 'M1 – Pesquisa de Mercado',
    'M2': 'M2 – Acervo Patrimonial',
    'M3': 'M3 – Correção IPCA',
}

IMAGES_PER_ROW = 4
IMG_SIZE = 4.2 * cm


def _strip_codigo(material):
    if not material:
        return ''
    return re.sub(r'\s*\(\d+\)\s*$', '', material).strip()


def _brl(value):
    if value is None:
        return 'N/D'
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def _planilha_curta(planilha):
    if planilha and ' - ' in planilha:
        return planilha.split(' - ', 1)[1]
    return planilha or ''


def _group_reviews(rows):
    """Agrupa avaliações idênticas: mesmo grupo de bem (planilha+tipo+material+marca+modelo)
    e mesmos dados de avaliação viram uma única entrada no relatório, listando os NRPs."""
    groups = {}
    order = []
    for r in rows:
        key = (
            r['planilha'], r['tipo'] or '', r['material'] or '', r['marca'] or '', r['modelo'] or '',
            r['valor_mercado'], r['metodologia'], r['ipca_percentual'], r['observacao'] or '',
            tuple(r['screenshot_paths']), r['user_id'],
        )
        if key not in groups:
            groups[key] = {
                'planilha': r['planilha'],
                'tipo': r['tipo'],
                'material': r['material'],
                'marca': r['marca'],
                'modelo': r['modelo'],
                'valor_mercado': r['valor_mercado'],
                'metodologia': r['metodologia'] or 'M1',
                'ipca_percentual': r['ipca_percentual'],
                'observacao': r['observacao'],
                'screenshot_paths': r['screenshot_paths'],
                'avaliador': r['avaliador'],
                'updated_at': r['updated_at'],
                'nrps': [],
            }
            order.append(key)
        groups[key]['nrps'].append(r['nrp'])
    return [groups[k] for k in order]


def _build_styles():
    styles = getSampleStyleSheet()
    return {
        'title': styles['Title'],
        'subtitle': ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10,
                                    textColor=colors.grey, alignment=TA_CENTER),
        'heading': ParagraphStyle('EntryHeading', parent=styles['Heading4'], spaceAfter=2),
        'label': ParagraphStyle('Label', parent=styles['Normal'], fontSize=9, leading=13),
        'obs': ParagraphStyle('Obs', parent=styles['Normal'], fontSize=9, leading=13,
                               textColor=colors.HexColor('#555555')),
        'empty': styles['Normal'],
    }


def _image_grid(paths):
    flowables = []
    for path in paths:
        full_path = os.path.join(SCREENSHOTS_DIR, os.path.basename(path))
        if not os.path.exists(full_path):
            continue
        try:
            flowables.append(RLImage(full_path, width=IMG_SIZE, height=IMG_SIZE, kind='proportional'))
        except Exception:
            continue
    if not flowables:
        return None

    rows = []
    for i in range(0, len(flowables), IMAGES_PER_ROW):
        row = flowables[i:i + IMAGES_PER_ROW]
        row += [''] * (IMAGES_PER_ROW - len(row))
        rows.append(row)

    table = Table(rows, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return table


def _entry_block(e, styles):
    block = []
    titulo = _strip_codigo(e['material']) or '(sem descrição de material)'
    complemento = f"{e['marca'] or ''} {e['modelo'] or ''}".strip()
    if complemento:
        titulo += f" — {complemento}"
    block.append(Paragraph(titulo, styles['heading']))

    nrps = e['nrps']
    nrp_txt = ', '.join(nrps[:15])
    if len(nrps) > 15:
        nrp_txt += f' e mais {len(nrps) - 15}'
    qty_txt = f' <b>({len(nrps)} bens idênticos)</b>' if len(nrps) > 1 else ''
    block.append(Paragraph(f"<b>NRP:</b> {nrp_txt}{qty_txt}", styles['label']))
    block.append(Paragraph(
        f"<b>Planilha:</b> {_planilha_curta(e['planilha'])} "
        f"&nbsp;·&nbsp; <b>Tipo:</b> {e['tipo'] or 'Principal'}",
        styles['label']
    ))

    met_label = METODOLOGIA_LABELS.get(e['metodologia'], e['metodologia'])
    if e['metodologia'] == 'M3' and e['ipca_percentual'] is not None:
        met_label += f" ({e['ipca_percentual']:.2f}% IPCA)"
    block.append(Paragraph(f"<b>Metodologia:</b> {met_label}", styles['label']))
    block.append(Paragraph(f"<b>Valor de mercado:</b> {_brl(e['valor_mercado'])}", styles['label']))

    data_txt = e['updated_at'][:16].replace('T', ' ') if e['updated_at'] else '—'
    block.append(Paragraph(
        f"<b>Avaliado por:</b> {e['avaliador'] or '—'} &nbsp;·&nbsp; <b>Data:</b> {data_txt}",
        styles['label']
    ))

    if e['observacao']:
        block.append(Paragraph(f"<b>Observação:</b> {e['observacao']}", styles['obs']))

    img_table = _image_grid(e['screenshot_paths'])
    if img_table:
        block.append(Spacer(1, 0.15 * cm))
        block.append(img_table)

    block.append(Spacer(1, 0.25 * cm))
    block.append(HRFlowable(width='100%', color=colors.HexColor('#e0e0e0')))
    block.append(Spacer(1, 0.25 * cm))
    return block


def generate_pdf_report(user_id=None, user_name=None):
    """Gera o relatório em PDF dos bens já avaliados e retorna os bytes do arquivo.
    Se user_id for informado, restringe às avaliações feitas por aquele servidor."""
    rows = db.get_reviews_for_report(user_id)
    entries = _group_reviews(rows)
    styles = _build_styles()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )

    story = []
    title = 'Relatório de Bens Reavaliados'
    if user_name:
        title += f' — {user_name}'
    story.append(Paragraph(title, styles['title']))

    total_bens = sum(len(e['nrps']) for e in entries)
    story.append(Paragraph(
        f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} "
        f"&nbsp;·&nbsp; {len(entries)} avaliação(ões) "
        f"&nbsp;·&nbsp; {total_bens} bem(ns)",
        styles['subtitle']
    ))
    story.append(Spacer(1, 0.6 * cm))
    story.append(HRFlowable(width='100%', color=colors.HexColor('#cccccc')))
    story.append(Spacer(1, 0.4 * cm))

    if not entries:
        story.append(Paragraph('Nenhum bem avaliado encontrado.', styles['empty']))
    else:
        for e in entries:
            story.append(KeepTogether(_entry_block(e, styles)))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
