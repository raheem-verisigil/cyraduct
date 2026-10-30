# NCS Cross-Project Evidence Contract — v0.1

**Status:** Proposed integration contract.

## 1. Integration principle

NCS is the independent evidence consumer and assurance layer. Cyraduct and VeriSigilAI remain separate products with their own source repositories, release processes, test suites, runtime environments and claims registries.

A product may submit a signed or otherwise integrity-protected test-result envelope. NCS validates its schema, source identity, run metadata, artifact/configuration binding, evidence references and declared limitations before displaying it.

A product's own PASS claim is an input assertion, not an NCS verdict.

## 2. Minimum result envelope

Required fields:
- schema: exact contract version;
- project ID: stable NCS integration identifier;
- product name and repository;
- source commit and branch;
- workflow run ID or local run identifier;
- test suite ID and version;
- started_at, completed_at and environment;
- test command and runtime/toolchain versions;
- tests_total, tests_passed, tests_failed, tests_skipped and tests_error;
- result: PASS, FAIL, PARTIAL or UNKNOWN;
- evidence_level: LOCAL_REPRODUCED, CI_RECORDED, LIVE_ENDPOINT_CHECKED or INDEPENDENTLY_REPRODUCED;
- limitations array;
- report digest and immutable report reference;
- producer identity and signature/attestation metadata where available.

A result is invalid if counts do not reconcile or if passed + failed + skipped + error does not equal total.

## 3. Status semantics

- PASS: all required tests in the named suite completed and passed.
- FAIL: at least one required test failed or a required integrity check failed.
- PARTIAL: only a subset completed or one or more tests were skipped/indeterminate.
- UNKNOWN: no trustworthy current run evidence is available.

The website must not infer pass from HTTP 200, deployment SUCCESS, a README badge, a historic count, or a product-authored narrative.

## 4. Evidence classes

NCS keeps separate:
1. model/native conduct evidence;
2. policy/configuration delta evidence;
3. application-control evidence;
4. consequence/sink-effect evidence;
5. formal-method/model-checking evidence;
6. infrastructure deployment and health evidence;
7. human review and organisational decision evidence.

A conformance suite for a runtime authorization API does not prove native foundation-model behaviour. A successful deployment does not prove functional correctness. Formal proof results apply only to the formal model and assumptions that were checked.

## 5. Product-specific boundaries

### Cyraduct
The current NCS adapter is limited to synthetic Finance Guard application-control tests and isolated sink effects. It must not call Railway production, a bank, real ERP, payment endpoint or live money movement. NBB requires a separately configured model provider runner and is not established by Cyraduct API tests.

### VeriSigilAI
The integration must use the current Verifiable Consequence Boundaries claims registry and proof report as the authoritative claim ceiling. Do not import historic claims from a different VeriSigil repository or API generation without proving repository, artifact and test-suite equivalence. The website must preserve statuses such as NOT_PROVEN, NOT_TESTED, PENDING_INDEPENDENT_CONFIRMATION and NOT_CLAIMABLE.

### NCS
NCS must identify which parts of its own engine have actually been implemented and tested. A document or schema is not a functioning governance workbench or certificate service.

## 6. Publication and freshness

Each result has source commit, run ID, report digest, completion timestamp, expiry/freshness policy and last independently verified timestamp.

When a new commit changes a relevant source path, previous results become STALE until the corresponding suite runs again. A deployment change alone does not refresh test evidence. A test result must not be edited manually on the website; the site consumes a validated result manifest.

## 7. Public dashboard rules

Public status page displays:
- product and repository;
- exact source commit (short SHA plus link);
- latest verified run timestamp;
- test suite and counts;
- status and evidence level;
- deployment status separately;
- limitations and scope notes;
- link to reproducible logs/report where public.

Never publish secrets, raw customer data, prompts or sensitive payloads. Public summaries should use synthetic test evidence only.

## 8. Acceptance criteria

- Reject malformed or count-inconsistent envelopes.
- Reject untrusted results where signature is required by configured trust policy.
- Preserve source commit and report digest.
- Mark evidence stale after a relevant source change.
- Keep test status separate from Railway deployment status.
- Keep each product's claims registry separate.
- Display unknown/partial states honestly.
