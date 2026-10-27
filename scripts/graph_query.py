#!/usr/bin/env python3
"""Read-only client and specialist workflows for the NCBI KG and NLM-CKN."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

NCBI_BASE = os.environ.get(
    "NCBI_KG_API_BASE", "https://ncbiaiagents-production.up.railway.app"
).rstrip("/")
NLM_BASE = os.environ.get("NLM_CKN_API_BASE", "https://stage.nlm-ckn.org").rstrip("/")
DEFAULT_TIMEOUT = min(max(int(os.environ.get("NCBI_GRAPH_HTTP_TIMEOUT", "30")), 1), 120)
MAX_RESPONSE_BYTES = min(
    max(int(os.environ.get("NCBI_GRAPH_MAX_RESPONSE_BYTES", str(20 * 1024 * 1024))), 1024),
    100 * 1024 * 1024,
)

DEFAULT_NLM_SEARCH_FIELDS = {
    "phenotypes": [
        "label",
        "markers",
        "author_cell_term",
        "cell_type",
        "definition",
        "hasExactSynonym",
        "exact_synonym",
        "gene_symbol",
        "gene_id",
        "biomarker_combination",
        "binary_gene_set",
        "_id",
    ],
    "ontologies": [
        "label",
        "definition",
        "hasExactSynonym",
        "exact_synonym",
        "comment",
        "gene_symbol",
        "gene_id",
        "_id",
    ],
}
DEFAULT_COLLECTIONS = [
    "GS",
    "PR",
    "CS",
    "CL",
    "CSD",
    "UBERON",
    "GO",
    "MONDO",
    "CHEMBL",
    "PUB",
]
FORBIDDEN_CYPHER = re.compile(
    r"\b(CREATE|DELETE|DETACH|SET|REMOVE|MERGE|DROP|LOAD\s+CSV|CALL)\b",
    re.IGNORECASE,
)
NLM_NODE_KEYS = [
    "_id",
    "label",
    "gene_symbol",
    "gene_id",
    "definition",
    "author_cell_term",
    "ontology_purl",
    "biomarker_combination",
    "binary_gene_set",
    "anatomical_structure",
    "dataset_name",
    "cellxgene_dataset",
    "publication",
    "precision",
    "recall",
    "on_target",
    "silhouette_score",
    "mean_silhouette",
    "species",
]
NLM_LINK_KEYS = ["_id", "_from", "_to", "Label", "Source", "skos", "Sampled_tissue"]


class GraphClientError(RuntimeError):
    """A bounded, user-facing graph client error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[Any, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json", "User-Agent": "ncbi-graph-analysis-skill/0.1"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, method=method, headers=headers)
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            status = response.status
    except HTTPError as exc:
        detail = exc.read(2000).decode("utf-8", errors="replace")
        raise GraphClientError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise GraphClientError(f"{method} {url} failed: {exc.reason}") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise GraphClientError(
            f"{method} {url} exceeded the {MAX_RESPONSE_BYTES}-byte response cap"
        )
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GraphClientError(f"{method} {url} returned invalid JSON") from exc
    return data, {
        "http_status": status,
        "response_bytes": len(raw),
        "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
    }


def source_record(
    name: str,
    endpoint: str,
    method: str,
    request_payload: dict[str, Any] | None,
    response_summary: dict[str, Any],
    transport: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "endpoint": endpoint,
        "method": method,
        "retrieved_at": utc_now(),
        "request": request_payload,
        "response_summary": response_summary,
        "transport": transport,
    }


def envelope(command: str, data: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "command": command,
        "answerability": data.get("answerability", "supported"),
        "sources": sources,
        "data": data,
    }


def validate_read_only_cypher(query: str) -> None:
    match = FORBIDDEN_CYPHER.search(query)
    if match:
        raise GraphClientError(
            f"Cypher rejected locally because it contains write/admin token {match.group(1)!r}"
        )
    if not query.strip():
        raise GraphClientError("Cypher query must not be empty")


def ncbi_get(path: str, source_name: str) -> tuple[Any, dict[str, Any]]:
    url = f"{NCBI_BASE}{path}"
    data, transport = request_json("GET", url)
    count = len(data) if isinstance(data, list) else None
    return data, source_record(
        source_name,
        url,
        "GET",
        None,
        {"count": count, "keys": sorted(data.keys()) if isinstance(data, dict) else None},
        transport,
    )


def ncbi_cypher(
    query: str,
    parameters: dict[str, Any] | None = None,
    max_results: int = 200,
    timeout: int = 30,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_read_only_cypher(query)
    max_results = min(max(max_results, 1), 1000)
    timeout = min(max(timeout, 1), 60)
    payload = {
        "query": query,
        "parameters": parameters or {},
        "max_results": max_results,
        "timeout": timeout,
    }
    url = f"{NCBI_BASE}/api/neo4j/cypher"
    data, transport = request_json("POST", url, payload, timeout=timeout + 5)
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise GraphClientError("NCBI Cypher returned an unexpected response shape")
    return data, source_record(
        "NCBI Knowledge Graph",
        url,
        "POST",
        payload,
        {
            "count": data.get("count"),
            "truncated": data.get("truncated"),
            "execution_time_ms": data.get("execution_time_ms"),
        },
        transport,
    )


def nlm_search(
    query: str,
    db: str = "phenotypes",
    limit: int = 20,
    fields: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    query = query.strip()
    if not query:
        raise GraphClientError("NLM search query must not be empty")
    if db not in DEFAULT_NLM_SEARCH_FIELDS:
        raise GraphClientError(f"Unsupported NLM database: {db}")
    limit = min(max(limit, 1), 100)
    payload = {
        "search_term": query,
        "db": db,
        "search_fields": fields or DEFAULT_NLM_SEARCH_FIELDS[db],
    }
    url = f"{NLM_BASE}/arango_api/search/"
    raw, transport = request_json("POST", url, payload)
    if not isinstance(raw, list):
        raise GraphClientError("NLM search returned an unexpected response shape")
    returned = raw[:limit]
    data = {
        "query": query,
        "db": db,
        "results": [compact_nlm_node(item) for item in returned],
        "count": len(returned),
        "available_count": len(raw),
        "truncated": len(raw) > limit,
    }
    return data, source_record(
        "NLM Cell Knowledge Network",
        url,
        "POST",
        payload,
        {
            "available_count": len(raw),
            "returned_count": len(returned),
            "truncated": len(raw) > limit,
        },
        transport,
    )


def nlm_graph(
    node_ids: list[str],
    depth: int = 1,
    direction: str = "ANY",
    collections: list[str] | None = None,
    max_items: int = 100,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cleaned = list(dict.fromkeys(node_id.strip() for node_id in node_ids if node_id.strip()))
    if not cleaned:
        raise GraphClientError("At least one NLM node id is required")
    if len(cleaned) > 25:
        raise GraphClientError("NLM traversal accepts at most 25 starting nodes")
    if depth not in (1, 2):
        raise GraphClientError("NLM traversal depth must be 1 or 2")
    if direction not in ("ANY", "OUTBOUND", "INBOUND"):
        raise GraphClientError("NLM direction must be ANY, OUTBOUND, or INBOUND")
    max_items = min(max(max_items, 1), 500)
    allowed = collections or DEFAULT_COLLECTIONS
    payload = {
        "node_ids": cleaned,
        "depth": depth,
        "edge_direction": direction,
        "allowed_collections": allowed,
    }
    url = f"{NLM_BASE}/arango_api/graph/"
    raw, transport = request_json("POST", url, payload)
    if not isinstance(raw, dict):
        raise GraphClientError("NLM graph traversal returned an unexpected response shape")
    results: dict[str, Any] = {}
    total_nodes = 0
    total_links = 0
    any_truncated = False
    for node_id in cleaned:
        record = raw.get(node_id, {})
        nodes = record.get("nodes", []) if isinstance(record, dict) else []
        links = record.get("links", []) if isinstance(record, dict) else []
        if not isinstance(nodes, list) or not isinstance(links, list):
            nodes, links = [], []
        node_truncated = len(nodes) > max_items
        link_truncated = len(links) > max_items
        any_truncated = any_truncated or node_truncated or link_truncated
        compact_nodes = [compact_nlm_node(node) for node in nodes[:max_items]]
        compact_links = [compact_nlm_link(link) for link in links[:max_items]]
        total_nodes += len(nodes)
        total_links += len(links)
        results[node_id] = {
            "node_count": len(nodes),
            "link_count": len(links),
            "nodes": compact_nodes,
            "links": compact_links,
            "nodes_truncated": node_truncated,
            "links_truncated": link_truncated,
            "collection_counts": dict(sorted(Counter(node_collection(n.get("_id")) for n in compact_nodes).items())),
            "relationship_counts": dict(sorted(Counter(link.get("Label") or "unknown" for link in compact_links).items())),
        }
    data = {
        "depth": depth,
        "edge_direction": direction,
        "allowed_collections": allowed,
        "results": results,
        "truncated": any_truncated,
    }
    return data, source_record(
        "NLM Cell Knowledge Network",
        url,
        "POST",
        payload,
        {
            "start_node_count": len(cleaned),
            "total_node_count": total_nodes,
            "total_link_count": total_links,
            "locally_truncated": any_truncated,
        },
        transport,
    )


def compact_nlm_node(node: Any) -> dict[str, Any]:
    if not isinstance(node, dict):
        return {"value": node}
    compact = {key: node[key] for key in NLM_NODE_KEYS if key in node}
    return compact or node


def compact_nlm_link(link: Any) -> dict[str, Any]:
    if not isinstance(link, dict):
        return {"value": link}
    compact = {key: link[key] for key in NLM_LINK_KEYS if key in link}
    return compact or link


def node_collection(node_id: Any) -> str:
    if not isinstance(node_id, str) or "/" not in node_id:
        return "unknown"
    return node_id.split("/", 1)[0]


def normalize_gene_number(identifier: Any) -> str | None:
    if not isinstance(identifier, str):
        return None
    match = re.fullmatch(r"(?:NCBIGene:)?(\d+)", identifier.strip(), re.IGNORECASE)
    return match.group(1) if match else None


def preflight() -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}

    def run_check(key: str, operation: Any) -> None:
        try:
            data, source = operation()
            sources.append(source)
            checks[key] = {"ok": True, "data": data}
        except GraphClientError as exc:
            checks[key] = {"ok": False, "error": str(exc)}

    run_check("ncbi_health", lambda: ncbi_get("/api/neo4j/health", "NCBI Knowledge Graph"))
    run_check("ncbi_schema", lambda: ncbi_get("/api/neo4j/schema", "NCBI Knowledge Graph"))
    run_check("ncbi_stats", lambda: ncbi_get("/api/neo4j/stats", "NCBI Knowledge Graph"))

    def collections_check() -> tuple[Any, dict[str, Any]]:
        url = f"{NLM_BASE}/arango_api/collections/"
        data, transport = request_json("POST", url, {})
        if not isinstance(data, list):
            raise GraphClientError("NLM collections returned an unexpected response shape")
        return data, source_record(
            "NLM Cell Knowledge Network",
            url,
            "POST",
            {},
            {"collection_count": len(data)},
            transport,
        )

    run_check("nlm_collections", collections_check)
    ncbi_ok = all(checks[name]["ok"] for name in ("ncbi_health", "ncbi_schema", "ncbi_stats"))
    nlm_ok = checks["nlm_collections"]["ok"]
    data = {
        "answerability": "supported" if ncbi_ok and nlm_ok else "partially_supported",
        "ok": ncbi_ok and nlm_ok,
        "configured_endpoints": {"ncbi": NCBI_BASE, "nlm": NLM_BASE},
        "checks": checks,
        "coverage_gaps": [] if ncbi_ok and nlm_ok else ["One or more graph preflight checks failed."],
    }
    return envelope("preflight", data, sources)


def profile_gene(symbol_or_id: str, max_neighbors: int) -> dict[str, Any]:
    term = symbol_or_id.strip()
    gene_number = normalize_gene_number(term) or ""
    query = """
MATCH (g:Gene)
WHERE toUpper(g.symbol) = toUpper($term) OR g.id = $gene_id
OPTIONAL MATCH (g)-[r]-(n)
RETURN properties(g) AS gene,
       CASE WHEN r IS NULL THEN null WHEN startNode(r) = g THEN 'outgoing' ELSE 'incoming' END AS direction,
       type(r) AS relationship,
       labels(n) AS neighbor_labels,
       properties(n) AS neighbor
LIMIT $limit
""".strip()
    ncbi, ncbi_source = ncbi_cypher(
        query,
        {"term": term, "gene_id": f"NCBIGene:{gene_number}" if gene_number else "", "limit": max_neighbors},
        max_results=max_neighbors,
    )
    rows = ncbi["results"]
    ncbi_gene = next((row.get("gene") for row in rows if isinstance(row.get("gene"), dict)), None)
    resolved_number = normalize_gene_number(ncbi_gene.get("id")) if ncbi_gene else gene_number or None
    resolved_symbol = (ncbi_gene or {}).get("symbol") or (term if not gene_number else "")

    nlm_result, nlm_search_source = nlm_search(resolved_symbol or term, "phenotypes", limit=100)
    candidates = []
    for item in nlm_result["results"]:
        if not isinstance(item, dict) or not str(item.get("_id", "")).startswith("GS/"):
            continue
        item_number = normalize_gene_number(str(item.get("gene_id", "")))
        symbol_match = str(item.get("gene_symbol", "")).upper() == str(resolved_symbol).upper()
        id_match = bool(resolved_number and item_number == resolved_number)
        if id_match or symbol_match:
            candidates.append(item)

    nlm_data: dict[str, Any] = {
        "depth": 1,
        "edge_direction": "ANY",
        "allowed_collections": DEFAULT_COLLECTIONS,
        "results": {},
        "truncated": False,
    }
    sources = [ncbi_source, nlm_search_source]
    candidate_ids = [item["_id"] for item in candidates if item.get("_id")]
    if candidate_ids:
        nlm_data, nlm_graph_source = nlm_graph(
            candidate_ids, collections=DEFAULT_COLLECTIONS, max_items=max_neighbors
        )
        sources.append(nlm_graph_source)

    joins = []
    for item in candidates:
        item_number = normalize_gene_number(str(item.get("gene_id", "")))
        if resolved_number and item_number == resolved_number:
            joins.append(
                {
                    "left_id": (ncbi_gene or {}).get("id"),
                    "right_id": item.get("_id"),
                    "join_key": resolved_number,
                    "join_method": "exact NCBI Gene ID",
                    "join_confidence": "A",
                }
            )
        elif resolved_symbol and str(item.get("gene_symbol", "")).upper() == str(resolved_symbol).upper():
            joins.append(
                {
                    "left_id": (ncbi_gene or {}).get("id"),
                    "right_id": item.get("_id"),
                    "join_key": resolved_symbol,
                    "join_method": "exact gene symbol fallback",
                    "join_confidence": "C",
                }
            )

    gaps = []
    if not ncbi_gene:
        gaps.append(f"No NCBI Gene node resolved for {term!r}.")
    if not candidates:
        gaps.append(f"No exact NLM GS candidate resolved for {resolved_symbol or term!r}.")
    if candidates and not any(join["join_confidence"] == "A" for join in joins):
        gaps.append("NLM candidates were found, but no exact numeric NCBI Gene ID join was confirmed.")
    for node_id, record in nlm_data["results"].items():
        if record["node_count"] == 0:
            gaps.append(f"NLM search found {node_id}, but the traversable graph returned no neighborhood.")

    answerability = "supported" if ncbi_gene and any(j["join_confidence"] == "A" for j in joins) else "partially_supported"
    if not ncbi_gene and not candidates:
        answerability = "unsupported"
    data = {
        "answerability": answerability,
        "input": {"gene": term},
        "ncbi": {
            "gene": ncbi_gene,
            "relationships": [
                {
                    "direction": row.get("direction"),
                    "relationship": row.get("relationship"),
                    "neighbor_labels": row.get("neighbor_labels"),
                    "neighbor": row.get("neighbor"),
                }
                for row in rows
                if row.get("relationship")
            ],
            "count": ncbi.get("count"),
            "truncated": ncbi.get("truncated"),
        },
        "nlm": {
            "search": nlm_result,
            "exact_gene_candidates": candidates,
            "neighborhoods": nlm_data,
        },
        "joins": joins,
        "coverage_gaps": gaps,
    }
    return envelope("profile-gene", data, sources)


def resolve_disease(term: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exact_query = """
MATCH (d:Disease)
WHERE d.id = $term OR toLower(d.name) = toLower($term)
RETURN properties(d) AS disease
LIMIT 10
""".strip()
    exact, source = ncbi_cypher(exact_query, {"term": term}, max_results=10)
    candidates = [row["disease"] for row in exact["results"] if isinstance(row.get("disease"), dict)]
    sources = [source]
    if candidates:
        return candidates, sources
    contains_query = """
MATCH (d:Disease)
WHERE toLower(d.name) CONTAINS toLower($term)
RETURN properties(d) AS disease
ORDER BY size(d.name), d.name
LIMIT 10
""".strip()
    contains, contains_source = ncbi_cypher(contains_query, {"term": term}, max_results=10)
    sources.append(contains_source)
    candidates = [
        row["disease"] for row in contains["results"] if isinstance(row.get("disease"), dict)
    ]
    return candidates, sources


def contextualize_disease(term: str, max_genes: int, max_neighbors: int) -> dict[str, Any]:
    candidates, sources = resolve_disease(term)
    if len(candidates) != 1:
        answerability = "unsupported" if not candidates else "ambiguous"
        data = {
            "answerability": answerability,
            "input": {"disease": term},
            "resolution_candidates": candidates,
            "genes": [],
            "coverage_gaps": [
                "No disease resolved in the NCBI graph."
                if not candidates
                else "Multiple disease candidates resolved; rerun with a stable identifier."
            ],
        }
        return envelope("contextualize-disease", data, sources)

    disease = candidates[0]
    disease_id = disease.get("id")
    gene_query = """
MATCH (g:Gene)-[:GENE_ASSOCIATED_WITH_CONDITION]->(d:Disease {id: $disease_id})
RETURN properties(g) AS gene, 'direct_association' AS evidence_type, null AS variant
UNION ALL
MATCH (g:Gene)<-[:IS_SEQUENCE_VARIANT_OF]-(v:SequenceVariant)-[:CAUSES]->(d:Disease {id: $disease_id})
RETURN properties(g) AS gene, 'variant_mediated' AS evidence_type, properties(v) AS variant
""".strip()
    evidence, evidence_source = ncbi_cypher(
        gene_query,
        {"disease_id": disease_id},
        max_results=min(max(max_genes * 25, 100), 1000),
    )
    sources.append(evidence_source)

    aggregated: dict[str, dict[str, Any]] = {}
    for row in evidence["results"]:
        gene = row.get("gene")
        if not isinstance(gene, dict) or not gene.get("id"):
            continue
        record = aggregated.setdefault(
            gene["id"],
            {"ncbi_gene": gene, "evidence_types": set(), "variants": []},
        )
        if row.get("evidence_type"):
            record["evidence_types"].add(row["evidence_type"])
        if isinstance(row.get("variant"), dict):
            record["variants"].append(row["variant"])

    ordered = sorted(
        aggregated.values(),
        key=lambda item: (
            "direct_association" not in item["evidence_types"],
            str(item["ncbi_gene"].get("symbol", "")),
        ),
    )
    total_gene_count = len(ordered)
    selected = ordered[:max_genes]
    node_ids = [
        f"GS/{item['ncbi_gene'].get('symbol')}"
        for item in selected
        if item["ncbi_gene"].get("symbol")
    ]

    nlm_data: dict[str, Any] = {
        "depth": 1,
        "edge_direction": "ANY",
        "allowed_collections": DEFAULT_COLLECTIONS,
        "results": {},
        "truncated": False,
    }
    if node_ids:
        nlm_data, nlm_source = nlm_graph(
            node_ids, collections=DEFAULT_COLLECTIONS, max_items=max_neighbors
        )
        sources.append(nlm_source)

    output_genes = []
    matched_count = 0
    for item in selected:
        gene = item["ncbi_gene"]
        symbol = gene.get("symbol")
        node_id = f"GS/{symbol}" if symbol else None
        neighborhood = nlm_data["results"].get(node_id, {}) if node_id else {}
        main_node = next(
            (
                node
                for node in neighborhood.get("nodes", [])
                if node.get("_id") == node_id
            ),
            None,
        )
        ncbi_number = normalize_gene_number(gene.get("id"))
        nlm_number = normalize_gene_number(str((main_node or {}).get("gene_id", "")))
        join = None
        if main_node and ncbi_number and nlm_number == ncbi_number:
            join = {
                "left_id": gene.get("id"),
                "right_id": node_id,
                "join_key": ncbi_number,
                "join_method": "exact NCBI Gene ID",
                "join_confidence": "A",
            }
            matched_count += 1
        elif main_node and symbol:
            join = {
                "left_id": gene.get("id"),
                "right_id": node_id,
                "join_key": symbol,
                "join_method": "exact gene symbol fallback",
                "join_confidence": "C",
            }
        output_genes.append(
            {
                "ncbi_gene": gene,
                "evidence_types": sorted(item["evidence_types"]),
                "variants": item["variants"],
                "nlm_query_id": node_id,
                "nlm_found": bool(main_node),
                "nlm_node": main_node,
                "nlm_node_count": neighborhood.get("node_count", 0),
                "nlm_link_count": neighborhood.get("link_count", 0),
                "nlm_collection_counts": neighborhood.get("collection_counts", {}),
                "nlm_relationship_counts": neighborhood.get("relationship_counts", {}),
                "nlm_nodes": neighborhood.get("nodes", []),
                "nlm_links": neighborhood.get("links", []),
                "join": join,
            }
        )

    gaps = []
    if not output_genes:
        gaps.append("The resolved disease has no direct or variant-mediated gene rows in the NCBI graph.")
    if total_gene_count > max_genes:
        gaps.append(f"Gene context was limited to {max_genes} of {total_gene_count} NCBI genes.")
    unmatched = len(output_genes) - matched_count
    if unmatched:
        gaps.append(f"{unmatched} selected NCBI genes lacked a confidence-A traversable NLM join.")
    if nlm_data.get("truncated"):
        gaps.append("One or more NLM neighborhoods were locally truncated.")

    if not output_genes:
        answerability = "unsupported"
    elif matched_count == len(output_genes):
        answerability = "supported"
    else:
        answerability = "partially_supported"
    data = {
        "answerability": answerability,
        "input": {"disease": term, "max_genes": max_genes},
        "resolved_disease": disease,
        "total_ncbi_gene_count": total_gene_count,
        "returned_gene_count": len(output_genes),
        "exact_nlm_join_count": matched_count,
        "genes": output_genes,
        "coverage_gaps": gaps,
    }
    return envelope("contextualize-disease", data, sources)


def parse_json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise GraphClientError(f"Invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise GraphClientError("Expected a JSON object")
    return parsed


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def write_result(result: dict[str, Any], output: str | None, compact: bool) -> None:
    text = json.dumps(result, indent=None if compact else 2, sort_keys=False)
    if output:
        Path(output).write_text(text + "\n")
        print(output)
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only NCBI KG and NLM-CKN query client with provenance."
    )
    parser.add_argument("--output", help="Write JSON to this path instead of stdout.")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("preflight", help="Check both graph services and inspect live schema.")

    subparsers.add_parser("ncbi-schema", help="Return the live NCBI graph schema.")
    subparsers.add_parser("ncbi-stats", help="Return live NCBI graph statistics.")

    cypher_parser = subparsers.add_parser("ncbi-cypher", help="Run bounded read-only Cypher.")
    group = cypher_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--query")
    group.add_argument("--query-file")
    cypher_parser.add_argument("--parameters", default="{}", help="JSON object.")
    cypher_parser.add_argument("--max-results", type=int, default=200)
    cypher_parser.add_argument("--timeout", type=int, default=30)

    search_parser = subparsers.add_parser("nlm-search", help="Search NLM-CKN.")
    search_parser.add_argument("query")
    search_parser.add_argument("--db", choices=["phenotypes", "ontologies"], default="phenotypes")
    search_parser.add_argument("--limit", type=int, default=20)
    search_parser.add_argument("--fields", help="Comma-separated search fields.")

    neighbors_parser = subparsers.add_parser("nlm-neighbors", help="Traverse NLM-CKN.")
    neighbors_parser.add_argument("node_ids", nargs="+")
    neighbors_parser.add_argument("--depth", type=int, choices=[1, 2], default=1)
    neighbors_parser.add_argument(
        "--direction", choices=["ANY", "OUTBOUND", "INBOUND"], default="ANY"
    )
    neighbors_parser.add_argument(
        "--collections", default=",".join(DEFAULT_COLLECTIONS)
    )
    neighbors_parser.add_argument("--max-items", type=int, default=100)

    profile_parser = subparsers.add_parser(
        "profile-gene", help="Profile one gene across NCBI KG and NLM-CKN."
    )
    profile_parser.add_argument("gene")
    profile_parser.add_argument("--max-neighbors", type=int, default=100)

    disease_parser = subparsers.add_parser(
        "contextualize-disease",
        help="Find NCBI disease-associated genes and add NLM context.",
    )
    disease_parser.add_argument("disease")
    disease_parser.add_argument("--max-genes", type=int, default=12)
    disease_parser.add_argument("--max-neighbors", type=int, default=75)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight()
        elif args.command == "ncbi-schema":
            data, source = ncbi_get("/api/neo4j/schema", "NCBI Knowledge Graph")
            result = envelope(
                "ncbi-schema",
                {"answerability": "supported", "schema": data, "coverage_gaps": []},
                [source],
            )
        elif args.command == "ncbi-stats":
            data, source = ncbi_get("/api/neo4j/stats", "NCBI Knowledge Graph")
            result = envelope(
                "ncbi-stats",
                {"answerability": "supported", "stats": data, "coverage_gaps": []},
                [source],
            )
        elif args.command == "ncbi-cypher":
            query = args.query or Path(args.query_file).read_text()
            parameters = parse_json_object(args.parameters)
            data, source = ncbi_cypher(
                query, parameters, args.max_results, args.timeout
            )
            result = envelope(
                "ncbi-cypher",
                {
                    "answerability": "supported",
                    "result": data,
                    "coverage_gaps": ["The result was truncated."]
                    if data.get("truncated")
                    else [],
                },
                [source],
            )
        elif args.command == "nlm-search":
            fields = split_csv(args.fields) if args.fields else None
            data, source = nlm_search(args.query, args.db, args.limit, fields)
            result = envelope(
                "nlm-search",
                {
                    "answerability": "supported" if data["count"] else "unsupported",
                    "result": data,
                    "coverage_gaps": ["No matching NLM records were returned."]
                    if not data["count"]
                    else [],
                },
                [source],
            )
        elif args.command == "nlm-neighbors":
            data, source = nlm_graph(
                args.node_ids,
                args.depth,
                args.direction,
                split_csv(args.collections),
                args.max_items,
            )
            found = sum(record["node_count"] for record in data["results"].values())
            result = envelope(
                "nlm-neighbors",
                {
                    "answerability": "supported" if found else "unsupported",
                    "result": data,
                    "coverage_gaps": ["No traversable NLM neighborhood was returned."]
                    if not found
                    else [],
                },
                [source],
            )
        elif args.command == "profile-gene":
            result = profile_gene(args.gene, min(max(args.max_neighbors, 1), 500))
        elif args.command == "contextualize-disease":
            result = contextualize_disease(
                args.disease,
                min(max(args.max_genes, 1), 25),
                min(max(args.max_neighbors, 1), 500),
            )
        else:
            raise GraphClientError(f"Unsupported command: {args.command}")
        write_result(result, args.output, args.compact)
        return 0
    except (GraphClientError, OSError) as exc:
        error = {
            "schema_version": "0.1.0",
            "generated_at": utc_now(),
            "command": getattr(args, "command", None),
            "error": str(exc),
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
