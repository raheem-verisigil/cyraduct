# Receipt signature v2

## Why
The original receipt signature (`signature`) covers only
`receipt_id | action_hash | expires_at | prev_receipt_hash` (plus `|runtime|<runtime_decision>` for runtime receipts).
It does **not** cover `decision`, the agent, the action type and consequence class, the policy pack or the evidence
assurance copied onto the receipt. Anyone who held a receipt could change `decision` from `conditional` to `allow`
(or the agent / consequence metadata) and the original signature would still verify. The issuer's own record was
never affected, and the broker uses it, but a sink that verified locally and trusted the presented fields could be misled.

## What changed
New receipts carry a second signature, `signature_v2` (`{alg, key_id, value}`), made with the same key. The original
`signature` is unchanged, so existing verifiers keep working. Verifiers that rely on `decision` or on any metadata field
**must require and check `signature_v2`**.

## Exactly what v2 signs
Message = the ASCII bytes `cyraduct.receipt.v2\n` followed by the canonical JSON (keys sorted, separators `,` and `:`,
UTF-8, no NaN) of this object, built from the receipt's JSON as returned by the API:

```json
{
  "v": 2,
  "receipt_id": "...", "action_id": "...", "decision": "allow|conditional",
  "authorization_type": "policy|runtime", "runtime_decision": null,
  "agent":  {"agent_id": "...", "principal": null, "framework": null},
  "action": {"type": "...", "consequence_class": "..."},
  "policy": {"policy_pack": "...", "policy_pack_version": "..."},
  "evidence_assurance": null,
  "action_hash": "...", "issued_at": "...", "expires_at": "...",
  "prev_receipt_hash": null,
  "key_id": "<signature_v2.key_id>"
}
```
Missing optional values are `null`. `authorization_type` defaults to `"policy"`.

**Not signed**: `matched_rules`, `reasons`, `consequence_score`, `score_factors`, `parameters_hash`, `evidence_refs`
(these are bound through `action_hash`, which commits to the full request), `revoked` and `consumed_at` (mutable state; only
the issuer knows them). A receipt can be revoked after issue, so check revocation at the issuer
(`GET /v1/attested/verify/{receipt_id}`) whenever it matters.

## Reference implementations
`verify_receipt.py` (standalone, `--require-v2`), `examples/sink_guard.py` (requires v2 by default), `app/receipts.py`
(`receipt_core_v2`, `signature_message_v2`). All three are tested to produce identical bytes.

## Verifier rules
1. Verify the Ed25519 signature over the v2 message with the pinned public key. If `signature_v2` is absent, **refuse**
   unless you have explicitly accepted legacy receipts (then `decision` and metadata are unauthenticated: confirm them with the issuer).
2. Stripping `signature_v2` is a downgrade attempt, which is why strict verifiers refuse a receipt without it.
3. Check expiry, then revocation at the issuer, then that the presented request hashes to `action_hash`.

## Compatibility and rollout
* Receipts issued before this change have no `signature_v2`. They keep verifying server-side and with legacy verifiers, and
  expire on their own within 24 hours (the longest consequence-class lifetime), after which every live receipt has v2.
* Receipts stored before the change load unchanged (the field is optional).
* Rollout: deploy, confirm new receipts show `signature_v2`, update any verifier you control (including any in the website's
  verification lab) to require it, then stop accepting legacy receipts.
* A v2 receipt altered in any signed field fails verification (`signature_v2 invalid`).
