# 02 — Database Schema (PostgreSQL 16 + TimescaleDB + pgvector)

Extensões necessárias:

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

## 1. Universo de ativos

```sql
CREATE TABLE assets (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL UNIQUE,          -- 'BTCUSDT', 'EURUSD', 'AAPL', 'SPX'
    asset_class     TEXT NOT NULL CHECK (asset_class IN
                        ('crypto','forex','equity','index','commodity')),
    exchange        TEXT,
    base_currency   TEXT,
    quote_currency  TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,  -- controla o universo do MVP (20-50 ativos)
    min_order_size  NUMERIC,
    tick_size       NUMERIC,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 2. Market data (séries temporais — hypertables Timescale)

```sql
CREATE TABLE ohlcv (
    asset_id     BIGINT NOT NULL REFERENCES assets(id),
    timeframe    TEXT NOT NULL CHECK (timeframe IN ('1m','5m','15m','1h','4h','1D','1W')),
    ts           TIMESTAMPTZ NOT NULL,
    open         NUMERIC NOT NULL,
    high         NUMERIC NOT NULL,
    low          NUMERIC NOT NULL,
    close        NUMERIC NOT NULL,
    volume       NUMERIC NOT NULL,
    PRIMARY KEY (asset_id, timeframe, ts)
);
SELECT create_hypertable('ohlcv', 'ts');
CREATE INDEX ON ohlcv (asset_id, timeframe, ts DESC);

CREATE TABLE orderbook_snapshots (
    asset_id      BIGINT NOT NULL REFERENCES assets(id),
    ts            TIMESTAMPTZ NOT NULL,
    best_bid      NUMERIC,
    best_ask      NUMERIC,
    spread_bps    NUMERIC,
    bid_liquidity NUMERIC,
    ask_liquidity NUMERIC,
    PRIMARY KEY (asset_id, ts)
);
SELECT create_hypertable('orderbook_snapshots', 'ts');
```

## 3. News & Intelligence Engine

```sql
CREATE TABLE news_events (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    published_at    TIMESTAMPTZ NOT NULL,
    headline        TEXT NOT NULL,
    body            TEXT,
    raw_url         TEXT,
    category        TEXT CHECK (category IN
                        ('central_bank','inflation','employment','gdp','geopolitics',
                         'regulation','crypto','earnings','m_and_a','other')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Saída do LLM interpretation layer para cada notícia relevante
CREATE TABLE news_impact (
    id              BIGSERIAL PRIMARY KEY,
    news_event_id   BIGINT NOT NULL REFERENCES news_events(id),
    asset_id        BIGINT NOT NULL REFERENCES assets(id),
    impact          TEXT NOT NULL CHECK (impact IN ('low','medium','high')),
    direction       TEXT NOT NULL CHECK (direction IN ('bullish','bearish','neutral')),
    confidence      NUMERIC NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    horizon_hours   NUMERIC NOT NULL,               -- relevância esperada (ex.: 4-24h)
    rationale       TEXT NOT NULL,                  -- explicação auditável gerada pelo LLM
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE macro_events (
    id              BIGSERIAL PRIMARY KEY,
    event_type      TEXT NOT NULL,                  -- 'FOMC','ECB','NFP','CPI','GDP',...
    scheduled_at    TIMESTAMPTZ NOT NULL,
    actual_at       TIMESTAMPTZ,
    forecast_value  NUMERIC,
    actual_value    NUMERIC,
    previous_value  NUMERIC,
    surprise_score  NUMERIC,                        -- (actual-forecast)/std histórico
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 4. Regime & Patterns

```sql
CREATE TABLE market_regimes (
    id              BIGSERIAL PRIMARY KEY,
    asset_id        BIGINT REFERENCES assets(id),   -- NULL = regime macro/global
    timeframe       TEXT NOT NULL,
    ts              TIMESTAMPTZ NOT NULL,
    regime          TEXT NOT NULL CHECK (regime IN
                        ('trending','ranging','high_vol','low_vol','bull','bear',
                         'panic','euphoria','transition')),
    confidence      NUMERIC NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    features        JSONB NOT NULL                  -- inputs que geraram a classificação
);
CREATE INDEX ON market_regimes (asset_id, timeframe, ts DESC);

CREATE TABLE patterns (
    id              BIGSERIAL PRIMARY KEY,
    asset_id        BIGINT NOT NULL REFERENCES assets(id),
    timeframe       TEXT NOT NULL,
    ts              TIMESTAMPTZ NOT NULL,
    pattern_type    TEXT NOT NULL,                  -- 'breakout','pullback','mean_reversion',...
    pattern_class   TEXT NOT NULL CHECK (pattern_class IN
                        ('technical','statistical','cross_market')),
    direction       TEXT CHECK (direction IN ('bullish','bearish','neutral')),
    strength        NUMERIC CHECK (strength BETWEEN 0 AND 1),
    metadata        JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX ON patterns (asset_id, timeframe, ts DESC);
CREATE INDEX ON patterns (pattern_type);

-- histórico de desempenho de cada tipo de padrão, por regime (alimenta o Pattern Memory)
CREATE TABLE pattern_performance (
    pattern_type    TEXT NOT NULL,
    regime          TEXT NOT NULL,
    sample_size     INTEGER NOT NULL DEFAULT 0,
    win_rate        NUMERIC,
    avg_r_multiple  NUMERIC,
    expectancy      NUMERIC,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (pattern_type, regime)
);
```

## 5. Strategies

```sql
CREATE TABLE strategies (
    id              BIGSERIAL PRIMARY KEY,
    code            TEXT NOT NULL UNIQUE,           -- 'momentum_v1', 'breakout_v2'
    name            TEXT NOT NULL,
    family          TEXT NOT NULL,                  -- momentum/trend/mean_reversion/breakout/...
    lifecycle_stage TEXT NOT NULL DEFAULT 'idea' CHECK (lifecycle_stage IN
                        ('idea','backtest','out_of_sample','paper','small_capital',
                         'production','quarantine','retired')),
    params          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE strategy_performance (
    strategy_id       BIGINT NOT NULL REFERENCES strategies(id),
    as_of             TIMESTAMPTZ NOT NULL,
    window_trades     INTEGER NOT NULL,             -- janela usada (ex.: últimas 200 trades)
    total_trades      INTEGER NOT NULL,
    win_rate          NUMERIC,
    profit_factor     NUMERIC,
    avg_win           NUMERIC,
    avg_loss          NUMERIC,
    sharpe            NUMERIC,
    max_drawdown      NUMERIC,
    expectancy        NUMERIC,
    best_regime       TEXT,
    worst_regime      TEXT,
    PRIMARY KEY (strategy_id, as_of)
);
```

## 6. Signals, Scoring, Risk

```sql
CREATE TABLE signals (
    id              BIGSERIAL PRIMARY KEY,
    strategy_id     BIGINT NOT NULL REFERENCES strategies(id),
    asset_id        BIGINT NOT NULL REFERENCES assets(id),
    ts              TIMESTAMPTZ NOT NULL,
    direction       TEXT NOT NULL CHECK (direction IN ('long','short')),
    entry_price     NUMERIC NOT NULL,
    stop_price      NUMERIC NOT NULL,
    target_price    NUMERIC,
    regime_id       BIGINT REFERENCES market_regimes(id),
    pattern_id      BIGINT REFERENCES patterns(id),
    news_impact_id  BIGINT REFERENCES news_impact(id),
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN
                        ('pending','scored','risk_rejected','approved','executed','expired'))
);

CREATE TABLE opportunity_scores (
    id                  BIGSERIAL PRIMARY KEY,
    signal_id           BIGINT NOT NULL REFERENCES signals(id),
    technical           NUMERIC NOT NULL,
    regime_fit          NUMERIC NOT NULL,
    news                NUMERIC NOT NULL,
    momentum            NUMERIC NOT NULL,
    historical_pattern  NUMERIC NOT NULL,
    liquidity           NUMERIC NOT NULL,
    risk_reward         NUMERIC NOT NULL,
    strategy_performance NUMERIC NOT NULL,
    volatility_penalty  NUMERIC NOT NULL DEFAULT 0,
    correlation_penalty NUMERIC NOT NULL DEFAULT 0,
    execution_cost_penalty NUMERIC NOT NULL DEFAULT 0,
    drawdown_penalty    NUMERIC NOT NULL DEFAULT 0,
    final_score         NUMERIC NOT NULL,            -- ver 07-scoring-engine.md
    tier                TEXT NOT NULL CHECK (tier IN
                            ('ignore','watch','possible','high_quality','exceptional')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE risk_checks (
    id              BIGSERIAL PRIMARY KEY,
    signal_id       BIGINT NOT NULL REFERENCES signals(id),
    check_name      TEXT NOT NULL,                  -- 'portfolio_exposure','correlation','drawdown',...
    passed          BOOLEAN NOT NULL,
    detail          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE risk_decisions (
    id              BIGSERIAL PRIMARY KEY,
    signal_id       BIGINT NOT NULL REFERENCES signals(id) UNIQUE,
    approved        BOOLEAN NOT NULL,
    approved_size   NUMERIC,                        -- posição final autorizada (pode ser < sugerido)
    reason          TEXT NOT NULL,
    safety_belt_level TEXT NOT NULL,                 -- ver 08-risk-engine.md
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 7. Portfolio & Correlation

```sql
CREATE TABLE portfolio_snapshots (
    ts              TIMESTAMPTZ NOT NULL PRIMARY KEY,
    equity          NUMERIC NOT NULL,
    cash            NUMERIC NOT NULL,
    exposure_pct    NUMERIC NOT NULL,
    daily_pnl       NUMERIC NOT NULL,
    drawdown_pct    NUMERIC NOT NULL,
    safety_belt_level TEXT NOT NULL
);
SELECT create_hypertable('portfolio_snapshots', 'ts');

CREATE TABLE positions (
    id              BIGSERIAL PRIMARY KEY,
    asset_id        BIGINT NOT NULL REFERENCES assets(id),
    strategy_id     BIGINT NOT NULL REFERENCES strategies(id),
    signal_id       BIGINT REFERENCES signals(id),
    direction       TEXT NOT NULL CHECK (direction IN ('long','short')),
    entry_price     NUMERIC NOT NULL,
    current_stop    NUMERIC NOT NULL,
    target_price    NUMERIC,
    size            NUMERIC NOT NULL,
    opened_at       TIMESTAMPTZ NOT NULL,
    closed_at       TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
    realized_pnl    NUMERIC,
    unrealized_pnl  NUMERIC
);

CREATE TABLE correlation_matrix (
    ts              TIMESTAMPTZ NOT NULL,
    asset_id_a      BIGINT NOT NULL REFERENCES assets(id),
    asset_id_b      BIGINT NOT NULL REFERENCES assets(id),
    window_days     INTEGER NOT NULL,
    correlation     NUMERIC NOT NULL,
    PRIMARY KEY (ts, asset_id_a, asset_id_b, window_days)
);
```

## 8. Execução

```sql
CREATE TABLE orders (
    id              BIGSERIAL PRIMARY KEY,
    position_id     BIGINT REFERENCES positions(id),
    signal_id       BIGINT REFERENCES signals(id),
    broker_order_id TEXT,
    order_type      TEXT NOT NULL CHECK (order_type IN ('market','limit','stop')),
    side            TEXT NOT NULL CHECK (side IN ('buy','sell')),
    qty             NUMERIC NOT NULL,
    limit_price     NUMERIC,
    status          TEXT NOT NULL DEFAULT 'new' CHECK (status IN
                        ('new','submitted','filled','partially_filled','cancelled','rejected')),
    submitted_at    TIMESTAMPTZ,
    filled_at       TIMESTAMPTZ,
    filled_price    NUMERIC,
    fees            NUMERIC,
    slippage_bps    NUMERIC,
    is_paper        BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE trades (
    id              BIGSERIAL PRIMARY KEY,
    position_id     BIGINT NOT NULL REFERENCES positions(id),
    opened_order_id BIGINT REFERENCES orders(id),
    closed_order_id BIGINT REFERENCES orders(id),
    pnl             NUMERIC NOT NULL,
    r_multiple      NUMERIC,                        -- pnl / risco inicial
    outcome         TEXT NOT NULL CHECK (outcome IN ('win','loss','breakeven')),
    is_paper        BOOLEAN NOT NULL DEFAULT TRUE,
    closed_at       TIMESTAMPTZ NOT NULL
);
```

## 9. Learning Engine & Market Memory

```sql
CREATE TABLE trade_journal (
    id              BIGSERIAL PRIMARY KEY,
    trade_id        BIGINT NOT NULL REFERENCES trades(id) UNIQUE,
    expected_outcome TEXT NOT NULL,                 -- o que o score/tese previa
    actual_outcome  TEXT NOT NULL,
    hypothesis      TEXT,                           -- explicação gerada pelo Learning Agent
    root_cause      TEXT,
    action_taken    TEXT,                           -- ex.: 'downgrade strategy in high_vol regime'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE learned_rules (
    id              BIGSERIAL PRIMARY KEY,
    scope           TEXT NOT NULL,                  -- 'strategy:breakout_v2', 'pattern:liquidity_sweep'
    condition       JSONB NOT NULL,                  -- ex.: {"regime":"high_vol","post_news":true}
    conclusion      TEXT NOT NULL,                   -- ex.: 'poor expectancy'
    confidence      NUMERIC NOT NULL,
    sample_size     INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN
                        ('candidate','validated','rejected','retired')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    validated_at    TIMESTAMPTZ
);

-- Market Memory: embedding do "estado de mercado" no momento da decisão
CREATE TABLE market_memory (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL,
    asset_id        BIGINT REFERENCES assets(id),
    context         JSONB NOT NULL,                 -- regime, padrões ativos, notícias, score
    signal_id       BIGINT REFERENCES signals(id),
    outcome         TEXT,                            -- preenchido após fecho do trade
    embedding       VECTOR(1536) NOT NULL
);
CREATE INDEX market_memory_embedding_idx ON market_memory
    USING hnsw (embedding vector_cosine_ops);
```

## 10. Sistema, auditoria e alertas

```sql
CREATE TABLE system_state (
    id                  BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id),  -- linha única (singleton)
    safety_belt_level   TEXT NOT NULL DEFAULT 'normal' CHECK (safety_belt_level IN
                            ('normal','caution','defensive','emergency','kill_switch')),
    trading_enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_reason      TEXT
);

CREATE TABLE alerts (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    severity        TEXT NOT NULL CHECK (severity IN ('info','warning','critical')),
    category        TEXT NOT NULL CHECK (category IN
                        ('trade','risk','loss','emergency','learning')),
    message         TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    acknowledged    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor           TEXT NOT NULL,                  -- nome do agente/serviço
    action          TEXT NOT NULL,
    entity_type     TEXT,
    entity_id       BIGINT,
    detail          JSONB NOT NULL DEFAULT '{}'
);
```

## Notas de implementação

- Migrations geridas com **Alembic** em `infra/migrations/`.
- `ohlcv` e `portfolio_snapshots` como hypertables Timescale desde o início (evita
  reescrever quando o volume crescer).
- `market_memory.embedding` assume embeddings de 1536 dims (compatível com modelos de
  embedding padrão); ajustar dimensão conforme o modelo escolhido em `06-memory-system.md`.
- Todas as tabelas de decisão (`opportunity_scores`, `risk_checks`, `risk_decisions`)
  existem para alimentar a aba **"Why?"** do dashboard (`09-dashboard-spec.md`) —
  nenhuma decisão de trade deve poder ser tomada sem gerar estas linhas.
