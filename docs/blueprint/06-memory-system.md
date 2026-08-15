# 06 — Memory System

Seis memórias distintas, cada uma com propósito e schema próprios (`02-database-schema.md`).

| Memória | Tabela(s) | Escrita por | Propósito |
|---|---|---|---|
| **Market Memory** | `market_memory` (pgvector) | Master Supervisor, no momento de cada `SIGNAL_CREATED` | "Já vi um contexto de mercado parecido com este — o que aconteceu?" |
| **Pattern Memory** | `patterns`, `pattern_performance` | Pattern Engine + Learning Agent | Desempenho histórico de cada tipo de padrão, por regime |
| **Strategy Memory** | `strategies`, `strategy_performance` | Learning Agent | Saúde e evolução de cada estratégia ao longo do tempo |
| **Trade Memory** | `trades`, `positions`, `orders` | Execution Engine | Registo factual e completo de tudo o que foi executado (paper ou real) |
| **Failure Memory** | `trade_journal` (outcome=LOSS) | Learning Agent | Condições associadas especificamente a perdas |
| **Research Memory** | `learned_rules`, hipóteses do Research Agent | Research Agent + Learning Agent | Hipóteses, experimentos e o que foi validado/rejeitado |

## Market Memory — como funciona

1. No momento em que um `Signal` é criado, monta-se um `context` estruturado:
   regime atual, padrões ativos, notícias recentes relevantes, score breakdown.
2. Esse `context` é serializado e passado a um modelo de embedding →
   `market_memory.embedding` (1536 dims).
3. Quando o trade fecha, `market_memory.outcome` é preenchido (`win`/`loss`/`r_multiple`).
4. Consulta típica (usada pelo Research Agent e pelo ecrã "Brain"):
   `ORDER BY embedding <=> query_embedding LIMIT 10` → "situações históricas
   semelhantes e o que aconteceu".

```python
def find_similar_contexts(context: MarketContext, k: int = 10) -> list[MarketMemoryHit]:
    embedding = embed(context.to_text())
    return db.query(MarketMemory).order_by(MarketMemory.embedding.cosine_distance(embedding)).limit(k)
```

## Regra de escrita

Todas as memórias são **append-only** para os factos (trade, sinal, padrão
detetado). Apenas `learned_rules` e `strategies.lifecycle_stage` têm um campo de
estado mutável (`status`/`lifecycle_stage`), e só transicionam através do fluxo
descrito em `04-agents-architecture.md §Agent 14` — nunca por escrita direta de um
agente LLM.
