# Sentiment Engine (Prompt 6 §10-11, §21-22)

## Regra fundamental — SENTIMENT NÃO É DIREÇÃO

> Não assumir: BULLISH NEWS = PRICE WILL RISE. Uma empresa pode reportar lucro
> recorde e o preço cair (expectativa já precificada, guidance fraco, realização
> de lucros). Sentiment é apenas uma feature.

Por isso `classify_sentiment()` (`packages/quant/news/sentiment.py`) é
**deliberadamente independente** de `NewsImpact.direction` — o resultado da
interpretação LLM (§ próprio ficheiro `packages/llm/news_intelligence.py`), que já
existia antes do Prompt 6. São dois sinais computados por caminhos totalmente
diferentes:

| | Sentiment (`NewsEvent.sentiment`) | Direction (`NewsImpact.direction`) |
|---|---|---|
| Mede | Tom do texto da notícia em si | Chamada do LLM: "isto provavelmente empurra o preço para X" |
| Como | Léxico DET (positivo/negativo) | LLM (`packages/llm`), só quando `ANTHROPIC_API_KEY` está configurado |
| Por | Notícia | Par (notícia, ativo) |

## Classificação (`classify_sentiment`)

Léxico financeiro curado (positivo: *surge, beats, upgrade, record, rebound...*;
negativo: *plunge, miss, downgrade, crisis, warning...*) — heurística documentada,
sem modelo de NLP/embeddings neste ambiente. `UNKNOWN` (não "neutral" forçado)
quando nenhuma palavra do léxico aparece — a ausência de sinal é honesta, não um
neutro fabricado.

```text
score = (positivos - negativos) / total_hits
score >= 0.6           -> VERY_BULLISH
0.2 <= score < 0.6      -> BULLISH
-0.2 < score < 0.2       -> NEUTRAL
-0.6 < score <= -0.2      -> BEARISH
score <= -0.6              -> VERY_BEARISH
total_hits == 0              -> UNKNOWN, confidence 0.0
```

`confidence = min(1.0, total_hits / 4)` — mais palavras de sentimento encontradas,
mais confiança na leitura (nunca no preço).

## Sentiment Shift (§22)

`compute_sentiment_shift(db, asset_id)` compara a fração bullish das últimas 2h
contra as últimas 24h (janelas configuráveis). `detected=True` exige no mínimo
`MIN_SAMPLES_FOR_SHIFT` (3) observações em cada janela E um desvio ≥
`SHIFT_DETECTION_THRESHOLD` (0.25) — sem amostra suficiente, `detected` fica
`False`, nunca um alarme sobre 1 notícia.

Um shift detetado **nunca** vira trade sozinho — só alimenta:
- `apps/worker/sentiment_agent.py`'s `run_sentiment_shift_cycle()`, que gera um
  `Alert` (categoria `news`, com cooldown de `REALERT_COOLDOWN_HOURS`=6h para não
  repetir o mesmo shift em curso a cada ciclo);
- `AssetNewsContext` (`docs/news-intelligence.md`), mostrado no painel do
  dashboard.

## News Momentum (§21)

`compute_news_momentum()`: contagem, velocidade (fração de itens na última quarta
parte da janela), importância, fontes distintas → `low\|medium\|high`.

## Conflito com o técnico (§27-28)

`packages/quant/scoring/inputs.py`'s `compute_opportunity_confidence()` recebe
`news_signals` e reduz `confidence` (não o `final_score` diretamente, e nunca
bloqueia por si só) quando a notícia mais impactante/confiante contradiz a
direção técnica do sinal — `_NEWS_CONFLICT_CONFIDENCE = 0.4`, mesma magnitude que
`_INSUFFICIENT_HISTORY_CONFIDENCE`. Testado em
`tests/test_opportunity_confidence.py` e `tests/test_news_simulation.py`.
