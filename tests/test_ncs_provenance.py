"""Tests for evidence-calibrated NCS AI provenance graphs."""
import copy
import pytest
from ncs_harness.provenance import build_provenance_graph, provenance_evidence_summary, verify_provenance_graph

D, E, F = "a" * 64, "b" * 64, "c" * 64

def nodes():
    return [
        {"node_id": "model", "node_type": "model_artifact", "content_digest": D},
        {"node_id": "source", "node_type": "source_document", "content_digest": E},
        {"node_id": "output", "node_type": "output", "content_digest": F},
        {"node_id": "run", "node_type": "inference_run", "content_digest": D},
    ]

def ref():
    return [{"kind": "fixture-evidence", "sha256": E, "uri": "evidence://fixture/one"}]

def graph_with(edge):
    return build_provenance_graph(model_artifact_digest=D, output_digest=F,
        inference_run_id="run-001", nodes=nodes(), edges=[edge])

def test_similarity_is_not_causal_influence():
    graph = graph_with({"edge_id": "sim", "source_node_id": "source", "target_node_id": "output",
        "relation": "similarity_candidate", "claim_state": "tested",
        "method": "embedding-nearest-neighbour", "evidence_refs": ref()})
    summary = provenance_evidence_summary(graph)
    assert summary["similarity_candidate_edges"] == 1
    assert summary["causal_influence_edges"] == 0

def test_measured_influence_requires_reproducible_experiment():
    graph = graph_with({"edge_id": "inf", "source_node_id": "source", "target_node_id": "output",
        "relation": "measured_influence", "claim_state": "tested", "evidence_refs": ref(),
        "experiment": {"method": "ablation", "metric": "held-out-task-score-delta",
            "baseline_output_digest": D, "perturbed_output_digest": E,
            "benchmark_digest": F, "repetitions": 3,
            "uncertainty_interval": {"lower": -0.1, "upper": 0.2}}})
    assert provenance_evidence_summary(graph)["causal_influence_edges"] == 1

def test_measured_influence_without_experiment_is_rejected():
    with pytest.raises(ValueError, match="controlled experiment"):
        graph_with({"edge_id": "inf", "source_node_id": "source", "target_node_id": "output",
            "relation": "measured_influence", "claim_state": "tested", "evidence_refs": ref()})

def test_influence_requires_multiple_repetitions():
    with pytest.raises(ValueError, match="two repetitions"):
        graph_with({"edge_id": "inf", "source_node_id": "source", "target_node_id": "output",
            "relation": "measured_influence", "claim_state": "tested", "evidence_refs": ref(),
            "experiment": {"method": "trak", "metric": "loss-change",
                "baseline_output_digest": D, "perturbed_output_digest": E,
                "benchmark_digest": F, "repetitions": 1,
                "uncertainty_interval": {"lower": 0.0, "upper": 0.1}}})

def test_unknown_is_explicit():
    summary = provenance_evidence_summary(graph_with({"edge_id": "unknown", "source_node_id": "source",
        "target_node_id": "output", "relation": "unverified_or_unknown", "claim_state": "unknown",
        "evidence_refs": ref(), "limitations": ["training corpus unavailable"]}))
    assert summary["unknown_edges"] == 1
    assert summary["evidence_status"] == "bounded-evidence-map"

def test_graph_digest_detects_tampering():
    graph = graph_with({"edge_id": "decl", "source_node_id": "source", "target_node_id": "model",
        "relation": "declared_training_source", "claim_state": "asserted", "evidence_refs": ref()})
    assert verify_provenance_graph(graph) == (True, "valid")
    altered = copy.deepcopy(graph)
    altered["edges"][0]["claim_state"] = "tested"
    assert verify_provenance_graph(altered) == (False, "graph_digest_mismatch")

def test_unknown_node_is_rejected():
    with pytest.raises(ValueError, match="unknown node"):
        graph_with({"edge_id": "bad", "source_node_id": "missing", "target_node_id": "output",
            "relation": "declared_training_source", "evidence_refs": ref()})

def test_report_never_claims_grade_eligibility():
    summary = provenance_evidence_summary(graph_with({"edge_id": "ret", "source_node_id": "source",
        "target_node_id": "output", "relation": "retrieved_at_inference", "claim_state": "observed",
        "evidence_refs": ref()}))
    assert summary["grade_eligible"] is False

def test_root_artifact_and_output_digests_must_match_graph_nodes():
    altered_nodes = nodes()
    altered_nodes[0]["content_digest"] = E
    with pytest.raises(ValueError, match="model_artifact node bound"):
        build_provenance_graph(model_artifact_digest=D, output_digest=F,
            inference_run_id="run-001", nodes=altered_nodes, edges=[])
