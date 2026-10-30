# NCS Cross-Project Assessment Snapshot — 2026-10-31

**Status:** Evidence snapshot from GitHub CI and source review. Not an independent certification.  
**Assessment scope:** NCS harness, Cyraduct Finance Guard test suite, and VeriSigilAI/VCB repository evidence.

## 1. NCS selected harness

- Repository: raheem-verisigil/cyraduct
- Pull request: #29, NCS Governance Operations and Policy Evidence Foundation
- Source commit: 45ba7d2b0fe40ec5bc845cc984170761972327cd
- Workflow: NCS Finance Guard Harness, run #230 (ID 41145853910)
- Result: **PASS — 93 passed, 0 failed, 4 warnings, 1.05 seconds.**
- Scope: selected synthetic NCS Finance Guard assessment tests.
- Limitations: not a live model-provider assessment, not a native model behaviour baseline, not production readiness, and not independent certification.

## 2. Cyraduct full product suite

- Repository: raheem-verisigil/cyraduct
- Source commit: 45ba7d2b0fe40ec5bc845cc984170761972327cd
- Workflow: Cyraduct tests, run #203 (ID 41145853905)
- Result: **PASS — 232 passed, 0 failed, 4 warnings, 3.51 seconds.**
- Python module compilation also completed successfully.
- The test-isolation fixture in tests/conftest.py reset the shared in-memory SlowAPI limiter storage between tests. Production rate-limit configuration was not weakened.
- This confirms the full suite is green for this tested commit. It does not establish production security or absence of defects.

## 3. VeriSigilAI / VCB source review

Two repository scopes must remain distinct:
- Current public VCB/product website: raheem-verisigil/verisigil-website. It is a static website repository; no tests directory or .github/workflows directory was present at the inspected main root. This is not evidence that the deployed API has no tests.
- Legacy/runtime API repository: raheem-verisigil/verisigil-api, latest inspected main commit 99072f711a8271479f0984e89d12cc205ef61a89. It must not be assumed identical to the current VCB website or deployed consequence-boundary implementation without artifact equivalence.

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
- This is a static source-review finding, not a fresh runtime test result. No 80/80 runtime pass is claimed.
- The connected GitHub integration returned HTTP 403 when attempting to create an audit branch in verisigil-api. No product code was modified and no VeriSigil CI run was triggered.

### Existing claim boundary

The inspected VeriSigil claims registry and proof report explicitly say:
- PRODUCTION_CLAIM_ALLOWED = False;
- LOCKED_CLAIM = NOT_YET_DELIVERED;
- real Paystack reference, multi-instance atomicity, distributed replay and full endpoint proof coverage are not proven;
- regulatory certification is not claimable.

The proof report is dated 2026-09-03 and describes its own V3/V4/V5 evidence. This assessment does not refresh or independently reproduce those historical tests.

## 4. Deployment inventory

- Cyraduct Railway web service: latest inspected deployment SUCCESS on main commit a8579bba806ba96e48b5627fee6bfa98166a6d7b. The tested NCS branch commit is not deployed.
- VeriSigil API Railway service: latest inspected deployment SUCCESS on 2026-09-30; no new deployment was triggered by this assessment.
- Current VCB website repository: static GitHub repository; no website change was made.
- No dedicated NCS workbench repository or runnable service has been identified. No NCS workbench deployment was made.
- No website was updated with new live test-result feeds.

## 5. CI remediation completed

- Commit 4723b18 added tests/conftest.py to reset the shared in-memory limiter storage around each test.
- Commit 45ba7d2 updated .github/workflows/tests.yml so the full Cyraduct test suite runs on the NCS integration branch and PR base.
- Both the NCS selected harness and full Cyraduct suite then completed successfully on commit 45ba7d2.
- The earlier consent/cohort precedence failure did not recur in this full-suite run. The privacy threshold remains in place.

## 6. Required next actions

1. Review and preserve the new full-suite CI result as the baseline; keep the limiter fixture and production throttles under regression testing.
2. Add executable oracles for VEC-043–VEC-058 and remove pass-by-default behaviour in both the Node runner and SDK. This requires write access to the VeriSigil API repository.
3. Add a required Node conformance CI job and make endpoint tests report failures honestly; do not use continue-on-error for required assurance gates.
4. Establish a dedicated NCS repository and runnable workbench service before deploying NCS to Railway.
5. Implement signed, schema-validated result manifests and website consumers for each product; display test status, deployment health, source commit, run timestamp, evidence level and limitations separately.
6. Only publish live result badges after the corresponding current source commit and test run have been verified.

## 7. Overall status

- NCS selected harness: **PASS, 93/93**.
- Cyraduct full suite on commit 45ba7d2: **PASS, 232/232**.
- Cyraduct full suite on commit 6976b17: **PASS, 213/213**.
- Latest full-suite run on commit b00d2222521a62bde6e9fce6ad97d67ca1d86f57: **PASS, 235/235**, 4 warnings (workflow run #235; job 124373932587).
- NCS selected harness on commit b00d222: **PASS, 93/93**, 4 warnings (workflow run #235; job 124373932453).
- A separate full-suite run on commit c36e9f4 also passed **213/213**, 4 warnings. Counts differ across snapshots because test discovery/base contents changed; each total is commit-scoped and not a performance trend.
- Week 2 provider-neutral runner contract tests are included in the latest full-suite pass; no real provider adapter or live model was invoked.
- VeriSigilAI/VCB: no complete fresh runtime test run; static audit found material conformance-test coverage gaps in the legacy API repository.
- NCS workbench/compiler: architecture specifications committed to draft PR #29; not yet implemented.
- Railway deployment: no NCS deployment or website result-feed deployment has been performed.
