# ETL: Pentaho Data Integration (PDI 9.4 CE)

```
job_carga_dw.kjb
 ├─ SQL  02_ddl_stg.sql / 03_ddl_dw.sql        cria estruturas (IF NOT EXISTS)
 ├─ trf_01_carga_staging   CSV ANP  ─────────► stg.precos_bruto      (texto puro + arquivo_origem)
 ├─ trf_02_dim_data        gerador de linhas ─► dw.dim_data           (calendário 2023–2025)
 ├─ trf_03_tratamento      stg.precos_bruto ──► stg.precos_tratado    (regras da EDA)
 ├─ trf_04_dimensoes       stg.precos_tratado ► dw.dim_localidade / revenda / produto / bandeira
 ├─ trf_05_fato            stg.precos_tratado ► dw.fato_coleta_preco  (dedup no grão + lookups)
 ├─ SQL  04_outliers.sql   marca fl_outlier (3×IQR por produto×mês)
 ├─ SQL  05_views_mart.sql views de consumo (Power BI / notebook)
 └─ SQL  06_validacoes.sql grava o checklist em dw.log_carga
 Qualquer falha → entrada "Falha" (abort)
```

| Transformação | Steps principais | Por quê |
|---|---|---|
| `trf_01` | Text file input (pasta + regex `ca-.*\.csv`, `;`, aspas, UTF-8) → Table output (truncate) | Staging fiel: dá para reprocessar sem baixar os arquivos de novo |
| `trf_02` | Generate rows → Add sequence → Calculator → JavaScript → Insert/Update | Calendário contínuo, nomes em português, idempotente |
| `trf_03` | Filter rows → String operations → Replace in string → Value mapper → Select values (tipagem) | Cada step é uma regra descoberta na EDA (ver notepad na tela) |
| `trf_04` | Table input (DISTINCT) → Value mapper → Insert/Update por chave natural | SCD tipo 1; `sk_*` gerada pelo banco e estável entre execuções |
| `trf_05` | Table input (ORDER BY grão + preço) → Unique rows → 5× Database lookup (cache total, default −1) → Table output | Garante o grão e que nenhuma linha fica sem chave. Se o mesmo posto tiver 2 preços no mesmo dia, fica sempre o menor: a carga dá o mesmo resultado em toda execução |

## Decisões de modelagem e carga

| Decisão | Justificativa |
|---|---|
| **Camadas** `stg` → `dw` → `mart` | A staging é cópia fiel do CSV: dá para reprocessar o DW sem baixar os arquivos de novo. Toda regra de limpeza fica em um lugar só (as transformações do Pentaho). Python, Metabase e Power BI só leem a `mart` e não corrigem dado |
| **Star schema** (1 fato + 5 dimensões) | Snowflake traria mais joins sem ganho nesse volume. Uma tabela única não demonstraria modelagem dimensional |
| **Grão:** 1 preço × 1 produto × 1 posto × 1 data | É o menor grão da fonte. Agregar antes impediria detectar outliers por posto e calcular mediana e dispersão. Consequência: preço médio não é aditivo (use média/mediana, nunca soma) |
| **Bandeira como dimensão própria**, ligada à fato | O posto pode trocar de bandeira. Na fato fica a bandeira vigente no dia da coleta, sem precisar de SCD tipo 2 na revenda |
| **`dim_data` gerada**, não extraída dos dados | Calendário contínuo, sem buracos nas semanas sem coleta. É pré-requisito para inteligência de tempo no DAX |
| **SCD tipo 1** em todas as dimensões | A mudança relevante (bandeira) já é tratada pela modelagem. SCD tipo 2 na revenda foi considerado e descartado: nenhuma pergunta de negócio depende do histórico de endereço ou razão social |
| **Chave `-1` ("Não informado")** em cada dimensão | Nenhuma linha da fato fica sem chave. A validação conta essas linhas (hoje: 0) |
| **Full reload**, não incremental | Os arquivos são semestrais e históricos, e a carga cabe em ~4 min. Incremental exigiria controle de *watermark* sem benefício. Em produção, com carga semanal, seria incremental por `arquivo_origem` ou data da coleta |
| **Outliers marcados** (`fl_outlier = 1`), não apagados | Apagar perde rastreabilidade e winsorizar altera um valor real. As métricas filtram `fl_outlier = 0` |
| **3×IQR por produto × mês**, não 1,5×IQR | Com 1,5×IQR, 13,6% das coletas do Norte seriam marcadas (contra ~1,2% nas outras regiões). São preços reais de uma região mais cara. Com 3×IQR são 0,46% no Brasil (notebook, seção 1.8) |
| **Regras de limpeza vindas da EDA** (`trf_03`) | Cada achado do notebook (linhas vazias, CNPJ com e sem máscara, unidade do GNV, bandeiras renomeadas, duplicatas) virou um step. A tabela "Achado → Regra" do notebook liga um ao outro |

## Executar pela linha de comando

```bash
./pentaho/run_etl.sh                          # job completo (≈ 4 min, 2,6 mi de linhas)
./pentaho/run_etl.sh trf_03_tratamento        # uma transformação só
```
O script lê o `.env` e passa conexão e pasta de dados como parâmetros. Os logs ficam em `pentaho/logs/` (fora do Git).
`PDI_HOME` aponta para a instalação do PDI (padrão `~/Apps/Pentaho`).

## Abrir no Spoon

As conexões usam variáveis (`${DW_HOST}`, `${DW_PORT}`, `${DW_DB}`, `${DW_USER}`, `${DW_PASSWORD}`, `${DIR_DADOS}`):
nenhuma senha fica gravada nos arquivos.

- **Job:** ao rodar pelo Spoon, preencha a aba *Parameters* (os padrões já vêm preenchidos, só falta `DW_PASSWORD`).
- **Transformação avulsa:** *Edit → Edit the kettle.properties file* e adicione as variáveis com base em
  [`kettle.properties.example`](kettle.properties.example). Depois reinicie o Spoon.

## Resultado da última execução (`dw.log_carga`)

| Verificação | Valor |
|---|---|
| Linhas na staging (= soma dos CSVs) | 2.616.267 |
| Linhas vazias descartadas | 9.114 |
| Linhas tratadas | 2.607.153 |
| Duplicatas removidas no grão | 14 |
| Linhas na fato | 2.607.139 |
| Linhas da fato com chave −1 | 0 |
| Outliers marcados | 11.951 (0,46%) |
| Dias faltando na `dim_data` | 0 |

O job foi executado duas vezes seguidas com o mesmo resultado: é idempotente.
