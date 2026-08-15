# 12 — Roadmap Executável

Regra de desenvolvimento: por fase — **implementar → executar → testar → corrigir →
verificar integração → documentar → só então avançar para a fase seguinte**. Nunca
gerar centenas de ficheiros sem verificar o projeto. Nunca substituir código
funcional sem necessidade. Nunca criar mocks permanentes a fingir que são APIs
reais — quando uma integração externa não está configurada: interface + mock
provider explícito + TODO claro.

## Fase 1 — Brain (fundação) — **status: implementada e validada nesta sessão**

Entregáveis: projeto, base de dados, autenticação, dashboard, abstração de market
data (com mock provider explícito), paper portfolio, scanner básico, logging.

**Critério de sucesso:**
- [x] banco de dados funciona (Alembic `upgrade head` aplicado com sucesso contra
      Postgres 16 real)
- [x] autenticação funciona (login admin, JWT — testado end-to-end via HTTP)
- [x] dashboard funciona e mostra o ecrã inicial (`09-dashboard-spec.md §Fase 1`) —
      testado end-to-end: login → cookie httpOnly → SSR do dashboard com dados reais
      da API; acesso sem sessão redireciona para `/login`
- [x] market data provider funciona ou tem adapter/mock claramente identificado
      (`MockMarketDataProvider`, `MARKET_DATA_PROVIDER=mock`)
- [x] dados são armazenados (ciclo do scanner testado: 22/22 ativos gravados em `ohlcv`)
- [x] paper portfolio funciona (€10.000 inicial via `scripts/seed.py`, equity visível
      em `/api/portfolio` e no dashboard)
- [x] logs funcionam (estruturados, por componente — `packages/shared/logging.py`)
- [x] health checks funcionam (`/api/system/health` — reporta `database` e
      `market_data`; outros componentes chegam nas fases seguintes, não são
      simulados como "green")
- [x] testes básicos passam (14/14 — auth, health, mock provider, scanner, portfolio)
- [x] documentação atualizada (este roadmap + README)
- [~] aplicação inicia corretamente via `docker-compose up` — `docker compose
      config` valida a stack e cada build step (pip install, npm ci/build) foi
      verificado isoladamente com sucesso; a subida completa dos 5 serviços não foi
      corrida nesta sessão por o daemon Docker não estar disponível no ambiente de
      desenvolvimento sandbox. Recomendado como primeiro passo de verificação antes
      de avançar para a Fase 2.

## Fase 2 — Intelligence

Technical Analyst, Strategy Engine (interface plugável + `TrendFollowing`,
`Momentum`, `Breakout`, `MeanReversion`), Signals, Opportunity Scoring Engine.
**Objetivo funcional:** o sistema encontra e mostra algo como "BTC/USD — Score 82 —
Momentum — Trending — R/R 2.4 — PAPER TRADE CANDIDATE" (sem ainda executar).

## Fase 3 — Risk & Execution

Risk Engine completo (Safety Belts, Correlation Guard, Position Sizing), Portfolio
Engine, `PaperExecutionProvider`. **Objetivo funcional:** `SIGNAL → RISK APPROVED →
PAPER ORDER → POSITION OPEN → MONITOR → POSITION CLOSED → RESULT SAVED`.

## Fase 4 — News, Regime, Patterns

News Intelligence Agent (LLM), Market Regime Engine, Pattern Engine com
`pattern_performance`.

## Fase 5 — Learning & Research

Learning Agent, Market/Pattern/Strategy/Failure/Research Memory, Strategy Health
Score, Strategy Quarantine, Research Agent. **Objetivo funcional:** o sistema
responde a "que estratégias tiveram melhor desempenho?", "que padrões falharam?",
"que regime domina agora?", "que estratégias devem ser reduzidas?", "o que o
sistema aprendeu recentemente?".

## Fase 6 — Backtesting

Motor de backtest orientado a eventos, walk-forward, out-of-sample, anti-overfitting,
critérios de promoção (`10-backtesting-paper-trading.md`).

## Fase 7 — Advanced Analytics, Alerts, Optimization

Canais de alerta adicionais (email/Telegram/WhatsApp — arquitetura preparada desde a
Fase 1, implementação aqui), otimização de parâmetros, analytics avançado.

## Evolução futura (fora de âmbito até validação completa)

Live brokers, exchanges reais (crypto/forex/ações), ML avançado, deep learning,
reinforcement learning, dados alternativos, order book profundo, sentiment,
opções, arbitragem, multi-agent research — só depois de:

> provar, com dados out-of-sample e paper trading (mínimo 30–90 dias), que existe
> vantagem estatística depois de custos e slippage. Só então uma pequena quantidade
> de capital real é considerada, com aumento gradual e monitorização.

## Fora de âmbito nesta fase (explícito)

Não implementar live trading. Não solicitar chaves privadas de brokers/exchanges.
Não enviar ordens reais. Não assumir que qualquer estratégia é lucrativa.
