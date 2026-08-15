# 09 — Dashboard Spec

Estética: **Dark Quant Terminal** — profissional, alta densidade de informação,
limpo, rápido. Não deve parecer um casino. Deve transmitir: inteligência + controlo +
segurança. Utilizador único (admin) — sem elementos de onboarding/multi-tenant.

## Ecrãs

### 1. Home / Overview

```text
TOTAL EQUITY | TODAY P&L | WEEK P&L | MONTH P&L | MAX DRAWDOWN | RISK STATE
──────────────────────────────────────────────────────────────────────────
ACTIVE POSITIONS (tabela)
──────────────────────────────────────────────────────────────────────────
TOP OPPORTUNITIES (tabela, ordenada por score)
──────────────────────────────────────────────────────────────────────────
MARKET REGIME (por classe de ativo)
──────────────────────────────────────────────────────────────────────────
STRATEGY HEALTH (mini cards por estratégia)
──────────────────────────────────────────────────────────────────────────
AI ACTIVITY (últimos eventos do Master Supervisor / Research Agent)
```

Dados: `GET /api/portfolio`, `GET /api/positions`, `GET /api/opportunities`,
`GET /api/regime`, `GET /api/strategies/*/performance`, WS `/ws/live`.

Fase 1 (estado inicial, antes de haver estratégias/sinais):

```text
AI QUANT SYSTEM
SYSTEM:        🟢 ONLINE
PAPER CAPITAL: €10,000
EQUITY:        €10,000
P&L:           €0
RISK:          NORMAL
MARKET DATA:   CONNECTED
ASSETS:        [lista do universo configurado]
OPPORTUNITIES: []
POSITIONS:     None
```

### 2. Opportunities

Tabela com, por linha: Asset, Direction, Strategy, Score, Probability estimate,
Risk/Reward, Market Regime, Volatility, Liquidity, News Context, Suggested Position,
Risk, Expiration. Ações: `VIEW ANALYSIS`, `VIEW HISTORY`, `SIMULATE TRADE`. **Não
existe botão de live trade neste MVP** — apenas paper.

### 3. Trade Detail — aba "Why?"

```text
WHY ENTERED
✓ Trend confirmed
✓ Breakout detected
✓ Historical expectancy positive
✓ Regime compatible
✓ Liquidity acceptable
⚠ High volatility

ENTRY / STOP / TARGET / RISK / EXPECTED VALUE / RESULT
```

Dados: `GET /api/opportunities/{signal_id}` (pré-trade) e `GET /api/trades/{id}/why`
(pós-trade) — consomem diretamente `opportunity_scores` + `risk_checks` +
`risk_decisions`. Nenhum texto aqui é gerado ad-hoc pelo LLM sem uma linha de dados
determinística por trás de cada `✓`/`⚠`.

### 4. Learning

```text
Patterns discovered (7d)
Strategies improving / deteriorating
Recent failed setups
Regime changes detected
Research experiments em curso

Exemplo:
BREAKOUT
  Trending:        Strong
  Ranging:         Weak
  High volatility: Weak
  Low volatility:  Strong
```

Dados: `GET /api/learning`, `GET /api/learning/journal`, `GET /api/research/*`.

### 5. Brain

Justificações estruturadas e auditáveis do comportamento recente do sistema (não
expõe raciocínio interno privado do LLM, expõe conclusões e a data que as suportam).
Exemplo de texto gerado (a partir de dados, não inventado):
> "BTC apresentou breakout com volume acima da média. O padrão tem expectativa
> positiva neste regime, mas a volatilidade atual elevou o risco — a posição foi
> reduzida pelo Risk Engine."

### 6. System Health

```text
Market Data       🟢/🟡/🔴
News Feed         🟢/🟡/🔴
Database          🟢/🟡/🔴
AI Services       🟢/🟡/🔴
Risk Engine       🟢/🟡/🔴
Execution         🟢/🟡/🔴
Learning Engine   🟢/🟡/🔴
```

Qualquer 🔴 num componente crítico → banner `DEGRADED MODE` (`08-risk-engine.md
§Failure Mode`). Dados: `GET /api/system/health`.

### 7. Alerts

Feed cronológico com severidade (`info`/`warning`/`critical`) e categoria
(`trade`/`risk`/`loss`/`emergency`/`learning`). `POST /api/alerts/{id}/ack`.

## Componentes partilhados

- `EquityCard`, `PnLCard`, `DrawdownCard`, `RiskStateBadge` (cores: verde=NORMAL,
  amarelo=CAUTION, laranja=DEFENSIVE, vermelho=EMERGENCY, preto=KILL_SWITCH)
- `OpportunityTable`, `PositionTable`, `WhyPanel`, `RegimeBadge`, `HealthGrid`,
  `AlertFeed`

## Autenticação (frontend)

Página `/login` → `POST /api/auth/login` → token JWT guardado em cookie
httpOnly (não em `localStorage`). Todas as chamadas subsequentes passam pelo
`lib/api-client.ts`, que injeta o header e trata `401` redirecionando para `/login`.
