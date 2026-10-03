# Cyraduct Design-Partner Pilot — Pitch Deck Talking Points

**Recommended format:** 10 slides, 8–10 minutes, followed by the one-minute Finance Guard demonstration.

## Slide 1 — The operational problem

**Headline:** AI-assisted AP actions create a new execution boundary problem.

Talking points:

- Agents can propose vendor and payment actions faster than teams can manually verify every detail.
- The dangerous moment is not only the model response; it is the final write or payment request.
- Existing ERP and AP tools remain valuable, but the exact authorization boundary is often difficult to inspect independently.

## Slide 2 — The core distinction

**Headline:** Decision is not authorization. Authorization is not execution.

Talking points:

- An agent may propose an action.
- Cyraduct evaluates the action against policy and trusted context.
- A downstream enforcement point verifies the exact authorization before execution.
- A changed beneficiary or amount must not inherit an old authorization.

## Slide 3 — What Cyraduct is

**Headline:** An open, vendor-neutral consequence-boundary protocol.

Talking points:

- Short-lived Ed25519-signed receipts
- Exact action and parameter binding
- Expiry, revocation and replay controls
- Independent verification using a published public key
- Conformance fixtures that expose both accepted and rejected cases

Do not describe Cyraduct as an ERP, payment processor, general IAM replacement or agent framework.

## Slide 4 — Where it fits

**Headline:** Add the boundary beside the system of record.

Talking points:

```text
Agent / email / ERP workflow
          ↓
Trusted adapter and evidence
          ↓
Cyraduct policy evaluation
          ↓
Signed authorization receipt
          ↓
ERP / payment sink verifies
          ↓
Controlled execution or rejection
```

- Cyraduct does not replace the ERP.
- The customer keeps its existing system of record.
- The pilot can begin with a controlled adapter and synthetic data.

## Slide 5 — First use case

**Headline:** Finance Guard for supplier and payment changes.

Talking points:

Start with one of:

- supplier bank-detail change;
- supplier remittance change;
- new-beneficiary payment initiation;
- high-value ACH or wire initiation.

The best first workflow is the one where a changed target or beneficiary would create the greatest operational and financial consequence.

## Slide 6 — The proof

**Headline:** A receipt is evidence of a bounded authorization, not a dashboard status.

Talking points:

The receipt binds:

- agent;
- principal and caller context;
- exact action;
- target and parameters;
- consequence class;
- policy;
- evidence context;
- expiry;
- signing key;
- receipt-chain context.

An engineer can verify the signature without trusting the Cyraduct server after obtaining the public key.

## Slide 7 — One-minute attack/defense demo

**Headline:** Same receipt, changed beneficiary: rejected.

Talking points:

1. Submit a valid synthetic supplier-account-change request.
2. Receive a signed receipt.
3. Verify it independently.
4. Present the unchanged request to the fake sink: allowed.
5. Change only the new-account fingerprint: rejected.
6. Replay or revoke the receipt: rejected.
7. Show that the sink was not called for the rejected cases.

The demo should use no real bank data and no real money movement.

## Slide 8 — Why a design partner

**Headline:** Validate one boundary, not an entire platform.

Talking points:

The design partner helps answer:

- Where is the final execution point?
- Which facts must be trusted from existing systems?
- Which fields must never change after approval?
- Which refusal cases matter in practice?
- What measurable reduction in investigation effort or bypass risk would justify adoption?

The design partner receives a reproducible test pack and integration findings.

## Slide 9 — Pilot scope and success criteria

**Headline:** Two to four weeks, synthetic data, one workflow.

Talking points:

Pilot scope:

- one workflow;
- one adapter or controlled sink;
- synthetic data only;
- no production financial execution;
- valid and negative conformance cases;
- written results and integration recommendation.

Success criteria:

- exact action can be reconstructed;
- altered target/parameter is refused;
- expiry, revocation and replay behave as expected;
- receipt can be independently verified;
- customer identifies a credible path to production readiness.

## Slide 10 — The ask

**Headline:** Choose one consequential workflow to test.

Talking points:

- Identify the AP or procurement workflow.
- Name the system that ultimately executes it.
- Nominate one technical reviewer and one process owner.
- Share a redacted workflow description, not customer bank data.
- Agree on the refusal cases and success metric.

**Closing line:**

> Cyraduct does not claim that AI is correct. It makes consequential authorization explicit, bounded, independently verifiable and enforceable at the point of execution.

## Likely objections and answers

### “We already have approval workflows.”

That is useful. Cyraduct is intended to sit at the enforcement boundary and make the exact authorization independently verifiable rather than replace existing approvals.

### “We cannot send production financial data.”

The initial pilot does not require it. Synthetic vendor IDs and fingerprints are sufficient to test the protocol and integration boundary.

### “Is this another IAM platform?”

No. Cyraduct does not replace enterprise identity. It consumes identity and authorization context to bind a specific consequential action at the execution boundary.

### “What if the external system fails?”

Authorization and execution are separate. The pilot records whether execution was attempted and whether the controlled sink succeeded; it does not claim that authorization guarantees external system success.

### “Does this prevent prompt injection?”

No broad claim is made. Cyraduct limits the impact of an agent proposing a consequential action by requiring independent policy and exact-action enforcement before execution.
