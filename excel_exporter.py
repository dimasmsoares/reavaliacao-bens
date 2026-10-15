import os
import shutil
from copy import copy
from datetime import datetime
import openpyxl
from database import get_db, get_distinct_planilhas
from excel_loader import _find_data_start
from pdf_report import REFERENCIA_PRECO_LABELS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLANILHAS_DIR = os.path.join(BASE_DIR, 'planilhas_excel')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

VMB_COL = 10          # Coluna "VALOR DE MERCADO (VMB)"
METODOLOGIA_COL = 19  # Colunas extras, após as 18 originais (a 11 é o EC e não é tocada)
REFERENCIA_COL = 20


def _write_header(ws, header_row, col, text):
    """Escreve o cabeçalho de uma coluna extra copiando o estilo da última coluna original."""
    src = ws.cell(row=header_row, column=18)
    dst = ws.cell(row=header_row, column=col)
    dst.value = text
    if src.has_style:
        dst.font = copy(src.font)
        dst.fill = copy(src.fill)
        dst.border = copy(src.border)
        dst.alignment = copy(src.alignment)
    ws.column_dimensions[dst.column_letter].width = 22


def export_all():
    """
    Para cada planilha com bens avaliados, cria uma cópia do Excel original
    na pasta output/ com a coluna VMB preenchida e, nas colunas extras 19 e 20,
    a metodologia e a referência do valor pesquisado.
    Retorna lista dos arquivos gerados.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime('%Y%m%d_%H%M')
    exported = []

    conn = get_db()
    for planilha in get_distinct_planilhas():
        rows = conn.execute("""
            SELECT a.row_index, r.valor_mercado, r.metodologia, r.referencia_preco
            FROM assets a
            JOIN reviews r ON a.id = r.asset_id
            WHERE a.planilha = ?
        """, (planilha,)).fetchall()

        if not rows:
            continue

        src = os.path.join(PLANILHAS_DIR, planilha + '.xlsx')
        if not os.path.exists(src):
            continue

        dst = os.path.join(OUTPUT_DIR, f"{planilha}_avaliado_{date_str}.xlsx")
        shutil.copy2(src, dst)

        wb = openpyxl.load_workbook(dst)
        ws = wb.active
        header_row = _find_data_start(ws) - 1
        _write_header(ws, header_row, METODOLOGIA_COL, 'METODOLOGIA DE AVALIAÇÃO')
        _write_header(ws, header_row, REFERENCIA_COL, 'REFERÊNCIA DO VALOR PESQUISADO')
        for row_index, valor_mercado, metodologia, referencia in rows:
            ws.cell(row=row_index, column=VMB_COL).value = valor_mercado
            ws.cell(row=row_index, column=METODOLOGIA_COL).value = metodologia or 'M1'
            ws.cell(row=row_index, column=REFERENCIA_COL).value = (
                REFERENCIA_PRECO_LABELS.get(referencia, referencia) if referencia else None
            )
        wb.save(dst)
        wb.close()
        exported.append(os.path.basename(dst))

    conn.close()
    return exported
