# Transfer checklist — dedicated NCS authority repository

Target: `raheem-verisigil/native-conduct-standard` (proposed name; repository creation not yet available through the connected GitHub integration).

## Source
Staging source: `raheem-verisigil/cyraduct`, branch `ncs/experiment-runner-v0.1`, directory `ncs-authority/`.

## Safe transfer procedure
1. Create an empty repository with a README disabled (or initialise with a single README and use a merge strategy that preserves both histories).
2. Transfer the complete `ncs-authority/` directory to the repository root, preserving file contents and commit provenance where possible.
3. Add the NCS-only workflow from `.github/workflows/ncs-authority.yml` as `.github/workflows/ci.yml`.
4. Run the workflow on the new repository and inspect every job log. Do not rely on the source repository's run as proof of target-repository execution.
5. Configure branch protection, CODEOWNERS, least-privilege GitHub App permissions, signed release policy and vulnerability reporting.
6. Appoint independent reviewers and publish the governance disclosures before describing the authority as independent.
7. Update both assessed projects' shared verification references to the new repository only after target files and CI are verified.
8. Keep Cyraduct's and VeriSigilAI's own assessment records as immutable subject-side copies that point to the NCS authority record.

## Not yet transferable as a live service
The portal is static/browser-local. It has no authenticated accounts, server-side evidence vault, durable challenge database, reviewer case-management workflow, signature verification, transparency-log proof or certificate issuance endpoint. Those require a separately threat-modelled service design and deployment.
