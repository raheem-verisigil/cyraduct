# NCS Capability-Lite Predictor Profile — v0.3 companion

Status: experimental predictor specification. It is not a general intelligence benchmark and is not part of the grading path.

## Purpose and boundary

NCS's differentiator is measured conduct under declared policy and evidence-backed policy fit. NCS MUST NOT build a broad, competing general-capability leaderboard. Public, independently maintained benchmark results may be cited as context for reasoning, mathematics and coding, with benchmark name, version, date, model identity and comparability limitations disclosed.

NCS records only four optional capability-lite features that plausibly predict policy execution failures:
1. Tool use: correct tool selection, argument validity, permission-boundary handling and verification of tool outcomes.
2. Context and instruction retention: retention of declared constraints, authority and task state across relevant context.
3. Calibration and abstention: calibrated uncertainty, appropriate abstention and correction when evidence is missing.
4. Robustness: consistency under benign paraphrase, context changes and novel combinations relevant to the declared policy.

These are predictors, not a general measure of intelligence. Each feature is optional. Untested features are NOT_TESTED, never zero.

## Unified NCS vocabulary

- NBB — Native Behavior Baseline: observed conduct before deployer-specific policy.
- PDP — Policy Delta Profile (Conduct Delta): paired changes between NBB and the same subject under the declared policy. It is a delta, not an absolute post-policy grade.
- ECP — Effective Conduct Profile: observed policy-configured conduct and effect-level outcomes, including application/sink evidence where available.
- Experiment Record: signed, aggregate-only record linking model configuration, profile features, policy/control features, attempt-level and effect-level outcomes, uncertainty, suite context and evidence-manifest provenance.

NCP/NBB/PDP/ECP must not be used as competing vocabularies. Capability-lite predictor features supplement the Experiment Record and do not replace the three conduct/effect profiles.

## Measurement and reporting

Store successes and trials for every feature. Report the observed rate and a 95% Wilson interval; publish raw numerator and denominator. Do not use a coarse 0–4 score as the underlying measure. Display bands, if ever needed, are presentation-only and must not replace rates or intervals.

The Experiment Record stores aggregates and hashes, never prompts, model outputs, training data or model weights. Exact prompts and outputs, where required for audit, remain in protected evidence storage and are referenced by access-controlled identifiers and hashes.

## Learner principle and scope

The learner proposes, rules decide, and evidence confirms.

The Assessment Learner is offline and advisory only. It may predict likely rule failures, recommend which tests to run next, summarize historical policy/control effects, predict likely change impact, and research threshold calibration only after suitable deployment outcome data exists.

The learner MUST NOT issue, modify, raise, lower or override a grade, certificate, policy-fit decision or deployment authorization. The deterministic grading engine MUST NOT import or call the learner.

Start with a small, interpretable regularized logistic regression. A model artifact must carry its feature definition, training-record hashes, code/version identity, validation report and limitations. The learner abstains for unfamiliar/out-of-distribution subjects.

## Pre-registered experiment checks

- H1/E1: compare the profile-feature predictor with model-size and public leaderboard-rank baselines using temporal holdout and leave-one-model-family-out evaluation. Initial research target: AUC improvement of at least 0.05 over the stronger baseline; report confidence intervals and Brier score.
- E2: assess probability calibration. The proposed calibration-slope interval 0.8–1.2 is provisional, not a validated universal acceptance threshold.
- E3: evaluate adaptive test selection by replaying completed runs. Target: at least 95% agreement with full-run pass/fail classifications with at least 30% fewer tests. Preserve a random-coverage fraction initially set at 20%.
- E4: compare profile-only prediction with profile-plus-capability-lite features. Retain capability-lite only if it improves held-out predictive performance; otherwise remove it.

Freeze thresholds, splits and exclusions before Phase D. Leave-one-family-out and temporal validation are both required; no random row split that leaks the same model configurations across train and test.

## Cold start, privacy and release gate

Record Experiment Records from the first run, but show no learner predictions to users until there are at least 15 distinct model configurations across at least four model families AND temporal validation passes. This is a minimum release gate, not proof of statistical adequacy; sample size and uncertainty remain visible.

Records remain local by default. Aggregate sharing is opt-in and anonymized. No prompts, outputs, raw datasets, weights, secrets or direct identifiers may be shared through the aggregate path. Secure aggregation/differential privacy are future research requirements before pooling sensitive cross-customer records.

## Independence and status

The standard and its authoritative registry must live in a dedicated NCS repository, separate from Cyraduct and VeriSigilAI product repositories. Until that repository is provisioned, this is a temporary engineering branch in Cyraduct and MUST NOT be represented as independent governance.

The learner is an experimental research component. No portfolio dataset currently establishes predictive validity. No NCS grade is issued by this component.
