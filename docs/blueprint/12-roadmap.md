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

## Fase 2 — Intelligence — **status: implementada e validada nesta sessão**

Technical Analyst, Strategy Engine (interface plugável + `TrendFollowing`,
`Momentum`, `Breakout`, `MeanReversion`), Regime Engine (subset de 5 regimes —
os restantes exigem o News Intelligence Agent da Fase 4), Signals, Opportunity
Scoring Engine. **Objetivo funcional:** o sistema encontra e mostra algo como
"BTC/USD — Score 82 — Momentum — Trending — R/R 2.4 — PAPER TRADE CANDIDATE"
(sem ainda executar).

**Critério de sucesso:**
- [x] indicadores técnicos (SMA/EMA/RSI/ATR/ROC/volatilidade/trend strength)
      com testes unitários (`packages/quant/indicators`)
- [x] Regime Engine classifica `trending_bull/bear`, `ranging`,
      `high/low_volatility` a partir de dados reais — testado com séries
      sintéticas de tendência/lateralização
- [x] 4 estratégias plugáveis, cada uma com `best_regimes`/`worst_regimes`
      declarados e testadas isoladamente (ex.: mean reversion corretamente
      contraria a tendência, sendo penalizada pelo `regime_fit`)
- [x] Opportunity Scoring Engine determinístico, pesos centralizados em
      `config/scoring_weights.yaml`, com testes de fronteira dos tiers
- [x] pipeline completo corrido ponta-a-ponta contra Postgres real: 22 ativos
      → 23 sinais → scores → 6 oportunidades em tier `watch` (nenhuma ainda
      em `possible`+, porque 4 dos 8 componentes do score ficam num default
      neutro honesto até `pattern`/`news`/`historical_edge`/
      `strategy_performance` existirem nas Fases 4-5 — ver
      `packages/quant/scoring/inputs.py`)
- [x] API: `/api/strategies`, `/api/strategies/{id}/performance`,
      `/api/opportunities`, `/api/opportunities/{id}`, `/api/signals`,
      `/api/regime` — testados via `TestClient`
- [x] dashboard mostra "Top Opportunities" e regime por ativo com dados reais
      (verificado via curl contra API+dashboard reais, não só build)
- [x] 34 novos testes automatizados (52/52 no total da suite)
- [x] documentação atualizada (este roadmap)

Nada disto executa uma ordem — o Execution Engine só chega na Fase 3. Todas
as "oportunidades" mostradas são candidatas de leitura, nunca uma posição.

## Fase 3 — Risk & Execution — **status: implementada e validada nesta sessão**

Risk Engine completo (Safety Belts, Correlation Guard, Position Sizing), Portfolio
Engine, `PaperExecutionProvider`. **Objetivo funcional:** `SIGNAL → RISK APPROVED →
PAPER ORDER → POSITION OPEN → MONITOR → POSITION CLOSED → RESULT SAVED`.

**Critério de sucesso:**
- [x] Portfolio Engine: `packages/portfolio` computa equity/cash/exposure/
      drawdown/P&L diário e semanal a partir de posições abertas + preços
      reais, `portfolio_snapshots` como ledger append-only
- [x] Position Sizing: sempre o menor entre risk-budget, portfolio headroom,
      correlation headroom e single-asset cap — nunca tamanho fixo
- [x] Correlation Guard: correlação de Pearson real sobre retornos de OHLCV
      (não assumida), bloqueia quando um cluster correlacionado excede o
      limite configurado
- [x] Safety Belts (`normal/caution/defensive/emergency/kill_switch`) 
      avaliados a partir de drawdown/perdas reais, com política de tamanho
      e piso de tier por nível; Kill Switch automático a 1.5× o limiar de
      `EMERGENCY`, deliberadamente conservador
- [x] Risk Engine: pipeline de 10 passos completo (kill switch → safety
      belt → data quality → risk/reward → exposição → concentração →
      correlação → liquidez → perdas diária/semanal → sizing), cada passo
      gravado em `risk_checks`/`risk_decisions` para auditoria — **nunca**
      pode ser contornado por outro módulo
- [x] `PaperExecutionProvider`: simula spread, slippage (cresce com o
      tamanho da ordem vs. volume) e fees; nunca liga a um broker real
- [x] Trade Monitor: fecha posições em stop hit, target hit, ou tese
      invalidada (mudança de regime para o pior regime da estratégia) —
      testado deterministicamente, não à espera de um random walk ao vivo
- [x] worker: ciclo de risco+execução corre organicamente dentro do
      Strategy Engine cycle — validado ao vivo contra Postgres real: um
      sinal GOOGL/breakout atingiu score 72.17 (tier `possible`), foi
      aprovado pelo Risk Engine e executado, sem qualquer atalho de teste
- [x] API: `/api/risk`, `/api/positions` (agora real), `/api/orders`,
      `/api/trades`, `/api/trades/{id}/why`, `PATCH /api/system/risk-limits`
- [x] dashboard mostra posições reais e trades recentes (verificado ao vivo)
- [x] 53 novos testes automatizados (105/105 no total da suite), incluindo
      isolamento real por teste (savepoint + rollback) depois de a suite
      partilhada ter começado a mascarar bugs — corrigido pelo caminho um
      bug real de wiring (`get_current_admin` não passava pela dependência
      de sessão testável)

Ainda nada de dinheiro real: `Order.is_paper`/`Trade.is_paper` sempre `true`,
nenhum adapter de broker/exchange real está registado.

## Fase 4 — News, Regime, Patterns — **status: implementada e validada nesta sessão**

News Intelligence Agent (LLM), Market Regime Engine (taxonomia completa), Pattern
Engine com `pattern_performance`.

**Critério de sucesso:**
- [x] News ingestion determinística (`packages/data/connectors/news`, mock
      provider claramente identificado — nunca fabrica um item de notícia)
- [x] LLM interpretation layer real (`packages/llm`, wrapper sobre a API da
      Anthropic): estruturalmente isolado da execução (`packages/llm` nunca
      é importado por `packages/execution`), e todo output é validado
      (símbolo tem de estar no universo, enums e ranges verificados) antes
      de ser aceite — testado com 14 casos incluindo saída malformada,
      símbolo fora do universo, enums inválidos
- [x] Sem `ANTHROPIC_API_KEY`: degrada de forma honesta — notícias
      continuam a ser ingeridas, interpretação fica a neutro, reportado como
      🟡 no health check, nunca fabricado
- [x] Pattern Engine: 8 detectores determinísticos (trend, breakout,
      reversal, momentum, mean_reversion, volatility, anomaly, cross_asset),
      cada um testado isoladamente com dados sintéticos
- [x] Regime Engine completo: `classify_regime_with_news` adiciona
      `panic`/`euphoria`/`transition` a partir de notícias reais e recentes
      — testado com os 5 casos (bearish→panic, bullish→euphoria,
      misto→transition, baixa confiança→transition, sem notícia→inalterado)
- [x] `pattern`/`news` deixam de ser neutros na Opportunity Scoring Engine:
      alinhados com o sinal sobem o score, em conflito descem — testado e
      confirmado ao vivo (score subiu de ~67 para 72.74 com um padrão
      momentum alinhado, `news_component` foi de 50 para 95 com uma notícia
      bullish de alta confiança)
- [x] `pattern_performance` atualizado pelo Trade Monitor quando uma posição
      cujo sinal tinha um padrão associado fecha — médias incrementais
      testadas (win rate, R médio, expectancy)
- [x] worker: novo ciclo de notícias com cadência própria, corre antes do
      Strategy Engine cycle para que `news_impact` esteja fresco quando a
      classificação de regime e o scoring o consultam
- [x] API: `/api/news`, `/api/patterns`, `/api/patterns/performance`
- [x] dashboard mostra painel de notícias com impacto interpretado por
      ativo (verificado ao vivo: notícia sintética → interpretação →
      renderizada na UI)
- [x] 51 novos testes automatizados (156/156 no total da suite)

`packages/llm` nunca é importado por `packages/execution` — a separação
estrutural "LLM ≠ Trading Engine" (`00-overview.md`) permanece válida mesmo
com uma LLM real ligada.

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
