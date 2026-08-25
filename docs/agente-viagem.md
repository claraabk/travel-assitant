# Agente de Viagens — Recife ⇄ Peru (LATAM)

Este documento é a instrução operacional do agente. As duas Routines
agendadas (monitor leve e dashboard completo) devem seguir este fluxo.
Todo estado é lido/escrito em `state/*.json` e commitado no repositório —
essa é a fonte de verdade entre execuções, não a memória de conversa.

## Restrição fixa desta viagem

Recife ⇄ Peru (Lima e Cusco) é **exclusivamente LATAM** — cotação em
dinheiro só em voos operados por LA, resgate só via LATAM Pass. Ignorar
Smiles/TudoAzul/outros programas para esta viagem.

O **roteiro não é fixo**. Comparar sempre as 4 combinações em
`state/precos_historico.json.combinacoes_monitoradas`:
- Ida e volta só por Lima (LIM-LIM)
- Ida e volta só por Cusco (CUZ-CUZ)
- Open-jaw: entrar por Lima e sair por Cusco (LIM-CUZ)
- Open-jaw: entrar por Cusco e sair por Lima (CUZ-LIM)

Para as combinações open-jaw, o preço total = trecho internacional de
ida (REC→entrada) + trecho internacional de volta (saída→REC), cada um
buscado como one-way, **mais** o trecho doméstico Lima↔Cusco necessário
para fechar o roteiro dentro do Peru (LATAM Perú também serve essa
rota — incluir no preço total e confirmar que segue operado por LATAM).
Atualizar `melhor_combinacao_geral` sempre que uma combinação ficar mais
barata que a atual, e mostrar no dashboard qual combinação venceu e por
quê (diferença em R$ vs. a 2ª colocada).

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

1. Rodar `fli.search_dates`/`fli.search_flights` (filtrando
   `airlines=["LA"]`) para a janela de jun/2027, cobrindo as 4
   combinações de roteiro (`LIM-LIM`, `CUZ-CUZ`, `LIM-CUZ`, `CUZ-LIM` —
   ver seção "Restrição fixa desta viagem" acima). Para as duas
   open-jaw, somar os dois trechos internacionais one-way + o trecho
   doméstico LIM↔CUZ.
2. Anexar cada resultado a `state/precos_historico.json.checagens.<id>`
   (não sobrescrever — é log por combinação). Calcular
   `media_movel_30_checagens` e `variacao_pct_vs_media` por combinação,
   e atualizar `melhor_combinacao_geral` se alguma ficou mais barata.
3. Tentar `Latam_PASS.list_latam_miles_purchase_prices`. Se falhar
   (bloqueio Akamai conhecido — o MCP roda em GCP e não passa no
   desafio do site), registrar o erro em
   `state/config.json.latam_miles_price_tool_status` e, em vez de
   insistir, ler `state/latam_miles_price.json` (escrito por scraper
   local da Clara) se existir e estiver atualizado nas últimas 24h;
   caso contrário seguir sem inventar preço.
4. **Não depender só da ferramenta de compra direta.** Buscar também na
   web por promoções de desconto na compra direta de milhas LATAM Pass
   (ex.: "LATAM Pass compra de milhas desconto promoção" + mês/ano
   atual) — descontos por perfil Clube/Itaú não se aplicam à Clara
   (ver `state/perfil.json.elegivel_desconto_30_35pct=false`), mas
   promoções gerais (sem perfil específico) contam. Exigir 2 fontes
   concordantes antes de marcar como ativa.
5. Buscar na web (com pelo menos 2 fontes concordantes antes de marcar
   como confirmada) bônus de transferência Ultravioleta→LATAM Pass e
   promoções Livelo/Esfera relevantes para LATAM Pass especificamente
   (ignorar bônus para outros programas — não se aplicam a esta
   viagem). Atualizar `state/promocoes.json`, marcando `ja_notificada`
   para evitar alertar a mesma oportunidade duas vezes.
6. **Gatilho de alerta urgente** (via `PushNotification`, nunca e-mail
   diário — não há relatório diário por e-mail neste fluxo):
   - Queda de preço ≥ `thresholds.queda_preco_pct_alerta_urgente` (15%)
     vs. média móvel, OU
   - Bônus de transferência Ultravioleta→LATAM Pass ou promoção
     Livelo/Esfera com destino LATAM Pass ≥ `thresholds.bonus_transferencia_pct_oportunidade`
     (60%) com prazo curto (expira em ≤48h), OU
   - Desconto ativo na compra direta de milhas LATAM Pass hoje.
   Cada uma dessas dispara no máximo uma notificação por oportunidade
   (`ja_notificada=true` depois de alertar).
7. Commitar `state/*.json` atualizado.

### 2) Dashboard completo (diário, `state/config.json.cadencia.dashboard_completo`)

Objetivo: visão completa, sempre publicada, sem depender de e-mail.

1. Repetir os passos 1–5 do monitor leve (ou reaproveitar se o monitor
   já rodou nas últimas horas).
2. Detalhar a **combinação vencedora** (`melhor_combinacao_geral`) com
   todos os campos exigidos: datas/horários de ida e volta, aeroportos
   de origem/conexão/destino (incluindo o trecho doméstico LIM↔CUZ se
   for open-jaw), paradas e duração de cada trecho, companhia operando
   cada trecho (confirmar LATAM), duração total, classe da tarifa e
   reembolsabilidade, link direto. Mostrar também as outras 3
   combinações e a diferença de preço entre elas, para deixar claro por
   que a vencedora venceu.
3. Calcular dinheiro vs. LATAM Pass: preço em R$, milhas estimadas
   (faixa pública: curto curso 6.000–25.000 econômica, longo curso
   30.000–70.000 econômica, deixando claro que é estimativa até haver
   fonte de resgate real), CPM e qual opção vence.
4. Se `Latam_PASS.list_latam_miles_purchase_prices` ou
   `state/latam_miles_price.json` (scraper local) tiver dado certo nas
   últimas 24h, **e/ou** se a busca na web (passo 4 do monitor leve)
   tiver achado uma promoção de desconto confirmada: comparar o melhor
   CPM disponível (oficial ou promocional) vs. custo de resgate
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

Preço de passagem vem de conectores reais (fli, Kiwi, Expedia,
lastminute) — tratar como confiável quando a chamada tiver sucesso.

Preço de compra direta de milhas tem duas fontes possíveis, nessa
ordem de prioridade: (1) `Latam_PASS.list_latam_miles_purchase_prices`
quando funcionar; (2) `state/latam_miles_price.json`, escrito por um
scraper rodando localmente na máquina da Clara (o MCP hospedado em GCP
é bloqueado pelo Akamai do site da LATAM — ver
`state/config.json.latam_miles_price_tool_status`). Nunca chamar o
site da LATAM diretamente por HTTP a partir do agente para contornar
isso.

Promoções de desconto na compra de milhas e bônus de transferência
(Ultravioleta→LATAM Pass, Livelo/Esfera) vêm de busca na web em blogs
de milhas — exigir 2 fontes concordantes antes de marcar como "ativa";
caso contrário, marcar como "não confirmada" e sugerir checagem manual
no app/site oficial.
