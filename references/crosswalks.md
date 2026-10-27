# Cross-graph identifier rules

## Confidence levels

| Level | Meaning | Permitted use |
|---|---|---|
| A | Exact stable identifier after deterministic syntax normalization | Primary join |
| B | Explicit cross-reference recorded by a source graph | Join with cross-reference provenance |
| C | Exact normalized symbol or label with no stable-ID confirmation | Fallback only; label visibly |
| Rejected | Fuzzy name, partial label, or ambiguous synonym | Entity discovery only, not a join |

## Initial crosswalks

### Gene

Primary join:

```text
NCBI Gene.id = NCBIGene:<digits>
NLM GS.gene_id = <digits>
```

Example:

```text
NCBIGene:6934 ↔ GS/TCF7L2 with gene_id 6934
```

The numeric identifier is the join key. `GS/<symbol>` is not enough by itself for confidence A. If the numeric identifiers do not agree, do not join the records.

Symbol-only matching is confidence C and must include `join_method: "exact gene symbol fallback"`.

### Disease

Normalize syntax only:

```text
NLM MONDO/0005148 ↔ MONDO:0005148
NLM UMLS/C123456 ↔ UMLS:C123456
```

An explicit `hasDbXref` or equivalent source property is confidence B. A shared label without an identifier is not a disease join.

### Gene Ontology

Normalize slash to colon only when the collection is GO:

```text
GO/0002456 ↔ GO:0002456
```

### Cell type, tissue, and experimental cell set

`CL`, `UBERON`, `CS`, and `CSD` currently supply NLM-only context because the live NCBI graph does not expose corresponding node labels. Do not invent a cross-graph join.

## Required join record

Every joined row must carry:

```json
{
  "left_id": "NCBIGene:6934",
  "right_id": "GS/TCF7L2",
  "join_key": "6934",
  "join_method": "exact NCBI Gene ID",
  "join_confidence": "A"
}
```

Also retain unmatched left and right records. Coverage accounting is part of the result.

## Adding a crosswalk

Before adding a new crosswalk:

1. Inspect live records from both graphs.
2. Identify stable identifiers or an explicit source cross-reference.
3. Add positive, negative, and ambiguous examples.
4. State the normalization transformation exactly.
5. Never promote a label match to confidence A or B.
