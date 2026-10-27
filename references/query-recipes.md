# Query recipes

## Preflight

Run before a new analysis or after an endpoint/schema failure:

```bash
python scripts/graph_query.py preflight
```

Review both service statuses, the NCBI schema, and NLM collections. Do not interpret a failed endpoint as an empty biological result.

## Gene profile

```bash
python scripts/graph_query.py --output gene.json profile-gene TCF7L2
python scripts/render_report.py gene.json --output gene.md
python scripts/validate_report.py gene.json --report gene.md
```

Expected output:

- NCBI gene record and bounded neighborhood
- NLM exact gene candidates and bounded neighborhoods
- Explicit crosswalk records
- NCBI-only and NLM-only observations
- Coverage gaps and exact request ledger

## Disease-associated gene context

```bash
python scripts/graph_query.py --output disease.json contextualize-disease MONDO:0005148 --max-genes 12
python scripts/render_report.py disease.json --output disease.md
python scripts/validate_report.py disease.json --report disease.md
```

Use a stable disease ID whenever possible. If a name resolves ambiguously, stop and present candidates.

The result distinguishes:

- Direct `GENE_ASSOCIATED_WITH_CONDITION` evidence
- Variant-mediated `Gene ← SequenceVariant → Disease` evidence
- Genes with exact NLM Gene ID matches
- Genes absent from the traversable NLM graph

## Drug-target exploration

The MVP has no dedicated drug workflow. Use NLM search and traversal:

```bash
python scripts/graph_query.py --output drug-search.json nlm-search sitagliptin --db phenotypes
python scripts/graph_query.py --output drug-neighbors.json nlm-neighbors CHEMBL/1422 --collections CHEMBL,PR,GS,MONDO
python scripts/graph_query.py --output target.json nlm-neighbors GS/DPP4 --collections GS,PR,CS,CL,CSD,UBERON,GO,MONDO,CHEMBL
```

Do not claim comparative effectiveness, contraindication, or adverse-event frequency from these graph paths.

## Answerability classification

Classify the requested answer before writing prose:

- **Supported:** the requested relation is explicitly represented and identifiers resolve.
- **Partially supported:** the graphs provide mechanistic context but not the requested clinical or causal conclusion.
- **Unsupported:** required entities or evidence types are absent.
- **Ambiguous:** multiple entities resolve and no stable identifier disambiguates them.

Record the classification and its reason in the answer.
