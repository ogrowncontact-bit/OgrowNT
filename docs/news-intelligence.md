# News Intelligence — visão geral (Prompt 6)

Camada de inteligência que transforma notícias externas em **EVENT → CONTEXT →
SENTIMENT → IMPACT ESTIMATE → MARKET RISK SIGNAL → OPPORTUNITY CONTEXT**, nunca em
uma ordem. Ver `docs/event-risk.md` para a regra de soberania do Risk Engine e
`docs/sentiment.md`/`docs/macro-events.md` para os dois módulos vizinhos.

## Regra fundamental

> Uma notícia nunca deve ser considerada automaticamente BUY ou SELL. É uma fonte
> de informação, não uma ordem.

Estruturalmente: `packages/quant/news/` nunca importa `packages/execution`, nunca
constrói um `RiskVerdict`/`RiskDecision`, e o único ponto onde influencia uma
operação é um multiplicador de tamanho + flag de bloqueio consumido pelo Risk
Engine (`packages/risk/news_guard.py`, ver `docs/event-risk.md`). Testado
estruturalmente em `tests/test_news_simulation.py` (percorre a AST de todo o
pacote e falha se algo importar `packages.execution`).

## Providers (abstração, nunca acoplado a um fornecedor)

```text
NewsProvider (packages/data/connectors/news/base.py)
│   get_recent_news(since, limit) -> list[NewsItem]
│
└── MockNewsProvider (packages/data/connectors/news/mock.py)
    # NÃO é uma fonte real — headlines sintéticas por categoria, determinísticas
    # por janela de 15 min. TODO(real-news-data): adaptador real antes de capital ao vivo.
```

`NewsItem`: `source, published_at, headline, body, raw_url, category`.

## Pipeline determinístico (`packages/quant/news/`)

Tudo abaixo é **DET** (determinístico) — nenhuma chamada a LLM. O único passo com
LLM em toda a stack é `packages/llm/news_intelligence.py`'s `interpret_news_item()`
(direction/impact/confidence/rationale por par notícia↔ativo), inalterado desde a
Fase 4 e chamado depois deste pipeline, nunca antes.

| Módulo | Função | O que faz |
|---|---|---|
| `entities.py` | `extract_entities()` | Dicionário curado (empresas, crypto, moedas, bancos centrais, commodities, índices, setores, indicadores) — nunca inventa uma entidade que não bate com um alias conhecido |
| `asset_mapping.py` | `map_entities_to_assets()` | Notícia → ativos potencialmente afetados, com `is_direct` (entidade É o ativo) vs indireto (driver macro/setor) — direto nunca é rebaixado por um match indireto do mesmo símbolo |
| `sentiment.py` | `classify_sentiment()` | Léxico financeiro DET → `very_bullish…very_bearish\|unknown`, com `confidence`. Ver `docs/sentiment.md` |
| `importance.py` | `classify_importance()` | Categoria + palavras-chave de urgência → `low\|medium\|high\|critical` |
| `novelty.py` | `compute_novelty_score()` | 100 para o primeiro item de um cluster, decai a cada repetição |
| `dedup.py` | `find_cluster()`, `compute_source_consensus()` | Similaridade de Jaccard sobre palavras significativas (heurística documentada — sem modelo de embeddings neste ambiente) + consenso/conflito entre fontes independentes |
| `source_quality.py` | `score_source()` | Tabela de reputação curada, 0–100 |
| `impact_score.py` | `compute_impact_score()` | 0–100, pesos configuráveis em `config/news_weights.yaml` |
| `momentum.py` | `compute_news_momentum()` | Volume + velocidade + importância + concentração de fontes por ativo |
| `context.py` | `build_asset_news_context()` | Agrega tudo acima por ativo — consumido pela API/dashboard |
| `event_reaction.py` | `compute_event_reactions()` | Event Reaction Memory — ver secção própria abaixo |

## Schema (`packages/shared/models.py`, migração `0011`)

`news_events` ganhou: `source_type, source_quality_score, retrieved_at, language,
entities (JSON), novelty_score, cluster_id (auto-referência), source_consensus_score,
has_conflicting_sources, sentiment, sentiment_confidence, importance, impact_score`.
`category` foi alargado (não renomeado) com as categorias do Prompt 6 §9.

`news_impact` ganhou `is_direct` (bool).

Novas tabelas: `macro_events` (`docs/macro-events.md`), `event_reactions` (abaixo).

## Event Reaction Memory (§19/§30-32)

"Como este tipo de evento costuma afetar este ativo?" — `event_reactions`,
recalculada por `compute_event_reactions()` a partir de movimentos de preço reais
(`packages/shared/market_data.py`'s `get_close_at_or_after()`) após notícias
passadas, mesmo padrão de recomputação total que `StrategyPerformance`
(`packages/quant/learning/strategy_stats.py`). Um par (categoria, ativo) só ganha
linha com `MIN_SAMPLES_FOR_REACTION` (5) observações — abaixo disso, nenhuma
estatística é mostrada, nunca uma "amostra de 2" a parecer confiável.

## Workers (cadências, não processos separados)

Todo o resto desta base de código (Fases 1-7) usa **um processo, múltiplas
cadências independentes** — nunca um processo por agente. O Prompt 6 §37 nomeia 6
workers separados; mantidos como cadências distintas dentro de `apps/worker/main.py`
pela mesma razão de sempre: isolamento real (uma cadência lenta/falha nunca bloqueia
outra) sem a complexidade operacional de gerir 6 processos para um sistema
single-user.

| Cadência | Intervalo (config) | O que faz |
|---|---|---|
| `news_interval_seconds` (900s) | Ingestão + pipeline DET completo + interpretação LLM (`apps/worker/news_agent.py`) — ingestão, análise e "deteção de evento" são um único passe sequencial sobre o mesmo item, não 3 passes redundantes |
| `macro_calendar_interval_seconds` (1800s) | `apps/worker/macro_agent.py` — ingere/resolve o calendário macro |
| `sentiment_shift_interval_seconds` (900s) | `apps/worker/sentiment_agent.py` — deteção agregada de SENTIMENT_SHIFT por ativo |
| `research_interval_seconds` (3600s) | Partilhada com o Research Agent — `compute_event_reactions()` (NewsLearningWorker), trabalho batch/lento como o resto desta cadência |

## Failure handling (§38)

Uma falha na cadência de notícias é isolada por `apps/worker/supervisor.py`'s
`CadenceFailureTracker` — não derruba o worker, e após falhas consecutivas gera um
`Alert`. `run_news_cycle()` também continua honestamente mesmo sem
`ANTHROPIC_API_KEY`: ingestão e todo o pipeline DET continuam a preencher
`news_events` com sentimento/importância/impact_score reais; só a interpretação
LLM por ativo fica vazia, e isso é registado, nunca fingido.

## Segurança (§40)

Conteúdo de notícia nunca é executado — é sempre um `NewsItem`/string em Python,
nunca `eval`ado. A única superfície onde texto de notícia chega a um LLM é
`interpret_news_item()`, cuja saída já era estritamente validada (enums, ranges,
símbolos dentro do universo) antes do Prompt 6 e continua assim.

## API

`GET /api/news` (agora com os campos acima), `GET /api/news/risk`, `GET
/api/news/context/{symbol}` — ver `apps/api/routers/news.py`.
