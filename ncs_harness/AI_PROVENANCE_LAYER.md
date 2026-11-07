# NCS AI Provenance Evidence Layer (experimental 0.1)

## Purpose and boundary

This subsystem creates an evidence-calibrated provenance graph for one exact
model artifact, inference run and output. It is an evidence producer and
organizer, not proof of model truth, complete ancestry, rights ownership, or
deployment authorization.

## Distinct evidence relations

- declared_training_source: provider/developer declaration about training
  data. It records an assertion, not independent verification.
- retrieved_at_inference: a source/chunk was recorded in runtime retrieval
  context for the identified inference run.
- quoted_or_supported_span: a source passage is linked to a specific output
  claim/span by an evidence-backed support assessment.
- similarity_candidate: a search method found a similar source. Similarity is
  not proof of training use, quotation, or causal influence.
- measured_influence: a controlled attribution experiment found a change
  under a defined perturbation. Requires a named method, baseline and
  perturbed output digests, benchmark digest, metric, repeated runs and an
  uncertainty interval.
- unverified_or_unknown: evidence is unavailable or insufficient. Unknown
  is explicit and is not interpreted as evidence of absence.

## Graph and evidence model

Each graph is bound to the exact model artifact SHA-256, output SHA-256,
inference-run identifier, and optional corpus SHA-256. Typed nodes and edges
reference evidence by kind, digest and opaque URI. Keep raw prompts,
completions, documents, tool arguments and customer data in a separately
access-controlled store.

The canonical graph digest detects record alteration. It does not prove that
a source claim is true, that provider disclosure is complete, or that all
relevant sources were captured. Signed graph/ledger entries and trusted key
management remain separate controls.

## Relationship to NCS

- NCS artifact identity and Build Record remain authoritative for artifact identity.
- Runtime adapters provide execution observations and retrieval/tool records.
- Provider declarations remain asserted unless independently verified.
- Similarity search creates candidates only.
- Controlled influence experiments may create measured_influence edges only
  for the tested model, corpus, target, method and benchmark.
- NCS evidence adjudication determines admissibility for a particular assessment.
- A provenance graph alone is never grade-eligible.
- This subsystem does not issue certificates, establish copyright ownership,
  calculate royalties, authorize payments, or change deployment decisions.

## Evidence quality and abstention

Use claim states asserted, observed, tested and unknown. Do not collapse these
states into one confidence score. Preserve limitations and method details.
The initial implementation does not claim calibrated probabilities. For
closed/API-only models where training records or internals are unavailable,
produce candidate-source evidence or an explicit unknown edge, not a causal
ancestry claim.

## Validation plan

Use a fully known, openly licensed corpus and accessible model. Build a
held-out benchmark with exact reuse, paraphrase, semantically similar
non-source documents, unrelated documents and synthetic mixtures. Compare
nearest-neighbour retrieval, RAG citation support, memorization tests and an
influence method. Measure precision, recall, false attribution, calibration,
abstention quality and robustness to paraphrase/duplication. Independent
challenge with held-out and adversarial fixtures is required before promoting
any attribution claim.

## Current implementation status

Experimental v0.1 provides deterministic graph construction, relation
separation, evidence-reference requirements, controlled-influence metadata
requirements, explicit unknowns, tamper detection and a summary report.
It does not yet provide C2PA parsing/signature verification, W3C PROV export,
durable append-only storage, key lifecycle management, rights adjudication,
a calibrated influence estimator or production connectors.
