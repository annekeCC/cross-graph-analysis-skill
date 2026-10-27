#!/usr/bin/env python3
"""Validate graph result provenance and an optional rendered Markdown report."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ANSWERABILITY = {"supported", "partially_supported", "unsupported", "ambiguous"}
REQUIRED_REPORT_HEADINGS = [
    "## Answerability",
    "## Summary",
    "## Evidence",
    "## Coverage gaps and caveats",
    "## Sources and provenance",
    "## Exact graph requests and results",
]


def validate_source(source: Any, index: int, errors: list[str]) -> None:
    if not isinstance(source, dict):
        errors.append(f"sources[{index}] is not an object")
        return
    for field in ("name", "endpoint", "method", "retrieved_at", "response_summary"):
        if not source.get(field):
            errors.append(f"sources[{index}] lacks {field}")
    endpoint = source.get("endpoint", "")
    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        errors.append(f"sources[{index}].endpoint is not HTTPS")


def validate_join(join: Any, context: str, errors: list[str]) -> None:
    if not isinstance(join, dict):
        errors.append(f"{context} is not an object")
        return
    for field in ("left_id", "right_id", "join_key", "join_method", "join_confidence"):
        if not join.get(field):
            errors.append(f"{context} lacks {field}")
    confidence = join.get("join_confidence")
    if confidence not in {"A", "B", "C"}:
        errors.append(f"{context} has invalid confidence {confidence!r}")
    if confidence == "A":
        left = str(join.get("left_id", ""))
        key = str(join.get("join_key", ""))
        match = re.fullmatch(r"NCBIGene:(\d+)", left)
        if not match or match.group(1) != key:
            errors.append(f"{context} confidence-A gene join does not preserve numeric ID")


def validate_result(result: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result is not a JSON object"]
    for field in ("schema_version", "generated_at", "command", "answerability", "sources", "data"):
        if field not in result:
            errors.append(f"result lacks {field}")
    if result.get("answerability") not in ANSWERABILITY:
        errors.append(f"invalid answerability: {result.get('answerability')!r}")
    sources = result.get("sources")
    if not isinstance(sources, list):
        errors.append("sources is not a list")
        sources = []
    for index, source in enumerate(sources):
        validate_source(source, index, errors)
    data = result.get("data")
    if not isinstance(data, dict):
        errors.append("data is not an object")
        return errors
    if not isinstance(data.get("coverage_gaps"), list):
        errors.append("data.coverage_gaps is not a list")

    command = result.get("command")
    if command == "profile-gene":
        for index, join in enumerate(data.get("joins", [])):
            validate_join(join, f"data.joins[{index}]", errors)
        if result.get("answerability") in {"supported", "partially_supported"}:
            names = {source.get("name") for source in sources if isinstance(source, dict)}
            if "NCBI Knowledge Graph" not in names:
                errors.append("profile-gene lacks NCBI provenance")
            if "NLM Cell Knowledge Network" not in names:
                errors.append("profile-gene lacks NLM provenance")
    elif command == "contextualize-disease":
        for gene_index, gene in enumerate(data.get("genes", [])):
            join = gene.get("join") if isinstance(gene, dict) else None
            if join:
                validate_join(join, f"data.genes[{gene_index}].join", errors)
        if data.get("resolved_disease") and "returned_gene_count" not in data:
            errors.append("resolved disease result lacks returned_gene_count")
    return errors


def validate_report(path: Path, result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    text = path.read_text()
    for heading in REQUIRED_REPORT_HEADINGS:
        if heading not in text:
            errors.append(f"report lacks heading {heading!r}")
    if all(heading in text for heading in REQUIRED_REPORT_HEADINGS):
        positions = [text.index(heading) for heading in REQUIRED_REPORT_HEADINGS]
        if positions != sorted(positions):
            errors.append("report headings do not follow the reader-first, audit-last order")
        top_level_headings = re.findall(r"^## .+$", text, flags=re.MULTILINE)
        if not top_level_headings or top_level_headings[-1] != REQUIRED_REPORT_HEADINGS[-1]:
            errors.append("exact graph requests and results must be the final report section")
    source_count = len(result.get("sources", []))
    if source_count and text.count("**Result summary**") < source_count:
        errors.append("audit appendix lacks a result summary for every source request")
    if "```mermaid" in text.lower():
        errors.append("report contains prohibited Mermaid output")
    generated_at = str(result.get("generated_at", ""))
    if generated_at and generated_at not in text:
        errors.append("report does not preserve result generated_at")
    if "not clinical guidance" not in text.lower():
        errors.append("report lacks the clinical-guidance boundary")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_json")
    parser.add_argument("--report")
    args = parser.parse_args()

    result_path = Path(args.result_json)
    try:
        result = json.loads(result_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[validate_report] FAIL: cannot read result JSON: {exc}")
        return 1

    errors = validate_result(result)
    if args.report:
        try:
            errors.extend(validate_report(Path(args.report), result))
        except OSError as exc:
            errors.append(f"cannot read report: {exc}")

    if errors:
        print("[validate_report] FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("[validate_report] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
