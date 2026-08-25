# Scraper local de preço de milhas LATAM Pass — setup do cron

O conector `Latam_PASS` (MCP) roda em GCP e é bloqueado pelo Akamai do
site da LATAM. Você mencionou que o scraper funciona rodando
localmente (IP residencial). Este documento é o contrato entre o seu
scraper e o agente: schema de saída, onde escrever, e como o cron deve
rodar.

## 1. Schema de saída — `state/latam_miles_price.json`

O agente (`docs/agente-viagem.md`, passo 3 do monitor leve) lê este
arquivo exatamente neste formato:

```json
{
  "atualizado_em": "2026-08-27T09:00:00-03:00",
  "fonte": "scraper local (cron)",
  "url_origem": "https://latampass.latam.com/pt_br/facilidades/compra-milhas",
  "desconto_pct_aplicado": 62,
  "tiers": [
    { "milhas": 1000, "preco_brl": 24.50, "cpm_brl": 24.50 },
    { "milhas": 5000, "preco_brl": 119.00, "cpm_brl": 23.80 },
    { "milhas": 10000, "preco_brl": 235.00, "cpm_brl": 23.50 },
    { "milhas": 50000, "preco_brl": 1150.00, "cpm_brl": 23.00 },
    { "milhas": 100000, "preco_brl": 2250.00, "cpm_brl": 22.50 }
  ],
  "melhor_tier": { "milhas": 100000, "preco_brl": 2250.00, "cpm_brl": 22.50 },
  "erro": null
}
```

Campos:
- `atualizado_em`: ISO 8601 com timezone, hora da coleta (não de agendamento).
- `desconto_pct_aplicado`: se o scraper conseguir identificar que há
  desconto ativo e qual %, preencher; senão `null`.
- `tiers`: um item por faixa de milhas oferecida na página. `cpm_brl` =
  preço ÷ (milhas / 1000) — custo por 1.000 milhas.
- `melhor_tier`: o item de `tiers` com menor `cpm_brl`.
- `erro`: `null` se a coleta funcionou. Se falhar, **não sobrescrever**
  o arquivo com dado velho fingindo sucesso — ver seção 3.

O agente trata esse arquivo como válido só se `atualizado_em` for das
últimas 24h (`docs/agente-viagem.md`, passo 3). Fora disso, ele ignora
e tenta o conector MCP de novo.

## 2. Script wrapper

O scraper já está em `scripts/latam_scraper.py` (usa Playwright para
renderizar a SPA de compra de milhas). Antes de usar o wrapper, instale
as dependências uma vez:

```bash
cd ~/travel-assitant/scripts
pip install -e .
playwright install chromium
```

`python3 scripts/latam_scraper.py` já imprime o JSON pronto no schema
da seção 1 (via `main()`) — não precisa adaptar nada nele, só apontar
o `SCRAPER_CMD` abaixo para o caminho do seu clone:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$HOME/travel-assitant"   # ajuste para o caminho real do clone local
OUT_FILE="$REPO_DIR/state/latam_miles_price.json"
LOCK_FILE="/tmp/latam-miles-scraper.lock"
SCRAPER_CMD="python3 $REPO_DIR/scripts/latam_scraper.py"  # já está no repo, em scripts/

exec 9>"$LOCK_FILE"
flock -n 9 || { echo "já rodando, saindo"; exit 0; }

cd "$REPO_DIR"
git fetch origin claude/travel-assistant-flights-xvrptk
git checkout claude/travel-assistant-flights-xvrptk
git pull --ff-only origin claude/travel-assistant-flights-xvrptk

TMP_OUT="$(mktemp)"
if $SCRAPER_CMD > "$TMP_OUT" 2> "$TMP_OUT.log"; then
  if jq empty "$TMP_OUT" 2>/dev/null; then
    cp "$TMP_OUT" "$OUT_FILE"
    git add "$OUT_FILE"
    git commit -m "chore: atualiza state/latam_miles_price.json (scraper local)" || true
    git push origin claude/travel-assistant-flights-xvrptk
  else
    echo "saída do scraper não é JSON válido, não sobrescrevendo" >&2
    cat "$TMP_OUT.log" >&2
  fi
else
  echo "scraper falhou, mantendo state/latam_miles_price.json anterior" >&2
  cat "$TMP_OUT.log" >&2
fi

rm -f "$TMP_OUT" "$TMP_OUT.log"
```

Salve como `~/scripts/run-latam-scraper.sh` e dê permissão de execução:

```bash
chmod +x ~/scripts/run-latam-scraper.sh
```

## 3. Regra de falha

Se o scraper falhar (site fora do ar, seletor mudou, etc.), **não
escreva o arquivo** — deixe o anterior no lugar. O agente já sabe
tratar "arquivo com mais de 24h" como indisponível (mesma lógica que
usa para o conector MCP falhando). Nunca inventar/repetir o último
preço como se fosse novo.

## 4. Linha de cron

Para acompanhar a mesma cadência do monitor leve (`state/config.json`
→ `cadencia.monitor_leve_horas = 6`):

```
0 */6 * * * /home/clara/scripts/run-latam-scraper.sh >> /home/clara/scripts/latam-scraper.log 2>&1
```

Editar com `crontab -e`. Ajuste o caminho do script e do log para o
seu usuário/máquina.

## 5. Segurança

- Se o scraper precisar de login/sessão na LATAM Pass, guarde
  credenciais fora do repositório (variável de ambiente, arquivo
  `.env` fora do git, ou um gerenciador de segredos local) — nunca
  commitar senha/token no `travel-assitant`.
- O `git push` do cron precisa das suas credenciais Git já configuradas
  nessa máquina (SSH key ou token salvo) — isso é local, fora do
  controle do agente na nuvem.

## 6. Verificação

Depois de rodar o script uma vez manualmente, confirme:

```bash
cat state/latam_miles_price.json | jq .
git log -1 --stat
```

Se o `atualizado_em` está recente e o JSON bate com o schema da seção
1, o próximo ciclo do agente (rodando na nuvem) já vai conseguir ler
esse arquivo em vez de depender só do conector MCP bloqueado.
