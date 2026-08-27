#!/usr/bin/env bash
# Wrapper para rodar latam_scraper.py via cron e commitar/pushar o JSON
# resultante para o git, só quando o scraper tiver sucesso.
set -euo pipefail

# ---- CONFIG ----
# Resolve o diretório do repo a partir da localização do próprio script,
# então não fica preso a um $HOME/usuário específico -- funciona em
# qualquer máquina/usuário que clonar o repo, sem editar nada aqui.
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UV_BIN="$HOME/.local/bin/uv"                   # caminho completo -- cron não tem seu PATH de login
JSON_PATH="$REPO_DIR/state/latam_miles_price.json"
GIT_BRANCH="claude/travel-assistant-flights-xvrptk"
LOCK_FILE="/tmp/latam_scraper.lock"
# ----------------------------------------

log() { echo "$(date -Iseconds) $*"; }

# Evita duas execuções sobrepostas (ex: um run demorou mais que o intervalo do cron)
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "já existe uma execução em andamento, pulando"
  exit 0
fi

cd "$REPO_DIR"

TMP_OUT="$(mktemp)"
TMP_ERR="$(mktemp)"
trap 'rm -f "$TMP_OUT" "$TMP_ERR"' EXIT

# --project garante que 'uv run' resolve o venv/lock certos mesmo se o cron
# rodar de outro diretório de trabalho.
if "$UV_BIN" run --project "$REPO_DIR" "$REPO_DIR/latam_scraper.py" > "$TMP_OUT" 2> "$TMP_ERR"; then
  mkdir -p "$(dirname "$JSON_PATH")"
  cp "$TMP_OUT" "$JSON_PATH"

  git add "$JSON_PATH"
  if git diff --cached --quiet; then
    log "sucesso, mas sem mudanças no preço -- nada para commitar"
  else
    git commit -m "chore(latam-miles): atualiza cotação ($(date -Iseconds))" -q
    if git push origin "$GIT_BRANCH" -q; then
      log "commit e push feitos com sucesso"
    else
      log "ERRO: commit feito mas push falhou -- verifique autenticação/rede"
      exit 1
    fi
  fi
else
  log "ERRO: scraper falhou, JSON anterior mantido intacto. stderr:"
  cat "$TMP_ERR" >&2
  exit 1
fi
