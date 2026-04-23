# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Sistema web interno da Câmara dos Deputados para auxiliar na **reavaliação de bens móveis**. Servidores avaliam 54.430 bens usando uma de três metodologias e registram o valor de mercado. Um administrador distribui os bens entre os servidores e acompanha o andamento. Bens com mesmo tipo+material+marca+modelo são avaliados em grupo: avaliar 1 propaga automaticamente para todos os idênticos do mesmo tipo.

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
- **`app.py`**: Flask app com rotas de autenticação, admin e servidor. Na inicialização: cria banco, admin padrão e importa as planilhas (idempotente). Usa `requests as http_requests` com `verify=False` para a API do BCB (proxy SSL corporativo). Importa `date` de `datetime` para o endpoint `/api/ipca`.
- **`database.py`**: Todas as operações SQLite. Funções nomeadas por entidade (`get_user_*`, `assign_*`, `get_*_progress`, etc.).
- **`excel_loader.py`**: Lê cada `.xlsx` com `openpyxl`. Detecta dinamicamente a linha de cabeçalho via `_find_data_start()` (busca "NRP" nas primeiras 20 linhas; fallback = 8). Commita por planilha para ser resiliente a interrupções.
- **`excel_exporter.py`**: Copia os `.xlsx` originais para `output/` e preenche a coluna 10 (VMB) e coluna 11 (metodologia: `M1`/`M2`/`M3`).

### Banco de dados (SQLite WAL)
- `users`: admin + servidores com senha hash (werkzeug)
- `assets`: 54.430 bens importados das planilhas (somente leitura lógica). Campos relevantes: `tipo TEXT` (NULL = bem principal, "Agregação" = agregação), `material`, `marca`, `modelo`, `data_tombamento TEXT` (formato `dd/mm/yyyy`), `valor_contabil REAL`.
- `assignments`: mapeamento servidor → bem (admin distribui)
- `reviews`: resultado da avaliação, indexado por `asset_id` (UNIQUE). Colunas adicionadas progressivamente via `ALTER TABLE` em `init_db()`:
  - `valor_mercado REAL` — valor final registrado
  - `prices TEXT` — JSON array de floats com os preços pesquisados
  - `screenshot_path TEXT` — compat. legada (primeiro screenshot)
  - `screenshot_paths TEXT` — JSON array de caminhos de screenshots
  - `observacao TEXT`
  - `metodologia TEXT DEFAULT "M1"` — `M1`, `M2` ou `M3`
  - `ipca_percentual REAL` — percentual IPCA acumulado (apenas M3)
  - `user_id INTEGER` — servidor que avaliou
  - `updated_at TEXT`
- `audit_log`: registro de ações administrativas sensíveis (desfazer avaliações). Campos: `action`, `asset_id`, `admin_id`, `target_user_id`, `justificativa`, `created_at`.

### Agrupamento de bens
A chave de grupo é `COALESCE(tipo,'') || '~~' || material || '~~' || marca || '~~' || modelo`. Bens principais (tipo IS NULL) e agregações (tipo = 'Agregação') são grupos separados mesmo com mesmo material+marca+modelo. Todas as queries de propagação, contagem única e distribuição usam `COALESCE(tipo,'')` para respeitar essa separação.

### Distribuição
`assign_by_unique_groups(planilha, n_grupos, user_id)`: seleciona N grupos únicos ainda não atribuídos de uma planilha e atribui todos os bens de cada grupo ao servidor. Garante que nenhum grupo seja dividido entre servidores.

### Metodologias de avaliação
- **M1 – Pesquisa de mercado**: servidor registra preços + prints; valor = média (editável).
- **M2 – Acervo patrimonial**: idêntico ao M1, botões de busca em e-commerce ocultos.
- **M3 – Correção IPCA**: valor = `valor_contabil × (1 + ipca_percentual/100)`. IPCA buscado via `GET /api/ipca?data_inicio=dd/mm/yyyy` → API BCB série 433. Sem obrigatoriedade de prints.

### Frontend (`templates/`, `static/`)
- `base.html`: layout Bootstrap 5 + navbar contextual (admin vs. servidor). Servidores têm link "Senha" na navbar.
- `admin/`: dashboard (progresso global + por planilha com únicos), gerência de servidores, distribuição por grupos únicos, `usuario_bens.html` (tabela de bens com metodologia + desfazer com justificativa).
- `servidor/avaliar.html`: tela principal — sidebar com filtro de texto + toggle "Só pendentes", seletor de metodologia (radio M1/M2/M3), seção de preços (`#section-prices`), seção IPCA (`#section-ipca`), seção de prints (`#section-screenshots`, oculta em M3), campo de valor de mercado editável, observação, botão "Refazer" para desfazer a avaliação.
- `servidor/minha_senha.html`: formulário de alteração de senha.
- `static/app.js`: gerência de preços (add/remove/média), `switchMetodologia()` (alterna seções/labels/readonly), `fetchIPCA()` (async fetch para `/api/ipca`, lê `data-tombamento` e `data-vc` do elemento `#section-ipca`), `updateIPCAValor()` (calcula valor de mercado em M3), screenshots (compressão canvas JPEG 1280px, clipboard, drag&drop, file picker), validação no submit (M3 não exige preços nem prints), filtro da sidebar.

### Dados passados ao JS no template
Os valores de `valor_contabil` e `data_tombamento` são passados via atributos `data-vc` e `data-tombamento` no elemento `#section-ipca` (não como variáveis JS globais), para evitar dependência de ordem de execução entre scripts.

### Filtros Jinja2 (`app.py`)
- `brl`: formata float como `R$ 1.234,56`
- `planilha_curta`: extrai a parte após ` - ` do nome da planilha
- `strip_codigo`: remove código numérico entre parênteses do campo material

### API endpoints relevantes
- `GET /api/ipca?data_inicio=dd/mm/yyyy` — retorna `{"acumulado": 48.52}` (IPCA % acumulado desde a data até hoje). Usa `requests.get(..., verify=False)` por causa do proxy SSL da rede corporativa.
- `GET /screenshots/<path>` — serve screenshots salvos.

### Fluxo principal
1. Admin cria servidores (`/admin/usuarios`) e distribui bens (`/admin/distribuir`) por planilha, grupos únicos ou redistribuição.
2. Servidor acessa `/avaliar`, escolhe a metodologia (M1/M2/M3), avalia o bem e salva.
3. Ao salvar: `save_review()` propaga automaticamente para todos os bens com mesmo `tipo+material+marca+modelo` sem review (`INSERT OR IGNORE`), persistindo também `metodologia` e `ipca_percentual`.
4. Admin acompanha via dashboard e pode desfazer avaliações individuais com justificativa (`audit_log`).
5. Admin exporta resultados em `/admin/export` → gera `output/<planilha>_avaliado_<data>.xlsx` com colunas VMB (10) e metodologia (11) preenchidas.

## Arquivos de dados
- `planilhas_excel/`: 9 planilhas xlsx com os bens (NUNCA modificar)
- `reavaliacao.db`: banco SQLite gerado automaticamente
- `screenshots/`: prints salvos como `<asset_id>_<timestamp>_<idx>.jpg`
- `output/`: Excel exportado com avaliações preenchidas
