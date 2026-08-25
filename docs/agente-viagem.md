# Agente de Viagens — Recife ⇄ Peru (LATAM)

Este documento é a instrução operacional do agente. As duas Routines
agendadas (monitor leve e dashboard completo) devem seguir este fluxo.
Todo estado é lido/escrito em `state/*.json` e commitado no repositório —
essa é a fonte de verdade entre execuções, não a memória de conversa.

## Restrição fixa desta viagem

Recife ⇄ Peru (Lima e Cusco) é **exclusivamente LATAM** — cotação em
dinheiro só em voos operados por LA, resgate só via LATAM Pass. Ignorar
Smiles/TudoAzul/outros programas para esta viagem.

## Perfil (`state/perfil.json`) e saldo (`state/saldo.json`)

Não repetir entrevista — ler desses arquivos. Saldo só é atualizado após
a Clara confirmar explicitamente que uma reserva/transferência foi
concluída (nunca por inferência). Antes disso, gravar em
`saldo.pendente_confirmacao` e perguntar "você realmente completou
isso?" na conversa/dashboard.

## Dois ciclos de execução

### 1) Monitor leve (a cada 6h, `state/config.json.cadencia.monitor_leve_horas`)

Objetivo: barato e frequente, só para detectar mudanças que não podem
esperar o dashboard diário.

1. Rodar `fli.search_dates` (REC→LIM e REC→CUZ, `is_round_trip=true`,
   filtrando `airlines=["LA"]`) para a janela de jun/2027.
2. Anexar o resultado a `state/precos_historico.json.checagens`
   (não sobrescrever — é log). Calcular `media_movel_30_checagens` e
   `variacao_pct_vs_media` sobre as últimas checagens.
3. Tentar `Latam_PASS.list_latam_miles_purchase_prices`. Se falhar,
   registrar o erro em `state/config.json.latam_miles_price_tool_status`
   e seguir sem inventar preço — a checagem seguinte tenta de novo.
4. Buscar na web (com pelo menos 2 fontes concordantes antes de marcar
   como confirmada) bônus de transferência Ultravioleta→LATAM Pass e
   promoções Livelo/Esfera relevantes para LATAM Pass especificamente
   (ignorar bônus para outros programas — não se aplicam a esta
   viagem). Atualizar `state/promocoes.json`, marcando `ja_notificada`
   para evitar alertar a mesma oportunidade duas vezes.
5. **Gatilho de alerta urgente** (via `PushNotification`, nunca e-mail
   diário — não há relatório diário por e-mail neste fluxo):
   - Queda de preço ≥ `thresholds.queda_preco_pct_alerta_urgente` (15%)
     vs. média móvel, OU
   - Bônus de transferência Ultravioleta→LATAM Pass ou promoção
     Livelo/Esfera com destino LATAM Pass ≥ `thresholds.bonus_transferencia_pct_oportunidade`
     (60%) com prazo curto (expira em ≤48h), OU
   - Desconto ativo na compra direta de milhas LATAM Pass hoje.
   Cada uma dessas dispara no máximo uma notificação por oportunidade
   (`ja_notificada=true` depois de alertar).
6. Commitar `state/*.json` atualizado.

### 2) Dashboard completo (diário, `state/config.json.cadencia.dashboard_completo`)

Objetivo: visão completa, sempre publicada, sem depender de e-mail.

1. Repetir os passos 1–4 do monitor leve (ou reaproveitar se o monitor
   já rodou nas últimas horas).
2. Detalhar a melhor opção do dia com todos os campos exigidos:
   datas/horários de ida e volta, aeroportos de origem/conexão/destino,
   paradas e duração de cada trecho, companhia operando cada trecho
   (confirmar LATAM), duração total, classe da tarifa e reembolsabilidade,
   link direto.
3. Calcular dinheiro vs. LATAM Pass: preço em R$, milhas estimadas
   (faixa pública: curto curso 6.000–25.000 econômica, longo curso
   30.000–70.000 econômica, deixando claro que é estimativa até haver
   fonte de resgate real), CPM e qual opção vence.
4. Se `Latam_PASS.list_latam_miles_purchase_prices` tiver dado certo
   nas últimas 24h: comparar CPM de compra direta vs. custo de resgate
   estimado e recomendar comprar só se o total (milhas + taxas) ficar
   abaixo do preço em dinheiro.
5. Regenerar `dashboard/dashboard.html` a partir do estado atualizado e
   publicar via Artifact **na mesma URL** (não criar um novo artifact a
   cada execução).
6. Commitar tudo.

## Regras de reserva (sempre valem)

Nunca reservar ou transferir sem "Vai"/"Reserva" explícito da Clara.
Antes de reservar: mostrar total com taxas, política de cancelamento,
milhas gastas/ganhas, e sinalizar o que não é reembolsável.

## Notas sobre confiabilidade das fontes

Preço de passagem e preço de compra de milhas vêm de conectores reais
(fli, Kiwi, Expedia, lastminute, Latam_PASS) — tratar como confiável
quando a chamada tiver sucesso. Bônus de transferência e promoções de
shopping vêm de busca na web em blogs de milhas — exigir 2 fontes
concordantes antes de marcar como "ativa"; caso contrário, marcar como
"não confirmada" e sugerir checagem manual no app/site oficial.
