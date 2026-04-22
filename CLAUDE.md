# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Sistema web interno da Câmara dos Deputados para auxiliar na **reavaliação de bens móveis**. Servidores pesquisam o valor de mercado de 54.430 bens em e-commerces, registram o valor e anexam um print como comprovante. Um administrador distribui os bens entre os servidores e acompanha o andamento.

**Stack**: Python 3.12 · Flask · SQLite · Bootstrap 5 · vanilla JS

## Como executar

```bash
# Instalar dependências (apenas na primeira vez)
pip install -r requirements.txt

# Iniciar servidor (inicializa BD e importa planilhas automaticamente)
python app.py
# → http://localhost:5000
# → Admin padrão: admin / admin123
```

O banco `reavaliacao.db` e os screenshots são gerados automaticamente na raiz do projeto. As planilhas originais em `planilhas_excel/` nunca são modificadas.

## Arquitetura

### Backend (`app.py`, `database.py`, `excel_loader.py`, `excel_exporter.py`)
- **`app.py`**: Flask app com rotas de autenticação, admin e servidor. Na inicialização: cria banco, admin padrão e importa as planilhas (idempotente).
- **`database.py`**: Todas as operações SQLite. Funções nomeadas por entidade (`get_user_*`, `assign_*`, `get_*_progress`, etc.).
- **`excel_loader.py`**: Lê cada `.xlsx` com `openpyxl` (`iter_rows`, `read_only=True`). Cabeçalhos na linha 7, dados a partir da linha 8. Commita por planilha para ser resiliente a interrupções.
- **`excel_exporter.py`**: Copia os `.xlsx` originais para `output/` e preenche a coluna 10 (VMB) com os valores avaliados.

### Banco de dados (SQLite WAL)
- `users`: admin + servidores com senha hash (werkzeug)
- `assets`: 54.430 bens importados das planilhas (somente leitura lógica)
- `assignments`: mapeamento servidor → bem (admin distribui)
- `reviews`: valor de mercado + caminho do screenshot, indexado por `asset_id`

### Frontend (`templates/`, `static/`)
- `base.html`: layout Bootstrap 5 + navbar contextual (admin vs. servidor)
- `admin/`: dashboard com barras de progresso, gerência de servidores, distribuição de bens
- `servidor/avaliar.html`: tela principal — sidebar com lista de bens, detalhes do bem, botões de busca em e-commerces, input de valor, zona de drag&drop/paste de screenshot
- `static/app.js`: captura de clipboard (`paste` event), drag&drop, file picker, formatação de moeda pt-BR

### Fluxo principal
1. Admin cria servidores (`/admin/usuarios`) e distribui bens (`/admin/distribuir`) — por planilha, quantidade ou redistribuição
2. Servidor acessa `/avaliar`, vê seu próximo bem pendente, pesquisa em ML/Amazon/Google, preenche valor + print
3. Admin exporta resultados em `/admin/export` → gera `output/<planilha>_avaliado_<data>.xlsx` com a coluna VMB preenchida

## Arquivos de dados
- `planilhas_excel/`: 9 planilhas xlsx com os bens (NUNCA modificar)
- `reavaliacao.db`: banco SQLite gerado automaticamente
- `screenshots/`: prints salvos como `<asset_id>_<timestamp>.png`
- `output/`: Excel exportado com avaliações preenchidas
