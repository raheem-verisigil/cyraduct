# NCS Certificate Lifecycle — Draft v0.1

1. **Proposed:** assessment scope and artifact identity submitted; no grade.
2. **Evidence complete:** manifest and mandatory evidence checks pass; not yet a certificate.
3. **Under independent review:** reproduction and adjudication underway.
4. **Issued:** authorized decision binds certificate ID to artifact digest, evidence-manifest digest, compiler/spec versions, capability profile, limitations, issue date and expiry.
5. **Suspended:** credible unresolved integrity, safety, or scope concern; verification endpoint reports suspension.
6. **Expired:** validity period elapsed; no implied renewal.
7. **Revoked:** material misrepresentation, artifact mismatch, failed required monitoring, or adjudicated invalidity.
8. **Superseded:** a new assessment revision replaces the prior one; history remains visible.

Any change to model weights, provider model version, system/developer prompt, retrieval corpus, tool permissions, quantization, safety configuration, inference runtime or other declared material dependency triggers impact analysis. A material change requires a derived assessment or full reassessment. Certificate IDs are never reused.

**v0.1 limitation:** this defines lifecycle policy only. No cryptographic signing, public registry, revocation service, or certificate issuance is active.
