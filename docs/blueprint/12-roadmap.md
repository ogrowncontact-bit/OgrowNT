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

## Fase 5 — Learning & Research — **status: implementada e validada nesta sessão**

Learning Agent, Market/Pattern/Strategy/Failure/Research Memory, Strategy Health
Score, Strategy Quarantine, Research Agent. **Objetivo funcional:** o sistema
responde a "que estratégias tiveram melhor desempenho?", "que padrões falharam?",
"que regime domina agora?", "que estratégias devem ser reduzidas?", "o que o
sistema aprendeu recentemente?".

**Critério de sucesso:**
- [x] Strategy Memory: `strategy_performance` recalculado (DET, janela das
      últimas 200 trades, não média incremental — profit factor, Sharpe e
      max drawdown exigem a série real) a cada trade fechado
      (`packages/quant/learning/strategy_stats.py`); Strategy Health Score
      0-100 (expectancy 40% + win rate 15% + profit factor 25% + drawdown
      20%, pesos centralizados) fica `None` (não fabricado) abaixo de 5
      trades na amostra
- [x] Strategy Quarantine: demoção automática e determinística
      (`lifecycle_stage='quarantine'`) quando o health score cai abaixo de
      35 com amostra suficiente — mesmo princípio conservador do Kill
      Switch (Fase 3): só reduz risco, nunca aumenta; o enforcement real é
      `apps/worker/strategy_runner.py` que salta estratégias em
      quarantine/retired antes de gerar sinal (testado ao vivo: 5 perdas
      seguidas da mesma estratégia via `run_trade_monitor_cycle` →
      quarantine automática → zero novos sinais dessa estratégia no ciclo
      seguinte). Restauro é sempre uma ação admin explícita
      (`POST /api/strategies/{id}/restore`), nunca automático
- [x] Failure/Trade Journal Memory: `trade_journal` grava expected vs.
      actual em cada trade fechado; quando divergem (perda), o Learning
      Agent (LLM) gera hipótese+root_cause grounded apenas no contexto
      dado — testado com 6 casos incluindo degradação honesta sem API key
      configurada (`hypothesis`/`root_cause` ficam `None`, nunca inventados)
- [x] Research Agent: candidatos `learned_rules` (LLM, `status='candidate'`)
      só para padrões/estratégias com amostra ≥8 e expectancy ≤ -0.1R;
      validação DET independente (z-test de uma amostra sobre o
      R-multiple real re-consultado da base, não sobre o número que a LLM
      disse) com amostra mínima de 20 — nunca promove `validated` com base
      na confiança declarada pela LLM (`packages/quant/learning/research.py`)
- [x] Market Memory: contexto (regime, padrão, direção, notícias, score)
      gravado por sinal (`market_memory`), outcome preenchido no fecho do
      trade. `pgvector` não está disponível neste Postgres (verificado:
      nem em `pg_available_extensions`) — em vez de fabricar embeddings,
      `embedding` fica explicitamente adiado (mesmo padrão do hypertable
      do `ohlcv` na Fase 1) e a similaridade usa correspondência
      estruturada (regime+padrão+direção) sobre `context`
      (`packages/quant/learning/memory.py`)
- [x] `historical_edge` e `strategy_performance` deixam de ser neutros na
      Opportunity Scoring Engine: `historical_edge` combina a expectancy
      histórica do padrão (Pattern Memory) com a da própria estratégia
      (Strategy Memory) no regime atual; `strategy_performance` usa o
      Health Score diretamente — testado e confirmado ao vivo (injetando
      um `StrategyPerformance` sintético: `strategy_performance` component
      88.0, `historical_edge` 68.75, exatamente conforme a fórmula;
      removido depois de validado, para não poluir os dados reais)
- [x] worker: o Learning Agent corre a cada trade fechado (não numa
      cadência própria — `strategy_performance`/quarantine/journal/market
      memory outcome vivem dentro do `Trade Monitor`, que já corre a cada
      ciclo de scan); o Research Agent tem cadência própria
      (`RESEARCH_INTERVAL_SECONDS`, default 3600s) por analisar dados que
      só mudam ao ritmo de trades fechados
- [x] API: `/api/learning/strategy-performance`, `/api/learning/trade-journal`,
      `/api/learning/memory`, `/api/learning/memory/similar`,
      `/api/research/rules`, `POST /api/strategies/{id}/restore`
      (admin-only); `/api/strategies/{id}/performance` deixa de devolver um
      placeholder e passa a ler `strategy_performance` real
- [x] dashboard mostra Strategy Health (health score, win rate, expectancy,
      lifecycle badge), Learned Rules (status candidate/validated/rejected)
      e Trade Journal (hipóteses) — verificado ao vivo via build de
      produção do Next.js + login real + curl da página renderizada
- [x] 63 novos testes automatizados (219/219 no total da suite, confirmado
      em duas corridas consecutivas)

`packages/llm` continua nunca importado por `packages/execution` — mesmo com
o Research Agent e o Learning Agent a gerar hipóteses/regras via LLM, nada
disso escreve em `positions`/`orders`/`strategies.lifecycle_stage` sem passar
por validação DET (quarantine automática é DET puro; `learned_rules`
validated nunca é aplicado automaticamente a comportamento nenhum — fica
disponível para leitura/auditoria, não para ação).

## Fase 6 — Backtesting — **status: implementada e validada nesta sessão**

Motor de backtest orientado a eventos, walk-forward, out-of-sample, anti-overfitting,
critérios de promoção (`10-backtesting-paper-trading.md`).

**Critério de sucesso:**
- [x] Backtest Engine orientado a eventos (`packages/backtest/engine.py`):
      percorre `ohlcv` já persistido barra a barra, a estratégia só vê
      `candles[0..i]` em cada passo (sem look-ahead) — corre o mesmo
      pipeline do worker (indicadores, regime, padrões, scoring) e reutiliza
      as mesmas funções puras de sizing/safety-belt do Risk Engine
      (`packages/backtest/risk.py`) contra um portfolio simulado isolado
      (`packages/backtest/portfolio.py`) que nunca escreve nas tabelas
      reais de paper trading. Fill simulation extraída para
      `packages/execution/fills.py` e partilhada com o
      `PaperExecutionProvider` — o mesmo modelo de spread/slippage/fees em
      backtest e produção
- [x] Limitações honestas documentadas em código, não escondidas: sem sinais
      de notícias (não são retroativamente atribuíveis a uma barra
      histórica arbitrária), sem `historical_edge`/`strategy_performance`
      vindos do aprendizado ao vivo (usar isso seria uma forma de
      look-ahead), sem correlation guard (motor de um único ativo/uma
      posição de cada vez — estruturalmente não há o que verificar)
- [x] Anti-overfitting: walk-forward (`packages/backtest/walkforward.py`,
      janelas de teste consecutivas, veredicto de consistência a partir da
      expectancy pooled + fração de janelas positivas, nunca `None`
      escondido como falso); parameter stability
      (`packages/backtest/stability.py`, perturbação de ±20% em cada
      parâmetro numérico, veredicto = nenhuma perturbação inverte o sinal
      da expectancy) — só possível porque as 4 estratégias
      (`packages/quant/strategies`) passaram a aceitar os seus parâmetros
      no construtor em vez de constantes fixas, sem alterar o
      comportamento por omissão (219/219 testes pré-existentes continuaram
      a passar inalterados depois do refactor)
- [x] Performance degradation analysis
      (`packages/quant/learning/degradation.py`): compara a expectancy real
      (paper) com a do backtest de referência da estratégia; divergência
      sustentada acima da tolerância → `Alert` de warning (nunca força
      quarentena sozinha — essa já é automática pelo Health Score desde a
      Fase 5), com cooldown de 24h para não repetir o aviso a cada trade
- [x] Critério de promoção (`config/promotion_criteria.yaml`,
      `packages/quant/learning/promotion.py`): `evaluate_promotion` é DET
      puro (nunca decide sozinho); `apply_promotion` só avança
      `lifecycle_stage` (`paper→small_capital→production`) através de uma
      ação admin explícita (`POST /api/strategies/{id}/promote`), que
      revalida os critérios no servidor — nunca confia num veredicto vindo
      do cliente
- [x] API: `POST/GET /api/backtests`, `GET /api/backtests/{id}`,
      `POST /api/backtests/walkforward`,
      `GET /api/strategies/{id}/promotion-check`,
      `POST /api/strategies/{id}/promote`
- [x] dashboard mostra painel de Backtests (execuções recentes) e indicador
      de promotion-readiness no painel de Strategy Health — verificado ao
      vivo via build de produção + login real + inspeção do HTML
      renderizado
- [x] verificado ao vivo contra Postgres real: backtest de
      `trend_following_v1` sobre os ~70 candles mock reais persistidos
      nesta sessão (única história disponível neste ambiente — sem
      fabricar um dataset histórico separado) devolveu corretamente 0
      trades (mercado essencialmente lateral/aleatório nesse curto
      intervalo), com equity curve completa e `params` auditáveis
      persistidos em `backtest_runs`
- [x] 35 novos testes automatizados (254/254 no total da suite, confirmado
      em duas corridas consecutivas)

Nada nesta fase aproxima o sistema de capital real: promoção só avança
`lifecycle_stage`, nunca liga a uma exchange/corretora; `Order.is_paper`/
`Trade.is_paper` continuam sempre `true`.

## Fase 7 — Advanced Analytics, Alerts, Optimization — **status: implementada e validada nesta sessão**

Canais de alerta adicionais (email/Telegram/WhatsApp), otimização de parâmetros,
analytics avançado.

**Critério de sucesso:**
- [x] Canais de entrega de alertas (`packages/notifications/`): `NotificationChannel`
      Protocol comum + `EmailChannel` (stdlib `smtplib`), `TelegramChannel`
      (`httpx` contra a Bot API), `WhatsAppChannel` — este último honesto: sem
      conta Business API real disponível neste ambiente, `is_configured()`
      devolve sempre `False` e o motivo fica documentado no código
      (`TODO(real-whatsapp)`), nunca finge um envio. `NotificationDispatcher`
      faz fan-out para todos os canais, nunca lança exceção — cada tentativa
      (sucesso, falha ou não configurado) fica registada por canal em
      `alert.meta["_delivery"]`. Nova cadência no worker
      (`apps/worker/alerts.py`, `ALERT_DELIVERY_INTERVAL_SECONDS`) marca
      `alerts.delivered_at` em todas as tentativas, mesmo quando nenhum canal
      está configurado
- [x] Lacuna corrigida: nem todos os eventos alerta-dignos escreviam `Alert`
      antes desta fase — mudança de nível de safety belt
      (`packages/risk/monitor.py`) e kill switch manual
      (`apps/api/routers/system.py`) agora escrevem sempre um `Alert` com
      severidade/categoria coerentes
- [x] Otimização de parâmetros (`packages/backtest/optimize.py`): grid search
      limitado (`MAX_COMBINATIONS=30`, amostragem determinística com seed
      quando a grelha excede o limite, combinação base sempre incluída);
      cada candidato é julgado pelo mesmo veredicto de consistência walk-forward
      da Fase 6 — nunca por um único backtest "sortudo". Nunca aplica nada
      sozinho: devolve sempre um relatório ranqueado (`OptimizationResult`),
      a decisão de mudar os parâmetros por omissão de uma estratégia continua
      manual, mesma disciplina "DET propõe, nunca aplica" do
      `promotion.py`/`research.py`
- [x] Analytics avançado (`packages/analytics/overview.py`): agregação pura de
      leitura sobre dados que as fases anteriores já escrevem — equity curve
      (`portfolio_snapshots`), estatísticas globais de trades (win rate,
      expectancy, profit factor), drawdown atual/máximo/pico de equity,
      distribuição de tiers de oportunidade (janela 30 dias), leaderboard de
      padrões por expectancy (`pattern_performance`), distribuição de regimes
      (janela 7 dias). Nenhuma escrita nova na base de dados, nenhum número
      inventado — estado vazio/insuficiente devolve `None`/lista vazia, nunca
      um placeholder
- [x] API: `POST /api/backtests/optimize`, `GET /api/alerts`,
      `POST /api/alerts/{id}/ack`, `GET /api/analytics/overview`
- [x] dashboard mostra painel de Alerts (severidade, categoria, estado de
      entrega/reconhecimento), painel de Equity Curve (sparkline SVG inline,
      sem nova dependência de gráficos) com peak equity/max drawdown/win
      rate/expectancy, distribuição de Opportunity Tiers e Regime Mix, e
      leaderboard de padrões — verificado ao vivo via build de produção do
      Next.js + login real + inspeção do HTML renderizado (SVG da equity
      curve, badges de tier/regime e contagens reais presentes no output)
- [x] verificado ao vivo contra Postgres real: `POST /api/backtests/optimize`
      sobre `trend_following_v1`/AAPL com os mesmos ~70 candles mock reais da
      Fase 6 devolveu corretamente `best_params: null` e a razão "none of N
      candidate parameter sets passed the walk-forward consistency bar"
      (mercado lateral, sem trades reais nessa janela curta — nenhum valor
      fabricado para parecer melhor), com todas as janelas de cada candidato
      persistidas em `backtest_runs` (32 grupos `opt-*` confirmados por query
      direta); `GET /api/analytics/overview` devolveu equity curve, trade
      stats, drawdown e distribuições de tier/regime reais, calculados a
      partir dos dados já existentes no Postgres de desenvolvimento (sem
      dataset fabricado)
- [x] 48 novos testes automatizados (302/302 no total da suite, confirmado em
      duas corridas consecutivas)

Nada nesta fase aproxima o sistema de capital real: os canais de alerta apenas
notificam, nunca decidem; a otimização de parâmetros nunca escreve nos
parâmetros por omissão de uma estratégia; `Order.is_paper`/`Trade.is_paper`
continuam sempre `true`.

## Hardening de segurança (pós-Fase 7) — **status: implementada e validada nesta sessão**

Com as 7 fases do blueprint completas, uma revisão de segurança dedicada
(metodologia: um agente de identificação sobre o branch inteiro, seguido de
um agente de verificação independente por achado candidato — cada um
julgando exploitabilidade concreta contra critérios explícitos de falso
positivo — e só reportando achados com confiança ≥ 8/10) encontrou 3 lacunas
reais, todas corrigidas nesta sessão:

- [x] **~30 endpoints `GET` sem autenticação** (`/api/portfolio`,
      `/api/trades`, `/api/trades/{id}/why`, `/api/opportunities`,
      `/api/backtests`, `/api/learning/*`, `/api/research/rules`,
      `/api/news`, `/api/patterns*`, `/api/analytics/overview`,
      `/api/strategies*`, `/api/market-data/*`, `/api/assets`, `/api/alerts`)
      — contradizia diretamente `docs/blueprint/03-api-spec.md` ("Todas as
      rotas abaixo, exceto `/api/auth/login` e `/api/system/health`, exigem
      `Authorization: Bearer <token>`") e era explorável no deployment
      padrão (`docker-compose up`, API exposta em `0.0.0.0:8000`). Corrigido
      adicionando `Depends(get_current_admin)` a cada um; o dashboard
      (`apps/dashboard/lib/api.ts`) agora passa o token em cada fetcher; 14
      novos testes `requires_auth` cobrem cada endpoint corrigido
- [x] **JWT_SECRET/ADMIN_PASSWORD com valores por omissão públicos e sem
      guarda de arranque** (`change-me-to-a-long-random-string`/`change-me`,
      idênticos ao `.env.example` commitado) — nada impedia o sistema de
      arrancar com esses valores, permitindo forjar um JWT admin válido.
      Corrigido com um `model_validator` em `packages/shared/settings.py`
      que recusa arrancar (`ValueError`) se `jwt_secret`/`admin_password`
      ainda forem exatamente os placeholders — verificado a bloquear o
      arranque com os valores por omissão e a passar com valores reais,
      sem afetar testes/CI (que já usam segredos fixos mas diferentes)
- [x] **CORS `allow_origins=["*"]`** — combinado com o achado anterior,
      permitia que qualquer página que o browser do operador visitasse lesse
      respostas da API via `fetch()` cross-origin. Corrigido com
      `CORS_ALLOWED_ORIGINS` (`packages/shared/settings.py`), por omissão
      restrito às origens do próprio dashboard (`localhost:3000`/
      `127.0.0.1:3000`) — verificado ao vivo: preflight de uma origem
      permitida devolve `Access-Control-Allow-Origin`, uma origem arbitrária
      não devolve nada
- [x] verificado ao vivo contra Postgres real: `curl` sem token a
      `/api/portfolio`/`/api/trades`/`/api/analytics/overview` devolve 401;
      `/api/system/health` continua público (200); login com a nova
      password funciona; todos os endpoints antes abertos devolvem 200 com
      token válido; dashboard testado via build de produção + login real —
      todos os painéis (incluindo o novo Equity Curve/Analytics) continuam a
      mostrar dados reais, zero fugas 401
- [x] 14 novos testes automatizados (316/316 no total da suite, confirmado
      em três corridas consecutivas, incluindo uma migração `alembic upgrade
      head` completa 0001→0007 contra uma base de dados nova)

Nada nesta secção altera comportamento de trading: são apenas correções de
controlo de acesso e configuração — nenhuma lógica de scoring, risco ou
execução foi tocada.

## Dev hygiene: lint, type-checking, container hardening (pós-Fase 7) — **status: implementada nesta sessão; ver notas de verificação abaixo**

- [x] **`ruff`** (`pyproject.toml`'s `[tool.ruff]`) adicionado e ligado ao CI
      (E/F/I/UP/B — bugs reais e higiene de imports, não uma reescrita de
      estilo). Corrigiu 7 imports não utilizados, um footgun de argumento
      por omissão mutável num endpoint (`apps/api/routers/strategies.py`'s
      `restore_strategy`), e um `zip()` sem `strict=`. 316/316 testes
      continuam a passar
- [x] **`mypy`** (com o plugin `pydantic.mypy`, para que os modelos de
      resposta FastAPI construídos a partir de dataclasses via
      `from_attributes` sejam corretamente verificados) adicionado e ligado
      ao CI, limpo em 116 ficheiros-fonte. O achado mais importante: o
      Trade Monitor podia falhar o ciclo inteiro (deixando todas as outras
      posições abertas sem monitorização até reiniciar) se uma posição
      referenciasse um `Asset` em falta — corrigido com o mesmo padrão de
      "saltar com aviso DATA_UNAVAILABLE" já usado para preço em falta.
      Corrigidos guardas semelhantes noutros pontos (um endpoint que podia
      devolver 500 numa única linha má, duas ações admin com invariantes
      cross-função agora explicitamente guardadas) — sem alterar
      comportamento fora desses casos
- [~] **Non-root containers**: as três Dockerfiles (`infra/docker/
      Dockerfile.{api,worker,dashboard}`) foram alteradas para correr como
      utilizador não-root (`useradd`+`chown`+`USER` nas imagens Python;
      o utilizador `node` já embutido na imagem `node:20-alpine`) — prática
      standard de hardening de containers. `docker compose config` continua
      a validar com sucesso. **Não verificado com um build/run real** (sem
      daemon Docker disponível nesta sandbox, o mesmo bloqueio documentado
      na Fase 1) — recomendado correr `docker compose up --build` uma vez
      antes de confiar nisto em produção.

## Supervisor 24/7 (pós-Fase 7) — **status: implementada e validada nesta sessão**

O worker (`apps/worker/main.py`) já corria em loop desde a Fase 1, mas com
um único `try/except` a envolver o ciclo inteiro e sem nenhuma forma de
`/api/system/health` saber se o processo em si estava vivo — o mesmo
princípio de "no hallucinated data" que já se aplicava a preços/notícias em
falta (`docs/blueprint/00-overview.md`) não se aplicava à própria saúde do
worker: todos os outros componentes podiam reportar verde com o loop 24/7
morto ou preso. Corrigido com três primitivas concretas, deliberadamente sem
reescrever o loop numa framework de orquestração (`docs/blueprint/
01-repo-structure.md`'s "O que não existe e porquê" continua válido — nada
de "Master Agent" de dispatch):

- [x] **Heartbeat** (`packages/shared/worker_health.py`,
      `SystemState.worker_last_heartbeat`, migração `0008`) — escrito uma vez
      por iteração completa do loop, independentemente do resultado de cada
      cadência. `/api/system/health` reporta o componente `worker` como
      `red` (`overall: degraded`) se não houver heartbeat ou se estiver mais
      velho que `max(3 × scan_interval_seconds, 180s)`, `green` caso
      contrário — vive em `packages/shared` (não em `apps/worker`) para que
      `apps/api` continue a nunca importar de `apps/worker`, o mesmo padrão
      já usado por `packages/shared/market_data.py`
- [x] **Isolamento por cadência** (`apps/worker/main.py`) — as 5 cadências do
      loop (scan+monitor+safety-belt, news, strategy, research,
      alert-delivery) passaram a ter cada uma o seu próprio `try/except`; uma
      falha numa cadência (ex.: notícias) já não impede as outras de
      correrem nesse mesmo ciclo nem mata o processo
- [x] **Alerta em falhas consecutivas** (`apps/worker/supervisor.py`'s
      `CadenceFailureTracker`) — 1 falha isolada é normal (já fica no log);
      3 falhas consecutivas na mesma cadência geram um `Alert`
      (`category=system`, `severity=warning`) através do pipeline de entrega
      já existente (Fase 7), exatamente uma vez por streak (não repete a
      cada falha subsequente; uma cadência que recupera e volta a falhar
      gera um novo alerta)
- [x] **`restart: unless-stopped`** adicionado a `postgres`/`api`/`worker`/
      `dashboard` em `infra/docker/docker-compose.yml` (o serviço `migrate`,
      one-shot, fica deliberadamente sem)
- [x] 13 novos/atualizados testes automatizados (333/333 no total da suite,
      confirmado após esta alteração) cobrindo `record_heartbeat`/
      `is_heartbeat_stale` (incluindo o piso de 180s com
      `scan_interval_seconds` muito curto) e `CadenceFailureTracker`
      (threshold exato, não-repetição, reset em sucesso, contadores
      independentes por cadência)
- [x] **verificado ao vivo** contra Postgres real: `/api/system/health`
      reportou `worker: red` ("no heartbeat recorded yet") antes do worker
      arrancar; após arrancar o processo real (`python -m apps.worker.main`)
      e completar um ciclo real, passou a `worker: green` ("last heartbeat
      2026-08-18T11:33:39+00:00"); um segundo ciclo real, ~60s depois,
      avançou o heartbeat para 11:34:40 — confirma que o mecanismo reflete
      liveness contínua, não uma escrita única. Dashboard renderiza o novo
      componente `worker` sem nenhuma alteração de código (mapeia
      genericamente sobre `health.components`)

Nada nesta secção altera lógica de scoring, risco ou execução — apenas
observabilidade do próprio processo 24/7 e isolamento de falhas entre
cadências.

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
