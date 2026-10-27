---
name: ncbi-graph-analysis
description: Query the NCBI Knowledge Graph and NLM Cell Knowledge Network, join biomedical evidence by stable identifiers, and produce provenance-rich gene or disease analyses. Use for cross-graph gene, disease, variant, protein, drug-target, cell-set, or tissue questions; not for clinical recommendations or adverse-event discovery when the required clinical or pharmacovigilance sources are absent.
---

# NCBI graph analysis

Use the bundled read-only client to inspect the live schemas, query each graph, perform explicit identifier joins, and retain an evidence ledger. Treat the two graphs as complementary sources, not a single federated database.

## Start here

Run commands from this skill directory. Network access may require the user's approval in a sandboxed session.

1. Preflight the services before a new analysis:

   ```bash
   python scripts/graph_query.py preflight
   ```

2. Choose the narrowest supported workflow:

   - A single gene across both graphs: `profile-gene`.
   - A disease and its direct or variant-mediated genes: `contextualize-disease`.
   - Graph inspection or an unsupported exploratory path: use the bounded low-level commands.

3. Keep the JSON result as the source of truth. Render Markdown only after reviewing identifiers, joins, coverage gaps, and truncation:

   ```bash
   python scripts/render_report.py result.json --output report.md
   python scripts/validate_report.py result.json --report report.md
   ```

## Specialist workflows

### Profile a gene

```bash
python scripts/graph_query.py --output tcf7l2.json profile-gene TCF7L2
```

Use this for function, cellular location, proteins, variants, diseases, and NLM cell-set or tissue context. The workflow joins an NCBI `Gene.id` such as `NCBIGene:6934` to an NLM `GS` node through its numeric `gene_id`.

### Contextualize disease-associated genes

Prefer a stable disease identifier when known:

```bash
python scripts/graph_query.py --output t2d.json contextualize-disease MONDO:0005148 --max-genes 12
```

This finds NCBI direct and variant-mediated gene connections, then checks the matched genes for NLM protein, disease, cell-set, tissue, and dataset context. Report unmatched genes; absence is a graph-coverage result, not evidence that the biology is absent.

### Low-level exploration

```bash
python scripts/graph_query.py ncbi-schema
python scripts/graph_query.py ncbi-stats
python scripts/graph_query.py ncbi-cypher --query 'MATCH (g:Gene {symbol: $symbol}) RETURN g LIMIT 5' --parameters '{"symbol":"TCF7L2"}'
python scripts/graph_query.py nlm-search DPP4 --db phenotypes --limit 20
python scripts/graph_query.py nlm-neighbors GS/DPP4 --collections GS,PR,CS,CL,CSD,UBERON,GO,MONDO,CHEMBL
```

Direct Cypher is a fallback. Prefer the specialist workflows for repeatable analyses.

## Evidence rules

- Label every claim as graph-observed, joined, or interpreted.
- Preserve source graph, endpoint, timestamp, request/query, row count, and truncation state.
- Use exact identifiers before names. Gene symbols are a labeled lower-confidence fallback only.
- Keep NCBI and NLM evidence separate in tables even when synthesizing them in prose.
- Report ambiguous entity resolution instead of choosing silently.
- Do not convert associations into causal claims.
- Do not infer clinical effectiveness, safety, contraindications, or adverse-event frequency from mechanistic graph evidence.
- State when a question needs drug labels, guidelines, trials, literature, pharmacogenomics, EHR/claims, or pharmacovigilance sources that are not present.

Read [references/crosswalks.md](references/crosswalks.md) before adding or changing join logic. Read [references/report-style.md](references/report-style.md) before producing a user-facing report.

## Safety and limits

- Use only the public read-only routes documented in [references/ncbi-kg-api.md](references/ncbi-kg-api.md) and [references/nlm-ckn-api.md](references/nlm-ckn-api.md).
- Never use NCBI admin, upload, feedback, or other state-changing routes.
- The client rejects write-like Cypher locally and the NCBI service enforces read-only queries again.
- Keep traversal depth at one unless the user explicitly needs a bounded deeper traversal.
- Respect result limits, timeouts, response-size caps, and truncation markers.
- Do not retry an expensive failing query more than once without narrowing it.

For supported command recipes and expected outputs, read [references/query-recipes.md](references/query-recipes.md).
