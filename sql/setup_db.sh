#!/usr/bin/env bash
# Cria schemas, usuários e tabelas no Postgres do container (idempotente).
# Uso: ./sql/setup_db.sh   (a partir da raiz do projeto, com o container no ar)
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

CONTAINER=dw_combustiveis
psql_as() {  # psql_as <usuario> <senha> <arquivo> [args...]
  local user=$1 pw=$2 file=$3; shift 3
  docker exec -i -e PGPASSWORD="$pw" -e PGOPTIONS="-c client_min_messages=warning" "$CONTAINER" \
    psql -v ON_ERROR_STOP=1 -q -h localhost -U "$user" -d "$POSTGRES_DB" "$@" < "$file"
}

psql_as "$POSTGRES_USER" "$POSTGRES_PASSWORD" sql/01_schemas_usuarios.sql \
  -v etl_pw="$ETL_PASSWORD" -v bi_pw="$BI_PASSWORD"
for f in sql/02_ddl_stg.sql sql/03_ddl_dw.sql; do
  psql_as etl "$ETL_PASSWORD" "$f"
done
echo "Banco pronto."
