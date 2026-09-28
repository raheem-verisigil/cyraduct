# Cyraduct Finance Guard

Cyraduct Finance Guard is the first reference application for the Cyraduct consequence-boundary protocol.

It protects consequential finance actions without moving money or replacing the ERP:

```text
email / ERP / agent proposes action
        -> trusted adapter collects evidence
        -> Cyraduct evaluates policy
        -> human review / callback verification
        -> signed, time-limited receipt
        -> ERP, bank, or payment sink verifies
        -> action executes only when the boundary is satisfied
```

## First actions to protect

Use explicit action types rather than a generic fraud score:

- `update_vendor_bank_details`
- `update_vendor_remittance_details`
- `initiate_ach_payment`
- `initiate_wire_transfer`

The shipped `finance_vendor_change_v1` policy pack fails closed when required facts are missing. It requires trusted callback provenance and a named reviewer for vendor-master changes, dual approval for new beneficiary accounts, and purpose, amount, age-of-bank-change, and approval facts for transfers.

## Minimal integration

The adapter must compute facts from trusted systems. Do not let an LLM, email body, or requester assert that a callback happened or that approval exists.

```bash
curl -X POST https://api.cyraduct.com/v1/attested/evaluate \\
  -H 'Content-Type: application/json' \\
  -d '{
    "agent_id": "ap-agent-acme",
    "principal": "org:acme:finance",
    "framework": "custom",
    "action_type": "update_vendor_bank_details",
    "consequence_class": "vendor_master_change",
    "purpose": "supplier payment-account update",
    "consumer": "erp:acme-payables",
    "jurisdiction": "US",
    "policy_pack": "finance_vendor_change_v1",
    "payload": {
      "vendor_id": "vendor_1842",
      "old_account_fingerprint": "sha256:...",
      "new_account_fingerprint": "sha256:...",
      "callback_verified": true,
      "callback_channel_preexisting": true,
      "reviewer_id": "user_391",
      "new_beneficiary": true,
      "dual_approval": true,
      "sender_domain_match": true
    }
  }'
```

Store only fingerprints and evidence references where raw bank details are not required. The returned receipt is bound to the action and expires according to the consequence class.

## Enforce at the sink

A compliant ERP, bank adapter, or payment service must verify the receipt before it changes the vendor or initiates payment:

```bash
curl https://api.cyraduct.com/v1/attested/verify/<receipt_id>
```

For independent verification, fetch the public key once from `/v1/public-key` and use the standalone `verify_receipt.py` verifier. For in-path pilots, use `/v1/broker/execute` only with an allowlisted, controlled execution webhook. The current broker is a reference webhook proxy, not a production banking terminator.

## Pilot boundaries

Start read-only or approval-gated. Do not:

- move funds;
- approve or deny payments autonomously;
- claim account ownership or reimbursement;
- claim that Cyraduct alone makes a customer Nacha-compliant;
- use customer bank data or mailboxes for model training by default.

Measure screened actions, high-risk cases, time to disposition, false positives, verification completion, reviewer bypasses, and audit completeness. The commercial case is proven by reduced investigation effort or a risky change existing controls failed to document.

## Production readiness before live finance use

The reference implementation is an MVP. Before processing real financial consequences, migrate SQLite to Postgres, add multi-tenant authentication and authorization, use tenant-specific signing keys with rotation, sign policy packs, restrict broker destinations, add replay/idempotency controls, and complete a security review.
