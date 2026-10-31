# NCS Governance Operations — pre-launch controls

**Status:** proposed controls only. No independent authority or board is currently constituted.

## Required before any public NCS decision
- Establish a legal/operational steward and publish its mandate, funding disclosures and decision rights.
- Appoint at least three reviewers from at least two independent organisations; no assessed vendor may control a majority.
- Separate test author, test operator, evidence verifier, technical reviewer and final decision approver.
- Require two-person approval for normative releases, grade decisions, certificate issuance, suspension and revocation.
- Publish conflict-of-interest declarations; require recusal for financial, employment, advisory, family or material competitive conflicts.
- Maintain public decision logs, versioned standards, appeals, correction history and reviewer rationale.
- Provide an independent partner reproduction route and a process to report security vulnerabilities privately.
- Keep assessed products' marketing, revenue and deployment decisions outside NCS decision authority.

## Interim restrictions
Until the above controls exist, repository maintainers may maintain code and publish engineering test results only. They must not call the project an accredited, legally recognised, independent certification body; issue NCS grades or certificates; or present self-assessment as independent assurance.

## Repository control baseline
- Protect the default branch; require pull requests and passing checks.
- Require at least two independent approvals for normative/specification and certificate-policy changes once independent reviewers are appointed.
- Require CODEOWNERS review for `spec/`, `schemas/`, `compiler/`, `verifier/`, and `certificates/`.
- Disallow force-push and deletion on protected branches.
- Sign release tags and publish checksums and provenance.
- Review permissions quarterly and remove departed reviewers promptly.

## Decision and appeal record
Each decision must record assessment ID, exact artifact/configuration digest, spec/compiler/verifier versions, evidence-manifest digest, capability profile, ceilings, limitations, reviewers, conflicts/recusals, rationale, validity period, appeal route and status. Corrections create a new revision; never overwrite the historical decision.
