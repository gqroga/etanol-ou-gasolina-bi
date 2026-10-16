-- =============================================================
-- 01 - Schemas por camada e usuários
-- Executar como superusuário. Senhas chegam por variável psql:
--   psql -v etl_pw=... -v bi_pw=... -f 01_schemas_usuarios.sql
-- =============================================================

-- Usuários: etl (escrita, Pentaho) e bi_reader (leitura, Python / Power BI)
SELECT format('CREATE ROLE etl LOGIN PASSWORD %L', :'etl_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etl') \gexec
SELECT format('CREATE ROLE bi_reader LOGIN PASSWORD %L', :'bi_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bi_reader') \gexec

-- Camadas: stg (bruto + tratado), dw (modelo estrela), mart (consumo)
CREATE SCHEMA IF NOT EXISTS stg  AUTHORIZATION etl;
CREATE SCHEMA IF NOT EXISTS dw   AUTHORIZATION etl;
CREATE SCHEMA IF NOT EXISTS mart AUTHORIZATION etl;

-- bi_reader lê staging (EDA de qualidade), dw e mart (EDA analítica e Power BI)
GRANT USAGE ON SCHEMA stg, dw, mart TO bi_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE etl IN SCHEMA stg  GRANT SELECT ON TABLES TO bi_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE etl IN SCHEMA dw   GRANT SELECT ON TABLES TO bi_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE etl IN SCHEMA mart GRANT SELECT ON TABLES TO bi_reader;
