# Cyraduct — NCS Assessment Status Report

**Date:** 31 October 2026  
**Assessment ID:** NCS-CYR-FG-2026-001  
**Status:** Software CI verified; native model assessment incomplete.

## Verified CI
- NCS Finance Guard selected synthetic harness: 93 passed, 0 failed, 4 warnings; run #240.
- Cyraduct product suite: 235 passed, 0 failed, 4 warnings; run #226.
- Source commit: `726babe4f76344493e7a340f260f49b1cd099a07`.

## Interpretation
These results validate the relevant software CI suites only. They do not assess an AI model's native behaviour, policy delta, production safety, or independent reproducibility.

## Outstanding
- Bind a specific AI artifact/provider version to the assessment.
- Run reproducible Native Behaviour Baseline.
- Inventory deployment transformations and execute Policy Delta.
- Complete independent partner reproduction and adjudication.

**No NCS grade or certificate has been issued.**


## NCS authority infrastructure progress (31 Oct 2026)
The staged authority package now includes draft governance operating controls, an interim CODEOWNERS file, a dedicated-repository transfer checklist, and a manually dispatchable/scoped CI workflow. The manifest verifier was hardened to reject empty evidence lists, duplicate evidence IDs/paths, absolute/traversal paths, symlinks, malformed digests and missing files. Smoke coverage was expanded from 3 to 7 cases. A local Node.js 22 execution of the matching verifier/compiler/test source passed 7/7. This local execution is not a GitHub Actions run; the newly committed workflow result has not yet been confirmed.

The separate repository and independent reviewer body are still not established. Current CODEOWNERS entries are administrative placeholders, not independent approvals. No grade or certificate is issued.


## Compiler hardening update (31 October 2026)
The provisional compiler now validates assessment ID, decision state, stage structure/status and duplicate stage names. It distinguishes invalid records, incomplete evidence and records structurally ready for authorized review. It never assigns a grade or issues a certificate; even READY_FOR_AUTHORIZED_REVIEW is not a decision. Six compiler validation cases passed locally under Node.js, covering ready structure, missing mandatory stages, duplicate stages, invalid decision state, invalid stage status and revoked state. The expanded CI workflow now includes this compiler test file. GitHub Actions execution is not yet confirmed.


## GitHub Actions validation confirmed (31 October 2026)
The NCS Authority Package Checks workflow completed successfully on commit `bb1e16b0e3c83a6f2a35f4204cd446721561e632`. Run: https://github.com/raheem-verisigil/cyraduct/actions/runs/41202010366 . Confirmed successful steps: checkout, Node.js 22 setup, both JSON schema parse checks, compiler/verifier/test syntax checks, evidence verifier adversarial smoke tests, and compiler validation tests. This validates the staging package on the Cyraduct branch only; it does not validate a dedicated NCS repository, independent governance, production portal security, or model conduct.


## Dedicated NCS authority repository update — 31 October 2026
The dedicated private NCS repository is now established at https://github.com/raheem-verisigil/naconstan. The authority package is present in its main branch. Its authority-transfer CI completed successfully: https://github.com/raheem-verisigil/naconstan/actions/runs/41204731119. A governance/documentation correction branch also passed CI: https://github.com/raheem-verisigil/naconstan/actions/runs/41211453109. The latter branch is pending pull-request review/merge.

The NCS authority remains pre-alpha. The repository default branch is currently unprotected; CODEOWNERS is an administrative placeholder, and independent reviewers/board have not been appointed. The partner portal is a private static preview, not an externally accessible production service. No NCS grade or certificate is issued. Cyraduct's software CI results above remain distinct from native model-conduct assessment.
