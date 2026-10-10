# Cyraduct Design-Partner Pilot Outreach

## Positioning

Cyraduct is an open, vendor-neutral authorization boundary for consequential AI-agent actions. The first pilot protects one AP or procurement workflow without replacing the customer’s ERP, AP automation platform, or payment system.

**Pilot promise:** synthetic data, no money movement, one workflow, measurable refusal and verification outcomes.

## Primary target

- Hospitality CFO or finance director
- Head of Procurement Systems
- AP Automation Lead
- Enterprise AI Platform Lead
- Security architect responsible for agent/tool execution

## Subject-line variants

1. A two-week synthetic-data pilot for AP action verification
2. Protecting supplier bank-detail changes in an AI-assisted AP workflow
3. Design-partner invitation: verifiable controls for consequential agent actions
4. Can we test one AP execution boundary beside your existing ERP?
5. A narrow pilot for supplier-payment change authorization

## Initial email

**Subject:** A two-week synthetic-data pilot for AP action verification

Hi {{first_name}},

I am building Cyraduct, an open authorization boundary for AI-agent actions. We are focused first on consequential finance workflows such as supplier bank-detail changes, remittance changes, and high-value payment initiation.

Cyraduct does not replace an ERP or AP automation platform. It sits immediately before the consequential operation and gives the sink an independently verifiable, short-lived receipt bound to the exact agent, action, target, parameters, policy and expiry.

We are looking for one hospitality finance or procurement design partner for a focused pilot:

- one workflow;
- synthetic data only;
- no money movement;
- existing ERP/AP system remains in place;
- valid, altered, expired, revoked and replayed cases tested;
- a short written results package at the end.

Would your team be open to reviewing one workflow asynchronously? The most useful starting point would be the workflow you would least want an AI-assisted process to execute with a changed supplier or beneficiary.

Best,
Raheem
Cyraduct
hello@cyraduct.com

## Finance director version

**Subject:** Protecting supplier bank-detail changes in an AI-assisted AP workflow

Hi {{first_name}},

Supplier-payment fraud often becomes consequential at the point where a vendor or payment record is changed. Cyraduct adds a narrow authorization boundary at that point.

For a synthetic-data pilot, we would take one existing AP workflow, define the trusted facts and approval conditions, issue a signed authorization receipt, and verify it immediately before the simulated execution. We would then mutate the vendor or account fingerprint and demonstrate that the original authorization is rejected.

The pilot does not move funds, replace your ERP, or require production mailbox access. The output is a reproducible test pack showing what was allowed, what was rejected, and why.

Would it be useful to send a one-page pilot outline?

Best,
Raheem

## Procurement-systems version

**Subject:** Can we test one AP execution boundary beside your existing ERP?

Hi {{first_name}},

Cyraduct is designed to work beside existing procurement and AP systems. An adapter submits a normalized action, Cyraduct evaluates the declared policy and trusted evidence, and the downstream sink verifies a signed receipt before acting.

We are looking for a design partner to test one integration surface with synthetic data. The technical questions are deliberately concrete:

1. Where is the final enforcement point before the supplier or payment record changes?
2. Which fields must be bound so a receipt cannot be reused for another vendor or beneficiary?
3. Which facts must come from trusted systems rather than an agent or email body?
4. Which refusal cases should be part of the conformance test?

There is no production financial execution in the pilot. If this is relevant, I can send the current receipt schema, public-key behavior, conformance fixtures and a short integration note.

Best,
Raheem

## Technical design-partner version

**Subject:** Design-partner invitation: verifiable controls for consequential agent actions

Hi {{first_name}},

Cyraduct is an open protocol for the boundary between an agent proposal and consequential execution. The reference implementation uses Ed25519-signed, time-bounded receipts and independent verification.

The first integration target is Finance Guard, but the protocol is intentionally vendor-neutral. We would like to test a two-to-four-week synthetic-data adapter that:

- canonicalizes the exact action;
- binds agent, principal, target and parameters;
- verifies policy and evidence context;
- rejects mutation, expiry, revocation and replay;
- records the enforcement outcome for independent inspection.

The integration can sit beside an existing tool gateway, AP workflow or ERP adapter. We are not asking you to replace your platform or trust a new dashboard.

Would you be open to a written technical review of the receipt and conformance contract?

Best,
Raheem

## Follow-up 1 — three business days later

**Subject:** Re: {{original_subject}}

Hi {{first_name}},

Following up with the narrow version of the idea: choose one consequential AP action, run it with synthetic data, and test whether a changed target or parameter is rejected before the sink is called.

The pilot is successful if your team can answer:

- What exact action was authorized?
- Which policy and evidence were used?
- Could the same receipt be replayed or applied to another beneficiary?
- Can an engineer verify the receipt without trusting the Cyraduct server?

If another person owns this workflow, I would appreciate being pointed in the right direction.

Best,
Raheem

## Follow-up 2 — seven business days later

**Subject:** Last note — AP authorization boundary pilot

Hi {{first_name}},

I will close the loop after this note. The design-partner pilot is limited to one workflow and synthetic data. It is intended to validate the enforcement boundary, not to introduce another ERP, payment processor or general IAM system.

If supplier bank-detail changes, remittance changes, or AI-assisted payment controls are on your roadmap, I would be glad to send the pilot outline asynchronously.

Best,
Raheem

## Qualification questions

Ask only after interest is confirmed:

1. Which workflow has the highest consequence if the target or beneficiary is changed?
2. Which system is the final execution sink?
3. Which system currently provides callback, approval or vendor-verification facts?
4. Where can an enforcement adapter be inserted without replacing the system of record?
5. What would count as a successful pilot?
6. Who should review the receipt and conformance fixtures?

## Pilot acceptance criteria

A design-partner pilot should produce:

- one documented workflow boundary;
- one synthetic action schema;
- one valid allow case;
- one wrong-target refusal;
- one changed-parameter refusal;
- one expired or revoked refusal;
- one replay refusal;
- one independent receipt-verification run;
- one list of integration blockers;
- one decision on whether to continue to a production-readiness assessment.

## Claims discipline

Say:

- “Cyraduct enforces the exact authorization boundary in the integrated path.”
- “The receipt is independently verifiable.”
- “The pilot uses synthetic data and does not move money.”

Do not say:

- “Cyraduct prevents prompt injection.”
- “Cyraduct proves the AI decision is correct.”
- “Cyraduct makes the customer compliant by itself.”
- “The reference broker is a production banking terminator.”
