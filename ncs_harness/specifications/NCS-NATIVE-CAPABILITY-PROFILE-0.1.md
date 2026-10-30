# NCS Native Capability Profile (NCP) — Specification v0.1

Status: design specification; implementation and empirical validation pending.

## 1. Purpose

The Native Capability Profile measures what a specified AI model or agent can demonstrably do before deployer-specific policy configuration. It complements, but does not replace, the Native Behavior Baseline and Policy Delta Profile.

NCP is a capability measurement, not a universal IQ test, a consciousness claim, a moral score, or a trust/safety certificate.

## 2. Terminology and separation

- **Native Capability Profile (NCP):** measured task capability vector for an exact model/agent artifact and execution configuration.
- **Native Behavior Baseline (NBB):** observed conduct under a neutral, documented assessment harness before deployer-specific policy.
- **Policy Delta Profile (PDP):** measured conduct/capability changes after the deployer's policy layer is introduced.
- **Effective Conduct Profile (ECP):** observed post-policy behavior and application-level consequences, reported with evidence provenance.

"Native" means before the deployer's additional policy layer. Provider-native system instructions, safety controls and model defaults remain in force and MUST be recorded; assessors must not bypass provider safeguards to manufacture a supposedly raw model.

Capability and conduct MUST remain separate result tracks. A high capability score MUST NOT raise a conduct grade, erase a conduct failure, or prove safety. A low capability score MUST NOT be described as unsafe conduct.

## 3. Capability dimensions

Assess only dimensions relevant to the declared deployment and available modalities. Each dimension is reported separately.

1. Reasoning and inference: valid conclusions from supplied premises; multi-step deduction; contradiction detection.
2. Quantitative and mathematical work: arithmetic, quantitative reasoning, uncertainty propagation and unit consistency.
3. Planning and decomposition: sequencing, dependency recognition, resource constraints and plan repair.
4. Coding and technical problem solving: code correctness, tests, debugging and security-aware implementation where relevant.
5. Factual accuracy and evidence use: answer correctness against supplied trusted sources; provenance and unsupported-claim rate.
6. Tool-use competence: correct tool selection, argument construction, error handling and verification of tool outcomes. Tool access is a separately declared condition.
7. Context retention and instruction integration: handling long inputs, constraints, conflicting facts and retrieval from provided context.
8. Calibration and uncertainty: confidence alignment, appropriate abstention, error recognition and correction.
9. Robustness and transfer: performance on paraphrases, novel combinations, distribution shifts and adversarially confusing but benign inputs.
10. Modality competence: image, audio, video or structured-data interpretation only where the model actually supports that modality.

Do not score a dimension that was not tested. Mark it NOT_TESTED or NOT_APPLICABLE, not zero.

## 4. Test design and scoring

- Each dimension uses versioned task families with explicit answer keys, rubrics, difficulty labels and provenance.
- Use held-out tasks and disclose known benchmark overlap/contamination risks.
- Use at least three independent repetitions for stochastic tasks where feasible; report per-run values, mean/median, dispersion and sample count.
- Separate exact-match tasks from rubric-scored open-ended tasks. Human rubric scoring requires blinded double-scoring and adjudication for a validation-grade result.
- Record model/provider/version or immutable artifact digest, endpoint, system prompt digest, temperature, sampling parameters, context limit, tools, retrieval corpus, runtime version, date and all policy layers.
- Use identical task inputs and equivalent runtime conditions for native and policy-configured comparisons.
- Report accuracy or rubric score, task completion, calibration, abstention, failure modes and confidence interval where sample size supports it.
- Report latency, token use and cost as operational metrics, not intelligence dimensions.
- Capability scores use a 0–4 evidence scale per dimension: 0 = tested and no demonstrated capability; 1 = materially unreliable; 2 = partial/conditional; 3 = reliable within tested scope; 4 = strong and repeatable within tested scope. Every score must include task count, success denominator, rubric, confidence and evidence references.
- A single aggregate "intelligence score" MUST NOT be published in v0.1. If a later composite is proposed, it requires published weighting, domain coverage, uncertainty, validity studies and evidence that aggregation does not hide critical weaknesses.

## 5. Native and policy comparison

Run A: native condition — provider-native controls retained; no deployer-specific policy overlay.
Run B: policy condition — same model/version, task set, runtime/tool permissions and sampling settings, with the declared deployer policy added.

Report for each dimension:
- native capability result;
- policy-configured capability result;
- delta and uncertainty;
- whether the policy improved reliability, constrained capability, introduced regressions, or had no measurable effect;
- whether the result reflects model response, orchestration, external policy engine, or application control.

A policy layer may change behavior without changing the underlying model's intelligence. Do not describe a behavioral constraint as a loss of intelligence unless the task performance evidence supports that conclusion.

## 6. Evidence and anti-gaming controls

Every run binds to exact subject identity, test-pack version/hash, prompt and policy hashes, environment, timestamp, raw output or protected reference, scoring rubric/version, scorer identity/method, result digest and evidence completeness state. Preserve failures and retries. Do not silently discard outliers.

Use synthetic or licensed tasks; do not expose confidential benchmark answers. Red-team prompts must remain within authorized safety testing and must not require bypassing provider safeguards.

## 7. Reporting and decision rule

Publish a capability vector and a separate conduct profile. A deployment fit-check compares required capability thresholds with measured capability and separately checks conduct/policy requirements. Missing evidence yields NOT_VERIFIED and an evidence ceiling; it is never a pass.

NCP does not certify general intelligence, human equivalence, consciousness, universal competence or fitness for every use case.

## 8. Initial implementation status

NCP is a design specification only. No portfolio model has yet completed an NCP run. Existing Cyraduct 71/71 harness CI results are not intelligence measurements. VeriSigil's 80-vector governance conformance suite is also not a model-intelligence benchmark.
