#!/usr/bin/env bash
# Executa o job mestre pelo Kitchen (linha de comando do Pentaho).
# Uso: ./pentaho/run_etl.sh            -> job completo
#      ./pentaho/run_etl.sh trf_01_carga_staging   -> só uma transformação (Pan)
# Variáveis: PDI_HOME (padrão ~/Apps/Pentaho) e as do .env na raiz.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set -a; source "$ROOT/.env"; set +a
PDI_HOME="${PDI_HOME:-$HOME/Apps/Pentaho}"
export PENTAHO_DI_JAVA_OPTIONS="${PENTAHO_DI_JAVA_OPTIONS:--Xms1g -Xmx6g}"

PARAMS=(
  "-param:DW_HOST=${DW_HOST:-localhost}"
  "-param:DW_PORT=${POSTGRES_PORT:-5432}"
  "-param:DW_DB=$POSTGRES_DB"
  "-param:DW_USER=etl"
  "-param:DW_PASSWORD=$ETL_PASSWORD"
  "-param:DIR_DADOS=$ROOT/data/raw"
)

mkdir -p "$ROOT/pentaho/logs"
LOG="$ROOT/pentaho/logs/$(date +%Y%m%d_%H%M%S)_${1:-job}.log"
if [ $# -eq 0 ]; then
  "$PDI_HOME/kitchen.sh" -file="$ROOT/pentaho/job_carga_dw.kjb" -level=Basic "${PARAMS[@]}" 2>&1 | tee "$LOG"
else
  # Pan não recebe parâmetros que a transformação não declara: passa como variáveis do sistema
  PENTAHO_DI_JAVA_OPTIONS="$PENTAHO_DI_JAVA_OPTIONS -DDW_HOST=${DW_HOST:-localhost} -DDW_PORT=${POSTGRES_PORT:-5432} -DDW_DB=$POSTGRES_DB -DDW_USER=etl -DDW_PASSWORD=$ETL_PASSWORD -DDIR_DADOS=$ROOT/data/raw" \
    "$PDI_HOME/pan.sh" -file="$ROOT/pentaho/transformations/$1.ktr" -level=Basic 2>&1 | tee "$LOG"
fi
exit "${PIPESTATUS[0]}"
