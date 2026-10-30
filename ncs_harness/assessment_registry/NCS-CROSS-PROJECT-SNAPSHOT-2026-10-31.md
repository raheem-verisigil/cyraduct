# NCS Cross-Project Assessment Snapshot — 2026-10-31

**Status:** Evidence snapshot from GitHub CI and source review. Not an independent certification.  
**Assessment scope:** NCS harness, Cyraduct Finance Guard test suite, and VeriSigilAI/VCB repository evidence.

## 1. NCS harness

- Repository: raheem-verisigil/cyraduct
- Pull request: #29, NCS Governance Operations and Policy Evidence Foundation
- Source branch: ncs/experiment-runner-v0.1
- Source commit: e162a3a67f791a1980873304588e898231e1d1a3
- CI merge commit: 1eb6bd23b35df963450e6627fb3300f46e3cd60d
- Workflow: NCS Finance Guard Harness
- Run: 41143920091 (run #226)
- Result: PASS — 93 passed, 0 failed, 4 warnings, 1.03 seconds.
- Scope: the NCS-selected synthetic harness tests listed in the workflow.
- Limitations: this is not a complete Cyraduct product suite, not a live model-provider assessment, not a native model behaviour baseline, not production readiness, and not independent certification.

## 2. Cyraduct full product suite

- Repository: raheem-verisigil/cyraduct
- Workflow: Cyraduct tests
- Rerun: 41138545104 (rerun of the prior failed full-suite workflow)
- Result: FAIL — 227 passed, 5 failed, 4 warnings, 5.07 seconds.
- The workflow compiled Python modules successfully; the failure occurred during pytest.

### Failure breakdown

1. tests/test_ncs_experiment_record.py::test_aggregate_sharing_requires_explicit_consent — ValueError: cohort is below the minimum anonymization threshold. This indicates the test's expected consent/error precedence and the actual guard ordering are not aligned in the tested merge commit. Reconcile the test and implementation; do not waive the minimum cohort rule.
2. tests/test_ncs_sink_guard_compat.py::test_sink_guard_rejects_expired_receipt — receipt issuance returned HTTP 429 due to shared in-memory rate-limit state.
3. tests/test_private_record_access.py::test_receipt_queries_require_authentication — receipt issuance returned HTTP 429 due to shared in-memory rate-limit state.
4. tests/test_private_record_access.py::test_test_key_receipt_query_is_limited_to_test_namespace — receipt issuance returned HTTP 429 due to shared in-memory rate-limit state.
5. tests/test_rate_limiting.py::test_broker_execute_rate_limit_is_tighter_than_advisory — expected receipt object missing after the prior 429 response; the test assumed successful receipt issuance.

The four rate-limit-related failures indicate test isolation/order coupling: the rate-limit test deliberately consumes the shared 60/minute quota, and subsequent tests reuse the same application/remote test-client identity. The proper correction is deterministic test isolation/reset of limiter state or independent client identities, while retaining production rate limits. Do not disable production rate limiting to make tests pass.

## 3. VeriSigilAI / VCB source review

Two repository scopes must remain distinct:
- Current public VCB/product website: raheem-verisigil/verisigil-website. It is a static website repository; no tests directory or .github/workflows directory was present at the inspected main root. This is not evidence that the deployed API has no tests.
- Legacy/runtime API repository: raheem-verisigil/verisigil-api, latest inspected main commit 99072f711a8271479f0984e89d12cc205ef61a89. It must not be assumed identical to the current VCB website or the deployed consequence-boundary implementation without artifact equivalence.

### Static test-quality finding

Inspected:
- test_conformance.js
- verisigil_sdk.js
- conformance_vectors.json
- .github/workflows/verisigil-ci.yml
- tests/test_verisigil.py
- CLAIMS_REGISTRY.md
- VERISIGIL_PROOF_REPORT_V1.md

Findings:
- VEC-043 through VEC-058 (16 vectors) carry jurisdiction-resolution expectations (expected_primary_regime, expected_decision, expected_conflicts) but the Node conformance runner's fallback branch executes assert(true, 'ok') for unrecognised vector shapes. Those 16 vectors therefore do not test the declared expected jurisdiction outcomes.
- The SDK's runConformanceTests also sets result.passed = true for the generic fallback case. This can overstate conformance coverage.
- The current GitHub workflow's invariant step includes constant/tautological assertions and does not execute test_conformance.js.
- Its API endpoint test job runs only on pushes to main and uses continue-on-error: true, so API endpoint failures do not fail the overall workflow.
- This is a static source-review finding, not a fresh runtime test result. No 80/80 runtime pass is claimed by this assessment.
- The connected GitHub integration returned HTTP 403 when attempting to create an audit branch in verisigil-api. No product code was modified and no VeriSigil CI run was triggered.

### Existing claim boundary

The inspected VeriSigil claims registry and proof report explicitly say:
- PRODUCTION_CLAIM_ALLOWED = False;
- LOCKED_CLAIM = NOT_YET_DELIVERED;
- real Paystack reference, multi-instance atomicity, distributed replay and full endpoint proof coverage are not proven;
- regulatory certification is not claimable.

The proof report is dated 2026-09-03 and describes its own V3/V4/V5 evidence. This assessment does not refresh or independently reproduce those historical tests.

## 4. Deployment inventory

- Cyraduct Railway web service: latest inspected deployment SUCCESS on main commit a8579bba806ba96e48b5627fee6bfa98166a6d7b. The NCS architecture branch/PR is not deployed.
- VeriSigil API Railway service: latest inspected deployment SUCCESS on 2026-09-30; no new deployment was triggered by this assessment.
- Current VCB website repository: static GitHub repository; no website change was made.
- Dedicated NCS Railway project/service: not found in the inspected Railway projects. No production NCS workbench exists to deploy.
- No project website was updated with new live test badges or live result feeds in this assessment.

## 5. Follow-up remediation committed after the snapshot

- Commit `4723b18abb0802431d69532b73b901fbae2d0655` adds `tests/conftest.py` to reset the shared SlowAPI in-memory limiter storage around each test. This is intended to isolate test quotas without changing production rate limits.
- This fixture has **not yet been executed in CI**. The PR currently targets `ncs/finance-guard-assessment`, while the inspected workflow is configured for pull requests targeting `main`; no check run was attached to the new head commit when inspected. Do not treat this mitigation as verified.
- The consent/cohort precedence failure remains unresolved.

## 6. Required next actions

1. Run the complete Cyraduct suite on the current PR head and verify whether the limiter fixture removes the four order-dependent failures; do not weaken privacy thresholds or production rate limiting.
2. Add executable oracles for VEC-043–VEC-058 and remove pass-by-default behavior in both Node runner and SDK.
3. Add a required Node conformance CI job and make endpoint tests report failures honestly; do not use continue-on-error for required assurance gates.
4. Establish a dedicated NCS repository and runnable workbench service before deploying NCS to Railway.
5. Implement a signed, schema-validated result manifest and website consumer for each product; display test status, deployment health, source commit, run timestamp, evidence level and limitations separately.
6. Only publish a new live result after its current source commit and test run have been verified.

## 6. Overall status

- NCS selected harness: PASS, 93/93.
- Cyraduct full suite: FAIL, 227/232; five failures remain.
- VeriSigilAI/VCB: no complete fresh runtime test run; static audit found material conformance-test coverage gaps in the legacy API repository.
- NCS workbench/compiler: architecture specifications committed to a draft PR; not yet implemented.
- Railway deployment: not performed; there is no dedicated NCS runnable service and no verified website result-feed integration.
