# NCBI Graph Analysis

A Codex skill with a read-only Python command-line client for investigating biomedical questions across a proof of concept small knowledge graph of NCBI data and the NLM Cell Knowledge Network (NLM-CKN). It queries the graphs separately, joins records using explicit identifiers, and produces JSON results and Markdown evidence reports with source provenance, coverage gaps, and query details. The Python commands can also be run directly without Codex.

This project was developed using OpenAI Codex.

This is a research analysis tool, not a clinical decision-support system. Graph associations do not establish causality or clinical effectiveness.

## What it supports

- Cross-graph gene profiles, including NCBI function, proteins, variants, diseases, and NLM cell-set or tissue context.
- Disease-associated gene context, including direct and variant-mediated NCBI evidence and matching NLM records.
- Bounded graph inspection, search, neighborhood traversal, and read-only NCBI Cypher queries.
- Provenance-rich JSON results, rendered Markdown reports, and report validation.

The NCBI Knowledge Graph and NLM-CKN provide different kinds of evidence. A missing match is a coverage gap, not evidence that a biological relationship is absent.

## Requirements

- Python 3.10 or later.
- Network access to the configured NCBI Knowledge Graph and NLM-CKN services. A sandboxed environment may require approval for network requests.
- No third-party Python packages are required; the client uses the standard library.

## Quick start

Run commands from this repository's directory. Check both services before starting an analysis:

```bash
python scripts/graph_query.py preflight
```

For example, to investigate "What functional, disease, and cellular context do these graphs provide for TCF7L2?", create a gene profile and render a Markdown report:

```bash
python scripts/graph_query.py --output tcf7l2.json profile-gene TCF7L2
python scripts/render_report.py tcf7l2.json --output tcf7l2.md
python scripts/validate_report.py tcf7l2.json --report tcf7l2.md
```

This example queries NCBI for the gene and its relationships, searches NLM-CKN for matching records, and retrieves their cellular context where available. It creates:

- `tcf7l2.json`: graph results, cross-graph join methods and confidence, source requests, and coverage gaps.
- `tcf7l2.md`: a readable evidence report with NCBI and NLM observations, joins, limitations, and an audit appendix.

The final command checks the JSON and report for required structure and evidence fields; it does not validate the biological conclusions. Results depend on the services' current graph coverage.

The JSON is the source of truth. Review identifiers, joins, answerability, coverage gaps, and truncation before relying on the rendered report.

For disease-associated gene context, use a stable identifier when possible:

```bash
python scripts/graph_query.py --output t2d.json contextualize-disease MONDO:0005148 --max-genes 12
python scripts/render_report.py t2d.json --output t2d.md
python scripts/validate_report.py t2d.json --report t2d.md
```

## Other commands

```bash
python scripts/graph_query.py ncbi-schema
python scripts/graph_query.py ncbi-stats
python scripts/graph_query.py nlm-search DPP4 --db phenotypes --limit 20
python scripts/graph_query.py nlm-neighbors GS/DPP4 --collections GS,PR,CS,CL,CSD,UBERON,GO,MONDO,CHEMBL
```

The client also supports bounded, read-only Cypher with `ncbi-cypher`. Prefer `profile-gene` and `contextualize-disease` when they fit the question. See [SKILL.md](SKILL.md) for examples and evidence rules, and [references/query-recipes.md](references/query-recipes.md) for workflow details.

## Evidence and safety

- Prefer stable identifiers; treat gene-symbol matching as a lower-confidence fallback.
- Keep NCBI observations, NLM observations, cross-graph joins, and interpretation distinct.
- Preserve source, endpoint, retrieval time, request, result counts, and truncation state.
- Report ambiguity and missing graph coverage rather than resolving them silently.
- Do not infer clinical effectiveness, safety, contraindications, or adverse-event rates from graph paths. These questions require suitable clinical sources.
- Use only the public read-only routes. The client rejects write-like Cypher locally; do not use administrative or state-changing routes.

## Configuration

The client uses these environment variables when set; otherwise, it uses the defaults in `scripts/graph_query.py`:

| Variable | Purpose | Default |
|---|---|---|
| `NCBI_KG_API_BASE` | NCBI Knowledge Graph API base URL | `https://ncbiaiagents-production.up.railway.app` |
| `NLM_CKN_API_BASE` | NLM-CKN API base URL | `https://stage.nlm-ckn.org` |
| `NCBI_GRAPH_HTTP_TIMEOUT` | HTTP timeout in seconds | `30` |
| `NCBI_GRAPH_MAX_RESPONSE_BYTES` | Maximum response size | `20971520` |

## Repository map

- `SKILL.md`: skill instructions and supported workflows.
- `scripts/graph_query.py`: graph client and analysis commands.
- `scripts/render_report.py`: Markdown report renderer.
- `scripts/validate_report.py`: result and report validator.
- `references/`: API notes, crosswalk rules, query recipes, and report style.
- `NLM KG Skill Summary.md`: project summary and demonstrated analyses.
