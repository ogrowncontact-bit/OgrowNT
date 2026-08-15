# 08 — Risk Engine (o guardião)

Motor **determinístico**, com **poder de veto** sobre qualquer sinal, independente
do score. Nenhum outro agente — incluindo o Master Supervisor e qualquer LLM — pode
sobrepor-se a uma rejeição do Risk Engine (`04-agents-architecture.md`).

## Config (tudo ajustável, nada hardcoded)

```yaml
# config/risk_limits.yaml
capital:
  initial_paper_capital: 10000        # EUR, editável no painel
per_trade:
  max_risk_pct: 1.0                   # % do equity arriscado por trade (distância à stop)
  min_risk_reward: 1.5
portfolio:
  max_exposure_pct: 60                # % do equity em posições abertas simultaneamente
  max_single_asset_pct: 15
  max_correlated_cluster_pct: 25      # exposição agregada a posições com correlação > correlation_threshold
  correlation_threshold: 0.7
loss_limits:
  max_daily_loss_pct: 3
  max_weekly_loss_pct: 6
  max_strategy_drawdown_pct: 10
  max_portfolio_drawdown_pct: 15      # aciona EMERGENCY
liquidity:
  max_spread_bps: 50
  min_orderbook_depth_multiple: 3     # profundidade mínima vs. tamanho da ordem
data_quality:
  max_staleness_seconds: 120
```

## Risk States (Safety Belts)

```text
NORMAL     → operação normal, limites completos
CAUTION    → performance a deteriorar → reduzir size em 25%, reduzir frequência
DEFENSIVE  → perdas acima do esperado → reduzir novas posições em 50%, só tier ≥ high_quality
EMERGENCY  → drawdown crítico atingido → parar novas operações, gerir só posições existentes
KILL_SWITCH→ anomalia grave (dados corrompidos, falha de execução, drawdown extremo) → parar toda a automação
```

Transições (avaliadas a cada `Portfolio Engine` tick — Fase 3+):

```python
def evaluate_safety_belt(portfolio: PortfolioState, limits: RiskLimits) -> SafetyBelt:
    if portfolio.drawdown_pct >= limits.loss_limits.max_portfolio_drawdown_pct:
        return "EMERGENCY"
    if portfolio.daily_loss_pct >= limits.loss_limits.max_daily_loss_pct:
        return "DEFENSIVE"
    if portfolio.weekly_loss_pct >= limits.loss_limits.max_weekly_loss_pct * 0.7:
        return "CAUTION"
    return "NORMAL"
    # KILL_SWITCH nunca é automático a partir só de drawdown — ver §Kill Switch
```

Cada transição publica `RISK_STATE_CHANGED` e é gravada em `system_state` +
`audit_log`. O dashboard mostra o estado atual em destaque (`09-dashboard-spec.md`).

## Kill Switch

Acionado por:
1. **Automaticamente**: anomalia grave e não ambígua — falha de dados críticos
   persistente, discrepância entre posição esperada e posição reportada pelo broker,
   drawdown > 1.5× `max_portfolio_drawdown_pct` num único dia.
2. **Manualmente**: `POST /api/system/kill-switch` pelo admin, a qualquer momento.

Efeito: `system_state.trading_enabled = false`, todas as novas ordens bloqueadas.
Posições existentes continuam a ser monitorizadas (não fecha posições à força — isso
seria uma decisão de mercado, não de segurança). Só sai de Kill Switch por ação
explícita do admin, após o **Diagnostic Mode**:

```text
KILL_SWITCH → DIAGNOSTIC MODE → ANALYZE LOSSES → FIND CAUSE →
GENERATE HYPOTHESES → BACKTEST → PAPER TEST → VALIDATE → RECOVER GRADUALLY
```

**Nunca**: recuperar aumentando risco. A regra `Never chase losses` é aplicada
literalmente no código — não existe nenhum caminho no `PositionSizer` (abaixo) cuja
entrada seja "perda recente" e cuja saída seja um tamanho maior.

## Decision Pipeline do Risk Engine

Para cada sinal que chega com `tier ∈ {possible, high_quality, exceptional}`:

```text
1. trading_enabled?                        senão → BLOCK("kill_switch")
2. data_quality == 'high' e não stale?      senão → BLOCK("data_unavailable")
3. risk_reward >= min_risk_reward?          senão → BLOCK("poor_rr")
4. per-trade risk <= max_risk_pct?          senão → resize ou BLOCK
5. portfolio exposure + novo <= max_exposure_pct?   senão → BLOCK("exposure")
6. single asset exposure <= max_single_asset_pct?   senão → BLOCK("concentration")
7. correlation guard (ver abaixo)           senão → BLOCK("correlation")
8. spread/liquidez dentro dos limites?      senão → BLOCK("liquidity")
9. daily/weekly loss limits não excedidos?  senão → BLOCK("loss_limit")
10. strategy drawdown <= max_strategy_drawdown_pct? senão → BLOCK("strategy_quarantine")
→ todas passam → APPROVE(size=min(sugerido, limites acima))
```

Cada etapa grava uma linha em `risk_checks` (passed/failed + detail). O resultado
final grava-se em `risk_decisions`. **Qualquer falha numa etapa = sinal bloqueado
nessa etapa** (sem tentar "compensar" numa etapa seguinte).

## Correlation Guard

```python
def correlation_guard(new_signal: Signal, open_positions: list[Position],
                       corr_matrix: CorrelationMatrix, limits: RiskLimits) -> GuardResult:
    cluster_exposure = sum(
        p.exposure_pct for p in open_positions
        if corr_matrix.get(p.asset_id, new_signal.asset_id) >= limits.portfolio.correlation_threshold
    )
    if cluster_exposure + new_signal.proposed_exposure_pct > limits.portfolio.max_correlated_cluster_pct:
        return GuardResult(blocked=True, reason="correlated_cluster_exceeded")
    return GuardResult(blocked=False)
```

Objetivo: evitar que 4 "operações diferentes" (ex.: BTC long, Nasdaq long, EUR/USD
long, Gold long) sejam, na prática, uma única aposta concentrada em risk-on.

## Position Sizing

```python
def size_position(capital: float, risk_limit_pct: float, stop_distance_pct: float,
                   volatility_factor: float, confidence: float,
                   portfolio_headroom_pct: float, correlation_headroom_pct: float) -> float:
    risk_budget = capital * (risk_limit_pct / 100)
    raw_size = risk_budget / stop_distance_pct
    confidence_adj = raw_size * min(1.0, confidence)          # nunca aumenta o tamanho
    vol_adj = confidence_adj / max(1.0, volatility_factor)     # penaliza alta volatilidade
    portfolio_cap = capital * (portfolio_headroom_pct / 100)
    correlation_cap = capital * (correlation_headroom_pct / 100)
    return min(vol_adj, portfolio_cap, correlation_cap)
```

Aplica-se sempre o **menor** entre: limite da estratégia, limite do ativo, limite do
portfolio, limite de risco global, limite de liquidez. Nunca tamanho fixo
indiscriminado.

## Data Quality Gate

Antes de qualquer dado ser usado por qualquer agente:

```text
timestamp válido → sem valores em falta → não stale (> max_staleness_seconds) →
sem valores anómalos (outlier vs. últimas N barras) → sem duplicados → fonte "up"
```

Se qualquer verificação falhar: `data_quality = 'DATA_UNAVAILABLE'`, **nunca** um
valor inventado/interpolado. `NO TRADE` para qualquer sinal dependente desses dados.

## Failure Mode / Safe Mode

Se um componente crítico cair (API de mercado, DB, serviço de IA, news feed,
execution engine):

```text
SAFE MODE:
  - não abrir novas posições
  - continuar a monitorizar o que já está aberto (se possível)
  - preservar o último estado conhecido
  - alertar o admin (severity=critical)
  - tentar reconexão/recovery com backoff
```

`GET /api/system/health` reflete isto como `DEGRADED_MODE` (`03-api-spec.md`,
`09-dashboard-spec.md §System Health`). Preferir não operar a operar com dados
incompletos.
