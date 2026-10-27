#!/usr/bin/env python3
"""Render a provenance-rich Markdown report from graph_query.py JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).replace("|", "\\|").replace("\n", " ")


def heading_for(result: dict[str, Any]) -> str:
    command = result.get("command")
    data = result.get("data", {})
    if command == "profile-gene":
        return f"Cross-graph gene profile: {data.get('input', {}).get('gene', 'unknown')}"
    if command == "contextualize-disease":
        disease = data.get("resolved_disease") or {}
        return f"Disease-associated gene context: {disease.get('name') or data.get('input', {}).get('disease', 'unknown')}"
    return f"NCBI graph analysis: {command or 'result'}"


def summary_lines(result: dict[str, Any]) -> list[str]:
    command = result.get("command")
    data = result.get("data", {})
    lines: list[str] = []
    if command == "profile-gene":
        gene = data.get("ncbi", {}).get("gene") or {}
        joins = data.get("joins", [])
        lines.append(
            f"NCBI resolved **{gene.get('symbol') or data.get('input', {}).get('gene', 'the gene')}** "
            f"as `{gene.get('id', 'unresolved')}`; {len(joins)} cross-graph join candidate(s) were recorded."
        )
    elif command == "contextualize-disease":
        disease = data.get("resolved_disease") or {}
        lines.append(
            f"The NCBI graph resolved **{disease.get('name', data.get('input', {}).get('disease', 'the disease'))}** "
            f"and returned {data.get('returned_gene_count', 0)} of {data.get('total_ncbi_gene_count', 0)} associated gene(s); "
            f"{data.get('exact_nlm_join_count', 0)} had confidence-A traversable NLM joins."
        )
    else:
        lines.append("This report presents the bounded graph result and its exact provenance.")
    return lines


def render_profile(data: dict[str, Any]) -> list[str]:
    lines = ["## Evidence", "", "### Cross-graph joins", ""]
    joins = data.get("joins", [])
    if joins:
        lines.extend(
            [
                "| NCBI ID | NLM ID | Join key | Method | Confidence |",
                "|---|---|---|---|---|",
            ]
        )
        for join in joins:
            lines.append(
                f"| {cell(join.get('left_id'))} | {cell(join.get('right_id'))} | "
                f"{cell(join.get('join_key'))} | {cell(join.get('join_method'))} | "
                f"{cell(join.get('join_confidence'))} |"
            )
    else:
        lines.append("No cross-graph join was confirmed.")

    lines.extend(["", "### NCBI observations", ""])
    relationships = data.get("ncbi", {}).get("relationships", [])
    if relationships:
        lines.extend(
            [
                "| Direction | Relationship | Neighbor type | Neighbor ID | Neighbor name | Source |",
                "|---|---|---|---|---|---|",
            ]
        )
        for row in relationships:
            neighbor = row.get("neighbor") or {}
            lines.append(
                f"| {cell(row.get('direction'))} | {cell(row.get('relationship'))} | "
                f"{cell(', '.join(row.get('neighbor_labels') or []))} | {cell(neighbor.get('id'))} | "
                f"{cell(neighbor.get('name'))} | {cell(neighbor.get('source') or neighbor.get('provided_by'))} |"
            )
    else:
        lines.append("No NCBI relationships were returned.")

    lines.extend(["", "### NLM observations", ""])
    neighborhoods = data.get("nlm", {}).get("neighborhoods", {}).get("results", {})
    if neighborhoods:
        lines.extend(
            [
                "| Start node | Nodes | Links | Collections | Relationships |",
                "|---|---:|---:|---|---|",
            ]
        )
        for node_id, record in neighborhoods.items():
            lines.append(
                f"| {cell(node_id)} | {record.get('node_count', 0)} | {record.get('link_count', 0)} | "
                f"{cell(record.get('collection_counts', {}))} | {cell(record.get('relationship_counts', {}))} |"
            )

        for node_id, record in neighborhoods.items():
            lines.extend(
                [
                    "",
                    f"#### NLM nodes from {node_id}",
                    "",
                    "| Node ID | Collection | Label / cell term | Dataset | Marker combination | Tissue | Publication |",
                    "|---|---|---|---|---|---|---|",
                ]
            )
            for node in record.get("nodes", []):
                display_label = node.get("label") or node.get("author_cell_term")
                lines.append(
                    f"| {cell(node.get('_id'))} | {cell(str(node.get('_id', '')).split('/', 1)[0])} | "
                    f"{cell(display_label)} | {cell(node.get('dataset_name'))} | "
                    f"{cell(node.get('biomarker_combination'))} | {cell(node.get('anatomical_structure'))} | "
                    f"{cell(node.get('publication'))} |"
                )

            lines.extend(
                [
                    "",
                    f"#### NLM links from {node_id}",
                    "",
                    "| From | Relationship | To | Underlying source |",
                    "|---|---|---|---|",
                ]
            )
            for link in record.get("links", []):
                lines.append(
                    f"| {cell(link.get('_from'))} | {cell(link.get('Label'))} | "
                    f"{cell(link.get('_to'))} | {cell(link.get('Source'))} |"
                )
    else:
        lines.append("No traversable NLM neighborhood was returned.")
    return lines


def render_disease(data: dict[str, Any]) -> list[str]:
    lines = ["## Evidence", ""]
    disease = data.get("resolved_disease")
    if not disease:
        candidates = data.get("resolution_candidates", [])
        lines.append("The disease did not resolve uniquely.")
        if candidates:
            lines.extend(
                [
                    "",
                    "| Candidate ID | Candidate name |",
                    "|---|---|",
                ]
            )
            for candidate in candidates:
                lines.append(
                    f"| {cell(candidate.get('id'))} | {cell(candidate.get('name'))} |"
                )
        return lines

    genes = data.get("genes", [])
    if not genes:
        lines.append("No direct or variant-mediated gene evidence was returned.")
        return lines

    lines.extend(
        [
            "| Gene | NCBI Gene ID | NCBI evidence | Variants | NLM found | NLM nodes | NLM links | Join |",
            "|---|---|---|---:|---|---:|---:|---|",
        ]
    )
    for record in genes:
        gene = record.get("ncbi_gene") or {}
        join = record.get("join") or {}
        lines.append(
            f"| {cell(gene.get('symbol'))} | {cell(gene.get('id'))} | "
            f"{cell(', '.join(record.get('evidence_types') or []))} | {len(record.get('variants') or [])} | "
            f"{'yes' if record.get('nlm_found') else 'no'} | {record.get('nlm_node_count', 0)} | "
            f"{record.get('nlm_link_count', 0)} | "
            f"{cell(join.get('join_confidence') or 'unmatched')} — {cell(join.get('join_method'))} |"
        )

    lines.extend(["", "### NLM context by gene", ""])
    for record in genes:
        gene = record.get("ncbi_gene") or {}
        if not record.get("nlm_found"):
            continue
        lines.append(f"#### {gene.get('symbol') or gene.get('id')}")
        lines.append("")
        lines.append(f"- Collections: {cell(record.get('nlm_collection_counts', {}))}")
        lines.append(f"- Relationships: {cell(record.get('nlm_relationship_counts', {}))}")
        lines.append("")
    return lines


def render_generic(data: dict[str, Any]) -> list[str]:
    return [
        "## Evidence",
        "",
        "```json",
        json.dumps(data, indent=2, ensure_ascii=False),
        "```",
    ]


def render_sources(result: dict[str, Any]) -> list[str]:
    lines = [
        "## Sources and provenance",
        "",
        "| # | Source | Method | Endpoint | Retrieved | Response summary |",
        "|---:|---|---|---|---|---|",
    ]
    sources = result.get("sources", [])
    for index, source in enumerate(sources, 1):
        lines.append(
            f"| {index} | {cell(source.get('name'))} | {cell(source.get('method'))} | "
            f"{cell(source.get('endpoint'))} | {cell(source.get('retrieved_at'))} | "
            f"{cell(source.get('response_summary'))} |"
        )
    if not sources:
        lines.append("| 1 | No source ledger present | | | | |")
    return lines


def render_reproducibility(result: dict[str, Any]) -> list[str]:
    lines = [
        "## Exact graph requests and results",
        "",
        "Audit appendix. Exact requests and machine-oriented result summaries are kept "
        "after the scientific evidence and provenance overview.",
        "",
        f"- Result schema version: `{result.get('schema_version', 'unknown')}`",
        f"- Generated: `{result.get('generated_at', 'unknown')}`",
        f"- Command: `{result.get('command', 'unknown')}`",
        "",
    ]
    for index, source in enumerate(result.get("sources", []), 1):
        lines.extend(
            [
                f"### Request {index}: {source.get('name', 'source')}",
                "",
                f"`{source.get('method', '')} {source.get('endpoint', '')}`",
                "",
                "**Request payload**",
                "",
                "```json",
                json.dumps(source.get("request"), indent=2, ensure_ascii=False),
                "```",
                "",
                "**Result summary**",
                "",
                "```json",
                json.dumps(source.get("response_summary"), indent=2, ensure_ascii=False),
                "```",
                "",
                f"Retrieved: `{source.get('retrieved_at', 'unknown')}`",
                "",
            ]
        )
    return lines


def render(result: dict[str, Any]) -> str:
    data = result.get("data", {})
    lines = [
        f"# {heading_for(result)}",
        "",
        f"> Generated {result.get('generated_at', 'unknown')}. This report describes graph evidence; it is not clinical guidance.",
        "",
        "## Answerability",
        "",
        f"**Classification:** {str(result.get('answerability', 'unknown')).replace('_', ' ')}",
        "",
        "## Summary",
        "",
        *summary_lines(result),
        "",
    ]
    if result.get("command") == "profile-gene":
        lines.extend(render_profile(data))
    elif result.get("command") == "contextualize-disease":
        lines.extend(render_disease(data))
    else:
        lines.extend(render_generic(data))

    lines.extend(["", "## Coverage gaps and caveats", ""])
    gaps = data.get("coverage_gaps", [])
    if gaps:
        lines.extend(f"- {gap}" for gap in gaps)
    else:
        lines.append("- No additional coverage gaps were recorded by the client.")
    lines.extend(
        [
            "- Associations and graph paths do not establish causality or clinical effect.",
            "- An absent record is a graph-coverage result, not negative biological evidence.",
            "",
        ]
    )
    lines.extend(render_sources(result))
    lines.extend([""])
    lines.extend(render_reproducibility(result))
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = json.loads(Path(args.result_json).read_text())
    if not isinstance(result, dict) or "data" not in result:
        raise SystemExit("Input is not a graph_query.py result envelope")
    output = render(result)
    Path(args.output).write_text(output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
