# INDEPORA–Cyraduct Sandbox Boundary Test
## Stakeholder presentation script

**Format:** 10 slides, approximately 8–10 minutes, plus a 60-second live walkthrough.

**Audience:** product stakeholders, security and assurance leaders, finance/procurement design partners, AI platform teams, and technical reviewers.

**Visual direction:** digitally inclined **Command & Control** aesthetic. Use a dark navy/black field, electric cyan for evidence flow, amber for uncertainty and human review, green for verified authorization, and red for blocked manipulation. Use a control-room motif: thin grid lines, evidence nodes, hash labels, decision gates, and a clear left-to-right execution boundary.

**Important framing:** this demonstration uses a synthetic Stemma-style result and a local test sink. It is a boundary contract experiment, not a production INDEPORA deployment and not a claim that Cyraduct independently determines evidence independence.

---

## Slide 1 — The question we are testing

### On-slide headline

**Can a valid authorization still be produced when apparent evidence collapses to fewer origins?**

### Visual

A split-screen control-room view:

```text
Evidence assurance                         Action authorization
INDEPORA                                   Cyraduct
        └────────────── trusted adapter ──────────────┘
```

Show eight small evidence nodes converging into two origin nodes, followed by a separate authorization gate.

### Speaker script

> Today’s test is deliberately narrow. We are not asking Cyraduct to decide whether evidence is independent. We are asking whether an evidence-assurance result can safely become an input to an authorization decision without allowing an agent to rewrite that result.
>
> INDEPORA and Cyraduct answer different questions. INDEPORA examines evidence lineage and the number of candidate origins. Cyraduct controls what action may proceed and whether execution matches the authorization.

### Stakeholder takeaway

**Different assurance questions can compose without being conflated.**

---

## Slide 2 — The architecture boundary

### On-slide headline

**Evidence assurance → authorization → execution integrity**

### Visual

```text
Synthetic evidence
       ↓
INDEPORA Stemma / Standing / Charter
       ↓  signed or integrity-protected result
Trusted adapter
       ↓  extracts approved facts only
Cyraduct canonical action envelope
       ↓
Signed authorization receipt
       ↓
Controlled sandbox sink
```

Place a red “agent cannot edit” barrier around the adapter output.

### Speaker script

> The adapter is the critical boundary. The agent may propose an action, but it cannot declare that eight items are independent, turn an unknown relationship into an independent one, or replace the result hash.
>
> The trusted adapter verifies the INDEPORA result, extracts only the agreed structured facts, and places those facts into the Cyraduct action. Cyraduct then binds the result reference, evidence references, policy and action parameters into one canonical hash.

### Stakeholder takeaway

**The agent can propose; it cannot author the assurance facts.**

---

## Slide 3 — The synthetic evidence set

### On-slide headline

**Eight apparent items. Two candidate origins. One unknown relationship.**

### On-slide data

| Evidence | Relationship | Origin |
|---|---|---|
| `ev-001` | source | Origin A |
| `ev-002` | derived | Origin A |
| `ev-003` | derived | Origin A |
| `ev-004` | derived | Origin A |
| `ev-005` | source | Origin B |
| `ev-006` | derived | Origin B |
| `ev-007` | republication | Origin A |
| `ev-008` | unknown | Unknown |

### Speaker script

> The synthetic decision appears to have eight supporting evidence items. The lineage structure says something more precise: four items derive from Origin A, two relate to Origin B, one is a republication, and one has unknown lineage.
>
> This is exactly the kind of structure that can create an inflated impression of evidence diversity if item count is mistaken for origin count.

### Stakeholder takeaway

**Eight evidence IDs do not equal eight independent origins.**

---

## Slide 4 — The Stemma result

### On-slide headline

**INDEPORA preserves the uncertainty instead of manufacturing certainty.**

### On-slide result

```json
{
  "apparent_evidence_count": 8,
  "candidate_origin_count": 2,
  "verified_relationship_count": 6,
  "inferred_relationship_count": 1,
  "unknown_relationship_count": 1,
  "standing": "insufficient_for_independence_claim"
}
```

### Speaker script

> The important result is not simply that the origin count is two. The important result is that the unknown remains unknown. The system does not silently convert missing lineage into independence.
>
> The Stemma conclusion is: these eight apparent pieces of evidence do not represent eight independent origins. That result is integrity-protected before it enters the authorization path.

### Stakeholder takeaway

**Uncertainty is a first-class result, not a hidden failure.**

---

## Slide 5 — The trusted adapter

### On-slide headline

**The adapter turns verified assurance into bounded authorization facts.**

### On-slide flow

```text
Verify result signature/hash
        ↓
Check schema and experiment identity
        ↓
Extract approved fields
        ↓
Reject agent overrides
        ↓
Build Cyraduct request
```

### On-slide facts

```json
{
  "indepora_result_ref": "stemma-result-001",
  "indepora_result_hash": "fd856f...6501",
  "candidate_origin_count": 2,
  "unknown_relationship_count": 1,
  "evidence_assurance_status":
    "insufficient_for_independence_claim",
  "sandbox_only": true
}
```

### Speaker script

> The adapter does not copy arbitrary text from an agent. It verifies the result, checks the expected experiment, and extracts a small allowlisted set of facts.
>
> If the agent says candidate origins equal eight, the adapter rejects the request because the signed Stemma says two. If somebody edits the Stemma to remove the unknown relationship, the integrity check fails before Cyraduct sees it.

### Stakeholder takeaway

**The adapter is a trust boundary, not a convenience transformer.**

---

## Slide 6 — Cyraduct’s canonical action envelope

### On-slide headline

**The exact assurance result becomes part of the authorized action.**

### Visual

Show a hash input panel:

```text
protocol version
agent + principal
action + parameters
evidence references
INDEPORA result reference/hash
policy pack
sandbox constraint
        ↓
canonical JSON
        ↓
SHA-256 action hash
        ↓
Ed25519 receipt signature
```

### Speaker script

> Cyraduct does not authorize a vague statement such as “the evidence looked strong.” It authorizes a structured action containing the exact result reference, result hash, evidence references, policy pack and parameters.
>
> Any material change produces a different action hash. The receipt is then signed and bounded by expiry and replay controls.

### Stakeholder takeaway

**Authorization is bound to the exact evidence result and exact action, not to a general intention.**

---

## Slide 7 — Baseline authorization and execution

### On-slide headline

**The sandbox action is allowed because it is explicitly sandbox-only.**

### On-slide response

```json
{
  "decision": "allow",
  "policy_pack": "indepora_sandbox_v1",
  "receipt_id": "rcpt_9c7fd97ca86f4a9eafdf",
  "action_hash":
    "5e7b7f2b080323d2230553ac1df342086cac84583ee3c490a51517b22e0aa31a"
}
```

### Speaker script

> Notice what this allow decision does and does not mean. It does not mean the evidence has been proven independent. It means the dedicated experimental policy permits this particular synthetic action in a sandbox-only mode.
>
> The controlled sink receives the action only after Cyraduct verifies the receipt, the action binding, expiry, signature and replay state.

### On-slide execution result

```json
{
  "executed": true,
  "status_code": 200,
  "sink_call_number": 1
}
```

### Stakeholder takeaway

**A sandbox allow can coexist with an evidence result that is insufficient for an independence claim.**

---

## Slide 8 — The adversarial matrix

### On-slide headline

**Each manipulation is caught at the layer that owns the invariant.**

| Attack | Detection layer | Result |
|---|---|---|
| Change INDEPORA result hash | Cyraduct broker binding | `action_binding_mismatch` |
| Change evidence references | Cyraduct broker binding | `action_binding_mismatch` |
| Change action parameters | Cyraduct broker binding | `action_binding_mismatch` |
| Agent claims 8 origins | Trusted adapter | `agent_supplied_assurance_fact_rejected` |
| Unknown → independent | Result integrity check | `result_hash_invalid` |
| Replay original receipt | Cyraduct broker/storage | `receipt_already_consumed` |
| Same evidence, new parameters | Canonical hashing | New action hash and receipt |

### Speaker script

> This is the main result of the experiment. The failures are not all handled by one system. The adapter catches manipulation of evidence-assurance facts. Cyraduct catches changes to the authorized action after the receipt is issued. The broker catches replay.
>
> That separation is a feature. It tells us which component needs to improve when a test fails.

### Stakeholder takeaway

**The architecture localizes failure instead of hiding it behind one confidence score.**

---

## Slide 9 — What this proves and what it does not

### On-slide headline

**A useful boundary test—not a claim of universal assurance.**

### Proves in this sandbox

- The evidence result can be integrity-protected.
- The trusted adapter can prevent agent overrides.
- Cyraduct binds the result hash and evidence references to the action.
- Changed actions are rejected before sink execution.
- A receipt can be consumed only once.
- A separate action with the same evidence receives a different hash.

### Does not prove yet

- INDEPORA’s lineage algorithm is correct in all cases.
- Evidence independence is established by Cyraduct.
- Production tenant isolation or key rotation is complete.
- A real ERP or payment system is safe to connect without further review.
- A sandbox result should authorize a production consequence.

### Speaker script

> We should be precise about the result. The experiment proves the boundary contract and the integrity behavior. It does not certify INDEPORA’s analysis, and it does not make Cyraduct an evidence-lineage engine.
>
> That precision is what makes the demonstration credible to a security or assurance stakeholder.

---

## Slide 10 — The next design-partner step

### On-slide headline

**Choose one synthetic workflow and expand the adversarial coverage.**

### Proposed next step

1. Replace the synthetic Stemma signer with INDEPORA’s actual result and verification contract.
2. Agree the exact adapter schema and allowlisted facts.
3. Add the five requested lineage adversarial cases:
   - dependent evidence treated as independent;
   - genuinely independent evidence incorrectly collapsed;
   - unknown lineage mishandled;
   - paraphrase/translation confusion;
   - multiple agents repeating one upstream source.
4. Run every case through the same Cyraduct policy and sink harness.
5. Produce a joint failure report showing which layer caught each case.

### Speaker script

> The next step is not to connect production systems. It is to replace the synthetic result with INDEPORA’s actual signed or integrity-protected output and repeat the same contract test.
>
> The success condition is not that every system always agrees. The success condition is that disagreement is visible, attributable and prevented from silently becoming unauthorized execution.

### Closing line

> INDEPORA answers: “How independent is the evidence?” Cyraduct answers: “What exact action is authorized, and did execution match it?” Together, they create a traceable path from evidence assurance to controlled action.

---

# 60-second live demo script

## 0–10 seconds — Show the Stemma

> Here are eight apparent evidence items. The lineage result identifies two candidate origins and preserves one relationship as unknown. It explicitly rejects the claim that there are eight independent origins.

## 10–20 seconds — Show the adapter

> The trusted adapter verifies the result and extracts the structured facts. If the agent submits candidate origin count eight, the adapter rejects it before Cyraduct receives the action.

## 20–35 seconds — Evaluate and show the receipt

> Cyraduct receives the exact result reference, result hash, evidence references and sandbox action parameters. It evaluates the dedicated policy and issues a signed receipt for this synthetic sandbox-only action.

## 35–45 seconds — Execute the unchanged action

> The local sink verifies the receipt and accepts the unchanged action. This is the only normal sink call.

## 45–55 seconds — Mutate the action

> Now we change the result hash, evidence list or action parameters while reusing the original receipt. Cyraduct reports `action_binding_mismatch`, and the sink is not called.

## 55–60 seconds — Replay

> Finally, we replay the original receipt. Cyraduct reports `receipt_already_consumed`.

---

# Stakeholder questions and suggested answers

## “Why not make Cyraduct evaluate the evidence itself?”

> That would conflate two assurance domains. Cyraduct can consume a verified evidence-assurance result, but evidence lineage belongs in the system that understands provenance and source relationships.

## “Does an allow decision mean the evidence is trustworthy?”

> No. In this experiment, allow means the dedicated sandbox policy permits the exact synthetic action. The Stemma still says the evidence is insufficient for an independence claim.

## “What prevents an agent from changing the facts?”

> The agent does not author the adapter facts. The adapter verifies the result and extracts them. Cyraduct then binds the result hash and facts into the canonical action envelope.

## “What happens if the evidence result changes after authorization?”

> The result hash or structured payload changes, the canonical action hash changes, and the original receipt no longer binds to the presented action.

## “What if the same evidence is used for a different decision?”

> That is allowed only as a separate authorization decision. The different action parameters produce a different action hash and a different receipt.

## “Is this ready for production finance?”

> No. This is a sandbox contract test. Production use would require the real INDEPORA verification contract, tenant-specific authorization, signing-key management, production-grade sink restrictions, deeper review and a controlled pilot.

---

# Final message for stakeholders

> This test is valuable because it does not force one system to claim what the other system knows. INDEPORA measures evidence lineage and preserves uncertainty. Cyraduct binds that result to an exact authorized action and prevents post-authorization manipulation. The result is a visible, testable boundary from evidence assurance to authorization to execution integrity.
