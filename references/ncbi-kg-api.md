# NCBI Knowledge Graph API

## Endpoint

Default base URL:

```text
https://ncbiaiagents-production.up.railway.app
```

Override it with `NCBI_KG_API_BASE`. Treat the configured base URL as the source of truth and record it in every result.

Public read-only routes used by this skill:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/neo4j/health` | Connection health and optional counts |
| GET | `/api/neo4j/schema` | Node labels, relationships, indexes, constraints, relationship patterns |
| GET | `/api/neo4j/stats` | Counts by node and relationship type |
| POST | `/api/neo4j/cypher` | Bounded read-only Cypher |

OpenAPI: <https://ncbiaiagents-production.up.railway.app/openapi.json>

Do not call admin, upload, feedback, export, or other routes from this skill.

## Cypher request

```json
{
  "query": "MATCH (g:Gene {symbol: $symbol}) RETURN properties(g) AS gene LIMIT 5",
  "parameters": {"symbol": "TCF7L2"},
  "max_results": 100,
  "timeout": 30
}
```

The service returns `results`, `count`, `truncated`, `query`, and `execution_time_ms`.

The bundled client additionally rejects write-oriented tokens, caps `max_results` at 1,000, caps timeout at 60 seconds, and limits response bytes.

## Current schema shape

Always call `preflight` or `ncbi-schema` rather than relying on a copied snapshot. At skill creation time the graph contained Gene, SequenceVariant, Disease, BiologicalProcess, MolecularActivity, Protein, CellularComponent, and Pathway nodes. Important relationships included:

- `IS_SEQUENCE_VARIANT_OF`
- `CAUSES`
- `GENE_ASSOCIATED_WITH_CONDITION`
- `ENABLES`
- `INVOLVED_IN`
- `LOCATED_IN`
- `HAS_GENE_PRODUCT`
- `PARTICIPATES_IN`

Coverage is selective. A missing gene, drug, variant, or edge is a graph-coverage result, not evidence that the biological relationship is false.
