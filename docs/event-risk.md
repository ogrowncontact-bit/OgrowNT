# News Risk Guard / Event Risk (Prompt 6 §17, §26, §29, §43, §48)

## A regra absoluta

> NEWS NUNCA deve diretamente BUY, SELL, EXECUTE. A notícia apenas fornece
> contexto. O Risk Engine continua soberano.

`packages/risk/news_guard.py`'s `evaluate_news_risk()` é o **único** ponto onde a
News Intelligence toca uma operação — e mesmo aí, apenas como mais um passo do
pipeline de decisão já existente em `packages/risk/engine.py`
(`evaluate_signal()`), com o mesmo poder que qualquer outro check: reduzir o
tamanho aprovado ou bloquear, nunca aprovar, nunca dimensionar sozinho, nunca
submeter uma ordem. Testado estruturalmente (nenhum ficheiro em
`packages/quant/news/` importa `packages.execution` ou constrói um
`RiskVerdict`/`RiskDecision`) e por simulação completa em
`tests/test_news_simulation.py`.

## Estados

```text
NORMAL     multiplicador 1.0    sem eventos relevantes
ELEVATED   multiplicador 0.75   evento high/critical fora da janela apertada, mas
                                  dentro de 3x essa janela ("aviso antecipado")
HIGH       multiplicador 0.5    evento macro high/critical iminente OU notícia
                                  high/critical recente
CRITICAL   multiplicador 0.0,   evento macro critical iminente OU notícia critical
           bloqueado             recente — bloqueia como qualquer outro veto do
                                  Risk Engine
```

Multiplicadores em `config/risk_limits.yaml`'s `news_risk_multipliers` —
configurável, não hardcoded em Python (mesmo padrão de
`safety_belt_multipliers`, Prompt 4 §35).

Deliberadamente **global/portfolio-wide**, não por ativo — mesmo âmbito que os
Safety Belts (`packages/risk/safety_belt.py`): uma decisão do Fed ou um choque
bancário sistémico é risco de mercado, não algo que se possa argumentar ser
irrelevante para um instrumento específico.

## Janelas (config/news_weights.yaml)

```yaml
pre_event_window_minutes: 30    # "iminente" para efeitos de HIGH/CRITICAL
post_event_window_minutes: 60   # quanto tempo uma notícia crítica recente continua a contar
```

`ELEVATED_WINDOW_MULTIPLIER = 3` em `news_guard.py` — a janela "aviso antecipado"
é 3x a janela apertada.

## Pipeline (`packages/risk/engine.py`)

O passo 11 (depois de Strategy Health, antes do dimensionamento) chama
`evaluate_news_risk()`:

```python
news_verdict = evaluate_news_risk(db, limits)
if news_verdict.blocked:
    return blocked("news_risk", ..., "news_risk_critical")
ok("news_risk", {"level": news_verdict.level, "reasons": news_verdict.reasons})
...
approved_quantity = sizing.quantity * policy.size_multiplier * health_verdict.size_multiplier * news_verdict.size_multiplier
```

O multiplicador de notícia combina-se multiplicativamente com o do Safety Belt e
o da Strategy Health — nunca substitui, nunca aumenta o tamanho.

## Alertas relacionados (§36)

`CRITICAL_NEWS` e `CONFLICTING_INFORMATION` (`apps/worker/news_agent.py`),
`HIGH_IMPACT_EVENT` e `MACRO_SURPRISE` (`apps/worker/macro_agent.py`),
`SENTIMENT_SHIFT` (`apps/worker/sentiment_agent.py`) — todos categoria `news`,
consultáveis via `GET /api/alerts` e visíveis no painel de Alertas do dashboard.
`NEWS_FEED_FAILURE` é coberto pelo mecanismo genérico já existente
(`apps/worker/supervisor.py`'s `CadenceFailureTracker`, que isola a falha e gera
um Alert após falhas consecutivas) — a mesma cobertura que qualquer outra
cadência do worker já tinha antes do Prompt 6.

## API

`GET /api/news/risk` — nível atual, multiplicador, `blocked`, `reasons` — o
mesmo cálculo que o Risk Engine consulta, exposto para o painel "Event Risk" do
dashboard.
