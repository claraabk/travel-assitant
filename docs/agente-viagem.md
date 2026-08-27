# Agente de Viagens — Recife ⇄ Peru (LATAM)

Este documento é a instrução operacional do agente. As duas Routines
agendadas (monitor leve e dashboard completo) devem seguir este fluxo.
Todo estado é lido/escrito em `state/*.json` e commitado no repositório —
essa é a fonte de verdade entre execuções, não a memória de conversa.

## Restrição fixa desta viagem

Recife ⇄ Peru (Lima e Cusco) é **exclusivamente LATAM** — cotação em
dinheiro só em voos operados por LA, resgate só via LATAM Pass. Ignorar
Smiles/TudoAzul/outros programas para esta viagem.

**Viagem é para 2 passageiros: Clara e Pedro** (atualizado em
27/08/2026, ver `state/config.json.roteiro.passageiros` e
`state/perfil.json.companheiro_viagem`). Todas as buscas de preço de
passagem (fli/Kiwi/Expedia/lastminute) devem ser feitas para **2
adultos**, não 1 — checagens em `state/precos_historico.json`
anteriores a 27/08/2026 foram feitas para 1 passageiro e não são
comparáveis diretamente com as novas; ao anexar novo checkin, registrar
`passageiros: 2` no registro para deixar isso rastreável.

**A Clara quer visitar Lima E Cusco na mesma viagem** — não é mais
"um destino ou outro". Ver `state/config.json.roteiro`:
- ~6 dias em Cusco, 2 a 3 dias em Lima (viagem total de 8-9 dias).
- Só 2 combinações fazem sentido agora, ambas open-jaw:
  - `LIM-CUZ`: entra por Lima, sai por Cusco
  - `CUZ-LIM`: entra por Cusco, sai por Lima
- `LIM-LIM` e `CUZ-CUZ` (ida e volta pelo mesmo destino) estão
  **descontinuadas** — não atendem mais o requisito de visitar os
  dois. Histórico antigo dessas duas fica em
  `state/precos_historico.json` só como referência, não comparar
  contra elas nem atualizá-las.

Preço total de cada combinação = trecho internacional de ida
(REC→entrada) + trecho doméstico Lima↔Cusco (a duração de estadia
determina a data desse trecho) + trecho internacional de volta
(saída→REC), todos buscados como one-way e confirmados como operados
por LATAM (LATAM Perú cobre o trecho doméstico). Testar 2 e 3 dias em
Lima dentro de cada ordem de entrada (4 variantes no total: LIM-CUZ×2d,
LIM-CUZ×3d, CUZ-LIM×2d, CUZ-LIM×3d) e usar a mais barata como
`melhor_combinacao_geral`. Mostrar no dashboard qual venceu e por
quanto vs. a 2ª colocada — sem repetir isso em texto longo, só um dado
direto (ver seção de formato do dashboard abaixo).

## Perfil (`state/perfil.json`) e saldo (`state/saldo.json`)

Não repetir entrevista — ler desses arquivos. Saldo só é atualizado após
a Clara confirmar explicitamente que uma reserva/transferência foi
concluída (nunca por inferência). Antes disso, gravar em
`saldo.pendente_confirmacao` (ou `saldo.pedro.pendente_confirmacao`) e
perguntar "você realmente completou isso?" na conversa/dashboard.

**Perfil do Pedro** (namorado da Clara, viaja junto — ver
`state/perfil.json.companheiro_viagem` e `state/saldo.json.pedro`):
cadastro LATAM Pass com saldo zerado, cartão Banco Inter Prime com
11.900 pontos, mesmo tier de elegibilidade de desconto que a Clara
(geral, sem Clube/Itaú). Considerar o saldo combinado do casal (milhas
LATAM Pass de ambos + potencial de transferência dos pontos Inter do
Pedro) ao calcular quanto falta para a faixa de resgate estimada — não
só o saldo da Clara isoladamente. Checar também bônus de transferência
Inter Loop/Prime → LATAM Pass (ver
`state/config.json.fontes_monitoradas_promocoes`,
`queries_obrigatorias_por_ciclo`), do mesmo jeito que já se checa
Nubank/Livelo/Esfera.

## Dois ciclos de execução

### 1) Monitor leve (a cada 6h, `state/config.json.cadencia.monitor_leve_horas`)

Objetivo: barato e frequente, só para detectar mudanças que não podem
esperar o dashboard diário.

1. Rodar `fli.search_dates`/`fli.search_flights` (filtrando
   `airlines=["LA"]`, **2 passageiros adultos** — ver
   `state/config.json.roteiro.passageiros`) para a janela de jun/2027,
   cobrindo as 4 variantes de roteiro (`LIM-CUZ`×2d, `LIM-CUZ`×3d,
   `CUZ-LIM`×2d, `CUZ-LIM`×3d — ver seção "Restrição fixa desta viagem"
   acima e `state/config.json.roteiro`). Cada variante soma o trecho
   internacional de ida one-way + o trecho doméstico LIM↔CUZ one-way +
   o trecho internacional de volta one-way, respeitando 6 dias em
   Cusco e 2 ou 3 dias em Lima. Se a ferramenta não suportar
   `passageiros=2` diretamente, buscar para 1 e multiplicar por 2 como
   aproximação, registrando essa ressalva no checkin.
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
4. **Não depender só da ferramenta de compra direta.** Antes de buscar
   na web, tentar entrar direto em
   `https://latampass.latam.com/pt_br/ofertas` e iterar pelas
   promoções listadas lá (fonte primária, prioridade sobre blog de
   milhas). Se o acesso falhar — hoje falha por dois motivos
   independentes: o proxy de rede desta sessão bloqueia o domínio
   (`EGRESS_BLOCKED`) e, mesmo quando acessível, o conector
   `Latam_PASS` (hospedado em GCP) esbarra no Akamai — cair para busca
   na web (ex.: "LATAM Pass compra de milhas desconto promoção" +
   mês/ano atual). Descontos por perfil Clube/Itaú não se aplicam à
   Clara (ver `state/perfil.json.elegivel_desconto_30_35pct=false`),
   mas promoções gerais (sem perfil específico) contam. **1 fonte
   confiável já é suficiente para marcar como ativa** — não é preciso
   esperar uma 2ª fonte confirmar. Preferir sempre a página oficial da
   LATAM Pass quando acessível; se a fonte for um blog de terceiros,
   registrar isso e sinalizar confiança mais baixa, mas ainda reportar.
5. Buscar (página oficial quando acessível, senão web) bônus de
   transferência Ultravioleta→LATAM Pass e promoções Livelo/Esfera
   relevantes para LATAM Pass especificamente (ignorar bônus para
   outros programas — não se aplicam a esta viagem). 1 fonte já basta
   para marcar como ativa. Atualizar `state/promocoes.json`, marcando
   `ja_notificada` para evitar alertar a mesma oportunidade duas vezes.
5b. **Checar sempre** `https://passageirodeprimeira.com/categorias/promocoes/`
   (ver `state/config.json.fontes_monitoradas_promocoes`, item com
   `sempre_checar=true`) — todo ciclo, não só quando outras buscas
   falharem. Acesso direto via `WebFetch` dá `EGRESS_BLOCKED`; em vez
   disso, usar `WebSearch` com `allowed_domains: ["passageirodeprimeira.com"]`.
   Rodar **as duas** buscas todo ciclo (ver
   `queries_obrigatorias_por_ciclo` em `state/config.json`), não só
   transferência:
   - bônus de **transferência** (ex.: "bônus transferência LATAM Pass
     Livelo Esfera Nubank")
   - desconto na **compra direta** de milhas (ex.: "LATAM Pass compra
     de milhas desconto")
   Tratar como fonte única válida (não precisa de 2ª fonte, mas é blog
   de terceiros — sinalizar como tal). Extrair só o que for relevante
   para LATAM Pass (ignorar Smiles/Azul/outros). Para promoções de
   compra por perfil de cliente (ex.: desconto maior para
   Clube/Itaú, menor para "inscritos no programa"), **não presumir
   automaticamente que a Clara está fora** só porque não tem Clube nem
   cartão Itaú — a redação dessas promoções às vezes inclui qualquer
   cadastrado no LATAM Pass num tier mais baixo. Registrar como
   "elegibilidade incerta, checar no app/site logada" em vez de
   descartar.
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
2. Detalhar a **variante vencedora** (`melhor_combinacao_geral`) com
   todos os campos exigidos: datas/horários de cada trecho (ida,
   doméstico LIM↔CUZ, volta), aeroportos de origem/conexão/destino,
   paradas e duração de cada trecho, companhia operando cada trecho
   (confirmar LATAM), duração total, classe da tarifa e
   reembolsabilidade, link direto. Mostrar as outras 3 variantes só
   como preço + diferença em R$ (uma linha cada, não repetir todo o
   detalhe de voo) — ver seção "Formato do dashboard" abaixo.
3. Calcular dinheiro vs. LATAM Pass: preço em R$ (para os 2
   passageiros), milhas estimadas — **para 2 passageiros a faixa de
   resgate pública dobra**: curto curso 12.000–50.000, longo curso
   60.000–140.000 milhas econômica (deixando claro que é estimativa até
   haver fonte de resgate real) —, e o **CPM de equilíbrio** — a
   fórmula é `preco_brl / milhas * 1000` (custo por 1.000 milhas no
   ponto em que pagar em dinheiro e resgatar dariam no mesmo). **Cuidado
   com a direção da conta**: não inverter (`milhas / preco_brl`) — um
   ciclo anterior cometeu esse erro de fator ~10x. Comparar esse CPM de
   equilíbrio contra o CPM real de compra/transferência: se for
   possível conseguir milhas por menos que o CPM de equilíbrio,
   resgatar vale mais que pagar em dinheiro. Considerar o **saldo
   combinado do casal** (`state/saldo.json.latam_pass_milhas` +
   `state/saldo.json.pedro.latam_pass_milhas` + potencial de
   transferência de `state/saldo.json.pedro.inter_prime_pontos`) contra
   essa faixa, não só o saldo da Clara.
3b. Calcular o **preço final estimado aplicando as milhas do casal**
   (novo card fixo no dashboard, adicionado em 27/08/2026; premissas
   revisadas em 27/08/2026, ver `state/config.json.premissas_calculo_milhas`):
   ```
   milhas_necessárias = TETO da faixa estimada para 2 pax (nunca a média/piso)
   milhas_que_já_têm  = milhas LATAM Pass confirmadas (Clara + Pedro)
                        + pontos Ultravioleta (Clara) convertidos a 1:1
                        + pontos Inter Prime (Pedro) convertidos a 1:1
                        (usar proporção maior só se houver bônus de
                        transferência ativo confirmado; nunca menor que 1:1)
   milhas_faltantes  = milhas_necessárias − milhas_que_já_têm
   CPM_de_aquisição  = TETO do CPM disponível no ciclo (maior custo,
                        não o menor nem a média)
   custo_para_completar = (milhas_faltantes / 1000) × CPM_de_aquisição
   preço_final_estimado ≈ custo_para_completar (+ taxas de embarque, que o resgate não cobre)
   ```
   **Sempre usar o cenário mais conservador (teto/pior caso)** tanto
   para milhas necessárias quanto para CPM de aquisição — nunca média
   nem melhor caso. Isso vale só para este cálculo de "valor restante";
   o card "Dinheiro vs. LATAM Pass" pode continuar mostrando a faixa
   completa normalmente. Mostrar a comparação com o preço em dinheiro e
   deixar explícito que a faixa de milhas necessárias é estimativa
   pública, não disponibilidade real para a data escolhida.
4. Se `Latam_PASS.list_latam_miles_purchase_prices` ou
   `state/latam_miles_price.json` (scraper local — schema e cron em
   `docs/scraper-local-setup.md`, válido só com `atualizado_em` das
   últimas 24h) tiver dado certo, **e/ou** se a busca na web (passo 4
   do monitor leve)
   tiver achado uma promoção de desconto confirmada: comparar o melhor
   CPM disponível (oficial ou promocional) vs. custo de resgate
   estimado e recomendar comprar só se o total (milhas + taxas) ficar
   abaixo do preço em dinheiro.
5. Regenerar `dashboard/dashboard.html` a partir do estado atualizado e
   publicar via Artifact **na mesma URL** (não criar um novo artifact a
   cada execução).
6. Commitar tudo.

- **Card "Preço final estimado aplicando as milhas do casal"**
  (sempre presente, logo após "Vale comprar mais milhas?"): tabela
  curta com preço em dinheiro, milhas necessárias, milhas que já têm,
  milhas faltantes, CPM de aquisição e custo para completar — ver
  fórmula no passo 3b do Ciclo 2 acima. Uma nota de 1-2 linhas, não
  mais que isso.
- **Chips de saldo no cabeçalho** identificam a pessoa: `Clara ·
  LATAM Pass`, `Clara · Nubank Ultravioleta`, `Pedro · LATAM Pass`,
  `Pedro · Inter Prime`, etc. — nunca mostrar um saldo sem o nome de
  quem ele pertence.

## Formato do dashboard

O dashboard é pra ser **escaneado, não lido como texto corrido**.
Regras de formato (valem pra toda regeneração de `dashboard/dashboard.html`):

- **Sem parágrafos longos.** Cada frase deve caber numa linha ou duas.
  Se uma explicação precisar de mais que isso, cortar para o essencial
  e deixar o detalhe num link/fonte em vez de texto.
- **Recomendação do dia em 2 listas de tópicos separadas**, nunca um
  parágrafo único:
  - **Recomendação de voo** (comprar agora / esperar / datas
    específicas) — bullets curtos.
  - **Recomendação de milhas** (comprar / transferir / ativar Modo
    LATAM Pass / nenhuma ação) — bullets curtos.
- **Oportunidades de acúmulo e transferência**: cada uma em **1 linha**
  — resumo curto (o quê + %/valor) + link para a fonte. Sem parágrafo
  de contexto, sem repetir ressalvas longas (isso fica em
  `state/promocoes.json`, não no dashboard).
- **Só mostrar oportunidades ainda ativas.** Antes de renderizar,
  filtrar `state/promocoes.json.ativas` por `valido_ate`: se
  `valido_ate` já passou (comparar com a data do ciclo), **não incluir
  no dashboard** — nem como item riscado/ignorado, simplesmente omitir.
  Mover promoções expiradas de `ativas` para um array `expiradas` no
  mesmo arquivo (mantém histórico sem poluir o que é lido pelo
  dashboard). `valido_ate: null` ou `e_permanente: true` conta como
  sempre ativa.

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
(Ultravioleta→LATAM Pass, Livelo/Esfera): tentar primeiro
`https://latampass.latam.com/pt_br/ofertas` diretamente; se
inacessível, usar busca web em blogs de milhas. **1 fonte já é
suficiente** para marcar como "ativa" — não exigir uma 2ª fonte
concordante. Registrar sempre a fonte e, quando for página oficial vs.
blog de terceiros, sinalizar isso no campo `confianca` (não como
bloqueio, só como contexto).

Acesso direto a `latampass.latam.com` a partir desta sessão está
bloqueado pelo proxy de rede do ambiente (`EGRESS_BLOCKED`) — separado
do bloqueio Akamai que afeta o conector `Latam_PASS` hospedado em GCP.
São duas barreiras diferentes; nenhuma das duas o agente resolve
sozinho. Se em algum ciclo futuro o acesso direto à página de ofertas
estiver liberado, usar como fonte primária a partir dali.
