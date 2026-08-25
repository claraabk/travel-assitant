# Travel Assistant — Recife ⇄ Peru (LATAM)

Projeto do agente de viagens/estrategista de milhas da Clara. Instrução
operacional completa em [`docs/agente-viagem.md`](docs/agente-viagem.md).

- `state/` — fonte de verdade entre execuções (perfil, saldo, histórico
  de preços, promoções, thresholds). Sempre ler/escrever aqui, nunca
  confiar em memória de conversa entre execuções agendadas.
- `dashboard/dashboard.html` — fonte do Artifact publicado. Regenerar a
  partir de `state/*.json` e republicar na mesma URL a cada execução do
  ciclo diário (ver `docs/agente-viagem.md`).
- Sem relatório diário por e-mail. Alertas urgentes usam
  `PushNotification`; o resto vive só no dashboard.
