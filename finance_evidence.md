# Finance Guard evidence - 2026-09-29T16:52:51+00:00
Pack `finance_vendor_change_v1`  Agent `test-finance-guard`

## Scene 1: Legitimate vendor bank change (known domain, callback to pre-existing number, two humans)
- OK **decision**: allow receipt rcpt_5e7004c209654ea79968
- OK **ERP applies change against receipt**: (True, 'ok')
- OK **receipt verifies offline with public key only**: True

## Scene 2: BEC attack: lookalike domain, callback to number from the email, one rushed reviewer
- OK **decision**: deny
- OK **matched rules**: ['fin.vendor.conditional.sender_domain_mismatch', 'fin.vendor.deny.callback_channel_from_request', 'fin.vendor.deny.new_beneficiary_no_dual_approval'] Callback used contact details supplied by the requester, not a pre-existing trusted channel; New beneficiary account requires dual approval; Request came from a domain that does not match the vendor master; escalate before acting
- OK **ERP refuses change with no receipt**: (False, 'no_receipt_presented')
- OK **vendor master unchanged**: True

## Scene 3: Fail-closed: a caller omits the verification facts entirely
- OK **decision**: deny 5 required facts missing
- OK **no receipt issued**: None

## Scene 4: Payment right after a bank change is held for a human
- OK **decision**: conditional Vendor bank details changed within 3 days; hold for review
- OK **bank refuses without escalation**: (False, 'conditional_receipt_requires_human_approval')
- OK **bank pays after named human escalation (stub)**: (True, 'ok')

## Scene 5: Normal payments flow; large wires need two people
- OK **20,000 wire to long-standing vendor**: allow
- OK **150,000 wire, one approver**: deny
- OK **150,000 wire, two approvers**: allow

## Scene 6: Tampering: reuse the legitimate change receipt to redirect to a different account
- OK **sink rejects altered action**: action_binding_mismatch

12/12 issued receipts verify against the public key. Raw bank details never left the adapter (fingerprints only).
This is decision evidence, not a compliance certification.
