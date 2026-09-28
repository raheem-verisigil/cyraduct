"""
Finance Guard adapter: the trusted layer between AP workflows and Cyraduct.

Design rule: every policy fact (new_beneficiary, callback_channel_preexisting,
sender_domain_match, dual_approval, days_since_bank_change) is COMPUTED HERE from
the vendor master and the human review record. Nothing is taken from the email
text, the requester, or an LLM. Raw bank details never leave this process: only
SHA-256 fingerprints go into the Cyraduct payload.
"""
import hashlib, os, sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "poisoned_invoice"))
from cyraduct_guard import CyraductClient, ActionDenied, Authorization, verify_at_sink  # noqa: E402

PACK = "finance_vendor_change_v1"


def fingerprint(routing: str, account: str) -> str:
    return "sha256:" + hashlib.sha256(f"{routing.strip()}:{account.strip()}".encode()).hexdigest()


def domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower()


@dataclass
class Vendor:
    vendor_id: str
    name: str
    domain: str                 # known-good domain, captured before any request
    phone: str                  # pre-existing callback number from the vendor master
    account_fp: str
    last_bank_change: datetime


class VendorMaster:
    """Stand-in for the ERP vendor master and its enforcement sink."""
    def __init__(self, vendors: List[Vendor], cy: CyraductClient):
        self.v = {x.vendor_id: x for x in vendors}
        self.cy, self.pub = cy, cy.public_key()
        self.paid: List[tuple] = []

    def apply_bank_change(self, auth: Optional[Authorization], new_fp: str, human_approved=False):
        req = auth.request if auth else None
        ok, why = verify_at_sink(auth.receipt if auth else None, req or {}, self.pub, self.cy, human_approved) \
            if auth else (False, "no_receipt_presented")
        if ok:
            v = self.v[req["payload"]["vendor_id"]]
            v.account_fp, v.last_bank_change = new_fp, datetime.now(timezone.utc)
        return ok, why

    def pay(self, auth: Optional[Authorization], human_approved=False):
        if not auth:
            return False, "no_receipt_presented"
        ok, why = verify_at_sink(auth.receipt, auth.request, self.pub, self.cy, human_approved)
        if ok:
            self.paid.append((auth.request["payload"]["vendor_id"], auth.request["payload"]["amount"]))
        return ok, why


@dataclass
class ReviewRecord:
    """What a human actually did. Produced by the approval queue, never by the requester."""
    reviewer_id: Optional[str]
    callback_number_used: Optional[str]
    callback_verified: Optional[bool]
    approvers: List[str] = field(default_factory=list)


class FinanceGuard:
    def __init__(self, cy: CyraductClient, master: VendorMaster, agent_id="test-finance-guard"):
        self.cy, self.m, self.agent_id = cy, master, agent_id

    def _req(self, action, cclass, purpose, payload):
        return dict(agent_id=self.agent_id, principal="org:demo:finance", framework="custom",
                    action_type=action, consequence_class=cclass, purpose=purpose,
                    jurisdiction="US", policy_pack=PACK, payload=payload)

    def vendor_change_request(self, vendor_id, requested_by, new_routing, new_account, review: ReviewRecord):
        v = self.m.v[vendor_id]
        new_fp = fingerprint(new_routing, new_account)
        people = {p for p in [review.reviewer_id, *review.approvers] if p}
        payload = dict(
            vendor_id=vendor_id, requested_by=requested_by,
            old_account_fingerprint=v.account_fp, new_account_fingerprint=new_fp,
            new_beneficiary=new_fp != v.account_fp,
            sender_domain_match=domain_of(requested_by) == v.domain,
            callback_channel_preexisting=(review.callback_number_used == v.phone)
            if review.callback_number_used else None,
            callback_verified=review.callback_verified,
            reviewer_id=review.reviewer_id,
            dual_approval=len(people) >= 2,
        )
        payload = {k: x for k, x in payload.items() if x is not None}  # absent stays absent: fail-closed
        return self._go(self._req("update_vendor_bank_details", "vendor_master_change",
                                  "supplier payment-account update", payload)), new_fp

    def payment_request(self, vendor_id, amount, invoice, approvers: List[str], action="initiate_wire_transfer"):
        v = self.m.v[vendor_id]
        days = (datetime.now(timezone.utc) - v.last_bank_change).days
        payload = dict(vendor_id=vendor_id, amount=amount, invoice=invoice,
                       days_since_bank_change=days, dual_approval=len(set(approvers)) >= 2,
                       account_fingerprint=v.account_fp)
        return self._go(self._req(action, "financial_transfer", f"invoice {invoice}", payload))

    def _go(self, req):
        try:
            return self.cy.authorize(req)
        except ActionDenied as d:
            return d
