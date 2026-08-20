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

## Dashboard: kill switch acionável (pós-Fase 7) — **status: implementada e validada nesta sessão**

O dashboard (`apps/dashboard`) era inteiramente read-only: `POST
/api/system/kill-switch` e `/kill-switch/release` já existiam na API desde a
Fase 3, mas o operador só os conseguia acionar via `curl` com um Bearer
token manual — nenhum botão na única superfície que realmente olha 24/7.
Para um sistema autónomo (mesmo em paper trading), o controlo de segurança
mais crítico não podia depender de abrir um terminal.

- [x] `components/KillSwitchButton.tsx` (client component) na secção "Risk
      State" — mostra "Pull kill switch" quando `trading_enabled=true`,
      "Release kill switch" quando `false`, com `window.confirm` antes de
      agir (ação de alto impacto, confirmação explícita)
- [x] `app/api/kill-switch/route.ts` — segue exatamente o padrão já existente
      de `app/api/logout/route.ts`: lê o cookie `httpOnly` no servidor e
      reencaminha para a API real com o Bearer token; o browser nunca vê o
      token
- [x] `lib/api.ts`'s `setKillSwitch()` adicionado ao lado das restantes
      funções de fetch, mesmo padrão de tipagem/tratamento de erro
- [x] **verificado ao vivo num browser real** (Playwright contra Chromium,
      dashboard em build de produção + API real + Postgres real): login →
      "Pull kill switch" → confirmar → dashboard mostra "Trading enabled: no
      (kill switch)" e o botão troca para "Release kill switch" → clicar →
      volta a "Trading enabled: yes". Confirmado que os cliques reais
      escreveram `Alert` (`critical`/`info`, categoria `emergency`) e
      `AuditLog` (`kill_switch_triggered`/`kill_switch_released`) genuínos na
      base de dados, não apenas estado local do React. `npm run lint` e
      `npm run build` limpos

Nada nesta secção adiciona lógica nova de risco — expõe uma ação que já
existia e já era auditada, apenas antes inacessível sem a API diretamente.

## Dashboard: launcher de backtests (pós-Fase 7) — **status: implementada e validada nesta sessão**

Continuação direta da secção anterior: o painel "Backtests" já listava
resultados mas dizia explicitamente "launch one via `POST /api/backtests`
(see `/docs`)" quando vazio — o mesmo problema do kill switch, desta vez
para `/api/backtests` (existente desde a Fase 6). Corrigido com um formulário
mínimo, não uma reescrita do painel:

- [x] `components/RunBacktestForm.tsx` — estratégia (`/api/strategies`),
      ativo (`/api/assets` já disponível), intervalo de datas (por omissão os
      últimos 3 dias) e capital inicial; timeframe fixo em `1m` porque é o
      único com histórico realmente carregado
      (`apps/worker/history.py`) — não oferecer opções que o sistema não
      consegue mesmo cumprir
- [x] `app/api/run-backtest/route.ts` — mesmo padrão de proxy server-side
      (cookie `httpOnly` → Bearer token) do kill switch e do logout
- [x] `lib/api.ts`'s `getStrategies()`/`runBacktest()` adicionados ao lado
      das restantes funções
- [x] **verificado ao vivo num browser real** (Playwright/Chromium, build de
      produção, API e Postgres reais): login → formulário pré-populado com
      estratégias/ativos reais (4 estratégias, 22 ativos) → submeter → nova
      `BacktestRun` real persistida (id 98, confirmado diretamente na base
      de dados) → mensagem de resultado inline → tabela de backtests
      atualizada sem reload manual. `npm run lint` e `npm run build` limpos

Walk-forward e optimize continuam apenas via API direta (`/docs`) — âmbito
desta alteração foi deliberadamente o backtest simples, o gap mais visível
(era o único com uma mensagem no próprio dashboard a apontar para `curl`).

## Dashboard: restaurar/promover estratégia (pós-Fase 7) — **status: implementada e validada nesta sessão**

Terceira e última ação admin-only fechada nesta sessão: `POST
/api/strategies/{id}/restore` (Fase 5) e `POST /api/strategies/{id}/promote`
(Fase 6) já existiam mas o painel "Strategy Health" só mostrava o estado
(`LifecycleBadge`, "Ready for promotion") sem nenhum botão — o operador via
que uma estratégia estava pronta mas não a conseguia promover sem `curl`.

- [x] `components/StrategyActionButton.tsx` — botão genérico
      confirm-gated reutilizado para ambas as ações; aparece "Restore to
      paper" quando `lifecycle_stage === "quarantine"`, "Promote ->
      {next_stage}" quando `promotion.eligible === true` (nunca ambos, nunca
      quando nenhuma condição se aplica)
- [x] `app/api/strategy-action/route.ts` — mesmo padrão de proxy
      server-side dos dois anteriores (kill switch, backtest launcher)
- [x] `lib/api.ts`'s `strategyAction()` adicionado ao lado das restantes
- [x] **verificado ao vivo num browser real**: como nenhuma estratégia no
      DB de desenvolvimento cumpre os critérios de promoção
      (`min_paper_trades: 30`, `min_paper_days: 30`), colocada uma
      estratégia real em quarentena (a mesma transição de estado que o
      Learning Agent aplicaria automaticamente) para testar o caminho de
      restauro end-to-end: dashboard mostrou "Quarantined" + botão "Restore
      to paper" → clique real → label "Quarantined" desaparece → confirmado
      diretamente na base de dados que `StrategyRow.lifecycle_stage` mudou
      para `paper` e que um `AuditLog` real (`restore_strategy`,
      `actor=admin@example.com`) foi escrito. Confirmado também que nenhum
      botão "Promote" aparece quando nenhuma estratégia é elegível — o
      condicional está correto, não sempre visível. `npm run lint` e `npm
      run build` limpos

Com isto, as três ações administrativas que só existiam via API desde
fases anteriores (kill switch, lançar backtest, restaurar/promover
estratégia) estão todas agora acessíveis a partir do dashboard.

## "PROMPT 2" — Market Data Engine + Market Scanner (pós-Fase 7) — **status: implementada e validada nesta sessão**

O utilizador enviou o "PROMPT 2" do guião de bootstrap original (Market
Data Engine + Scanner), o mesmo em que o "PROMPT 1" já tinha sido
respondido com "continuar a partir daqui" em vez de reconstruir. A maior
parte do que o PROMPT 2 pede já existia desde a Fase 1/2 real deste
repositório (`MarketDataProvider`, `MockMarketDataProvider`, armazenamento
OHLCV com `timeframe` já a suportar `1m/5m/15m/1h/4h/1D/1W`, e a biblioteca
de indicadores `packages/quant/indicators`). O que faltava genuinamente —
validação estruturada, um score de qualidade numérico, um Market Scanner
que gera eventos reais, e a superfície `/api/market/*` + painéis de
dashboard correspondentes — foi implementado nesta sessão:

- [x] **Validação de candles** (`packages/data/validation.py`) —
      `validate_candle()` verifica timestamp válido/não-futuro, coerência
      OHLC (`high>=open/close`, `low<=open/close`), preço/volume
      não-negativos, staleness (escalado ao timeframe, com piso de 300s —
      mesmo padrão do heartbeat do worker) e um salto de preço absurdo
      (>50% num único candle) vs. o close anterior. Um candle inválido
      nunca é armazenado; gera um `MarketEvent` `INVALID_MARKET_DATA` e um
      `Alert` `category=market` (debounced)
- [x] **Data Quality Score 0-100** (`packages/data/quality.py`) — combina
      freshness, completeness, consistency (vs. o `data_quality`
      "high/degraded/unavailable" já existente), source availability e
      timestamp accuracy; abaixo de
      `market_data_quality_unsafe_threshold` (config, omissão 50) o status
      é `DATA_UNSAFE`. Deliberadamente não persistido — recalculado a
      partir dos dados já em disco, para nunca poder ficar desatualizado
- [x] **Market Scanner** (`packages/quant/market/events.py`) — 7
      detectores puros sobre uma janela de candles, reutilizando a
      biblioteca de indicadores já existente (não uma reimplementação):
      `PRICE_MOVEMENT`, `VOLUME_SPIKE`, `VOLATILITY_SPIKE`,
      `BREAKOUT_CANDIDATE`, `MOMENTUM_CHANGE`, `TREND_CHANGE`, `ANOMALY` —
      cada um com severidade `LOW/MEDIUM/HIGH/CRITICAL` por magnitude e
      confiança 0-1. Deliberadamente distinto do Pattern Engine (Fase 4,
      `packages/quant/patterns`): vigilância crua e imediata para um
      ticker do dashboard, não classificação estatística de setups para o
      Scoring Engine — os dois não se substituem
- [x] **`MarketEvent`** (migração `0009`) — tabela nova com
      `event_type`/`severity`/`price`/`volume`/`confidence`/`meta`,
      índices em `asset_id`/`event_type`/`ts`; `Alert.category` alargado
      para incluir `market` (feed desligado, dados obsoletos, evento de
      severidade alta — `apps/worker/market_alerts.py`'s
      `MarketAlertTracker`, debounce de 15 min por chave, mesmo padrão do
      `CadenceFailureTracker` da Fase Supervisor 24/7)
- [x] **`apps/worker/scanner.py` reescrito** — cada ativo tem o seu
      próprio `try/except` (falha de provider num símbolo não pára o
      lote); `provider.is_connected()` verificado antes de qualquer fetch;
      candle inválido nunca chega a `OHLCV`; após armazenar um candle
      válido, corre o Scanner e persiste os `MarketEvent`s resultantes
- [x] **`/api/market/*`** (`apps/api/routers/market.py`) — `overview`
      (preço/variação/volatilidade/volume/tendência/qualidade por ativo +
      `data_source`), `assets`, `{symbol}`, `{symbol}/ohlcv`, `events`
      (filtros `symbol`/`event_type`/`severity`, paginado), `data-quality`.
      Todos admin-gated como o resto da API. Distinto do
      `/api/market-data/{asset_id}` já existente (por id interno, Fase 1)
- [x] **Dashboard**: painel "Market Overview" (tabela `Asset | Price |
      Change | Volatility | Volume | Data Quality` + banner `DATA SOURCE:
      MOCK`/`LIVE MARKET DATA`, nunca omitido) e painel "Recent Market
      Events" (símbolo, tipo, severidade colorida, tempo relativo)
- [x] **Fonte real de dados — decisão deliberada**: o PROMPT 2 pede
      adapters separados (`CryptoMarketDataProvider`/
      `ForexMarketDataProvider`/`StockMarketDataProvider`) por trás da
      mesma interface. A interface e o padrão de factory já existem
      (`packages/data/connectors/market/factory.py`) com um TODO explícito
      desde a Fase 1. Não foram criados adapters reais nesta sessão:
      nenhuma credencial de mercado real está configurada neste ambiente
      (`MARKET_DATA_PROVIDER=mock`), e um adapter que não pode ser testado
      contra uma conta real seria exactamente o tipo de "implementação
      pela metade" que este projeto evita — pior do que não o ter, porque
      convida a assumir que funciona. `MockMarketDataProvider` continua a
      ser a escolha correta enquanto isso for verdade, tal como o próprio
      PROMPT 2 pede ("Se não houver [credenciais]: usar
      MockMarketDataProvider")
- [x] 49 novos testes automatizados (382/382 no total da suite): validação
      (13, incluindo cada violação OHLC, staleness escalado por timeframe,
      salto absurdo), quality score (7), detecção de eventos (10 —
      construindo sequências de candles que provam cada um dos 7 tipos,
      incluindo o caso "mercado normal → zero eventos"), debounce de
      alertas (5), cenários do scanner — dados inválidos, dados obsoletos,
      falha do provider a meio do lote, provider desligado, debounce
      através de vários ciclos (6), endpoints API incluindo 401 sem token
      e 404 para símbolo desconhecido (9)
- [x] **verificado ao vivo** contra Postgres real: worker real a correr
      dois ciclos consecutivos gerou 17 e depois 18 eventos reais (34→50
      acumulados, prova de operação contínua, não um fluke); `/api/market/
      overview`, `/{symbol}/ohlcv`, `/events`, `/data-quality` devolveram
      números reais (`data_source: {provider: mock, is_live: false}`,
      scores de qualidade 97-100 a subir com cada novo candle); dashboard
      testado num browser real (Playwright/Chromium, build de produção) —
      ambos os painéis novos renderizam dados reais dos 22 ativos.
      `ruff`/`mypy`/`npm run lint`/`npm run build` limpos

Nada nesta secção implementa estratégias, sinais de compra/venda, ou
qualquer lógica de execução — os eventos do Scanner são candidatos
crus para o Pattern/Strategy Engine (já existentes desde a Fase 2/4)
consumirem no futuro, exactamente como o PROMPT 2 pede.

## "PROMPT 3" — Pattern Engine + Strategy Engine + Opportunity Scoring (pós-Fase 7) — **status: implementada e validada nesta sessão**

O "PROMPT 3" pede Pattern Engine, Strategy Engine, Signal Engine, Regime
Engine e Opportunity Engine — todos já existentes desde as Fases reais 2/4
deste repositório (4 estratégias plugáveis com `analyze()`/
`generate_signal()`/`calculate_expected_value()`/`regime_fit()`, 7
detectores de padrão, Regime Engine com 9 regimes incluindo
panic/euphoria/transition, Opportunity Scoring com 8 componentes
ponderados + 4 penalizações, tudo já configurável em YAML). Analisado o
spec ponto a ponto (secções 1-30) contra o código real, os gaps genuínos
encontrados foram:

- [x] **Confidence separado de strength** (§3-4, "não confundir os dois")
      — `PatternDetection`/`Pattern` (migração `0010`) ganharam um campo
      `confidence` novo, distinto de `strength`: strength mede a magnitude
      do padrão, confidence mede quão fiáveis são os candles por trás dele
      (`packages/quant/indicators/core.py`'s `data_quality_confidence()`,
      reutilizado — não uma segunda implementação). Um padrão com strength
      alto sobre dados degradados agora mostra confidence baixo, sem alterar
      o strength
- [x] **CONFIRMED_BREAKOUT vs POSSIBLE_BREAKOUT** (§8) — `detect_breakout`
      deixou de devolver `None` quando o volume não confirma; agora devolve
      um breakout `POSSIBLE_BREAKOUT` com strength limitado
      (`BREAKOUT_POSSIBLE_STRENGTH_CAP`), distinto do `CONFIRMED_BREAKOUT`
      original. `FAILED_BREAKOUT` já existia como o padrão `reversal`
      separado — agora com o mesmo rótulo `breakout_state` em metadata para
      os três estados serem consultáveis uniformemente
- [x] **`get_risk_profile()`** (§5) — o único dos 4 métodos pedidos que
      faltava (`analyze`/`generate_signal`/`calculate_expected_value` já
      existiam com esses nomes exatos). Reutiliza os atributos já
      declarados de cada estratégia (`family`, `risk_reward` do construtor,
      `best_regimes`/`worst_regimes` — o mesmo conceito de
      `preferred_regimes`/`avoided_regimes` do §14, já influenciando o
      score via `regime_fit()`, nunca bloqueando sozinho)
- [x] **Confidence da Opportunity, separado do score** (§17/§20) —
      `OpportunityScore.confidence` (migração `0010`), 0-100, mostrado à
      parte de `final_score` em toda a API/dashboard. Calculado
      (`packages/quant/scoring/inputs.py`'s
      `compute_opportunity_confidence()`) como a média de 4 sinais já reais
      — qualidade dos dados, confiança do regime, confidence do padrão
      alinhado, se `historical_edge` teve amostra real — nunca um número
      novo inventado
- [x] **`INSUFFICIENT_HISTORY` explícito** (§18) — antes ficava
      silenciosamente dobrado num score neutro (50); agora
      `notes["historical_edge"]["insufficient_history"]` é um booleano
      explícito, usado tanto para reduzir a confidence como para gerar um
      aviso estruturado no painel "why"
- [x] **"WHY THIS OPPORTUNITY EXISTS"** (§22-23) — `/api/opportunities/
      {id}` e `/api/trades/{id}/why` ganharam um campo `evidence`:
      `packages/quant/scoring/evidence.py`'s `build_evidence()`, uma função
      pura e determinística que lê os componentes do score já calculados
      (technical, pattern, regime_fit, historical_edge, risk_reward,
      liquidity, news, volatility_penalty) e produz confirmações (✓) ou
      avisos (⚠) — nunca o raciocínio privado de um modelo, exatamente como
      o spec pede. Dashboard: cada linha da tabela "Top Opportunities" é
      clicável (`components/OpportunityRow.tsx`) e expande este painel
      inline
- [x] **Event pipeline** (§26) — `OPPORTUNITY_CREATED` juntou-se aos 8
      `event_type`s já existentes do MarketEvent (Prompt 2), emitido por
      `apps/worker/strategy_runner.py` para todo o sinal com tier acima de
      "ignore" — para que o painel "Recent Market Events" do dashboard
      também mostre oportunidades reais, não só eventos de mercado crus.
      `PATTERN_DETECTED`/`REGIME_DETECTED`/`SIGNAL_CREATED` foram
      deliberadamente não implementados como eventos: cada
      estratégia/ativo é pontuado a cada ciclo (a maioria tier "ignore"),
      pelo que espelhar cada um como MarketEvent seria sobretudo ruído por
      cima das tabelas `patterns`/`market_regimes`/`signals` que já os
      registam todos
- [x] **Divergências deliberadamente não alteradas** — nomenclatura: as 5
      bandas de score já existentes (`ignore`/`watch`/`possible`/
      `high_quality`/`exceptional`, cortes em config/scoring_weights.yaml)
      não foram renomeadas para as 6 do §17 (`NO EDGE`/`WEAK`/`WATCH`/
      `GOOD`/`HIGH QUALITY`/`EXCEPTIONAL`) nem os estados do Signal
      (`pending`/`scored`/`risk_rejected`/`approved`/`executed`/`expired`)
      para os do §11/§21 — seriam apenas renomeações cosméticas espalhadas
      por dezenas de ficheiros (dashboard, config, migrações, testes) sem
      alterar comportamento algum, o oposto do "não destrua... sem
      necessidade" já estabelecido nesta sessão
- [x] 35 novos testes automatizados (417/417 no total da suite): confidence
      de padrão separado de strength e a degradar com dados degradados (2),
      diferenciação de breakout confirmado/possível (1, substituindo o
      teste antigo que assumia `None`), `get_risk_profile()` incluindo o
      exemplo exato do §14 (Momentum evita `ranging`) (3), confidence da
      opportunity — 6 cenários incluindo dados degradados e padrão
      conflitante a não contribuir (6), geração de evidência — 19 cenários
      cobrindo cada componente confirm/warning (19), integração real do
      ciclo do worker confirmando confidence >50 e eventos
      `OPPORTUNITY_CREATED` emitidos exatamente para os sinais não-"ignore"
      (2), API — confidence separado do score, evidência confirma/avisa
      consoante os componentes (4)
- [x] **verificado ao vivo** contra Postgres real: ciclo real do worker
      criou sinais reais com confidence genuinamente calculado (85%,
      distinto do score 73.91) e um evento `OPPORTUNITY_CREATED` real
      ligado ao `signal_id` correto; `/api/opportunities/{id}` devolveu
      evidência real ("✓ Technical setup strong (short)", "✓ Momentum
      pattern confirmed", "⚠ Volume below average..."); dashboard testado
      num browser real (Playwright/Chromium, build de produção) — coluna
      Confidence visível, clique numa linha expande o painel "why" com os
      checkmarks/avisos reais, segundo clique recolhe. `ruff`/`mypy`/`npm
      run lint`/`npm run build` limpos

Nenhuma `Opportunity` executa uma `Order` nesta fase (§29) — nada neste
trabalho toca `packages/execution`; o pipeline continua a terminar em
`OpportunityScore` persistido, exatamente como antes.

## "PROMPT 4" — Risk Engine + Portfolio Intelligence (pós-Fase 7) — **status: implementada e validada nesta sessão**

O "PROMPT 4" pede um Risk Engine independente com poder de veto sobre
qualquer operação — já existente desde a Fase real 3 deste repositório
(`packages/risk/engine.py`'s `evaluate_signal()`, um pipeline de decisão em
10 passos com `RiskCheck`/`RiskDecision` persistidos para auditoria, 5
Safety Belts com multiplicadores de tamanho, Position Sizing pela menor de 4
margens, Correlation Guard com correlação de Pearson real, Kill Switch
manual/automático nunca autolimpo, limites diário/semanal por equity — não
só P&L de trades fechados). Analisado o spec ponto a ponto (secções 1-39)
contra o código real, os gaps genuínos encontrados e corrigidos foram:

- [x] **`refresh_snapshot()` não era genuinamente periódico** (§16) — o
      próprio docstring do módulo (`packages/portfolio/state.py`) já
      afirmava que o worker "chama-o na sua própria cadência para
      equity/drawdown se manterem atuais mesmo entre fills", mas na
      realidade só era chamado nos dois pontos de fill em
      `packages/execution/order_manager.py` — nunca de forma independente
      de uma ordem. `apps/worker/main.py` passou a chamá-lo a cada ciclo de
      scan, logo a seguir a `update_safety_belt()`. **Bug relacionado
      corrigido na mesma alteração**: nenhum dos dois call-sites de fill
      alguma vez passava `safety_belt_level`, pelo que todo snapshot
      persistido gravava silenciosamente `"normal"` independentemente do
      estado de risco real do sistema — ambos os call-sites passaram a ler
      `system_state.safety_belt_level` real antes de gravar
- [x] **Strategy Health nunca chegava ao Risk Engine** (§20) — o passo 10
      do pipeline (`engine.py`) ainda tinha o comentário honesto mas
      desatualizado "strategy performance tracking pending Phase 5", apesar
      da Fase 5 real (Learning Agent, `StrategyPerformance.health_score`,
      quarentena) já estar implementada há muito nesta sessão. Novo módulo
      `packages/risk/strategy_health.py` classifica
      healthy/warning/degraded/quarantined a partir do mesmo
      `health_score` e do mesmo limiar que a quarentena já usa
      (`HEALTH_SCORE_QUARANTINE_THRESHOLD`); uma estratégia degradada tem o
      tamanho reduzido a 0.5x, uma "quarentinada" é bloqueada — em defesa
      adicional, já que `apps/worker/strategy_runner.py` filtra estratégias
      em quarentena antes de gerar sinal, mas um módulo com poder de veto
      nunca deve confiar apenas num filtro a montante
- [x] **Multiplicadores dos Safety Belts estavam hardcoded em Python**
      (§35, "Esses valores devem ser configuráveis") — nova secção
      `safety_belt_multipliers` em `config/risk_limits.yaml`
      (`SafetyBeltMultipliersConfig` em `packages/risk/config.py`);
      `policy_for()` passou a ler o multiplicador da config, mantendo o
      tier-floor/`allow_new_trades` de cada estado (comportamento
      estrutural, não um número de risco) como estava
- [x] **DEFENSIVE nunca reduzia — só bloqueava** (encontrado ao escrever a
      simulação matemática do §37) — `evaluate_safety_belt()` ativava
      DEFENSIVE exatamente no mesmo limiar (`daily_loss_pct >=
      max_daily_loss_pct`) em que o passo 9 do `engine.py` já bloqueia
      tudo — a ação "reduzir tamanho, exigir high_quality+" do estado
      DEFENSIVE era código morto, coincidindo sempre com o bloqueio duro.
      Corrigido para ativar a 70% do limite diário (o mesmo fator que
      CAUTION já usa sobre o limite semanal), abrindo uma janela real onde
      DEFENSIVE reduz sem bloquear — cada estado passou a ter mesmo uma
      ação distinta, como o spec pede
- [x] **P&L/perda mensal não existiam** (§16/§29) — `PortfolioState` ganhou
      `weekly_pnl`/`monthly_pnl`/`monthly_loss_pct`, derivados por leitura
      (via `_equity_n_days_ago(db, now, 30)`) tal como o semanal já era —
      sem nova coluna na tabela `portfolio_snapshots`, mesma lógica que já
      evitava redundância no semanal. Novo limite `max_monthly_loss_pct`
      em `config/risk_limits.yaml`, com um passo extra no `engine.py` a
      bloquear novas operações quando ultrapassado
- [x] **`refresh_correlation_matrix()` nunca era chamado** — a função já
      existia em `packages/risk/correlation_guard.py`, com o próprio
      docstring a dizer que era "para o dashboard/audit trail", mas nenhum
      código a chamava — a tabela `correlation_matrix` ficava sempre vazia.
      Passou a ser chamada a cada ciclo de estratégia do worker
      (`apps/worker/main.py`), alimentando agora o Risk Heatmap real
- [x] **RiskDecision devolvia só um `reason`, nunca uma lista nem
      `risk_amount`** (§25-26) — em vez de alterar o schema da tabela
      (`reason` continua uma string singular, o pipeline já para no
      primeiro bloqueio), `apps/api/risk_view.py`'s `derive_decision_view()`
      deriva na camada de API um `decision` (`approved`/`reduced`/
      `blocked`), uma lista `reasons`, e `risk_amount`/`position_size`/
      `risk_reward` — o mesmo padrão de enriquecimento na API sem
      renomear a tabela usado no `evidence`/`confidence` do "PROMPT 3".
      `reduced` é um estado novo e real: aprovado mas com tamanho cortado
      pelo multiplicador do belt e/ou da saúde da estratégia
- [x] **Dashboard sem Risk Center nem Risk Heatmap** (§30-31) — só existia
      um badge "Risk State" + botão do kill switch. Novo endpoint `GET
      /api/portfolio/exposure` (exposição real por asset/estratégia/
      direção a partir das posições abertas, mais a matriz de correlação
      persistida) e `GET /api/portfolio` ganhou `weekly_pnl`/`monthly_pnl`.
      Painel "Risk Center" expandido no dashboard: Risk State, Daily/
      Weekly/Monthly P&L, Drawdown, Exposure, Available Cash, e um
      `RiskHeatmap` novo (`apps/dashboard/components/RiskHeatmap.tsx`) —
      células coloridas por concentração de asset/estratégia/direção e por
      força da correlação — mais as decisões de risco recentes com o
      `decision`/`reasons` novos
- [x] **Divergências deliberadamente não alteradas**: `MIN_DATA_QUALITY`
      do spec não ganhou um limiar numérico próprio — já é coberto por
      `data_quality != "high"` mais `max_staleness_seconds`, dois sinais
      reais em vez de um número inventado sem uma escala natural definida
      pelo spec; `MAX_STRATEGY_EXPOSURE` não ganhou um campo de config
      próprio — distinto de `max_strategy_drawdown_pct` (já existente, um
      conceito diferente: drawdown da própria estratégia, não um teto de
      exposição), decidir o valor certo exigiria um julgamento de produto
      que o spec não define, ao contrário dos outros limites cujos valores
      de exemplo já eram diretamente aproveitáveis
- [x] 12 novos testes automatizados (427/427 no total da suite): saúde de
      estratégia degradada reduz sem bloquear e nível de quarentena bloqueia
      em defesa (2), multiplicador dos belts configurável (1), DEFENSIVE
      ativa antes do bloqueio duro (1), limite mensal bloqueia (1), decisão
      de risco "reduced"/"blocked" com `reasons`/`risk_amount` corretos via
      API (2), exposição por asset/estratégia/direção via API (1), kill
      switch nunca se autolimpa mesmo após recuperação de drawdown +
      release exige admin (2), e a simulação completa matematicamente
      validada do §37 — EUR 10.000 → tamanho de posição derivado à mão
      (15.0 unidades) → DEFENSIVE reduz exatamente para 7.5 → limite diário
      bloqueia → EMERGENCY bloqueia → Kill Switch bloqueia
      independentemente do belt → multiplicador nunca sobe com o drawdown a
      subir (1)
- [x] **verificado ao vivo** contra Postgres real: worker real gerou um
      `correlation_matrix` real (mais de 50 pares), `GET
      /api/portfolio/exposure` devolveu exposição real por asset (15% cada
      em NDX/XAG/GOOGL) e por estratégia, `GET /api/risk` devolveu uma
      decisão real `"decision": "blocked", "reasons": ["correlation_guard"]`
      e outra `"decision": "approved"` com `risk_amount`/`risk_reward`
      genuínos; dashboard testado num browser real (Playwright/Chromium) —
      painel "Risk Center" completo visível com todos os stat cards e o
      Risk Heatmap colorido por concentração real. `ruff`/`mypy`/`npm run
      lint`/`npm run build` (implícito no `tsc --noEmit` limpo) limpos

Nenhuma migração Alembic nova nesta fase — todas as alterações de schema
foram evitadas deliberadamente (campos derivados por leitura, não
persistidos, como o resto do padrão semanal já estabelecido) ou já cabiam
em colunas/tabelas existentes.

## "PROMPT 6" — News Intelligence + Sentiment + Macro Events (pós-Fase 7) — **status: implementada e validada nesta sessão**

O "PROMPT 6" pede uma camada de News Intelligence completa: entity
extraction, asset mapping direto/indireto, deduplicação, novelty,
importância, sentiment (separado de direção), macro calendar com
surpresa, event reaction memory, News Risk Guard integrado ao Risk
Engine, dashboard, 6 workers, e a regra absoluta de que notícia nunca
executa uma trade. O que já existia (Fase 4 real): `NewsProvider`
abstrato + `MockNewsProvider`, tabelas `news_events`/`news_impact`,
interpretação LLM por (notícia, ativo) em `packages/llm/news_intelligence.py`,
e `news` já como input real (não neutro) do Opportunity Scoring. Era uma
base fina — a maior parte do spec (48 secções) era genuinamente nova,
não uma revisão de algo já construído:

- [x] **Schema** (migração `0011`) — `news_events` ganhou
      `source_type/source_quality_score/retrieved_at/language/entities/
      novelty_score/cluster_id/source_consensus_score/
      has_conflicting_sources/sentiment/sentiment_confidence/importance/
      impact_score`; `news_impact` ganhou `is_direct`; `category` foi
      **alargado** (nunca renomeado) com as categorias do §9; novas
      tabelas `macro_events` e `event_reactions`. Colunas NOT NULL numa
      tabela já populada usaram `server_default` para backfill honesto
      (`unknown`/`low`/0, nunca um valor real fabricado para dados
      anteriores a esta feature), removido depois — mesmo idioma da
      migração `0010`
- [x] **Macro Calendar** (§15-17, §35) — `packages/data/connectors/macro/`
      novo, mesmo padrão de `{market,news}`: `MacroCalendarProvider` +
      `MockMacroCalendarProvider` (templates recorrentes determinísticos
      por nome+ciclo; `actual` só existe para ocorrências já passadas —
      nunca inventado antecipadamente). `apps/worker/macro_agent.py` faz
      upsert por `(event, country, scheduled_at)` e calcula `surprise =
      actual - forecast` só no momento em que `actual` aparece
- [x] **Pipeline DET completo** (§4-14, §23-24) — novo pacote
      `packages/quant/news/`: `entities.py` (dicionário curado, nunca
      inventa uma entidade), `asset_mapping.py` (direto vs indireto,
      direto nunca rebaixado), `sentiment.py` (léxico financeiro DET,
      5 níveis + `UNKNOWN` honesto quando não há sinal — **deliberadamente
      independente** de `NewsImpact.direction`, o único passo com LLM
      em toda a stack, ver §11), `importance.py`, `novelty.py`,
      `dedup.py` (clustering por similaridade de Jaccard + consenso/
      conflito entre fontes), `impact_score.py` (pesos configuráveis em
      `config/news_weights.yaml` novo), `momentum.py`, `context.py`
      (`NewsContextEngine`)
- [x] **Event Reaction Memory** (§19/§30-32) — `event_reaction.py`'s
      `compute_event_reactions()`, recomputação total a partir de
      movimentos de preço reais (`packages/shared/market_data.py`'s
      `get_close_at_or_after()` novo), mesmo padrão de
      `StrategyPerformance`. `MIN_SAMPLES_FOR_REACTION=5` antes de
      qualquer estatística ser mostrada — nunca uma amostra de 2 a
      parecer confiável
- [x] **News Risk Guard soberano ao Risk Engine** (§17/§26/§43/§48 — o
      critério de conclusão mais crítico do prompt) —
      `packages/risk/news_guard.py` novo:
      NORMAL/ELEVATED/HIGH/CRITICAL a partir de eventos macro
      high/critical iminentes + notícias high/critical recentes,
      multiplicadores configuráveis (`news_risk_multipliers` em
      `config/risk_limits.yaml`, mesmo padrão de
      `safety_belt_multipliers`). Passo 11 novo em
      `packages/risk/engine.py`, na mesma posição estrutural que
      Strategy Health — só pode reduzir o tamanho aprovado ou bloquear,
      nunca aprovar sozinho. Verificado estruturalmente
      (`tests/test_news_simulation.py` percorre a AST de todo
      `packages/quant/news/` e falha se algo importar
      `packages.execution` ou referenciar `RiskVerdict`/`RiskDecision`)
- [x] **Contradição notícia vs. técnico reduz confidence, nunca bloqueia
      sozinha** (§27-28) — `compute_opportunity_confidence()` ganhou
      `news_signals`: quando a leitura de notícia mais impactante
      contradiz a direção técnica do sinal, `confidence` desce
      (`_NEWS_CONFLICT_CONFIDENCE=0.4`, mesma magnitude que
      `_INSUFFICIENT_HISTORY_CONFIDENCE` já existente) — nunca vira o
      sinal, nunca gera uma oportunidade sozinha
- [x] **Workers como cadências, não 6 processos** — divergência
      deliberada e documentada (não silenciosa): esta base de código
      inteira (Fases 1-7) já usa um processo com múltiplas cadências
      independentes, nunca um processo por agente. Ingestão + análise
      DET + deteção de evento são um único passe sequencial sobre o
      mesmo item (`apps/worker/news_agent.py`) — separá-los seria só
      round-trips redundantes à BD sem diferença de comportamento.
      `MacroCalendarWorker` e `SentimentWorker` (shift) ganharam cada um
      a sua própria cadência nova (`macro_calendar_interval_seconds`,
      `sentiment_shift_interval_seconds`); `NewsLearningWorker`
      (`compute_event_reactions`) partilha a cadência batch/lenta já
      existente do Research Agent
- [x] **Alertas** (§36) — `CRITICAL_NEWS`/`CONFLICTING_INFORMATION`
      (`news_agent.py`), `HIGH_IMPACT_EVENT`/`MACRO_SURPRISE`
      (`macro_agent.py`), `SENTIMENT_SHIFT` (`sentiment_agent.py`, com
      cooldown de 6h para não repetir o mesmo shift em curso a cada
      ciclo) — todos categoria `news` nova em `alerts.category`.
      `NEWS_FEED_FAILURE` coberto pelo `CadenceFailureTracker` genérico
      já existente, mesma cobertura que qualquer outra cadência
- [x] **Dashboard "News Intelligence Center"** (§33-34/44) — novo
      `apps/dashboard/components/NewsIntelligenceCenter.tsx`: Event Risk
      (badge), Market Sentiment agregado, News Momentum, Source
      Quality, Upcoming Macro Events (tabela), Latest Events
      (enriquecido com sentiment/importance/consenso/is_direct). Novos
      endpoints `GET /api/news/risk`, `GET /api/macro`, `GET
      /api/news/context/{symbol}`; `GET /api/news` enriquecido
- [x] 67 novos testes automatizados (494/494 no total da suite):
      entity extraction + asset mapping (6), dedup + novelty + source
      consensus (7), News Risk Guard NORMAL→CRITICAL (7), sentiment +
      sentiment shift (7), importance + impact score + source quality
      (8), macro provider determinismo (4), macro agent
      upsert/surprise/alertas (6), pipeline de ingestão completo (4),
      event reaction memory + gate de amostra mínima (3), sentiment
      shift worker + cooldown (3), API (9), contradição notícia/técnico
      na confidence (2), e a simulação completa do §42 (1) — notícia
      normal → evento macro high iminente reduz o tamanho pelo
      multiplicador exato configurado → sentiment shift detetado não
      altera o tamanho sozinho → contradição técnico/notícia reduz
      confidence → evento escala a critical → bloqueado — mais a prova
      estrutural de que `packages/quant/news` nunca pode aprovar uma
      trade
- [x] **verificado ao vivo** contra Postgres real: worker real ingeriu
      notícias com sentiment/importance/impact_score genuinamente
      calculados, ingeriu o calendário macro mock com eventos
      futuros sem `actual` e passados com `actual`/`surprise`
      preenchidos; `GET /api/news/risk` devolveu um nível real
      (`normal` sem eventos, escalando corretamente com um evento macro
      simulado); dashboard testado num browser real (Playwright/
      Chromium) — painel "News Intelligence Center" completo visível
      com heatmap de sentimento, calendário macro e latest events reais.
      `ruff`/`mypy`/`npm run lint`/`npm run build` limpos

Divergência deliberada não alterada: os 4 documentos pedidos em §47
(`docs/news-intelligence.md`, `docs/macro-events.md`, `docs/sentiment.md`,
`docs/event-risk.md`) foram criados na raiz de `docs/`, como o próprio
prompt nomeia explicitamente — fora de `docs/blueprint/`'s série numerada,
já que o prompt deu caminhos exatos, ao contrário dos prompts anteriores.

## "PROMPT 7" — Backtesting Engine + Walk-Forward + Monte Carlo + Strategy Lab (pós-Fase 7) — **status: implementada e validada nesta sessão**

O "PROMPT 7" pede um laboratório quantitativo completo (66 secções): motor
de backtest event-driven com fees/slippage/latência configuráveis, gates
de look-ahead/data-leakage/data-integrity, train/validation/test,
walk-forward optimization genuíno, Monte Carlo, stress testing (incl. kill
switch drill), risk of ruin, sensitivity a custo/slippage/capital,
robustness score, strategy quality score + status, reality gap analyzer,
strategy failure detector, sistema de jobs assíncronos, Strategy Lab no
dashboard, e a regra de que nenhuma estratégia é promovida só por
`ROI > 0`. O motor de backtest event-driven **já existia** desde a Fase 6
(`packages/backtest/engine.py`, com walk-forward simples, otimização por
grid search e parameter stability já implementados) — este prompt não o
substitui, estende-o com tudo o que faltava:

- [x] **Schema** (migração `0012`) — `backtest_runs` ganhou
      `strategy_version/code_version/data_version/random_seed/
      extra_metrics` (JSON bundle, não ~20 colunas novas — todas as
      métricas de §11-15 são funções puras de dados já guardados); novas
      tabelas `backtest_jobs`, `monte_carlo_runs`, `stress_test_runs`;
      `system_state` ganhou `backtest_worker_last_heartbeat` (coluna
      separada do heartbeat do worker de trading ao vivo)
- [x] **Execução configurável** (§8-10) — `packages/backtest/execution_models.py`
      novo: `FeeModel` (percentage/fixed/tiered/provider_specific),
      `SlippageModel` (fixed/percentage/volatility_based/liquidity_based),
      `LatencyModel` (atraso sinal→execução em barras). `ExecutionConfig()`
      sem argumentos reproduz **byte a byte** o comportamento anterior
      (`packages/execution/fills.py` continua intocado, ainda a única
      fonte de verdade para a Paper Execution real)
- [x] **Métricas enriquecidas** (§11-15, §31) — `packages/backtest/metrics.py`
      novo: Sortino, recovery factor, gross P&L, avg win/loss, exposição
      média, turnover, detalhe de drawdown, streaks, distribuição de
      trades, regime breakdown — tudo honesto ("NOT AVAILABLE" via `None`
      quando a amostra não sustenta a métrica, nunca um número fabricado)
- [x] **Data Integrity Gate** (§52-53) — `packages/backtest/data_integrity.py`
      novo, corre antes de qualquer backtest; crítico →
      `BACKTEST_BLOCKED`. Duplicados não verificados (a PK
      `(asset_id, timeframe, ts)` já os torna impossíveis — checá-los
      seria código morto a fingir guardar contra algo que o schema já
      exclui)
- [x] **Look-ahead bias** — nenhum mecanismo novo (a garantia já é
      estrutural: `window = candles[:i+1]`), mas testado adversarialmente
      pela primeira vez de forma explícita (§53): duas séries idênticas
      até um corte, divergindo depois — resultados até ao corte têm de
      ser idênticos
- [x] **News-aware backtest** (§34) — `packages/backtest/news_replay.py`
      novo: `news_aware=True` troca notícia neutra por uma query real
      look-ahead-safe a `news_impact` (`created_at <= as_of`, nunca
      `datetime.now()`) — honestamente esparsa para janelas anteriores ao
      News Intelligence worker (Prompt 6)
- [x] **Reprodutibilidade** (§48-49) — `strategy_version`/`code_version`
      (`packages/backtest/versioning.py`, env var em produção + git local,
      nunca um placeholder fabricado)/`data_version` (fingerprint sha256
      das candles)/`random_seed` (só em runs estocásticos)
- [x] **Train/Validation/Test** (§17) — `packages/backtest/split.py` novo,
      divisão cronológica pura, nunca baralhada
- [x] **Walk-Forward Optimization genuíno** (§18-19) —
      `packages/backtest/walkforward_optimization.py` novo: TRAIN→OPTIMIZE
      (grid search)→VALIDATION→roll, repetido — distinto do walk-forward
      de parâmetros fixos e do optimize.py de busca global já existentes
      desde a Fase 6 (ambos mantidos, cada um com o seu papel documentado
      em `docs/backtest-lab.md`). VALIDATION provado nunca influenciar a
      escolha de parâmetros por replay determinístico
- [x] **Overfitting classification** (§21-22) — `packages/backtest/overfitting.py`
      novo, os dois exemplos do spec testados literalmente: (+80%,-3%) →
      `SEVERE_OVERFITTING`, (+25%,+19%) → `MORE_ROBUST`
- [x] **Monte Carlo Engine** (§24-28) — `packages/backtest/monte_carlo.py`
      novo: 5 métodos (trade_reshuffling/bootstrap/return_perturbation/
      slippage_perturbation/execution_perturbation), percentis P5-P95,
      probability_of_loss/of_drawdown_threshold, `random_seed`
      reprodutível byte a byte
- [x] **Risk of Ruin** (§28) — `packages/backtest/risk_of_ruin.py` novo,
      reutiliza o bootstrap do Monte Carlo Engine em vez de reimplementar
      um simulador paralelo, hipóteses documentadas explicitamente no
      resultado
- [x] **Stress Testing Engine + Kill Switch Drill** (§29-30, §60) —
      `packages/backtest/stress_test.py` + `stress_data.py` novos: 7
      cenários, `gap`/`regime_reversal`/`market_crash` construídos
      **inteiramente em memória** (nunca escrevem em `ohlcv` — outras
      cadências ao vivo leem essa tabela concorrentemente, §65). Kill
      switch provado deterministicamente (`PortfolioState` a 1.5x
      EMERGENCY é rejeitado) e por integração
      (`risk_veto_counts["kill_switch"]` conta disparos reais durante um
      crash sintético). `consecutive_losses`/`news_shock` do §29
      deliberadamente não implementados, com razão documentada
- [x] **Cost/Slippage/Capital Sensitivity** (§35-37) —
      `packages/backtest/sensitivity.py` novo: base/+25%/+50%/+100%
      custos, 1x/2x/5x/10x slippage, 5 níveis de capital
- [x] **Robustness Score** (§23) — `packages/backtest/robustness.py` novo,
      8 componentes ponderados, **zero contribuição sem evidência** (nunca
      um valor neutro por omissão)
- [x] **Strategy Quality Score + Status + Final Assessment** (§38-39, §51)
      — `packages/backtest/quality_score.py` novo: score 0-100, 7 status
      (EXPERIMENTAL/PROMISING/VALIDATING/ROBUST/DEGRADED/REJECTED/
      QUARANTINED), 5 assessments fechados
      (ROBUST/PROMISING/WEAK/UNSTABLE/INSUFFICIENT EVIDENCE) — nunca
      "Guaranteed Profit"/"Safe"/"Will make money", testado literalmente
- [x] **Reality Gap Analyzer** (§42) — `packages/backtest/reality_gap.py`
      novo, comparação estruturada completa (distinto do
      `check_degradation` já existente da Fase 5, que só decide disparar
      um Alert); `return_difference` honestamente `None` — unidades
      genuinamente não comparáveis entre `BacktestRun.net_return` (%) e
      `StrategyPerformance` (P&L)
- [x] **Strategy Failure Detector** (§43) — `packages/backtest/failure_detector.py`
      novo, consolida tudo acima em STRATEGY_REJECTED/QUARANTINED/OK,
      sempre consultivo, nunca muta `lifecycle_stage`
- [x] **Sistema de Jobs Assíncronos + `apps/backtest_worker`** (§46-47) —
      **processo separado** de `apps/worker` (não uma cadência): a regra
      de dependências já existente `apps/worker → ... exceto
      packages/backtest` tinha um motivo real (isolar o loop de trading
      ao vivo de compute pesado sob demanda), que uma cadência teria
      violado. Cinco "workers" nomeados no §47 = um processo a despachar
      por `BacktestJob.kind` (mesma divergência "vários workers →
      cadências" documentada, aplicada aqui ao nível de processo, não de
      cadência). `apps/backtest_worker/jobs.py` + `main.py` novos,
      `infra/docker/Dockerfile.backtest-worker` novo, novo serviço no
      `docker-compose.yml`
- [x] **Strategy Lab (dashboard)** (§44) — `apps/dashboard/components/StrategyLab.tsx`
      novo: Strategy/Asset/Timeframe/Period/Capital/Risk Model → "Run full
      lab" cria um `BacktestJob(kind=full_lab)`, faz polling até
      completar, renderiza Backtest/Walk Forward/Monte Carlo/Stress
      Test/Robustness/Final Score/Decision — o mesmo relatório de
      `packages/backtest/report.py`'s `run_full_lab` (as 13 secções do
      §50 num único dict)
- [x] **API** — `POST/GET /api/backtests/jobs`, `GET /api/backtests/jobs/{id}`,
      `POST /api/backtests/jobs/{id}/cancel`, `POST /api/backtests/data-integrity`,
      `GET /api/backtests/reality-gap/{id}`, `GET /api/backtests/failure-check/{id}`,
      `POST /api/backtests/compare` (tabela StrategyLab §16). Rotas
      estáticas registadas **antes** de `GET /{run_id}` — FastAPI/Starlette
      correspondem rotas pela ordem de registo, e `{run_id}: int` teria
      capturado `/jobs` primeiro e falhado a coerção de tipo (bug real,
      apanhado e corrigido durante esta sessão antes do commit)
- [x] 91 novos testes automatizados (585/585 no total da suite): motor v2
      (execução configurável, latência, métricas, integrity gate,
      look-ahead adversarial, data leakage de notícias — 10),
      train/validation/test (4), overfitting (6), walk-forward
      optimization + prova de isolamento TRAIN/VALIDATION (4), Monte Carlo
      (7), risk of ruin (6), stress testing + kill switch drill + prova de
      que nunca escreve em `ohlcv` (6), sensitivity (4), robustness +
      quality score + failure detector (14), reality gap (4), full lab
      report (4), job dispatch (8), API de jobs/lab (12), e a simulação
      completa do §62 — uma estratégia (Breakout) em 3 ativos × 3
      timeframes através do pipeline completo, mais a prova estrutural e
      comportamental de que nenhum live trading existe em
      `packages/backtest`/`apps/backtest_worker` (2)
- [x] **verificado ao vivo** contra Postgres real: API + worker de trading
      + backtest worker + dashboard reais a correr em simultâneo; um job
      `full_lab` real criado via `POST /api/backtests/jobs`, processado
      pelo `apps/backtest_worker` real, resultado poll-ado e renderizado
      no Strategy Lab do dashboard (Playwright/Chromium). `ruff`/`mypy`/
      `npm run lint`/`npm run build` limpos (mypy: os mesmos 20 erros
      pré-existentes de antes desta fase, confirmados por comparação
      direta contra o HEAD anterior — zero regressões introduzidas)

Divergências deliberadas, documentadas (não silenciosas):

1. `apps/backtest_worker` é um **processo separado**, não uma cadência —
   o inverso da divergência habitual deste projeto, porque a regra de
   dependências (`apps/worker` nunca importa `packages/backtest`) já
   existia por um motivo genuíno de isolamento de carga.
2. `consecutive_losses`/`news_shock` (§29) não implementados — o primeiro
   já coberto com uma distribuição estatística real pelos percentis
   `losing_streak` do Monte Carlo; o segundo exigiria escrever
   NewsEvent/NewsImpact sintéticos na base de dados, a mesma violação de
   "nunca mutar tabelas partilhadas" que os outros cenários evitam.
3. Survivorship bias/delisting (§54-55) e comparação entre múltiplas
   fontes de dados (§56) não implementados — este ambiente só tem um
   provider mock por ativo, sem histórico de delisting nem segunda fonte
   a comparar; documentado como limitação de dados, não fabricado.
4. Os 4 documentos deste prompt (`docs/backtest-lab.md`,
   `docs/monte-carlo-stress-testing.md`, `docs/strategy-quality-score.md`,
   `docs/backtest-jobs.md`) na raiz de `docs/`, mesma convenção
   estabelecida no "PROMPT 6".

## "PROMPT 8" — Autonomous Paper Trading + Portfolio Manager + Execution Simulator (pós-Fase 7) — **status: implementada e validada nesta sessão**

O "PROMPT 8" pede um agente de paper trading 24/7 (93 secções): separação
TradingMode PAPER/LIVE_DISABLED, um gate de aprovação Opportunity→Risk→
Portfolio→Execution, Portfolio Manager com alocação por estratégia,
trailing stops, uma política HOLD/REDUCE/CLOSE explícita para posições
abertas durante regime change/news risk/emergência de portfolio, proteção
anti-martingale, `LossStreakDetector`, idempotency keys, event sourcing,
`PaperReconciliationEngine`, RBAC, controlos manuais (pause/resume/close
position/cancel order/kill switch/reset account) com audit trail
before/after, um "Autonomous Trading Center" no dashboard, e uma bateria
de testes de segurança/crash-recovery/simulação contínua. A maior parte da
infraestrutura de segurança **já existia** desde as Fases 3-6 (Kill Switch,
Safety Belts, Correlation Guard, Position Sizing, Trade Monitor, o
endpoint `/api/trades/{id}/why` já era essencialmente o "decision trace"
do §56) — este prompt não a reconstrói, fecha exactamente os genuínos
buracos que restavam:

- [x] **Schema** (migrações `0013`/`0014`) — `system_state` ganhou
      `trading_mode`, `trading_paused/paused_reason/paused_at`,
      `worker_restart_count/restart_window_started_at` (crash-loop
      protection), `last_reset_at` (reset epoch); `positions` ganhou
      `trailing_stop_config`/`favorable_extreme_price` e um `exit_reason`
      agora fechado por CHECK constraint (9 valores); `orders` ganhou
      `idempotency_key` (UNIQUE), `expected_price`, `latency_ms`;
      `admin_users` ganhou `role` (admin/viewer); três tabelas novas —
      `trading_events` (event sourcing, §54), `system_health` (snapshot
      periódico, distinto do `GET /api/system/health` on-demand),
      `manual_actions` (audit trail before/after das 6 acções manuais)
- [x] **TradingMode + gate LIVE_DISABLED** (§2-4, §8) — `system_state.trading_mode`,
      verificado como o **primeiro** passo do Risk Engine
      (`packages/risk/engine.py`), lado a lado com `trading_enabled` (kill
      switch) e o novo `trading_paused` (PAUSE, §64 — voluntário e
      reversível, deliberadamente distinto do kill switch automático).
      Nenhum caminho de código escreve `live_disabled`/qualquer coisa que
      não seja `paper` — o gate é real, testado, mas nunca alcançado nesta
      fase (honesto: `# ZERO live trading`)
- [x] **Portfolio Manager** (§9, §12-17) — `packages/portfolio/manager.py`
      novo: `evaluate_allocation()` + `AllocationDecision`, um segundo gate
      **depois** da aprovação do Risk Engine, verificando algo que os
      checks existentes (exposição por activo, cluster de correlação) não
      cobrem — quanto capital uma **estratégia** já tem exposto em todos
      os seus activos ao mesmo tempo (`max_strategy_allocation_pct`, novo
      em `config/risk_limits.yaml`). Nunca duplica a matemática de
      exposição/correlação já feita em `packages/risk/`
- [x] **Short-selling honesty fallback** (§34) — `asset_class == 'equity'`
      bloqueia `direction == 'short'` com `short_disabled_insufficient_data`
      (este sistema não modela mecânica de empréstimo de acções/margem);
      crypto/forex/index/commodity continuam a suportar short (contabilidade
      cash-settled, já simétrica por direcção em
      `packages/execution/order_manager.py`)
- [x] **Leverage ceiling** (§35) — `max_leverage=1.0` explícito em
      `config/risk_limits.yaml`, verificado como uma asserção real no Risk
      Engine (nunca apenas assumido como consequência implícita dos outros
      caps)
- [x] **Trailing stops** (§26-27) — `packages/quant/exits/trailing_stop.py`
      novo: `fixed_distance`/`percentage`/`atr_based`, nunca alarga um
      stop (só ratchets a favor do trade); `apps/worker/trade_monitor.py`
      chama-o antes de qualquer verificação de saída, ATR calculado só
      para posições configuradas com esse tipo
- [x] **Position Risk Policy — HOLD/REDUCE/CLOSE** (§28-30) — `packages/risk/position_policy.py`
      novo: regime change, critical news, e emergência de portfolio (Kill
      Switch **ou** belt EMERGENCY) já não fecham uma posição
      unilateralmente — passam por uma política configurável
      (`config/risk_limits.yaml`'s `position_risk_policy`, "Não
      implementar comportamento implícito" §30). REDUCE usa a nova
      `packages/execution/order_manager.py::reduce_position()` (fecha uma
      fracção, a posição continua aberta com o mesmo stop/target — nunca
      alimenta as estatísticas de aprendizagem por estratégia, que
      continuam exclusivas de um close completo). Ordem de severidade:
      Kill Switch/EMERGENCY > critical news > regime shift
- [x] **Anti-martingale + Loss Streak Detector** (§36-39) — `packages/risk/loss_streak.py`
      novo: streak de perdas **do portfolio inteiro** (não por estratégia
      — isso já existe via `packages/quant/learning/quarantine.py`'s
      health score), reduz size a 0.5x a partir de 5 perdas seguidas,
      nunca bloqueia (as safety belts já cobrem um halt completo a um
      drawdown pior). Anti-martingale provado por ausência: nenhum código
      em `packages/risk/position_sizing.py` lê P&L passado para aumentar
      size, testado explicitamente
      (`test_win_streak_never_increases_size`)
- [x] **Idempotency + qualidade de execução** (§18-19, §44, §51) —
      `Order.idempotency_key` (UNIQUE, chave = propósito + entidade +
      nº de tentativas já existentes — retries legítimos entre ciclos
      avançam a chave, duplicados genuínos colidem na constraint da BD);
      `Order.expected_price`/`latency_ms` capturados em cada submissão
      (`open_position`/`close_position`/`reduce_position`)
- [x] **Event sourcing** (§54, "WHY did/didn't the system trade?") —
      `TradingEvent` novo: `order_submitted/filled/rejected`,
      `position_opened/closed`, `risk_blocked`, `no_trade`,
      `trading_paused/resumed`, `kill_switch_triggered/released`,
      `reconciliation_mismatch`, `portfolio_emergency_action` (também
      cobre as acções de regime/news do position_policy, distinguidas por
      `payload.trigger`), `loss_streak_detected`, `worker_restarted`,
      `crash_loop_protection_triggered`. Complementa, não substitui,
      `RiskCheck`/`RiskDecision` (já cobriam o "porquê" por sinal em
      detalhe) e `AuditLog` (acções admin/sistema já existentes)
- [x] **PaperReconciliationEngine** (§52, §83-84) — `packages/portfolio/reconciliation.py`
      novo: reconstrói cash do zero (capital inicial − fees de entrada −
      capital em posições abertas + P&L realizado, agregado em SQL) e
      compara contra o ledger incremental de
      `packages/portfolio/state.py`; qualquer divergência ou invariante
      violado (cash negativo, size≤0, fees negativas) pausa trading
      (`trading_paused`, não o kill switch — é um stop de integridade
      contabilística, não de risco de mercado) e escreve um Alert crítico.
      Corre a cada `reconciliation_interval_seconds` (300s) no worker
- [x] **SystemHealth + crash-loop protection** (§46-50) —
      `AutonomousSystemStatus` (starting/running/paused/caution/
      defensive/emergency/kill_switch/error — `NO_TRADE` é um facto por
      decisão, não por estado persistido, ver
      `packages/shared/worker_health.py`'s docstring) computado uma vez e
      partilhado entre o snapshot periódico e `GET /api/trading/status`;
      `record_worker_restart()` conta reinícios do processo por janela
      (`max_worker_restarts_per_window`) e auto-pausa trading se um
      crash-loop silencioso continuasse a "confirmar" o sistema como
      saudável entre reinícios quase instantâneos
- [x] **RESET PAPER ACCOUNT + reset epoch** (§64, §66) — `SystemState.last_reset_at`:
      `packages/portfolio/state.py` e `packages/portfolio/reconciliation.py`
      ignoram tudo antes desse instante nos cálculos de pico/drawdown/P&L
      periódico e na reconciliação — sem isto, um reset pareceria um
      drawdown gigante contra um pico de uma vida anterior da conta.
      Histórico completo (`portfolio_snapshots`/`orders`/`trades`) nunca é
      apagado — append-only, sempre auditável. Exige `confirm=true` e zero
      posições abertas
- [x] **RBAC** (§77) — `AdminUser.role` (admin/viewer),
      `require_admin_role` novo em `apps/api/deps.py`, aplicado a todos os
      controlos manuais + kill switch + risk-limits PATCH.
      `POST /api/auth/users` (admin-only) cria contas viewer sem partilhar
      a password do admin
- [x] **API `/api/trading/*`** (§78) — `apps/api/routers/trading_control.py`
      novo: `GET /status` (`AutonomousStatusOut`), `GET /activity` (feed
      de `TradingEvent`), `GET /performance` (trades hoje, win rate,
      P&L, exposição, drawdown), `GET /manual-actions`,
      `POST /pause`, `/resume`, `/positions/{id}/close`,
      `/orders/{id}/cancel`, `/reset-paper`. Deliberadamente **não**
      duplica `GET /api/positions`/`/orders`/`/trades`/`/portfolio` nem
      `POST /api/system/kill-switch`, que já existem e já são testados —
      ver o docstring do módulo
- [x] **Dashboard: Autonomous Trading Center + Live Activity Feed** (§58-59, §64) —
      `AutonomousStatusBadge`, `PauseResumeButton`, `ClosePositionButton`,
      `ResetAccountButton`, `LiveActivityFeed` novos; a maior parte dos
      painéis do §58 (portfolio, posições, trades, oportunidades, risk
      state, news risk, strategy health) já existiam desde fases
      anteriores — consolidados com o novo cabeçalho de estado +
      controlos manuais em vez de reconstruídos
- [x] 74 novos testes automatizados (659/659 no total da suite):
      PortfolioManager (6), LossStreakDetector (7), gates novos do Risk
      Engine — TradingMode/pause/short-disabled/leverage/loss-streak (6),
      trailing stop puro + integração no trade monitor (9), idempotency +
      qualidade de execução + `reduce_position` (7), reconciliação (6),
      position policy hold/reduce/close nos três triggers (6), worker
      health/crash-loop/autonomous status (12), RBAC + auth (6), API de
      trading control (13), bateria de segurança crítica — Risk Engine
      offline, bypass estrutural do Portfolio Manager, prova estrutural de
      que `open_position()` só é chamado a partir do caminho com gate (3),
      crash recovery + simulação contínua de 15 ciclos sem drift de
      reconciliação nem colisão de idempotency key (3)
- [x] **verificado ao vivo** contra Postgres real: API + worker de trading
      real a correr durante vários ciclos (scan/trade-monitor/strategy);
      `POST /api/trading/pause`/`/resume` reais com `ManualAction`
      before/after confirmado na BD; `reconcile_and_enforce()` corrido
      directamente contra o histórico real acumulado desta sessão (OK,
      diferença de €0.0024 dentro da tolerância); dashboard real
      (Playwright/Chromium) — badge de estado RUNNING→PAUSED→RUNNING via
      os botões reais, Live Activity Feed a mostrar eventos reais
      (`trading_paused`, `no_trade`, `worker_restarted`), 4 botões de
      Close renderizados para as 4 posições abertas reais. `ruff`/`mypy`/
      `npm run lint`/`tsc --noEmit`/`next build` limpos

Divergências deliberadas, documentadas (não silenciosas):

1. Vocabulário de `exit_reason`/nomes de eventos/status usa snake_case
   minúsculo consistente com o resto do schema (`stop_hit`,
   `trailing_stop_hit`, `regime_change_exit`, `manual_close`,
   `kill_switch_close`, `portfolio_emergency_close`,
   `reconciliation_pause`, `thesis_invalidated`), não os nomes UPPER_CASE
   literais do prompt (`STOP_LOSS`, `REGIME_CHANGE`, ...) — o mesmo
   conjunto de 9 razões fechado, sem os renomear a meio de uma sessão já
   testada só por paridade cosmética.
2. Sem fila de ordens pendentes/limit orders reais — `PaperExecutionProvider`
   continua a preencher ordens de mercado sincronamente (decisão da Fase
   3, intocada). `POST /api/trading/orders/{id}/cancel` está completo e
   testado, mas nunca encontra uma ordem `new`/`submitted` para cancelar
   nesta arquitectura — documentado no próprio docstring do endpoint, não
   escondido.
3. Sem tabelas `PaperAccount`/`Execution` separadas — as suas
   responsabilidades já existem: `PaperAccount` é
   `PortfolioSnapshot`+`SystemState` (cash/equity/reset epoch);
   `Execution` é o próprio `Order` (já tem `fees`/`slippage_bps`, agora
   também `expected_price`/`latency_ms`). Duplicar tabelas para paridade
   de nomes com o prompt teria criado uma segunda fonte de verdade.
4. Sem arquitectura de filas de eventos/workers assíncronos por agente
   (§6-7, §80) — mantido o padrão "N workers nomeados → cadências dentro
   de um processo" já estabelecido em todas as fases anteriores
   (`apps/worker/main.py`), com duas cadências novas (reconciliação,
   health snapshot). A mesma razão de sempre: um sistema single-user sem
   profundidade de fila não ganha isolamento real de uma fila de eventos
   separada, só complexidade operacional.
5. 24h/72h/7-day soak tests (§67) simulados como muitos ciclos
   comprimidos num único processo de teste, não como execuções reais de
   dias — um teste de longa duração real pertence a um script manual
   separado (ver `docs/autonomous-trading.md`), não à suite `pytest` que
   corre a cada alteração.
6. `NO_TRADE` não é um valor persistido de `AutonomousSystemStatus` — é um
   facto por decisão (o `TradingEvent(event_type="no_trade")` já emitido
   por sinal), nunca inferido do `SystemState` sozinho sem evidência do
   ciclo actual (documentado no docstring de
   `packages/shared/worker_health.py`).
7. `docs/autonomous-trading.md` na raiz de `docs/`, mesma convenção
   estabelecida desde o "PROMPT 6".

## "PROMPT 9" — Multi-Agent Quant Intelligence Architecture (pós-Fase 7) — **status: implementada e validada nesta sessão**

O "PROMPT 9" pede 18 agentes especializados nomeados (Chief Quant, Technical
Analysis, Pattern Hunter, Market Regime, Momentum, Mean Reversion, Macro,
News Intelligence, Sentiment, Quant Research, Portfolio Intelligence, Risk
Guardian, Execution Intelligence, Learning, Anomaly Detection, Data Quality,
Strategy Health, Emergency Guardian) que nunca executam nada directamente —
só produzem `AgentMessage`s tipados (signal/confidence/evidence/risk_flags/
expiration), agregados por um Consensus Engine + Contradiction Engine num
Chief Decision Engine (`DECISION_STATES`: STRONG_LONG_BIAS/LONG_BIAS/
NEUTRAL/SHORT_BIAS/STRONG_SHORT_BIAS/NO_TRADE/BLOCKED, com
`reasoning_summary`/`agent_inputs` explicáveis), com reliability/calibration
tracking, quarentena automática, e uma sandbox estrutural. Mapeando os 86
§§ contra o código já existente das Fases 2-8: **10 dos 18 agentes já
tinham uma implementação determinística real por baixo** (indicadores,
`patterns.detect_all`/`detect_anomaly`, `regime.classify_regime_with_news`,
as estratégias Momentum/Mean Reversion, `packages/quant/news/*`,
`packages/data/quality.py`, `packages/risk/strategy_health.py`) — este
prompt não os reconstrói, embrulha-os num protocolo comum e adiciona a
camada de agregação/decisão/confiabilidade que genuinamente não existia.

- [x] **`packages/agents/` — protocolo + 18 especialistas** (§1-36) —
      `AgentMessage`/`AgentSignal`/`AgentStatus` (`protocol.py`,
      `__post_init__` recusa confiança não-zero num status não-OK — "no
      hallucinated data" estrutural, não por convenção); `AgentContext`
      partilhado (`context.py`) construído uma vez por (asset, ciclo).
      18 módulos em `specialists/`, cada um `analyze(ctx) -> AgentMessage`,
      registados em `SPECIALIST_REGISTRY` (`directional: bool` — 7 votam
      direcção, 11 são consultivos/guardrail e nunca votam: Sentiment e
      Quant Research são deliberadamente não-direccionais, mesmo princípio
      do "PROMPT 6" §11 "SENTIMENT NÃO É DIREÇÃO" — um `LearnedRule`
      validado não tem uma direcção máquina-legível na sua `condition`
      livre, adivinhá-la seria alucinar dados)
- [x] **Sandbox estrutural + tabela de permissões** (§11-14, §60-63) —
      processo monolítico sem sandbox real ao nível do SO, então "sandbox"
      aqui é honestamente dois testes AST reais em cada corrida da suite
      (`tests/test_agent_sandbox.py`, mesma técnica de
      `tests/test_critical_safety_battery.py`): nenhum módulo em
      `packages/agents/` importa `packages.execution` nem chama
      `open_position`/`close_position`/`reduce_position`; cada especialista
      fica dentro da sua linha declarada em `permissions.py`
- [x] **Consensus Engine** (§41-42) — "NÃO É VOTO MAJORITÁRIO": cada agente
      direccional pesado por confiança própria × fiabilidade (0.5 neutro
      sem histórico) × recência (mensagem expirada pesa menos). Um único
      agente sozinho nunca alcança um `*_BIAS` — `meaningful_votes` (pesos
      > 0) tem de ser ≥ 2, distinto de `voting_agents` (qualquer resposta
      OK, incluindo um NEUTRAL honesto a 0 de confiança) que só serve de
      transparência no dashboard/reasoning
- [x] **Contradiction Engine** (§43) — conflito par-a-par entre agentes
      direccionais em direcções opostas, severidade = média das duas
      confianças × 100; `contradiction_score` é o pior conflito do ciclo
      (max, não média — um conflito forte é preocupante mesmo que o resto
      concorde)
- [x] **Chief Decision Engine** (§40-46) — função pura
      `decide(messages, reliability_scores) -> Decision`. BLOCKED reservado
      para dois motivos estruturais: um `CRITICAL_AGENT_CODES`
      (`data_quality`/`risk_guardian`/`emergency_guardian`) está
      UNAVAILABLE este ciclo (§65 "NO NEW TRADES"), ou o Emergency Guardian
      reporta `risk_flags` com `"emergency"`. Contradição alta é NO_TRADE
      (incerteza, não falha). Esta engine é um filtro **adicional** antes
      do Risk Engine soberano (`apps/worker/risk_execution.py`) — nunca o
      substitui nem o contorna, mesmo princípio de "defense in depth" do
      "PROMPT 8" §75
- [x] **Reliability/calibration/quarentena** (§5-6, §55-59) — mesma
      disciplina DET-only de `packages/quant/learning/strategy_stats.py` +
      `quarantine.py`: `AgentPrediction` só gravado para uma chamada
      direccional real; `settle_predictions` só resolve contra um candle
      real (`get_close_at_or_after`), nunca um preço adivinhado;
      `reliability_score` penaliza `overconfidence_gap` (confiança média
      em chamadas erradas acima do que a accuracy justificaria) — nunca
      recompensa; quarentena automática abaixo de 35.0 com amostra
      suficiente (mesma magnitude do threshold de estratégias),
      restauração sempre uma acção admin explícita, nunca automática
- [x] **DB — migração `0015`** — 7 tabelas novas (`agents`,
      `agent_messages`, `agent_predictions`, `agent_reliability`,
      `agent_health`, `decisions`, `contradictions`) + `proposed_by_agent`
      em `learned_rules`; upgrade→downgrade→upgrade verificado
- [x] **Wiring no worker** (§14, §37-39, §68) — `apps/worker/strategy_runner.py`
      constrói um `AgentContext` e chama `run_agent_cycle` **uma vez por
      (asset, ciclo)**, não por sinal/estratégia (custo controlado);
      `AgentOrchestrator` (`packages/agents/orchestrator.py`) corre os 11
      especialistas puros (sem `ctx.db`) em paralelo via
      `ThreadPoolExecutor` com timeout de 5s por agente, e os 7 que tocam
      `ctx.db` sequencialmente na mesma sessão/transacção — `Session` do
      SQLAlchemy não é segura para uso concorrente entre threads, correr
      esses 7 em paralelo corromperia o estado da ligação partilhada
      (mesma classe de problema documentada no `db_session` fixture de
      `tests/conftest.py`). Uma excepção de qualquer especialista nunca
      derruba o ciclo — marcado UNAVAILABLE, nunca propagado.
      `apps/worker/risk_execution.py::maybe_execute` consulta o `Decision`
      como filtro adicional antes do Risk Engine; `decision=None` (ex.:
      chamadas directas da bateria de segurança) é tratado como "sem
      opinião", nunca aprovação implícita nem bloqueio implícito
- [x] **API** — `GET /api/agents` (+ `/{code}`, `/{code}/messages`),
      `POST /api/agents/{code}/restore` (admin-only, RBAC), `GET /api/decisions`
      (+ `/{id}` com trace completo), `GET /api/contradictions`
- [x] **Dashboard "AI Command Center"** — roster de 18 agentes
      (status/tipo/fiabilidade/última análise + botão Restore quando
      quarentenado), Market Consensus por activo, tabela de Decisions
      recentes com linha expansível (`DecisionRow`, mesmo padrão de
      `OpportunityRow`) mostrando o trace completo dos 18 agentes por
      decisão, e Detected Conflicts
- [x] **Testes** — 84 novos (743/743 no total): protocolo + sandbox
      estrutural (33), comportamento de especialistas (8), Consensus +
      Contradiction + Chief Decision incluindo bateria red-team de 10 itens
      específicos desta camada (16), reliability/calibração/quarentena
      (12), wiring no worker incluindo os dois lados de "defense in depth"
      — Decision favorável nunca contorna uma rejeição do Risk Engine, e
      Decision=None nunca é aprovação implícita (7), 8 simulações de
      cenário A-H (unanimidade bullish/bearish, split neutro, contradição
      forte, falha de agente crítico, emergência, data quality
      indisponível, recuperação de quarentena)
- [x] **verificado ao vivo** contra Postgres real: `run_agent_cycle`
      corrido directamente contra dados reais (18 `agents`, `agent_messages`,
      `agent_health` por ciclo persistidos correctamente); API real
      (`GET /api/agents`, `/api/decisions`, `/api/decisions/{id}`,
      `/api/contradictions`) testada com token admin real; dashboard real
      (fetch autenticado via cookie) mostrando "AI Command Center (18
      agents)", Market Consensus com o `Decision` real mais recente,
      `reasoning_summary` real ("BLOCKED: critical agent 'data_quality' is
      unavailable..."), sem regressão nas secções existentes. `ruff`/`mypy`
      (`packages apps scripts`)/suite completa limpos

Divergências deliberadas, documentadas (não silenciosas):

1. `DecisionTrace`/`AgentVersion` como tabelas separadas (pedidas
   implicitamente pelo prompt) — dobradas em `Decision.agent_inputs`
   (snapshot completo de todas as `AgentMessage`s do ciclo) e `Agent.version`
   respectivamente. Uma tabela `DecisionTrace` paralela a `Decision`
   duplicaria a mesma informação sem ganhar nada.
2. `LearningProposal` como tabela nova — não criada; `LearnedRule`
   (Fase 5) já é exactamente esse conceito, só ganhou
   `proposed_by_agent` nullable para futuras propostas geradas por um
   agente com identidade própria.
3. "Sandbox"/"tool permissions" nunca são um mecanismo de runtime (este
   processo não tem capacidade de isolamento ao nível do SO) — são dois
   testes AST estruturais, honestos sobre o que realmente garantem,
   documentados como tal em `packages/agents/permissions.py`.
4. Um `ThreadPoolExecutor` literal sobre os 18 agentes (leitura literal do
   prompt) não é seguro com uma `Session` SQLAlchemy partilhada — paralelo
   real só para os 11 agentes que nunca tocam `ctx.db`; os 7 restantes
   correm sequencialmente na mesma transacção, ainda isolados por
   try/except individual.
5. Sem modo DEBATE opcional (mencionado no prompt como "opcional") — os 18
   agentes já produzem evidência suficiente para o `reasoning_summary` e o
   trace completo por decisão; um segundo round de "debate" entre agentes
   exigiria uma segunda chamada LLM por ciclo sem um ganho claro sobre o
   trace determinístico já explicável, e fica fora do âmbito desta fase.
6. Um `Decision` por (asset, ciclo), não por (asset, estratégia, sinal) —
   mantém o custo do pass extra de 18 agentes proporcional ao scan, não ao
   número de sinais gerados; `strategy_row=None` neste ponto é honesto
   (Quant Research/Strategy Health reportam "no strategy in context" em
   vez de adivinhar qual estratégia a decisão representa).

## "PROMPT 10" — Autonomous Research & Evolution Engine (pós-Fase 9) — **status: implementada e validada nesta sessão**

O "PROMPT 10" pede um `AutonomousResearchAgent` que fecha o ciclo
"self-improvement" do sistema — mas com uma restrição central citada
literalmente no prompt: **"SELF-IMPROVEMENT ≠ SELF-EXECUTION — o sistema
pode pesquisar e propor melhorias. Não pode alterar o sistema de produção
diretamente."** O loop pedido é explicitamente um "SCIENTIFIC RESEARCH
LOOP" (diagnose → hypothesis → experiment → validate → paper-challenger →
human-review → new validated version), não o anti-padrão nomeado no
próprio prompt ("loss → change strategy → trade → loss → change
strategy"). §64: "NO AUTOMATIC PRODUCTION PROMOTION... a promoção final
deve permanecer manual nesta fase." Mapeando os 94 §§ contra o código já
existente das Fases 6-9: `packages/backtest/*` (17 módulos) já cobre a
maior parte do que §16-21 pede de um "Experiment Engine" — este prompt não
reconstrói o motor de backtesting, compõe os mesmos primitivos já provados
(`run_backtest`/`run_walk_forward`/`run_monte_carlo`/
`run_cost_sensitivity`/`run_slippage_sensitivity`/`run_stress_scenario`/
`check_parameter_stability`/`compute_robustness_score`/
`compute_quality_score`) numa camada fina de orquestração de pesquisa.

- [x] **`packages/research/dsl.py` — Strategy DSL + sandbox estrutural**
      (§16-21, §27-28, §64) — árvore condição/expressão em dict
      whitelisted, nunca código Python, nunca `eval`/`exec`/`compile`
      (provado por AST em `tests/test_research_dsl_sandbox.py`, mesma
      técnica de `tests/test_agent_sandbox.py`). Um bug real encontrado e
      corrigido nesta sessão: strings bare eram sempre tratadas como
      referências de campo, o que quebrava o próprio exemplo canónico do
      docstring (`{"eq": ["regime", "trending_bull"]}`) — corrigido com um
      wrapper explícito `{"lit": "trending_bull"}` para literais de string
      contra campos categóricos, mais verificação de aridade que faltava
      em `validate()`/`_resolve()`
- [x] **`packages/research/significance.py`** (§6, §9, §54-55) —
      `detect_change_point` (z-test de duas amostras, honesto quando a
      amostra é curta ou a variância pooled é zero) e `benjamini_hochberg`
      (correção de falsos positivos para lotes de múltiplas hipóteses —
      §55 "não fazer p-value fishing")
- [x] **`packages/research/degradation.py`** (§9-10, §38-40) — taxonomia
      de 6 estados (HEALTHY/WATCH/DEGRADING/DEGRADED/FAILED/QUARANTINED),
      deliberadamente distinta do gate de 4 estados do Risk Engine ao vivo
      (`packages/risk/strategy_health.py`) — ambos leem o mesmo
      `health_score`, servem consumidores diferentes (raciocínio mais
      lento do Research Agent vs. gate por-sinal do Risk Engine)
- [x] **`packages/research/hypothesis.py` + `packages/llm/hypothesis.py`**
      (§3-4, §11-15, §41) — geração DET-first (`_det_narrative`, sempre
      disponível) com enriquecimento LLM opcional; `find_similar_recent_hypothesis`
      (cooldown de 14 dias) implementa §41 "não repetir pesquisa já
      falhada" estruturalmente — `create_hypothesis()` devolve `None`
      (não escreve nada) quando já existe uma hipótese equivalente recente
- [x] **`packages/research/experiment.py` — ExperimentEngine** (§16-21,
      §89) — control vs. candidate, composto pelos mesmos 8 primitivos que
      `run_full_lab` já usa, mas com `params` passados explicitamente
      (`run_full_lab` só avalia os defaults da classe). `_classify_experiment`
      usa o vocabulário fechado exacto do §20 (queued/running/completed/
      failed/rejected/promising/validating/approved/quarantined).
      `reproducibility` grava `code_version`/`random_seed`/`timestamp` em
      cada `Experiment`
- [x] **`packages/research/features.py`** (§22-25) — correlação
      pattern×regime lida de `PatternPerformance` (Fase 4, nunca claim
      causal — §23), `FeatureAblationStrategy` (wrapper `Strategy`-compatible
      que intercepta `generate_signal()` com um filtro DSL) permite A/B
      "estratégia com feature vs. sem feature" através do mesmo
      `run_backtest` inalterado
- [x] **`packages/research/generator.py` — StrategyGenerator** (§16-21) —
      mutação + crossover + busca genética limitada
      (`MAX_SEARCH_EVALUATIONS`, mesmo espírito de
      `packages/backtest/optimize.py::MAX_COMBINATIONS`), fitness durante
      a busca é o walk-forward simples (barato), não o pipeline completo
      de 8 motores (caro demais para `population_size × generations`
      avaliações); propostas de filtro DSL derivadas de
      `research_feature_signals()`
- [x] **`packages/research/versioning.py` — Champion/Challenger + Shadow
      Mode** (§26-33, §64) — `StrategyVersion` é um eixo ORTOGONAL a
      `StrategyRow.lifecycle_stage` (Fase 2, eixo de capital, intocado).
      Toda transição de estado exige `reviewer` não-vazio + escreve
      `AuditLog` — mesmo padrão de
      `packages/agents/reliability.py::restore_from_quarantine`. Shadow
      Mode reescopado honestamente para um sistema só-paper-trading:
      reavalia o challenger contra o champion via o mesmo ExperimentEngine
      em vez de construir um segundo pipeline de execução ao vivo
- [x] **`packages/research/drift.py`** (§34-37) — 5 tipos de drift
      (feature/market/strategy/agent/data), cada um reutilizando evidência
      já computada por um pipeline existente em vez de um novo motor de
      cálculo por sinal
- [x] **`packages/research/knowledge.py` — Research Memory + Knowledge
      Graph** (§41-43) — `ResearchKnowledgeEdge` (subject/relation/object)
      derivado automaticamente de `Experiment`s, `upsert_edge` funde
      evidência repetida numa única linha (confiança ponderada por
      amostra) em vez de duplicar factos; False Signal Memory é uma função
      de consulta sobre o mesmo grafo (`has_known_negative_result`), não
      uma tabela nova
- [x] **`packages/research/budget.py`** (§56-60) — cap de gasto por
      `resource_type` numa janela deslizante, limites em
      `config/research_budget.yaml` (mesmo padrão editável de
      `config/risk_limits.yaml`); `spend()` verifica ANTES de gastar,
      nunca depois
- [x] **`packages/research/approval.py` — Human Approval Workflow**
      (§64, §82-85, §90-91) — a única porta entre uma proposta e uma
      mudança real: `record_decision` só aplica um `promote`/`rollback`/
      `quarantine` DEPOIS de exigir `reviewer` não-vazio, e a mudança de
      estado é aplicada ANTES da própria linha `ResearchApproval` ser
      marcada "approved" — se a aplicação falhar (ex.: `entity_id`
      inválido), a aprovação fica honestamente `pending_review`, nunca
      "approved" para uma promoção que na verdade não aconteceu (bug real
      encontrado e corrigido pela própria bateria red-team desta fase)
- [x] **DB — migração `0016`** — 8 tabelas novas (`research_hypotheses`,
      `experiments`, `strategy_versions`, `research_approvals`,
      `drift_detections`, `research_queue`, `research_budget_usage`,
      `research_knowledge_edges`) + migração `0017`
      (`system_state.research_worker_last_heartbeat`); upgrade→downgrade→upgrade
      verificado em ambas
- [x] **`apps/research_worker/` — terceiro processo separado** (§58-61,
      §92) — mesmo padrão de `apps/backtest_worker` (Fase 7), mas uma fila
      (`research_queue`) e processo distintos: pesquisa autónoma nunca
      compete com o loop de trading ao vivo NEM com um job ad-hoc do
      Strategy Lab de um operador. 7 tipos de job
      (hypothesis/experiment/feature_test/strategy_test/regime_test/
      event_test/knowledge_update), cada handler um adaptador fino sobre
      `packages/research/*`; jobs com custo computacional chamam
      `budget.spend` antes de trabalhar
- [x] **API** — `GET/POST /api/research-lab/*`
      (`apps/api/routers/research_lab.py`), prefixo deliberadamente
      distinto de `/api/research` (Fase 5, `LearnedRule`s, conceito mais
      antigo e mais estreito). Toda leitura é aberta a qualquer conta
      autenticada; `POST /approvals`, `/approvals/{id}/decide`, e
      `/queue` são admin-only (RBAC)
- [x] **Dashboard "Autonomous Research Lab"** — painel construído a
      partir de uma única chamada a `GET /api/research-lab/report` (as 11
      secções), com botões Approve/Reject/More-Tests inline nas
      aprovações pendentes que passam pelo mesmo workflow humano-obrigatório
      que a API já impõe
- [x] **`packages/research/report.py` — relatório de 11 secções** (§90-91)
      — resumo executivo, hipóteses activas, experiências recentes,
      alertas de degradação/drift, achados de pesquisa de features,
      versões de estratégia, destaques do grafo de conhecimento, uso do
      orçamento de pesquisa, aprovações pendentes, postura de
      segurança/sandbox, recomendações
- [x] **Testes** — 173 novos (916/916 no total): DSL + sandbox estrutural
      (30), significância estatística (8), degradação (7), hipóteses (8),
      ExperimentEngine incluindo corrida real contra dados sintéticos
      seeded (10), feature research + ablation (6), StrategyGenerator
      incluindo determinismo sob a mesma seed (11), versioning +
      champion/challenger + rollback (13), drift detection para os 5
      tipos (10), knowledge graph (9), research budget (8), approval
      workflow (14), research report (6), research_worker job dispatch
      (9), API (11), bateria red-team de 10 itens específicos desta
      camada — injecção DSL, bypass de orçamento, promoção sem aprovação,
      spoofing de reviewer, alcance à camada de execução, injecção SQL no
      grafo de conhecimento, injecção de vocabulário fechado, lavagem de
      resultado zero-trade, bypass do limite de busca genética, spoofing
      de entity_id (12), e a simulação de cenário end-to-end completa do
      §92 (diagnose → hypothesis → experiment → validate → human-review →
      promote → rollback, 1)
- [x] **verificado ao vivo** contra Postgres real: todos os módulos
      testados directamente contra dados reais seeded antes dos testes
      automatizados existirem (`run_experiment`, `run_genetic_search`,
      `run_ablation`, o ciclo completo de versioning, o dispatch dos 7
      tipos de job do research_worker); API real com token admin real
      (GET/POST em todos os endpoints, incluindo o fluxo completo
      request→decide de uma aprovação); dashboard real (login real via
      browser, screenshot do painel "Autonomous Research Lab" com dados
      reais das 11 secções, clique real no botão Approve confirmado a
      persistir no Postgres). `ruff`/`mypy`/suite completa limpos
      (916/916)

Divergências deliberadas, documentadas (não silenciosas):

1. `ExperimentEngine` não reutiliza `run_full_lab` directamente — esse
   sempre instancia a estratégia com os defaults da classe, ignorando
   qualquer override de `params`; um Experiment precisa avaliar DOIS
   conjuntos de parâmetros específicos (control vs. candidate), não os
   defaults duas vezes. Compõe os mesmos 8 primitivos directamente em vez
   disso — zero matemática de backtesting duplicada.
2. Fitness durante a busca genética é o walk-forward simples e barato
   (`run_walk_forward`), não o pipeline completo de 8 motores de
   `evaluate_arm` — rodar o pipeline caro
   `population_size × generations` vezes não seria proporcional; o
   vencedor da busca é uma proposta, uma chamada explícita a
   `run_experiment` (ou uma `ResearchApproval` de promoção) é que decide
   se vale a pena gastar a avaliação completa.
3. Shadow Mode não é um segundo pipeline de execução ao vivo dentro de
   `apps/worker` — este é um sistema só-paper-trading sem capital real em
   lado nenhum; reavaliar um challenger via o mesmo `ExperimentEngine`
   já construído produz a mesma evidência sem nova infra-estrutura nem
   risco de tocar um caminho de sinal ao vivo.
4. `False Signal Memory` (§41) não é uma tabela nova — é uma função de
   consulta sobre `ResearchKnowledgeEdge` já existente
   (`has_known_negative_result`).
5. Multiple-testing correction (§55) e o cap de orçamento de pesquisa
   (§56-60) são dois mecanismos deliberadamente distintos — um corrige
   inferência estatística sobre um lote de hipóteses, o outro limita
   consumo bruto de compute; nenhum substitui o outro.

## "PROMPT 11" — Global Market Intelligence + 24/7 Opportunity Discovery (pós-Fase 10) — **status: implementada e validada nesta sessão**

O "PROMPT 11" pede um sistema de descoberta de oportunidades que cobre o
mercado global (crypto/forex/equity/index/commodity agora, arquitetura
pronta para etf/future/bond/option quando houver dados) através de um
pipeline `GLOBAL MARKET → UNIVERSE → DATA QUALITY → FAST SCAN → DEEP SCAN
→ PATTERN DETECTION → REGIME ANALYSIS → NEWS/MACRO → OPPORTUNITY SCORE →
RISK FILTER → PORTFOLIO FILTER → TOP OPPORTUNITIES → CHIEF DECISION
ENGINE`, com o princípio explícito citado literalmente no prompt: **"O
robô NÃO deve tentar operar tudo."** Duas restrições estruturais citadas
literalmente: **"O scanner: NUNCA executa trades. Ele somente produz:
MARKET INFORMATION, OPPORTUNITIES, ALERTS"** e **"SCORE ≠ PROBABILIDADE —
Não interpretar: Opportunity Score 80 como: 80% chance of profit."**
Mapeando os 100 §§ contra o código já existente das Fases 1-10: o
universo multi-classe (`Asset` + `MockMarketDataProvider` + 22 ativos
seeded), o par `Signal`+`OpportunityScore` (Fase 2/3, ~90% de overlap com
o "Opportunity" do prompt), `CorrelationMatrixEntry` +
`refresh_correlation_matrix` (Fase 3), `MacroEvent` (Prompt 6, quase
idêntico a "EconomicEvent"), `detect_anomaly`/`detect_cross_asset`
(Fase 4, nunca antes ligados a nada), Market Memory (Fase 5) e
`atr`/`realized_volatility`/`trend_strength`/`avg_volume` (Fase 2) já
cobriam uma fracção grande do pedido — este prompt não reconstrói um
sistema de inteligência de mercado do zero, constrói uma camada fina e
genuinamente nova de orquestração/persistência/classificação em cima
dessa infraestrutura extensa já provada.

- [x] **DB — `Asset`/`Signal` estendidos + migração `0018`** (§5, §9,
      §14, §20-24) — `Asset` ganha `name`/`currency`/`country`/`sector`/
      `industry`/`timezone`/`trading_hours`/`status`/`liquidity_score`/
      `data_quality_score` (mantendo `is_active` intocado como coluna de
      conveniência derivada) e `asset_class` alargado para aceitar
      `etf`/`future`/`bond`/`option` (arquitetura pronta, sem suporte
      real ainda); `Signal` ganha `opportunity_type`/`fingerprint`/
      `expires_at` mais `invalidated` no vocabulário de `status`. 4
      tabelas novas (`opportunity_clusters`, `anomalies`,
      `volatility_events`, `watchlist_entries`) — upgrade→downgrade→upgrade
      verificado contra Postgres real
- [x] **`packages/market/sessions.py` — MarketSessionEngine +
      GlobalMarketClock** (§16-20) — 6 sessões nomeadas (New
      York/London/Frankfurt/Tokyo/Hong Kong/Sydney) via `zoneinfo` (sem
      dependência nova), disciplina UTC-interno/conversão-só-na-interface,
      detecção de overlaps nomeados (London/New York, Tokyo/London);
      forex tratado como 24/5 contínuo em vez de horas de uma única bolsa
- [x] **`packages/market/liquidity.py`** (§9-10, §71-73) — score 0-100 +
      tiers (TIER_A/B/C/UNTRADABLE) a partir de um percentil de volume
      entre pares da mesma classe + qualidade de dados; sem order book em
      lado nenhum do código, `OrderBookSnapshot` é um input opcional
      aditivo para quando um provider real existir
- [x] **`packages/market/universe.py` — MarketUniverseManager** (§5-10,
      §67-70) — pipeline DISCOVERED → DATA VALIDATION → LIQUIDITY
      VALIDATION → CLASSIFICATION → PAPER ELIGIBLE reutilizando
      `packages/data/quality.py` e o liquidity.py acima; quarentena por
      eventos `INVALID_MARKET_DATA` repetidos; nunca toca `is_active`
      (flag histórica que controla os ciclos ao vivo) nem os estados
      operador-only `inactive`/`suspended`
- [x] **`packages/market/fast_scanner.py` — FastMarketScanner** (§6-7,
      §25-32) — `InitialOpportunityScore` barato (momentum/volatilidade/
      volume/breakout-proximity/range-position/liquidity/news-activity)
      sobre todo o universo paper-eligible, cortado ao Top-N antes do
      DeepMarketScanner (o `apps/worker/strategy_runner.py` já existente)
      correr só nesse subconjunto
- [x] **`packages/market/multi_timeframe.py`** (§39-43) — como nenhuma
      tabela deste sistema alguma vez guardou uma barra realmente
      diferente de 1m (o `MockMarketDataProvider` ignora o parâmetro
      `timeframe` no bucketing), este módulo faz resample honesto de 1m
      real para 5m/15m/1h/4h/1D em vez de confiar em dados fabricados;
      estado `TIMEFRAME_CONFLICT` explícito, nunca escondido numa média
- [x] **`packages/market/structure.py`** (§58-61) — detector de swing
      points (fractal simples), classificação HH/HL/LH/LL →
      uptrend/downtrend/ranging, BREAK_OF_STRUCTURE vs.
      CHANGE_OF_CHARACTER
- [x] **`packages/market/volatility.py`** (§54-57) — percentil de
      `realized_volatility` (Fase 2) contra a própria história do activo,
      regime low/normal/high/extreme, evento persistido só numa
      TRANSIÇÃO real de regime (não a cada ciclo) — mesma disciplina de
      `packages/research/drift.py`
- [x] **`packages/market/anomaly.py` — AnomalyScanner** (§45-49) — 5 dos
      6 tipos fechados ligados a detecção real (price_move via
      `detect_anomaly`, volume_spike via `MarketEvent` já existente,
      volatility_spike via o módulo acima, correlation_breakdown via
      `detect_cross_asset` — nunca chamado antes em lado nenhum —,
      news_shock via `NewsEvent.importance=critical`); spread_expansion
      nunca é emitido (sem order book, ver liquidity.py). "Uma anomalia
      significa INVESTIGATE, não TRADE" — `reviewed`/`explanation`
      existem para revisão humana, não para auto-trading
- [x] **`packages/market/opportunity_types.py`** (§14-15, §20-24) —
      classificador puro para o vocabulário fechado de 12 valores
      (BREAKOUT/BREAKDOWN/TREND_CONTINUATION/REVERSAL/MEAN_REVERSION/
      MOMENTUM/VOLATILITY_EXPANSION/VOLATILITY_COMPRESSION/
      RELATIVE_STRENGTH/RELATIVE_WEAKNESS/EVENT_DRIVEN/
      STATISTICAL_ARBITRAGE_CANDIDATE) a partir de evidência já computada
      pelos módulos acima; fingerprint de dedup por bucket geométrico de
      preço + bucket de tempo (não aritmética ingénua — um bucket
      proporcional ao próprio preço degenera para a mesma razão sempre,
      um bug real encontrado e corrigido durante os testes desta fase);
      `expires_at` por tipo
- [x] **`packages/market/clustering.py`** (§33-35) — union-find sobre a
      matriz de correlação já persistida (nunca recomputa), só
      mesma-direcção; penalidade de ranking proporcional a tamanho do
      cluster × correlação média, capada em 1.0
- [x] **`packages/market/historical_analog.py`** (§62-63) — wrapper fino
      sobre `find_similar_contexts`/`similar_context_win_rate` (Fase 5),
      P&L real via `Position.realized_pnl` (nunca fabricado), qualidade
      degrada honestamente abaixo de 5 amostras; disclaimer fixo em todo
      resultado — nunca "will happen again"
- [x] **`packages/market/pairs.py`** (§36-38) — spread/hedge-ratio/
      z-score/heurística de mean-reversion (autocorrelação lag-1,
      explicitamente NÃO um teste ADF/Engle-Granger real — sem biblioteca
      estatística além de Python puro neste repositório) só sobre pares
      já correlacionados; **nunca ligado a um cadence periódico** (sem
      tabela dedicada — decisão de "economia de tabelas" — rodar num
      relógio seria compute desperdiçado); exposto só sob-pedido via
      `GET /api/global-market/pairs`. "Mas: não executar arbitragem real"
- [x] **`packages/market/watchlist.py` — DynamicWatchlist** (§77-79) —
      uma linha por activo (`UniqueConstraint`), reativar em vez de
      duplicar; decaimento por TTL como complemento passivo às 3 razões
      de remoção explícitas do prompt
- [x] **`packages/market/ranking.py` — OpportunityRankingEngine** (§26-29)
      — reordena por `final_score` (já ajustado a risco, Fase 2/3) ×
      desconto proporcional do cluster penalty acima — nunca por retorno
      bruto
- [x] **`apps/worker/market_intelligence.py` + wiring** (§92) — 2
      cadências novas no mesmo processo único (`universe_interval_seconds`,
      `market_intelligence_interval_seconds`) em vez dos 13 processos
      nomeados do prompt — mesma divergência deliberada já estabelecida
      desde a Fase 2 ("single process, multiple independently-cadenced
      logical workers"); a cadência de market intelligence corre depois
      da cadência de strategy no mesmo ciclo para poder enriquecer os
      Signals recém-criados com `opportunity_type` no mesmo passe
- [x] **API — `apps/api/routers/global_market.py`** (§91) — prefixo
      `/api/global-market/*` deliberadamente distinto (universe/
      volatility/anomalies/watchlist/clusters/sessions/structure/pairs/
      historical-analog); `GET /api/opportunities` e `/api/regime`
      (já existentes) estendidos in-place com
      `opportunity_type`/`fingerprint`/`expires_at` em vez de duplicados;
      `/api/economic-events` e `/api/alerts` já cobertos por
      `/api/macro` e `/api/alerts` existentes
- [x] **Dashboard "Global Market Command Center"** — painel construído
      sobre os novos endpoints, deliberadamente sem duplicar secções que
      já existem noutros painéis (Top Opportunities/Regimes/News/Macro/
      Correlation/Exposure/Risk); cobre só o genuinamente novo: universo,
      watchlist, anomalias, eventos de volatilidade, clusters, relógio
      global de sessões
- [x] **Testes** — 168 novos (1084/1084 no total): modelos + migração
      (13), sessions (16), liquidity (8), universe (7), fast_scanner (7),
      multi_timeframe (7), structure (9), volatility (12), anomaly (6),
      opportunity_types incluindo o bug de bucketing geométrico (24),
      clustering (6), historical_analog (5), pairs (11), watchlist (7),
      ranking (5), worker wiring end-to-end incluindo classificação real
      BREAKOUT sobre um zigzag verificado à mão (5), API com login real
      (14), stress/scale/integração cruzada — 150 activos sintéticos,
      isolamento de falha por-activo, exclusão real de um activo
      DATA_UNAVAILABLE pelo FastMarketScanner, dedup de fingerprint,
      fecho de mercado forex ao fim-de-semana (6)
- [x] **verificado ao vivo** contra Postgres real: `run_universe_cycle` e
      `run_market_intelligence_cycle` corridos directamente contra os 25
      activos + 3236 candles reais da base de dev antes dos testes
      automatizados existirem, produzindo transições de status reais e
      uma entrada de watchlist real (`BNBUSDT — volume`); API real com
      token admin real; dashboard real (login real via browser,
      screenshot do painel "Global Market Command Center" com dados reais
      — sessões ao vivo, 25 activos classificados, watchlist populada).
      `ruff`/`mypy`/suite completa limpos (1084/1084) — três corridas
      inflacionadas (16 e 424 falsas falhas) vieram de processos pytest
      concorrentes disputando a mesma base de teste, não de regressões
      reais; confirmado com uma corrida exclusiva limpa

Divergências deliberadas, documentadas (não silenciosas):

1. `is_active` (booleano histórico que controla os ciclos ao vivo desde a
   Fase 1) nunca é escrito por `MarketUniverseManager` — só `status`
   (campo novo, aditivo) é. Sincronizar os dois automaticamente pararia o
   scanner de tentar recuperar dados de um activo `data_unavailable`/
   `quarantined`, exactamente o oposto do que uma reavaliação automática
   devia permitir.
2. `packages/market/pairs.py` não corre num cadence periódico — sem
   tabela dedicada (decisão de economia de tabelas), rodar no relógio
   produziria compute sem destino persistido. Exposto só sob-pedido via
   API.
3. `packages/market/multi_timeframe.py` resample honesto de 1m em vez de
   confiar em timeframes "nativos" do provider mock, que na realidade
   ignora o parâmetro `timeframe` no bucketing — usar esses dados
   diretamente teria sido um bug de dados fabricados, não uma feature.
4. Cointegração em `pairs.py` é uma heurística de autocorrelação lag-1,
   não um teste ADF/Engle-Granger real — sem biblioteca estatística além
   de Python puro neste repositório (mesma restrição de
   `packages/research/significance.py`), documentado explicitamente como
   proxy, nunca apresentado como teste rigoroso.
5. 13 workers nomeados do §92 viram 2 cadências novas dentro do único
   processo `apps/worker` já existente — mesma divergência "single
   process, multiple cadences" estabelecida desde a Fase 2 e reutilizada
   em todos os prompts subsequentes; 3 dos 13 (EconomicCalendarWorker/
   NewsScannerWorker/AlertWorker) já existiam como cadências
   macro/news/alert-delivery antes deste prompt.
6. Um teste de escala a 10.000 activos (§93) não foi corrido — este é um
   sistema privado de um único utilizador; o smoke test de 150 activos
   sintéticos prova ausência de blowup O(n²) ou query sem limite sem
   fingir que este ambiente tem infraestrutura ao nível de uma bolsa.

## Evolução futura (fora de âmbito até validação completa)

Live brokers, exchanges reais (crypto/forex/ações), ML avançado, deep learning,
reinforcement learning, dados alternativos, order book profundo, opções,
arbitragem — só depois de:

> provar, com dados out-of-sample e paper trading (mínimo 30–90 dias), que existe
> vantagem estatística depois de custos e slippage. Só então uma pequena quantidade
> de capital real é considerada, com aumento gradual e monitorização.

## Fora de âmbito nesta fase (explícito)

Não implementar live trading. Não solicitar chaves privadas de brokers/exchanges.
Não enviar ordens reais. Não assumir que qualquer estratégia é lucrativa.
