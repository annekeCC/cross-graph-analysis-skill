# NLM KG Skill Summary

## Executive summary

The NLM KG Skill is a working Codex capability that answers biomedical questions by combining two complementary knowledge graphs: the NCBI Knowledge Graph and the NLM Cell Knowledge Network (NLM-CKN).

The value is not simply access to two databases. The skill translates a research question into bounded graph queries, reconciles compatible records using stable biomedical identifiers, distinguishes evidence from interpretation, and produces a provenance-rich answer that can be audited and reproduced.

This is an effective prototype for a future MCP service. The skill lets us validate scientific use cases, identifier mappings, query patterns, safeguards, and report design before committing them to a formal tool interface.

## What it enables

The skill can currently support:

- Cross-graph profiles of genes, including functions, proteins, variants, diseases, cell sets, and tissues.
- Disease-centered analyses that connect NCBI-associated genes with NLM cellular context.
- Drug-to-target-to-cell-set exploration, where the graph coverage exists.
- Tissue and cell-type analyses, including marker recurrence across experimental datasets.
- Evidence reports with source attribution, coverage gaps, exact queries, and machine-readable results.

The two graphs contribute different strengths:

| Source | Primary contribution |
|---|---|
| NCBI Knowledge Graph | Gene function, proteins, variants, diseases, ontology annotations, and pathways |
| NLM-CKN | Cell types, tissues, experimental cell sets, marker genes, datasets, publications, drugs, and targets |

## Demonstrated value

Three examples show the breadth of the approach:

1. **TCF7L2 gene profile:** joined the same gene across both graphs with an exact NCBI Gene identifier and separated NCBI functional evidence from NLM cellular evidence.
2. **Sitagliptin–DPP4 analysis:** traced a drug to its protein target, recorded disease connections, and identified experimental cell sets that selectively express DPP4.
3. **Liver marker analysis:** compared 241 liver-associated cell sets from 11 CELLxGENE dataset artifacts, identified recurrent markers, and added NCBI function and disease context where the graph supported an exact join.

These examples also expose coverage limitations clearly rather than filling gaps with unsupported assumptions.

## How it maintains trust

The skill is designed for evidence traceability:

- It uses public, read-only graph routes.
- It prefers stable identifiers over name matching.
- Every cross-graph join records its method and confidence.
- Every query records the endpoint, request, retrieval time, counts, and truncation state.
- Reports distinguish graph observations, cross-graph joins, and interpretation.
- Missing records are reported as coverage gaps, not biological absence.
- Exact graph requests and result summaries are retained in a final audit appendix.

The output is a research evidence summary, not clinical guidance. The skill does not infer comparative effectiveness, contraindications, adverse-event rates, or treatment recommendations from graph paths.

## Current status

The prototype is operational and includes:

- A reusable dual-graph query client.
- Preflight and live-schema checks.
- Specialist gene and disease workflows.
- Bounded exploratory search, traversal, and read-only Cypher.
- Identifier crosswalk rules and confidence levels.
- Machine-readable evidence envelopes.
- Markdown validation and a self-contained HTML report example.

## Leadership takeaway

The skill demonstrates that NCBI and NLM graph assets can be combined into a coherent, auditable research experience without merging the underlying systems. It already supports credible cross-graph analyses and provides a low-risk path for testing with users.

