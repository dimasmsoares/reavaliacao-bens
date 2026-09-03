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

### Backend (`app.py`, `database.py`, `excel_loader.py`, `excel_exporter.py`, `pdf_report.py`)
- **`app.py`**: Flask app com rotas de autenticação, admin e servidor. Na inicialização: cria banco, admin padrão e importa as planilhas (idempotente). Usa `requests as http_requests` com `verify=False` para a API do BCB (proxy SSL corporativo). Importa `date` de `datetime` para o endpoint `/api/ipca`.
- **`database.py`**: Todas as operações SQLite. Funções nomeadas por entidade (`get_user_*`, `assign_*`, `get_*_progress`, etc.). Funções de remoção de avaliação: `delete_review(asset_id, user_id)` — cascata no grupo do servidor; `delete_review_single(asset_id)` — só este bem; `admin_delete_review(...)` — admin, bem único + audit_log; `admin_delete_review_group(...)` — admin, grupo inteiro + audit_log por bem. `get_group_reviewed_count(asset_id, user_id)` retorna quantas avaliações existem no grupo daquele servidor. `delete_user(user_id)` apaga também as reviews feitas pelo servidor removido (bens voltam a pendentes), além de liberar assignments. `get_reviews_for_report(user_id=None)` retorna os bens avaliados (com dados do bem, da avaliação e do avaliador) para o relatório PDF; `user_id=None` traz todos, informado restringe a um servidor.
- **`excel_loader.py`**: Lê cada `.xlsx` com `openpyxl`. Detecta dinamicamente a linha de cabeçalho via `_find_data_start()` (busca "NRP" nas primeiras 20 linhas; fallback = 8). Commita por planilha para ser resiliente a interrupções.
- **`excel_exporter.py`**: Copia os `.xlsx` originais para `output/` e preenche a coluna 10 (VMB) e coluna 11 (metodologia: `M1`/`M2`/`M3`).
- **`pdf_report.py`**: Gera o relatório PDF (`reportlab`) dos bens já avaliados via `generate_pdf_report(user_id=None, user_name=None)`. Agrupa em uma única entrada os bens com mesma assinatura de avaliação (planilha+tipo+material+marca+modelo + mesmos `valor_mercado`/`metodologia`/`ipca_percentual`/`observacao`/`screenshot_paths`/`user_id`), listando os NRPs incluídos. Cada entrada mostra metodologia, valor de mercado, avaliador, data, observação (se houver) e as imagens (lidas de `SCREENSHOTS_DIR`).

### Banco de dados (SQLite WAL)
- `users`: admin + servidores com senha hash (werkzeug)
- `assets`: 54.430 bens importados das planilhas (somente leitura lógica). Campos relevantes: `tipo TEXT` (NULL = bem principal, "Agregação" = agregação), `material`, `marca`, `modelo`, `data_tombamento TEXT` (formato `dd/mm/yyyy`), `valor_contabil REAL`, `valor_atual REAL`.
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
- `audit_log`: registro de ações administrativas sensíveis (desfazer avaliações). Campos: `action`, `asset_id`, `admin_id`, `target_user_id`, `justificativa`, `created_at`. Ao desfazer um grupo, cada bem removido gera uma entrada separada.

### Agrupamento de bens
A chave de grupo é `COALESCE(tipo,'') || '~~' || material || '~~' || marca || '~~' || modelo`. Bens principais (tipo IS NULL) e agregações (tipo = 'Agregação') são grupos separados mesmo com mesmo material+marca+modelo. Todas as queries de propagação, contagem única e distribuição usam `COALESCE(tipo,'')` para respeitar essa separação. Índice `idx_assets_group (planilha, tipo, material, marca, modelo)` acelera essas queries de agrupamento.

### Distribuição
- `assign_by_unique_groups(planilha, n_grupos, user_id)`: seleciona N grupos únicos ainda não atribuídos de uma planilha e atribui todos os bens de cada grupo ao servidor. Garante que nenhum grupo seja dividido entre servidores.
- `assign_balanced_spread(user_ids)`: redistribui **todos** os bens pendentes (sem review, de qualquer planilha) entre os servidores em `user_ids`. Como avaliar 1 bem de um grupo propaga para os demais do mesmo grupo, a unidade real de esforço é o grupo, não o bem — a função ordena todos os grupos por tamanho decrescente e atribui cada um ao servidor com menos grupos no momento. Isso espalha os grupos gigantes (centenas/milhares de bens idênticos) entre servidores diferentes antes de nivelar o restante. Acionado pelo botão "Distribuição Balanceada" em `/admin/distribuir` (modo `balanceada`).
- `clear_pending_assignments()`: remove as atribuições de bens ainda **não avaliados** (preserva as de bens já avaliados). Usado internamente por `assign_balanced_spread` e exposto sozinho pelo botão "Desfazer Distribuição" em `/admin/distribuir` (modo `desfazer_distribuicao`), que zera toda a distribuição pendente sem tocar em avaliações já feitas.

### Metodologias de avaliação
- **M1 – Pesquisa de mercado**: servidor registra preços + prints; valor = média (editável).
- **M2 – Acervo patrimonial**: idêntico ao M1, botões de busca em e-commerce ocultos.
- **M3 – Correção IPCA**: valor = `valor_contabil × (1 + ipca_percentual/100)`. IPCA buscado via `GET /api/ipca?data_inicio=dd/mm/yyyy` → API BCB série 433. Sem obrigatoriedade de prints.

### Frontend (`templates/`, `static/`)
- `base.html`: layout Bootstrap 5 + navbar contextual (admin vs. servidor). Servidores têm link "Senha" na navbar.
- `admin/`: dashboard (progresso global + por planilha com únicos), gerência de servidores, distribuição por grupos únicos, `usuario_bens.html` (tabela de bens com metodologia + desfazer com justificativa; quando o bem tem similares avaliados, exibe checkbox para desfazer o grupo inteiro).
- `servidor/avaliar.html`: tela principal — sidebar com filtro de texto + toggle "Só pendentes", seletor de metodologia (radio M1/M2/M3), botões de pesquisa (`#section-search-links`: Mercado Livre/Amazon/Google Shopping/Buscapé + Claude/ChatGPT/Gemini com prompt de pesquisa pré-preenchido via query string e copiado para a área de transferência, classe `.btn-ai-search`), seção de preços (`#section-prices`), seção IPCA (`#section-ipca`), seção de prints (`#section-screenshots`, oculta em M3), campo de valor de mercado editável, observação, botão "Refazer" que abre modal — se `group_reviewed_count > 1` oferece opção de desfazer só este bem ou todos os similares do grupo.
- `servidor/minha_senha.html`: formulário de alteração de senha.
- `static/app.js`: gerência de preços (add/remove/média), `switchMetodologia()` (alterna seções/labels/readonly), `fetchIPCA()` (async fetch para `/api/ipca`, lê `data-tombamento` e `data-vc` do elemento `#section-ipca`), `updateIPCAValor()` (calcula valor de mercado em M3), screenshots (compressão canvas JPEG 1280px, clipboard, drag&drop, file picker), botões `.btn-ai-search` (copiam `data-ai-prompt` para a área de transferência via `navigator.clipboard`), validação no submit (M3 não exige preços nem prints), filtro da sidebar.

### Dados passados ao JS no template
Os valores de `valor_contabil` e `data_tombamento` são passados via atributos `data-vc` e `data-tombamento` no elemento `#section-ipca` (não como variáveis JS globais), para evitar dependência de ordem de execução entre scripts.

### Filtros Jinja2 (`app.py`)
- `brl`: formata float como `R$ 1.234,56`
- `planilha_curta`: extrai a parte após ` - ` do nome da planilha
- `strip_codigo`: remove código numérico entre parênteses do campo material

### API endpoints relevantes
- `GET /api/ipca?data_inicio=dd/mm/yyyy` — retorna `{"acumulado": 48.52}` (IPCA % acumulado desde a data até hoje). Usa `requests.get(..., verify=False)` por causa do proxy SSL da rede corporativa.
- `GET /screenshots/<path>` — serve screenshots salvos.
- `POST /admin/export/pdf` — gera e baixa o relatório PDF global (todos os servidores).
- `POST /admin/usuarios/<user_id>/export/pdf` — gera e baixa o relatório PDF restrito a um servidor.

### Fluxo principal
1. Admin cria servidores (`/admin/usuarios`) e distribui bens (`/admin/distribuir`) por planilha, grupos únicos ou redistribuição.
2. Servidor acessa `/avaliar`, escolhe a metodologia (M1/M2/M3), avalia o bem e salva.
3. Ao salvar: `save_review()` propaga automaticamente para todos os bens com mesmo `tipo+material+marca+modelo` sem review (`INSERT OR IGNORE`), persistindo também `metodologia` e `ipca_percentual`.
4. Admin acompanha via dashboard e pode desfazer avaliações com justificativa (`audit_log`). Ao desfazer, se o bem pertence a um grupo com múltiplos similares avaliados, o modal oferece checkbox para reverter o grupo inteiro (cada bem gera entrada no `audit_log`). O servidor também pode desfazer pela tela de avaliação, com escolha entre "só este bem" ou "todos os similares".
5. Admin exporta resultados em `/admin/export` → gera `output/<planilha>_avaliado_<data>.xlsx` com colunas VMB (10) e metodologia (11) preenchidas.
6. Admin gera relatório PDF dos bens avaliados (botão "Exportar PDF" no dashboard ou na tela de bens de um servidor) → `pdf_report.generate_pdf_report()`.

## Arquivos de dados
- `planilhas_excel/`: 9 planilhas xlsx com os bens (NUNCA modificar)
- `reavaliacao.db`: banco SQLite gerado automaticamente
- `screenshots/`: prints salvos como `<asset_id>_<timestamp>_<idx>.jpg`
- `output/`: Excel exportado com avaliações preenchidas
