-- =============================================================
-- 05 - Camada mart
-- O Power BI e o notebook leem daqui, não do dw: mudança interna
-- no modelo não quebra o .pbix.
-- =============================================================

CREATE OR REPLACE VIEW mart.vw_fato_preco AS
SELECT sk_data, sk_localidade, sk_revenda, sk_produto, sk_bandeira,
       valor_venda, valor_compra, fl_outlier
FROM dw.fato_coleta_preco;

CREATE OR REPLACE VIEW mart.vw_dim_data AS
SELECT sk_data, data, dia, dia_semana, nome_dia_semana, semana_ano, mes, nome_mes,
       mes_abrev, trimestre, semestre, ano, ano_mes, ano_mes_ordem
FROM dw.dim_data
WHERE sk_data > 0;

CREATE OR REPLACE VIEW mart.vw_dim_localidade AS
SELECT sk_localidade, regiao_sigla, regiao_nome, uf_sigla, uf_nome, municipio,
       municipio || ' - ' || uf_sigla AS municipio_uf
FROM dw.dim_localidade;

-- Endereço completo fica fora: não é usado na análise e pesa no .pbix
CREATE OR REPLACE VIEW mart.vw_dim_revenda AS
SELECT sk_revenda, cnpj, razao_social
FROM dw.dim_revenda;

CREATE OR REPLACE VIEW mart.vw_dim_produto AS
SELECT sk_produto, produto, grupo_produto, unidade_medida
FROM dw.dim_produto;

CREATE OR REPLACE VIEW mart.vw_dim_bandeira AS
SELECT sk_bandeira, bandeira, tipo_bandeira
FROM dw.dim_bandeira;

-- Agregado mensal por UF e produto (EDA analítica e conferência dos KPIs)
CREATE OR REPLACE VIEW mart.vw_preco_mensal_uf AS
SELECT d.ano_mes, d.ano, d.mes, l.regiao_nome, l.uf_sigla, p.produto, p.grupo_produto,
       COUNT(*)                                                     AS qtd_coletas,
       ROUND(AVG(f.valor_venda), 3)                                 AS preco_medio,
       ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY f.valor_venda)::numeric, 3) AS preco_mediano
FROM dw.fato_coleta_preco f
JOIN dw.dim_data d       ON d.sk_data = f.sk_data
JOIN dw.dim_localidade l ON l.sk_localidade = f.sk_localidade
JOIN dw.dim_produto p    ON p.sk_produto = f.sk_produto
WHERE f.fl_outlier = 0
GROUP BY d.ano_mes, d.ano, d.mes, l.regiao_nome, l.uf_sigla, p.produto, p.grupo_produto;

-- Paridade etanol / gasolina comum por UF e mês (regra dos 70%)
CREATE OR REPLACE VIEW mart.vw_paridade_mensal_uf AS
SELECT e.ano_mes, e.regiao_nome, e.uf_sigla,
       e.preco_medio AS preco_etanol,
       g.preco_medio AS preco_gasolina,
       ROUND(e.preco_medio / g.preco_medio, 4) AS paridade,
       (e.preco_medio / g.preco_medio) <= 0.70 AS etanol_compensa
FROM mart.vw_preco_mensal_uf e
JOIN mart.vw_preco_mensal_uf g
  ON g.ano_mes = e.ano_mes AND g.uf_sigla = e.uf_sigla AND g.produto = 'GASOLINA'
WHERE e.produto = 'ETANOL';

-- Última execução do job (página técnica do dashboard)
CREATE OR REPLACE VIEW mart.vw_log_carga AS
SELECT dt_execucao, verificacao, valor, ok
FROM dw.log_carga
WHERE dt_execucao = (SELECT MAX(dt_execucao) FROM dw.log_carga);
