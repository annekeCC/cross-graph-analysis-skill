# NLM Cell Knowledge Network API

## Endpoint

The existing NLM-CKN MCP client currently uses:

```text
https://stage.nlm-ckn.org
```

Override it with `NLM_CKN_API_BASE`. This is a stage endpoint; confirmation of a supported production endpoint remains a release gate.

Relevant implementation: <https://github.com/NIH-NLM/NLM-CKN-MCP/blob/main/src/cell_kg_mcp/client.py>

## Read-only routes

All current routes are POST requests with JSON bodies.

| Path | Purpose |
|---|---|
| `/arango_api/search/` | Search phenotype or ontology records |
| `/arango_api/collections/` | List available graph collections |
| `/arango_api/graph/` | Retrieve bounded graph neighborhoods |

### Search

```json
{
  "search_term": "TCF7L2",
  "db": "phenotypes",
  "search_fields": [
    "label",
    "markers",
    "author_cell_term",
    "cell_type",
    "definition",
    "hasExactSynonym",
    "exact_synonym",
    "_id"
  ]
}
```

Supported database values are `phenotypes` and `ontologies`. The backend does not accept a result limit, so the client slices the response locally and records the original count.

### Graph traversal

```json
{
  "node_ids": ["GS/TCF7L2"],
  "depth": 1,
  "edge_direction": "ANY",
  "allowed_collections": ["GS", "PR", "CS", "CL", "CSD", "UBERON", "GO", "MONDO", "CHEMBL"]
}
```

Keep depth at one by default. Valid directions are `ANY`, `OUTBOUND`, and `INBOUND`.

Important collections include:

- `GS`: genes
- `PR`: proteins
- `CS`: experimental cell sets
- `CSD`: cell-set datasets
- `CL`: Cell Ontology
- `UBERON`: anatomy
- `GO`: Gene Ontology
- `MONDO`: diseases
- `CHEMBL`: drug entities
- `PUB`: publications

Important relationships observed in the live graph include `SELECTIVELY_EXPRESSES`, `PRODUCES`, `MOLECULARLY_INTERACTS_WITH`, `IS_GENETIC_BASIS_FOR_CONDITION`, `DERIVES_FROM`, and `COMPOSED_PRIMARILY_OF`.

Coverage differs between the searchable database and the induced graph. A search hit may have no traversable neighborhood; preserve that distinction.
