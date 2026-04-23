# Sistema de Reavaliação de Bens Móveis

Sistema web interno desenvolvido para auxiliar a **Câmara dos Deputados** no processo periódico de reavaliação de bens móveis patrimoniais. O sistema organiza o trabalho de múltiplos servidores que pesquisam o valor de mercado de cada bem e registram os valores encontrados junto com prints comprobatórios.

---

## Visão Geral

O processo de reavaliação exige que cada bem tenha seu **valor de mercado atual** pesquisado e documentado. Com 54.430 bens distribuídos em 9 planilhas Excel, o sistema permite que:

- O **administrador** distribua os bens entre os servidores e acompanhe o andamento em tempo real.
- Cada **servidor** acesse apenas sua parcela de bens, realize as pesquisas, registre os preços e annexe os prints correspondentes.
- Bens **idênticos** (mesmo tipo, material, marca e modelo) sejam avaliados uma única vez — a avaliação é propagada automaticamente para os demais.
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

#### 2. Distribuir os Bens

Acesse **Distribuir** no menu superior. Existem três formas de atribuir bens:

| Modalidade | Quando usar |
|---|---|
| **Por planilha** | Designa uma categoria inteira a um servidor específico |
| **Por grupos únicos** | Atribui N grupos únicos de uma planilha. Cada grupo (mesmo tipo+material+marca+modelo) conta como 1, mas todos os bens do grupo são distribuídos juntos |
| **Redistribuir** | Move os bens ainda não avaliados de um servidor para outro (ex: licença) |

> Os bens já avaliados não são afetados pela redistribuição.

#### 3. Acompanhar o Andamento

O **Dashboard** (`/admin`) exibe:
- Progresso geral com total de bens avaliados
- Progresso individual de cada servidor
- Progresso por planilha, discriminando bens principais, agregações e grupos únicos

#### 4. Ver Bens de um Servidor

Na tela **Servidores**, clique em **Bens** para ver a lista completa de bens atribuídos a um servidor, com valor de mercado, metodologia utilizada, observação e data de avaliação.

Para desfazer uma avaliação, clique no botão de desfazer e informe a justificativa. Quando o bem pertence a um grupo com vários bens similares avaliados, o modal exibe um checkbox opcional **"Desfazer também para todos os bens similares do grupo"**, permitindo reverter o grupo inteiro de uma só vez. Todas as remoções são registradas no `audit_log`.

#### 5. Exportar os Resultados

Clique em **Exportar Excel** no Dashboard. O sistema gera cópias das planilhas originais em `output/` com:
- Coluna 10 (VMB) preenchida com o valor de mercado
- Coluna 11 com a metodologia utilizada (`M1`, `M2` ou `M3`)

---

### Perfil Servidor

#### Tela de Avaliação

Ao fazer login, o servidor é direcionado automaticamente ao seu próximo bem pendente. A sidebar lateral lista todos os bens atribuídos com filtro por texto e toggle "Só pendentes".

#### Metodologias de Avaliação

Cada bem deve ser avaliado com uma das três metodologias disponíveis, selecionadas por radio buttons no topo do formulário:

---

**M1 – Pesquisa de mercado**

Pesquisa o bem em plataformas de e-commerce. Links de busca diretos para Mercado Livre, Amazon, Google Shopping e Buscapé são fornecidos automaticamente.

1. Clique no botão da plataforma desejada (abre em nova aba já com o nome do bem).
2. No campo **Preços encontrados**, registre cada valor localizado e clique em **+** (ou Enter).
3. O **Valor de Mercado** é calculado automaticamente como a média dos preços. O valor pode ser editado manualmente se necessário.
4. Annexe os prints da pesquisa (Ctrl+V, arrastar ou selecionar arquivo).
5. Clique em **Salvar e Próximo**.

---

**M2 – Acervo patrimonial**

Idêntica à M1, mas voltada para consulta em acervos patrimoniais de referência. Os botões de busca em e-commerce são ocultados.

---

**M3 – Correção pelo IPCA**

Atualiza o valor contábil do bem desde a data de tombamento até hoje usando o IPCA acumulado.

1. O valor contábil e a data de tombamento aparecem para conferência.
2. Clique em **Buscar IPCA** — o sistema consulta automaticamente a API do Banco Central (série 433) e preenche o percentual acumulado.
3. O **Valor de Mercado** é calculado automaticamente: `valor_contábil × (1 + IPCA% / 100)`.
4. Se preferir conferir manualmente, use o link **Calculadora do Banco Central**.
5. Clique em **Salvar** (prints não são necessários nesta metodologia).

> M3 requer que o bem possua valor contábil e data de tombamento cadastrados.

---

#### Navegação

- **Anterior**: volta ao bem anterior
- **Pular**: avança para o próximo sem salvar
- **Refazer**: abre um modal para desfazer a avaliação atual. Se o bem pertence a um grupo com múltiplos similares avaliados, o modal oferece a opção de desfazer só este bem ou todos os similares do grupo
- A sidebar lista todos os bens com indicação visual de concluído (✓) ou pendente

#### Alterar Senha

O servidor pode alterar sua própria senha acessando **Senha** na navbar.

---

## Avaliação em Grupo

Bens com mesmo tipo, material, marca e modelo diferem apenas pelo NRP. **Basta avaliar um único bem do grupo**: o sistema propaga automaticamente o mesmo valor de mercado para todos os demais.

Ao acessar um bem de grupo, um aviso indica quantos bens serão avaliados automaticamente ao salvar.

> Os bens principais (tipo vazio) e suas agregações (tipo = "Agregação") formam grupos separados. Avaliar um principal não propaga para as agregações e vice-versa.

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
├── planilhas_excel/        # Planilhas originais (NUNCA modificar)
│
├── templates/
│   ├── base.html           # Layout base com navbar
│   ├── login.html
│   ├── admin/
│   │   ├── dashboard.html
│   │   ├── usuarios.html
│   │   ├── editar_usuario.html
│   │   ├── distribuir.html
│   │   └── usuario_bens.html   # Bens de um servidor (admin)
│   └── servidor/
│       ├── avaliar.html        # Tela principal de avaliação
│       └── minha_senha.html    # Alterar senha
│
├── static/
│   ├── style.css
│   └── app.js              # Lógica de preços, IPCA, screenshots, metodologias
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
| Leitura/escrita de Excel | openpyxl |
| Processamento de imagens | Pillow |
| Busca de IPCA | requests → API Banco Central (série 433) |
| Interface | Bootstrap 5 + JavaScript puro |
| Autenticação | Sessão server-side + hash werkzeug |
| Compatibilidade | Windows · Linux · macOS |

### Segurança

- Senhas armazenadas como hashes (werkzeug)
- Cada servidor só visualiza e avalia os bens atribuídos a ele
- As planilhas originais nunca são alteradas; a exportação sempre gera novos arquivos
- Ações administrativas sensíveis (desfazer avaliação) são registradas em `audit_log`

### Rede Corporativa

Em ambientes com proxy de inspeção SSL (ex: rede interna da Câmara), a chamada à API do Banco Central usa `verify=False` para contornar certificados auto-assinados na cadeia corporativa.

### Backup

O arquivo `reavaliacao.db` contém todos os dados do sistema. Recomenda-se fazer cópias regulares durante o processo de reavaliação.

---

## Dependências

```
flask       — framework web
openpyxl    — leitura e escrita de arquivos .xlsx
pillow      — processamento das imagens de comprovante
requests    — consulta à API do Banco Central (IPCA)
```
