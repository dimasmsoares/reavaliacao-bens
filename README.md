# Sistema de Reavaliação de Bens Móveis

Sistema web interno desenvolvido para auxiliar a **Câmara dos Deputados** no processo periódico de reavaliação de bens móveis patrimoniais. O sistema organiza o trabalho de múltiplos servidores que pesquisam o valor de mercado de cada bem em plataformas de e-commerce e registram os valores encontrados junto com prints comprobatórios.

---

## Visão Geral

O processo de reavaliação exige que cada bem tenha seu **valor de mercado atual** pesquisado e documentado com imagens comprobatórias. Com 54.430 bens distribuídos em 9 planilhas Excel, o sistema permite que:

- O **administrador** distribua os bens entre os servidores e acompanhe o andamento em tempo real.
- Cada **servidor** acesse apenas sua parcela de bens, realize as pesquisas em múltiplas plataformas, registre todos os preços encontrados e anexe os prints correspondentes.
- Bens **idênticos** (mesmo material, marca e modelo) sejam avaliados uma única vez — a avaliação é propagada automaticamente para os demais.
- Ao final, os dados sejam exportados de volta para os arquivos Excel originais com a coluna de valor de mercado preenchida.

---

## Pré-requisitos

- Python 3.12 ou superior
- As planilhas Excel na pasta `planilhas_excel/` (já incluídas no repositório)

> **Compatibilidade:** Windows, Linux e macOS são totalmente suportados.

---

## Instalação e Inicialização

### 1. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 2. Iniciar o servidor

```bash
python app.py
```

Na primeira execução, o sistema automaticamente:
- Cria o banco de dados (`reavaliacao.db`)
- Cria o usuário administrador padrão
- Importa todos os bens das planilhas Excel para o banco

O servidor estará disponível em **http://localhost:5000**

> **Acesso inicial:** usuário `admin`, senha `admin123`  
> Altere a senha padrão antes de colocar o sistema em uso.

---

## Como Utilizar

### Perfil Administrador

#### 1. Cadastrar os Servidores

Acesse **Servidores** no menu superior e crie um login para cada servidor que participará do processo.

- Informe um nome de usuário (sem espaços, ex: `joao.silva`)
- Defina uma senha inicial (o servidor poderá usar esta senha ao longo do trabalho)

#### 2. Distribuir os Bens

Acesse **Distribuir** no menu superior. Existem três formas de atribuir bens:

| Modalidade | Quando usar |
|---|---|
| **Por planilha** | Para designar uma categoria inteira (ex: todas as impressoras) a um servidor específico |
| **Por quantidade** | Para dividir um número fixo de bens entre servidores, independentemente da categoria |
| **Redistribuir** | Para mover os bens ainda não avaliados de um servidor para outro (ex: em caso de licença) |

> Os bens já avaliados não são afetados pela redistribuição.

#### 3. Acompanhar o Andamento

O **Dashboard** (`/admin`) exibe:
- Progresso geral com total de bens avaliados
- Progresso individual de cada servidor (bens atribuídos vs. concluídos)
- Progresso por planilha/categoria

#### 4. Exportar os Resultados

Quando o trabalho estiver concluído (total ou parcialmente), clique em **Exportar Excel** no Dashboard. O sistema irá:

1. Gerar uma cópia de cada planilha original na pasta `output/`
2. Preencher a coluna **VALOR DE MERCADO (VMB)** com a média dos preços pesquisados
3. Preservar todas as fórmulas das colunas seguintes (fator de reavaliação, valor reavaliado, etc.), que recalcularão automaticamente ao abrir o arquivo no Excel

Os arquivos gerados seguem o padrão: `<nome_original>_avaliado_<data_hora>.xlsx`

---

### Perfil Servidor

#### Tela de Avaliação

Ao fazer login, o servidor é direcionado automaticamente ao seu próximo bem pendente.

```
┌──────────────────────────────────────────────────────────────────┐
│  Lista de bens  │  APARELHO TELEFÔNICO CELULAR - GRADIENTE TD-600│
│  (sidebar)      │  NRP · Tipo · Data de Tombamento · Vlr Contábil│
│                 │                                                  │
│  ✓ BEM 1        │  [Mercado Livre] [Amazon] [Google] [Buscapé]   │
│  ✓ BEM 2        │                                                  │
│  → BEM 3 ←      │  Preços encontrados                             │
│    BEM 4        │  R$[________] [+]                               │
│    BEM 5        │  [R$ 1.500,00 ×] [R$ 1.800,00 ×]               │
│    ...          │  Média (Valor de Mercado): R$ 1.650,00          │
│                 │                                                  │
│                 │  Prints da pesquisa                             │
│                 │  [thumb1 ×] [thumb2 ×] [+ Adicionar]           │
│                 │                                                  │
│                 │  [Anterior]  [Pular]  [Salvar e Próximo →]      │
└──────────────────────────────────────────────────────────────────┘
```

#### Passo a passo para avaliar um bem

1. **Leia as informações do bem**: o título exibe o nome completo no formato  
   `MATERIAL - MARCA MODELO`. NRP, tipo, data de tombamento e valor contábil aparecem abaixo.

2. **Pesquise o valor atual**: clique em um dos botões de busca. O sistema abrirá uma nova aba já com o nome completo do bem pesquisado:
   - Mercado Livre
   - Amazon
   - Google Shopping
   - Buscapé

3. **Registre cada preço encontrado**: no campo **Preços encontrados**, digite o valor e clique em **+** (ou pressione **Enter**). Repita para cada plataforma pesquisada. O **Valor de Mercado** (média) é calculado automaticamente.
   - Para remover um preço, clique no **×** ao lado do badge.

4. **Anexe os prints**: após registrar um preço, tire print da tela e anexe como comprovante. O print pode ser adicionado de três formas:
   - **Colar**: após copiar a imagem (`Print Screen` ou Snipping Tool), cole com `Ctrl+V`
   - **Arrastar**: arraste o arquivo de imagem para a área indicada
   - **Selecionar arquivo**: clique em **Adicionar print** e escolha o arquivo
   - Repita para adicionar prints de cada plataforma pesquisada.

5. **Salve**: clique em **Salvar e Próximo**. O sistema salva a avaliação e carrega automaticamente o próximo bem pendente.

#### Navegação

- **Anterior**: volta ao bem anterior (útil para corrigir uma avaliação já salva)
- **Pular**: avança para o próximo bem sem salvar (o bem pulado voltará à fila)
- A **sidebar** lateral lista todos os bens atribuídos, com indicação visual de concluído (✓) ou pendente

---

## Avaliação em Grupo

Muitos bens possuem o mesmo material, marca e modelo — diferindo apenas pelo NRP (número de registro patrimonial). Nesses casos, **basta avaliar um único bem do grupo**: o sistema propaga automaticamente o mesmo valor de mercado e prints para todos os demais bens com as mesmas características.

Ao acessar um bem que pertence a um grupo, um aviso é exibido indicando quantos bens serão avaliados automaticamente ao salvar:

> ℹ️ Este bem pertence a um grupo de **12** bens com o mesmo material, marca e modelo. Ao salvar esta avaliação, os demais **11** serão avaliados automaticamente.

---

## Estrutura de Arquivos

```
reavaliacao_bens/
├── app.py                  # Servidor Flask (ponto de entrada)
├── database.py             # Operações do banco de dados SQLite
├── excel_loader.py         # Importação das planilhas para o banco
├── excel_exporter.py       # Exportação dos resultados para Excel
├── requirements.txt        # Dependências Python
│
├── planilhas_excel/        # Planilhas originais (não modificadas)
│   ├── ND 44905206 - APARELHOS E EQUIPAMENTOS DE COMUNICAÇÃO.xlsx
│   ├── ND 44905233 - EQUIPAMENTOS PARA ÁUDIO, VÍDEO E FOTO.xlsx
│   ├── ND 44905235 - EQUIPAMENTOS DE PROCESSAMENTO DE DADOS.xlsx
│   ├── ND 44905241 - EQUIPAMENTOS DE TIC (COMPUTADORES).xlsx
│   └── ... (demais planilhas)
│
├── templates/
│   ├── base.html           # Layout base com navbar
│   ├── login.html
│   ├── admin/              # Telas do administrador
│   │   ├── dashboard.html
│   │   ├── usuarios.html
│   │   ├── editar_usuario.html
│   │   └── distribuir.html
│   └── servidor/
│       └── avaliar.html    # Tela principal de avaliação
│
├── static/
│   ├── style.css
│   └── app.js              # Lógica de preços, clipboard, drag&drop
│
├── reavaliacao.db          # Banco de dados (gerado automaticamente)
├── screenshots/            # Prints salvos (gerado automaticamente)
└── output/                 # Excel exportados (gerado automaticamente)
```

---

## Informações Técnicas

| Item | Detalhe |
|---|---|
| Linguagem | Python 3.12 |
| Framework web | Flask 3.x |
| Banco de dados | SQLite (modo WAL) |
| Leitura de Excel | openpyxl |
| Processamento de imagens | Pillow |
| Interface | Bootstrap 5 + JavaScript puro |
| Autenticação | Sessão server-side + hash werkzeug |
| Compatibilidade | Windows · Linux · macOS |

### Segurança

- As senhas são armazenadas como hashes (nunca em texto puro)
- Cada servidor só consegue visualizar e avaliar os bens atribuídos a ele
- As planilhas Excel originais nunca são alteradas; a exportação sempre gera novos arquivos

### Backup

O arquivo `reavaliacao.db` contém todos os dados do sistema (usuários, distribuições e avaliações). Recomenda-se fazer cópias regulares deste arquivo durante o processo de reavaliação.

---

## Dependências

```
flask       — framework web
openpyxl    — leitura e escrita de arquivos .xlsx
pillow      — processamento das imagens de comprovante
```
