# Macro Events — calendário económico (Prompt 6 §15-17, §35)

## Provider

```text
MacroCalendarProvider (packages/data/connectors/macro/base.py)
│   get_events(start, end) -> list[MacroEventItem]
│
└── MockMacroCalendarProvider (packages/data/connectors/macro/mock.py)
    # NÃO é um calendário real — templates recorrentes (CPI, NFP, GDP, decisões
    # de juros, PMI, retail sales, unemployment, consumer confidence) com
    # ocorrência determinística por nome+ciclo. `actual` só existe para uma
    # ocorrência cujo scheduled_at já passou — nunca inventado antecipadamente.
    # TODO(real-macro-data): adaptador real (ex. Trading Economics, calendário
    # FRED) antes de capital ao vivo.
```

`MacroEventItem`: `event, country, currency, scheduled_at, importance, forecast,
previous, actual`.

## Schema

```python
# packages/shared/models.py — tabela macro_events (migração 0011)
id, event, country, currency, scheduled_at, importance (low|medium|high|critical),
forecast, previous, actual, surprise, status (scheduled|released)
```

`UniqueConstraint(event, country, scheduled_at)` — reingestão do mesmo evento
atualiza a linha existente (`apps/worker/macro_agent.py`'s upsert), nunca duplica.

## Surprise (§16)

```python
surprise = actual - forecast   # só calculado quando actual existe
```

Calculado em `apps/worker/macro_agent.py`, nunca no provider — o sistema nunca
assume a direção do mercado a partir da surpresa; ela é armazenada, ponto.

## Worker

`run_macro_calendar_cycle()` corre na cadência `macro_calendar_interval_seconds`
(1800s por omissão — um calendário muda muito menos vezes que as manchetes).
Janela de ingestão: 3 dias atrás → 14 dias à frente
(`LOOKBACK_DAYS`/`LOOKAHEAD_DAYS`).

## Alertas (§36)

- `HIGH_IMPACT_EVENT`: quando um evento `high`/`critical` entra na janela
  pré-evento (`pre_event_window_minutes`, `config/news_weights.yaml`) — uma vez
  por evento, nunca repetido a cada ciclo.
- `MACRO_SURPRISE`: no momento exato em que `status` passa de `scheduled` para
  `released` com `surprise` calculado.

## Integração com o Risk Engine

Ver `docs/event-risk.md` — um evento macro `high`/`critical` iminente é a
condição de "pre-event risk" (§17) que o News Risk Guard usa para reduzir ou
bloquear novas operações, nunca diretamente.

## API

`GET /api/macro?days_back=3&days_ahead=14` — `apps/api/routers/news.py`'s
`macro_router`.
