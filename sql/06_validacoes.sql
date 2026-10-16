-- =============================================================
-- 06 - Validações da carga -> dw.log_carga
-- Um único INSERT para que todas as linhas tenham o mesmo dt_execucao.
-- =============================================================

INSERT INTO dw.log_carga (verificacao, valor, ok)
WITH c AS (
    SELECT
        (SELECT COUNT(*) FROM stg.precos_bruto)   AS stg_bruto,
        (SELECT COUNT(*) FROM stg.precos_tratado) AS stg_tratado,
        (SELECT COUNT(*) FROM stg.precos_bruto
          WHERE cnpj_revenda IS NULL OR produto IS NULL) AS vazias,
        (SELECT COUNT(*) FROM dw.fato_coleta_preco) AS fato,
        (SELECT COUNT(*) FROM dw.fato_coleta_preco
          WHERE -1 IN (sk_data, sk_localidade, sk_revenda, sk_produto, sk_bandeira)) AS sem_chave,
        (SELECT COUNT(*) FROM dw.fato_coleta_preco WHERE fl_outlier = 1) AS outliers,
        (SELECT (MAX(data) - MIN(data) + 1) - COUNT(*) FROM dw.dim_data WHERE sk_data > 0) AS dias_faltando,
        (SELECT COUNT(*) FROM stg.precos_tratado WHERE valor_compra IS NOT NULL) AS com_valor_compra
)
SELECT v.verificacao, v.valor, v.ok
FROM c, LATERAL (VALUES
    ('linhas_stg_bruto',            stg_bruto,                stg_bruto > 0),
    ('linhas_vazias_descartadas',   vazias,                   true),
    ('linhas_stg_tratado',          stg_tratado,              stg_tratado = stg_bruto - vazias),
    ('linhas_fato',                 fato,                     fato > 0),
    ('duplicatas_removidas_no_grao', stg_tratado - fato,      true),
    ('linhas_fato_com_chave_-1',    sem_chave,                sem_chave = 0),
    ('outliers_marcados',           outliers,                 outliers < fato * 0.01),
    ('dias_faltando_dim_data',      dias_faltando,            dias_faltando = 0),
    ('linhas_com_valor_compra',     com_valor_compra,         true)
) AS v(verificacao, valor, ok);
