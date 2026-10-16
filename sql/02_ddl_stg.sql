-- =============================================================
-- 02 - Staging
-- precos_bruto   : cópia fiel do CSV, tudo texto, sem regra de negócio
-- precos_tratado : saída da transformação de limpeza do Pentaho
-- Executar como etl.
-- =============================================================

CREATE TABLE IF NOT EXISTS stg.precos_bruto (
    regiao_sigla      TEXT,
    estado_sigla      TEXT,
    municipio         TEXT,
    revenda           TEXT,
    cnpj_revenda      TEXT,
    nome_rua          TEXT,
    numero_rua        TEXT,
    complemento       TEXT,
    bairro            TEXT,
    cep               TEXT,
    produto           TEXT,
    data_coleta       TEXT,
    valor_venda       TEXT,
    valor_compra      TEXT,
    unidade_medida    TEXT,
    bandeira          TEXT,
    arquivo_origem    TEXT,
    dt_carga          TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stg.precos_tratado (
    regiao_sigla      VARCHAR(2),
    uf_sigla          VARCHAR(2),
    municipio         VARCHAR(100),
    razao_social      VARCHAR(200),
    cnpj              CHAR(14),
    bairro            VARCHAR(100),
    cep               CHAR(8),
    produto           VARCHAR(50),
    data_coleta       DATE,
    valor_venda       NUMERIC(10,3),
    valor_compra      NUMERIC(10,3),
    unidade_medida    VARCHAR(20),
    bandeira          VARCHAR(100),
    arquivo_origem    VARCHAR(100)
);
