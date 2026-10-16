# Dados

Os arquivos brutos **não são versionados**, por causa do tamanho.

| Item | Valor |
|---|---|
| Fonte | ANP: Série Histórica de Preços de Combustíveis (combustíveis automotivos) |
| Página | https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/serie-historica-de-precos-de-combustiveis |
| Arquivos | `ca-2023-01` … `ca-2025-02` (6 semestres). GLP fora do escopo |
| Formato | CSV `;`, UTF-8 com BOM, CRLF, decimal com vírgula |
| Data do download | 16/10/2026 |

| Arquivo | Linhas (sem cabeçalho) | Observação |
|---|---:|---|
| ca-2023-01.csv | 431.576 | |
| ca-2023-02.csv | 472.424 | |
| ca-2024-01.csv | 477.154 | |
| ca-2024-02.csv | 421.382 | |
| ca-2025-01.csv | 429.523 | inclui 9.114 linhas vazias |
| ca-2025-02.csv | 384.208 | CNPJ sem máscara |
| **Total** | **2.616.267** | |

O arquivo `ca-2022-01` não está mais disponível no portal (HTTP 404). Por isso o recorte é 2023–2025.

## Por que esta fonte e este recorte

- **Por que a ANP:** CSV simples (bom para mostrar o ETL), dimensões naturais (tempo, geografia, produto),
  problemas reais de qualidade para a EDA e um tema que todo mundo entende (preço na bomba).
  Alternativas descartadas: DATASUS (formato DBC e dicionários complexos), INEP (microdados pesados demais para o prazo)
  e Portal da Transparência (dimensões menos intuitivas para leigos).
- **Por que 2023–2025:** os 3 anos completos mais recentes. A ideia inicial era 2022–2024, para comparar antes e depois
  do corte de ICMS, mas sem o 1º semestre de 2022 essa comparação perdeu o "antes". A série inteira (desde 2004)
  deixaria a carga e a EDA lentas sem acrescentar à história.
- **Por que sem GLP:** vem em arquivos separados e tem outra unidade (R$/13 kg).
- **Preços nominais (sem correção pela inflação):** a pergunta compara combustíveis no mesmo mês (paridade),
  e essa razão não é afetada pela inflação.

Os zips contêm arquivos chamados `Preços semestrais - AUTOMOTIVOS_AAAA.SS.csv`. O passo 2 do README raiz os renomeia para `ca-AAAA-SS.csv`, padrão que o Pentaho espera.
