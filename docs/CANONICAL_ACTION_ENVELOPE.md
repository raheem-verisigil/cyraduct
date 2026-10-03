# Canonical Action Envelope and Hash Verification

## Purpose

Cyraduct signs authorization for an exact action, not a free-form description. The canonical envelope is the deterministic security representation used to calculate `action_hash` before a receipt is issued and when a sink verifies the presented request.

## Version

The current envelope version is:

```text
1.0
```

`ActionRequest.protocol_version` defaults to `1.0` for backward compatibility. `request_id` is optional for legacy callers but should be supplied by new integrations for correlation and idempotency.

## Policy envelope

The policy/attested envelope contains:

```json
{
  "protocol_version": "1.0",
  "request_id": "req_123",
  "action_id": "action_123",
  "agent": {
    "id": "ap-agent-acme",
    "principal": "org:acme:finance",
    "framework": "custom"
  },
  "action": {
    "type": "update_vendor_bank_details",
    "consequence_class": "vendor_master_change",
    "purpose": "supplier payment-account update",
    "consumer": "erp:acme-payables",
    "jurisdiction": "US",
    "parameters": {
      "vendor_id": "vendor_1842"
    }
  },
  "policy": {
    "pack": "finance_vendor_change_v1"
  },
  "evidence_refs": ["ev_123"]
}
```

## Runtime envelope

Runtime authorization uses the same policy envelope plus a `runtime` object containing:

- target;
- resource;
- reversibility;
- authority;
- authorization expiry;
- authorized state version;
- current state version;
- idempotency key.

Policy receipts and runtime receipts intentionally use different envelopes. A policy receipt must not silently acquire runtime-only fields during broker verification.

## Serialization rules

The implementation in `app/canonical.py` is the single source of truth:

- JSON object keys are sorted;
- separators are `,` and `:` with no insignificant whitespace;
- UTF-8 encoding is used;
- non-finite numbers are rejected;
- values are hashed as structured JSON, not string concatenation;
- SHA-256 returns the lowercase hexadecimal digest;
- Ed25519 signs the receipt message containing the receipt ID, action hash, expiry and previous receipt hash.

## Verification invariant

A receipt may be used only when:

```text
hash(canonical presented request) == receipt.action_hash
```

and the receipt also passes:

- signature verification;
- expiry check;
- revocation check;
- agent/action/policy binding;
- replay/consumption check for broker execution;
- conditional/hold enforcement rules.

Changing any of these fields must change the hash and fail the binding check:

- protocol version;
- request ID;
- agent;
- principal;
- framework;
- action type;
- consequence class;
- purpose;
- consumer;
- jurisdiction;
- parameters;
- policy pack;
- evidence references;
- runtime state and target fields for runtime receipts.

## Backward compatibility

Existing flat request fields remain accepted. The canonical module maps them into the envelope. New protocol versions must not reinterpret old signed objects; a breaking semantic change requires a new version and migration path.

## Tests

`tests/test_canonical.py` covers:

- stable output when input mapping order changes;
- explicit envelope fields;
- mutation of every security-relevant policy field;
- action-ID binding.

The broader conformance and broker tests prove that mismatched, expired, revoked, invalid, conditional and replayed receipts do not reach the execution sink.
