# etanol-ou-gasolina-bi

**Etanol ou gasolina? Um pipeline de BI de ponta a ponta com dados da ANP.**

Projeto integrador do MBA: do dado bruto à decisão de negócio, com **Pentaho (DW) → Python/Pandas (EDA) → Metabase (dashboard)**.

**Fonte:** ANP, Série Histórica de Preços de Combustíveis, jan/2023 a dez/2025. São 2,6 milhões de coletas em 13,5 mil postos de 462 municípios.

**Pergunta de negócio:** *onde e quando vale a pena abastecer com etanol?*

**Achado:** na média nacional, o etanol compensou de ago/2023 a dez/2024 (com jul–ago/2024 no limite, em 0,70) e deixou de compensar em 2025 (paridade de 0,716).
Em 2025 ele só valeu a pena em **4 de 27 estados (MS, MT, SP e PR)** e em 34% dos municípios pesquisados.
A regra dos 70% depende de onde você mora.

![Dashboard no Metabase](docs/img/metabase_dashboard.png)

> Para abrir o dashboard, veja [Acessar o dashboard (Metabase)](#acessar-o-dashboard-metabase).

## Arquitetura

```
 data/raw/ca-*.csv  (6 arquivos semestrais da ANP)
        │  Pentaho trf_01: Text file input → Table output           (sem regra de negócio)
        ▼
 stg.precos_bruto   (2.616.267 linhas, texto puro + arquivo_origem)
        │  Pentaho trf_03: filtro de vazias, CNPJ só dígitos,       (regras vindas da EDA)
        │                  unidade, sinônimos de bandeira, tipagem
        ▼
 stg.precos_tratado
        │  Pentaho trf_02/04/05: dim_data gerada, dimensões por chave natural,
        │                        dedup no grão, lookups com default -1
        ▼
 dw: fato_coleta_preco + 5 dimensões (star schema) ── SQL: outliers (3×IQR), validações → dw.log_carga
        │  SQL: views
        ▼
 mart.vw_*  ──────────────┬──► notebooks/eda_combustiveis.ipynb  (EDA + valores de referência)
                          ├──► Metabase (dashboard de página única, provisionado por código)
                          └──► Power BI (opcional: medidas DAX e guia prontos)
```

**Modelo estrela.** Grão: 1 preço × 1 produto × 1 posto × 1 data.

```
                 dim_data
                    │
 dim_localidade ── fato_coleta_preco ── dim_produto
                    │            │
               dim_revenda   dim_bandeira
```

| Etapa | Ferramenta | Onde |
|---|---|---|
| Banco do DW | PostgreSQL 16 (Docker) | [`infra/`](infra), [`sql/`](sql) |
| ETL e modelo dimensional | Pentaho Data Integration 9.4 | [`pentaho/`](pentaho) |
| Análise exploratória | Python, Pandas, Matplotlib | [`notebooks/`](notebooks) |
| Dashboard e storytelling | Metabase 0.63 (Docker) · Power BI opcional | [`metabase/`](metabase) · [`powerbi/`](powerbi) |

## Principais decisões

| Decisão | Por quê | Detalhes |
|---|---|---|
| ANP, 2023–2025, sem GLP | Base pública, CSV simples, tema que todo mundo entende. O 1º semestre de 2022 saiu do portal, então a comparação antes/depois do ICMS perdeu o "antes" | [`data/`](data/README.md#por-que-esta-fonte-e-este-recorte) |
| PostgreSQL em Docker, schemas por camada | Pentaho grava via JDBC e Power BI/Metabase/Python leem nativamente. Usuário `etl` escreve, `bi_reader` só lê | [`infra/`](infra), [`sql/`](sql) |
| Camadas, star schema, grão, SCD 1, full reload, outliers | Rastreabilidade de ponta a ponta e regra de limpeza em um lugar só | [`pentaho/`](pentaho/README.md#decisões-de-modelagem-e-carga) |
| EDA em duas fases | A parte 1 (lê `stg`) descobre problemas que viram regras no ETL. A parte 2 (lê `mart`) valida os números: o dashboard precisa bater com o notebook | [`notebooks/`](notebooks) |
| Pergunta: "etanol ou gasolina?" | É acionável para leigos e tem a regra dos 70% como fio condutor. "Antes/depois do ICMS" perdeu o "antes" (sem 2022), e "bandeira branca é mais barata?" virou achado secundário (~R$ 0,18/l) | [Dashboard](metabase/README.md) |
| Metabase no lugar do Power BI | O ambiente é Linux, e o dashboard fica provisionado por código. Power BI segue documentado | [`metabase/`](metabase/README.md#por-que-metabase) |

## Documentação

- [ETL no Pentaho](pentaho/README.md): fluxo do job, steps e resultado da última carga.
- [Dashboard no Metabase](metabase/README.md)
- [Guia do dashboard no Power BI (opcional)](powerbi/GUIA_DASHBOARD.md)

## Como inicializar o projeto

### Pré-requisitos

| Item | Versão / observação |
|---|---|
| Docker + Docker Compose | Sobe o Postgres e o Metabase |
| Python | 3.12, com `venv` (no Ubuntu: `sudo apt install python3-venv`; sem sudo, ver o passo 5) |
| Pentaho Data Integration (PDI) | 9.4 CE, com Java 11. O script procura em `~/Apps/Pentaho`. Se instalou em outro lugar: `export PDI_HOME=/caminho/do/pdi` |
| `curl` e `unzip` | Para baixar e extrair os dados da ANP |
| Memória | Pelo menos 8 GB de RAM. O ETL usa até 6 GB. Com menos memória: `export PENTAHO_DI_JAVA_OPTIONS="-Xms1g -Xmx3g"` |
| Power BI Desktop | Opcional, só no Windows |

### Passo a passo (primeira vez)

**1. Configure o `.env`.** Copie o modelo e troque todos os valores de exemplo:

```bash
cp .env.example .env
```

| Variável | Para quê |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Banco do DW e superusuário do Postgres |
| `POSTGRES_PORT` | Porta do Postgres na máquina (padrão `5432`). Troque se já houver outro Postgres usando essa porta |
| `ETL_PASSWORD` | Senha do usuário `etl` (escrita, usado pelo Pentaho) |
| `BI_PASSWORD` | Senha do usuário `bi_reader` (somente leitura: notebook, Metabase e Power BI) |
| `METABASE_PORT` | Porta da interface do Metabase (padrão `3000`) |
| `MB_ADMIN_EMAIL`, `MB_ADMIN_PASSWORD` | Login do Metabase (ver [Acessar o dashboard](#acessar-o-dashboard-metabase)) |

O `.env` está no `.gitignore` e **nunca vai para o GitHub**. Cada integrante tem o seu.

**2. Suba os containers e prepare o banco:**

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d    # Postgres + Metabase
until docker exec dw_combustiveis pg_isready -h localhost -q; do sleep 2; done   # espera o Postgres aceitar conexões
./sql/setup_db.sh                                                   # schemas, usuários e tabelas -> "Banco pronto."
```

**3. Baixe os dados da ANP** (cerca de 430 MB depois de extraídos; detalhes em [`data/README.md`](data/README.md)):

```bash
cd data/raw && for s in 2023-01 2023-02 2024-01 2024-02 2025-01 2025-02; do
  curl -sSLO "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/shpc/dsas/ca/ca-$s.zip"; done
for z in *.zip; do unzip -o -q "$z"; done && rm *.zip
for f in *AUTOMOTIVOS_*.csv; do mv "$f" "ca-$(echo "$f" | grep -oE '[0-9]{4}\.[0-9]{2}' | tr . -).csv"; done
cd ../..
ls data/raw    # devem aparecer ca-2023-01.csv ... ca-2025-02.csv (6 arquivos)
```

**4. Rode o ETL** (cerca de 5 minutos):

```bash
./pentaho/run_etl.sh    # deve terminar com "Kitchen - Finished!" e o log em pentaho/logs/
```

**5. Crie o ambiente Python e execute o notebook:**

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/eda_combustiveis.ipynb
```

Se o primeiro comando falhar com "ensurepip is not available" e você não tiver `sudo` para instalar o `python3-venv`,
crie o ambiente sem pip e instale o pip pelo instalador oficial:

```bash
python3 -m venv --without-pip .venv
curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
.venv/bin/pip install -r requirements.txt
```

**6. Monte o dashboard:**

```bash
.venv/bin/python metabase/provisionar.py    # -> Dashboard pronto: http://localhost:3000/dashboard/<id>
```

Depois, faça o login conforme [Acessar o dashboard](#acessar-o-dashboard-metabase).
O Power BI é opcional: siga [`powerbi/GUIA_DASHBOARD.md`](powerbi/GUIA_DASHBOARD.md).

### Verificar se está tudo certo

**1. Validações da carga.** As 9 linhas devem ter `ok = t`:

```bash
set -a; source .env; set +a
docker exec dw_combustiveis psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT verificacao, valor, ok FROM mart.vw_log_carga"
```

| Verificação | Valor esperado |
|---|---:|
| `linhas_stg_bruto` (= soma dos CSVs) | 2.616.267 |
| `linhas_vazias_descartadas` | 9.114 |
| `linhas_stg_tratado` | 2.607.153 |
| `linhas_fato` | 2.607.139 |
| `duplicatas_removidas_no_grao` | 14 |
| `linhas_fato_com_chave_-1` | 0 |
| `outliers_marcados` | 11.951 |
| `dias_faltando_dim_data` | 0 |
| `linhas_com_valor_compra` | 0 |

**2. Números do dashboard.** No Metabase, com **Ano = 2025** e sem UF, os cards devem mostrar os mesmos valores que o notebook
calculou em Pandas ([`docs/kpis_referencia.csv`](docs/kpis_referencia.csv)):

| Card | Valor esperado |
|---|---:|
| Preço médio da gasolina | R$ 6,230 |
| Preço médio do etanol | R$ 4,458 |
| Paridade etanol ÷ gasolina | 0,716 |
| Postos pesquisados | 8.699 |
| No Brasil, o etanol compensou em… | 4 de 27 estados |
| Municípios onde o etanol compensou | 33,9% |

**3. Filtro de UF.** Escolha **UF = SP** (Ano = 2025). Os KPIs devem mudar para gasolina R$ 6,056, etanol R$ 4,104 e
paridade 0,678, e a manchete continua nacional ("4 de 27").

### No dia a dia

| Situação | O que fazer |
|---|---|
| Ligou a máquina de novo | `docker compose --env-file .env -f infra/docker-compose.yml up -d` e abrir http://localhost:3000. Não é preciso rodar ETL nem `provisionar.py` |
| Desligar | `docker compose --env-file .env -f infra/docker-compose.yml stop`. Os dados ficam nos volumes |
| Mudou o ETL ou os dados | `./pentaho/run_etl.sh`. O dashboard lê a `mart`, então já mostra os novos números |
| Mudou o dashboard no código | `.venv/bin/python metabase/provisionar.py` (o dashboard ganha um novo id) |

### Problemas na inicialização

| Sintoma | Causa e solução |
|---|---|
| `setup_db.sh` falha com "connection refused" ou "the database system is starting up" | O Postgres ainda está subindo. Rode a linha do `pg_isready` do passo 2 e tente de novo |
| `docker compose up` falha com "port is already allocated" | A porta já está em uso (outro Postgres ou outro Metabase). Troque `POSTGRES_PORT` ou `METABASE_PORT` no `.env` |
| `run_etl.sh`: "kitchen.sh: No such file or directory" | O PDI não está em `~/Apps/Pentaho`. Defina `export PDI_HOME=/caminho/do/pdi` |
| ETL falha com `OutOfMemoryError` | Pouca RAM. Reduza a memória do Java (ver Pré-requisitos) e feche outros programas |
| `linhas_stg_bruto` diferente de 2.616.267 | Falta algum CSV, ou ele está com outro nome. Confira o `ls data/raw` do passo 3 |
| Notebook falha ao conectar no banco | Confira `BI_PASSWORD` e `POSTGRES_PORT` no `.env` e se o container `dw_combustiveis` está no ar (`docker ps`) |

## Acessar o dashboard (Metabase)

**Resumo:** o login é o `MB_ADMIN_EMAIL` e a `MB_ADMIN_PASSWORD` do **seu** `.env`, em **http://localhost:3000**.
Esse usuário só passa a existir depois que você roda `metabase/provisionar.py` pela primeira vez.

O Metabase **não vem com usuário pronto**. Quem cria a conta de administrador é o script de provisionamento,
usando o e-mail e a senha do `.env`. Não existe login padrão (`admin`/`admin` não funciona).

### 1. Defina as credenciais no `.env`

No `.env` (passo 1 da [inicialização](#passo-a-passo-primeira-vez)), preencha:

| Variável | Para quê | Exemplo |
|---|---|---|
| `MB_ADMIN_EMAIL` | e-mail de login do administrador (precisa ter formato de e-mail, não precisa existir) | `voce@exemplo.com` |
| `MB_ADMIN_PASSWORD` | senha de login: mínimo de 8 caracteres, com letras **e** números | `Combustivel2025` |
| `METABASE_PORT` | porta da interface web | `3000` |

### 2. Suba os containers e crie o administrador

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d   # Postgres + Metabase
.venv/bin/python metabase/provisionar.py
# -> Dashboard pronto: http://localhost:3000/dashboard/<id>
```

Na primeira vez o Metabase leva cerca de 1 minuto para iniciar, e o script espera sozinho.
Para conferir se ele já está no ar: `curl -s http://localhost:3000/api/health` deve responder `{"status":"ok"}`
(troque `3000` se você mudou o `METABASE_PORT` no `.env`).

O script cria, nesta ordem: o administrador, a conexão com o DW (usuário somente leitura `bi_reader`, camada `mart`),
a coleção **Combustíveis MBA** e o dashboard.

> **Atenção:** se ao abrir o navegador aparecer a tela de boas-vindas do Metabase ("Vamos começar" / "Let's get started"),
> **não preencha**. Ela só aparece porque o `provisionar.py` ainda não rodou. Rode o script e recarregue a página.
> Se você criar a conta pela tela com outro e-mail ou senha, o script não consegue entrar (ver tabela abaixo).

### 3. Faça o login

1. Abra **http://localhost:3000** (ou a porta definida em `METABASE_PORT`).
2. **E-mail:** o valor de `MB_ADMIN_EMAIL`. **Senha:** o valor de `MB_ADMIN_PASSWORD`.
3. No menu lateral: **Coleções → Combustíveis MBA → "Etanol ou gasolina? Preços de combustíveis 2023–2025"**.
   Também dá para usar o link impresso pelo script.
4. Use os filtros **Ano** e **UF** no topo. São listas de seleção, e o padrão é o ano mais recente.

A sessão fica salva no navegador. Nas próximas vezes basta `docker compose ... up -d` e abrir o endereço.
Só é preciso rodar o `provisionar.py` de novo se o dashboard mudar no código. Cada execução arquiva o dashboard
anterior e cria outro com **novo id**, então links antigos (`/dashboard/<id>`) deixam de valer.
Para compartilhar, prefira o caminho pela coleção **Combustíveis MBA**.

### Problemas comuns

| Situação | O que fazer |
|---|---|
| A página não abre / "conexão recusada" | O container ainda está iniciando ou caiu. Veja `docker ps` e `docker logs -f metabase_combustiveis` |
| Script falha com `POST /session -> 401` ou "senha incorreta" no login | O administrador já existe com outra senha (o `.env` mudou depois da primeira execução, ou a conta foi criada pela tela). Use a senha antiga ou recrie o Metabase do zero (linha abaixo) |
| Esqueci a senha / quero recriar do zero | `docker compose --env-file .env -f infra/docker-compose.yml rm -sf metabase && docker volume rm infra_mbdata`, depois suba de novo e rode o `provisionar.py`. Apaga só o Metabase, o DW fica intacto |
| Script falha com `POST /setup -> 400` | Leia a mensagem completa do erro. As causas mais comuns são senha fraca (use pelo menos 8 caracteres com letras e números em `MB_ADMIN_PASSWORD`) ou e-mail inválido em `MB_ADMIN_EMAIL` |
| Porta 3000 ocupada | Troque `METABASE_PORT` no `.env` (ex.: `3001`), suba de novo e acesse `http://localhost:3001` |
| Acessar de outra máquina da rede (ex.: a outra pessoa da dupla) | `http://<IP-da-máquina>:3000` (ou a porta do `METABASE_PORT`). O IP sai de `hostname -I` |
| Dar acesso à outra pessoa da dupla | Logado como admin: **Configurações de admin → Pessoas → Convidar alguém**. Melhor do que compartilhar a senha do admin |
| `provisionar.py` falha com `500` e "Unique index or primary key violation" | O banco interno do Metabase (H2) se corrompeu, geralmente depois de um desligamento brusco da máquina. Recrie o Metabase do zero (linha "Esqueci a senha" acima): o dashboard é recriado pelo script e o DW não é afetado |
| Dashboard sem dados | Confira se o ETL rodou (`./pentaho/run_etl.sh`) e se o container `dw_combustiveis` está no ar (`docker ps`) |

Mais detalhes (estrutura do dashboard e equivalência SQL × DAX) em [`metabase/README.md`](metabase/README.md).

## Equipe

| Integrante | Responsabilidade principal |
|---|---|
| Gabriel Cristian Queiroga | Infraestrutura, modelagem dimensional, ETL (Pentaho) |
| Maria Alice Albuquerque | EDA (Python), dashboard (Metabase) e DAX (Power BI, opcional) |
