-- =============================================================
-- 04 - Marca outliers na fato. Executado pelo job.
-- Regra: fora de [Q1 - 3*IQR , Q3 + 3*IQR] dentro de produto x mês,
-- ou preço nulo / não positivo. O registro NÃO é apagado: fl_outlier = 1.
-- 3*IQR (e não 1,5) para não marcar preço real de regiões mais caras.
-- =============================================================

UPDATE dw.fato_coleta_preco SET fl_outlier = 0 WHERE fl_outlier <> 0;

WITH limites AS (
    SELECT f.sk_produto, d.ano_mes,
           percentile_cont(0.25) WITHIN GROUP (ORDER BY f.valor_venda) AS q1,
           percentile_cont(0.75) WITHIN GROUP (ORDER BY f.valor_venda) AS q3
    FROM dw.fato_coleta_preco f
    JOIN dw.dim_data d ON d.sk_data = f.sk_data
    WHERE f.valor_venda > 0
    GROUP BY f.sk_produto, d.ano_mes
)
UPDATE dw.fato_coleta_preco f
SET fl_outlier = 1
FROM dw.dim_data d, limites l
WHERE d.sk_data = f.sk_data
  AND l.sk_produto = f.sk_produto
  AND l.ano_mes = d.ano_mes
  AND (f.valor_venda < l.q1 - 3 * (l.q3 - l.q1)
    OR f.valor_venda > l.q3 + 3 * (l.q3 - l.q1));

UPDATE dw.fato_coleta_preco SET fl_outlier = 1
WHERE valor_venda IS NULL OR valor_venda <= 0;
