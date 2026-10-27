# Report style

## Required sections

1. **Answerability** — supported, partially supported, unsupported, or ambiguous, with one-line reason.
2. **Summary** — concise answer limited to what the graph evidence supports.
3. **Evidence** — tables that keep NCBI observations, NLM observations, and joined evidence distinguishable.
4. **Coverage gaps and caveats** — missing entities, unmatched identifiers, truncation, and evidence types not present.
5. **Sources and provenance** — endpoint, retrieval time, request/query, row counts, and truncation.
6. **Reproducibility / audit appendix** — exact graph requests, parameters or payloads, retrieval timestamps, and result summaries needed to repeat and audit the result.

Keep exact graph requests and machine-oriented result summaries at the bottom of the report, after the scientific answer, evidence, caveats, and source overview. The original natural-language question and a readable graph-pattern translation may appear near the top; full request payloads belong in the final audit appendix. Link the complete raw JSON rather than expanding every returned node and edge inline.

Do not include a Mermaid evidence graph. Add a conventional chart only when it materially clarifies a ranking or comparison.

## Evidence table fields

Use the fields that apply:

- Entity label and stable identifier
- Source graph
- Relationship and direction
- Neighbor label and identifier
- Underlying source named by the graph
- Join key, method, and confidence
- Cell-set dataset and tissue
- NS-Forest or other quantitative metrics
- Evidence type: direct, variant-mediated, joined, or interpreted

Do not compress heterogeneous evidence into a single unexplained score. If ranking is useful, show the component dimensions.

## Language

- Say “the graph records,” “is associated with,” or “is connected through.”
- Do not say “causes,” “prevents,” “is safer,” or “responds better” unless that exact evidence and study design are present.
- Distinguish an absent record from negative evidence.
- State when clinical guidance, drug labels, trials, literature, pharmacogenomics, EHR/claims, or pharmacovigilance data are needed.

## Reproducibility

The JSON result is the source of truth. Markdown is rendered from it. Never retype identifiers, counts, queries, or timestamps when they can be taken from the JSON evidence ledger.
