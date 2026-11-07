"""Evidence-calibrated AI provenance graph (experimental v0.1).

Separates declared lineage, runtime execution lineage, support/quotation,
similarity candidates, and experimentally measured influence. Similarity is
never converted into causation or a universal contribution percentage.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any

HEX64 = set("0123456789abcdef")
RELATIONS = {"declared_training_source", "retrieved_at_inference", "quoted_or_supported_span", "similarity_candidate", "measured_influence", "unverified_or_unknown"}
NODE_TYPES = {"model_artifact", "training_dataset", "dataset_record", "inference_run", "prompt_template", "retrieval_corpus", "retrieved_chunk", "tool", "output", "source_document", "claim_span", "evaluation"}
CLAIM_STATES = {"asserted", "observed", "tested", "unknown"}
INFLUENCE_METHODS = {"trak", "tracin", "influence_functions", "data_shapley", "ablation"}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in HEX64 for c in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _evidence_refs(refs: Any) -> list[dict[str, Any]]:
    if not isinstance(refs, list) or not refs:
        raise ValueError("each provenance edge requires at least one evidence reference")
    normalized = []
    for ref in refs:
        if not isinstance(ref, dict):
            raise ValueError("evidence reference must be an object")
        normalized.append({
            "kind": _nonempty(ref.get("kind"), "evidence.kind"),
            "sha256": _digest(ref.get("sha256"), "evidence.sha256"),
            "uri": _nonempty(ref.get("uri"), "evidence.uri"),
        })
    return normalized


def build_provenance_graph(*, model_artifact_digest: str, output_digest: str,
                           inference_run_id: str, nodes: list[dict[str, Any]],
                           edges: list[dict[str, Any]], corpus_digest: str | None = None) -> dict[str, Any]:
    """Build a deterministic graph. Edges are claims, not ground truth."""
    _digest(model_artifact_digest, "model_artifact_digest")
    _digest(output_digest, "output_digest")
    _nonempty(inference_run_id, "inference_run_id")
    if corpus_digest is not None:
        _digest(corpus_digest, "corpus_digest")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("nodes and edges must be lists")

    normalized_nodes = []
    by_id = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("node must be an object")
        node_id = _nonempty(node.get("node_id"), "node.node_id")
        if node.get("node_type") not in NODE_TYPES:
            raise ValueError("unsupported provenance node_type")
        if node_id in by_id:
            raise ValueError("duplicate provenance node_id")
        item = {"node_id": node_id, "node_type": node["node_type"],
                "content_digest": _digest(node.get("content_digest"), "node.content_digest"),
                "label": node.get("label")}
        by_id[node_id] = item
        normalized_nodes.append(item)

    normalized_edges = []
    seen = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("edge must be an object")
        edge_id = _nonempty(edge.get("edge_id"), "edge.edge_id")
        if edge_id in seen:
            raise ValueError("duplicate provenance edge_id")
        seen.add(edge_id)
        relation = edge.get("relation")
        if relation not in RELATIONS:
            raise ValueError("unsupported provenance relation")
        source_id = _nonempty(edge.get("source_node_id"), "edge.source_node_id")
        target_id = _nonempty(edge.get("target_node_id"), "edge.target_node_id")
        if source_id not in by_id or target_id not in by_id:
            raise ValueError("provenance edge references an unknown node")
        state = edge.get("claim_state", "asserted")
        if state not in CLAIM_STATES:
            raise ValueError("unsupported claim_state")
        item = {"edge_id": edge_id, "source_node_id": source_id,
                "target_node_id": target_id, "relation": relation,
                "claim_state": state, "method": edge.get("method"),
                "evidence_refs": _evidence_refs(edge.get("evidence_refs")),
                "limitations": list(edge.get("limitations") or [])}
        if relation == "measured_influence":
            experiment = edge.get("experiment")
            if not isinstance(experiment, dict):
                raise ValueError("measured_influence requires a controlled experiment record")
            method = experiment.get("method")
            if method not in INFLUENCE_METHODS:
                raise ValueError("measured_influence requires a recognized attribution method")
            _digest(experiment.get("baseline_output_digest"), "experiment.baseline_output_digest")
            _digest(experiment.get("perturbed_output_digest"), "experiment.perturbed_output_digest")
            _digest(experiment.get("benchmark_digest"), "experiment.benchmark_digest")
            metric = _nonempty(experiment.get("metric"), "experiment.metric")
            repetitions = experiment.get("repetitions")
            if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 2:
                raise ValueError("measured_influence requires at least two repetitions")
            interval = experiment.get("uncertainty_interval")
            if not isinstance(interval, dict):
                raise ValueError("measured_influence requires an uncertainty_interval")
            lower, upper = interval.get("lower"), interval.get("upper")
            if not isinstance(lower, (int, float)) or not isinstance(upper, (int, float)) or lower > upper:
                raise ValueError("invalid uncertainty_interval")
            item["experiment"] = {"method": method, "metric": metric,
                "baseline_output_digest": experiment["baseline_output_digest"],
                "perturbed_output_digest": experiment["perturbed_output_digest"],
                "benchmark_digest": experiment["benchmark_digest"],
                "repetitions": repetitions, "uncertainty_interval": {"lower": lower, "upper": upper}}
            item["method"] = method
            if state != "tested":
                raise ValueError("measured_influence must have claim_state='tested'")
        elif edge.get("experiment") is not None:
            raise ValueError("experiment details are only valid for measured_influence")
        if relation == "unverified_or_unknown" and state != "unknown":
            raise ValueError("unverified_or_unknown edges must have claim_state='unknown'")
        if relation == "retrieved_at_inference" and state not in {"observed", "tested"}:
            raise ValueError("retrieved_at_inference must be observed or tested")
        normalized_edges.append(item)

    graph = {"schema": "ncs-ai-provenance-graph/0.1",
        "model_artifact_digest": model_artifact_digest, "output_digest": output_digest,
        "inference_run_id": inference_run_id, "corpus_digest": corpus_digest,
        "nodes": sorted(normalized_nodes, key=lambda x: x["node_id"]),
        "edges": sorted(normalized_edges, key=lambda x: x["edge_id"]),
        "interpretation": {"similarity_is_not_causation": True,
            "declared_lineage_is_not_independently_verified": True,
            "unknown_must_not_be_inferred_as_absence": True,
            "universal_contribution_percentage_emitted": False},
        "grade_eligible": False}
    graph["graph_digest"] = sha256_json(graph)
    return graph


def verify_provenance_graph(graph: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(graph, dict) or graph.get("schema") != "ncs-ai-provenance-graph/0.1":
        return False, "unsupported_graph_schema"
    unsigned = dict(graph)
    supplied = unsigned.pop("graph_digest", None)
    if supplied != sha256_json(unsigned):
        return False, "graph_digest_mismatch"
    if graph.get("grade_eligible") is not False:
        return False, "invalid_grade_eligibility"
    flags = graph.get("interpretation") or {}
    if not (flags.get("similarity_is_not_causation") is True
            and flags.get("declared_lineage_is_not_independently_verified") is True
            and flags.get("unknown_must_not_be_inferred_as_absence") is True
            and flags.get("universal_contribution_percentage_emitted") is False):
        return False, "provenance_claim_boundary_missing"
    return True, "valid"


def provenance_evidence_summary(graph: dict[str, Any]) -> dict[str, Any]:
    valid, reason = verify_provenance_graph(graph)
    if not valid:
        raise ValueError(f"provenance graph verification failed: {reason}")
    counts = {relation: 0 for relation in sorted(RELATIONS)}
    states = {state: 0 for state in sorted(CLAIM_STATES)}
    for edge in graph["edges"]:
        counts[edge["relation"]] += 1
        states[edge["claim_state"]] += 1
    return {"schema": "ncs-ai-provenance-summary/0.1",
        "graph_digest": graph["graph_digest"], "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]), "relation_counts": counts,
        "claim_state_counts": states, "causal_influence_edges": counts["measured_influence"],
        "similarity_candidate_edges": counts["similarity_candidate"],
        "unknown_edges": counts["unverified_or_unknown"],
        "evidence_status": "bounded-evidence-map", "grade_eligible": False,
        "limitations": [
            "A valid graph digest proves record integrity, not truth or completeness.",
            "Declared lineage records an assertion, not independent provider verification.",
            "Similarity candidates are not evidence of causal training influence.",
            "Measured influence is specific to its model, corpus, target, method, benchmark and uncertainty.",
            "Absence of a recorded source is not proof that the source had no influence."]}
