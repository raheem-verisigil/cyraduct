#!/usr/bin/env python3
"""
Cyraduct production conformance fixture.

Unlike tests/test_conformance.py (which runs in-process against a test
client), this script runs against a REAL deployed API over the network.
It is the reproducible artifact behind claims like "the broker rejects a
revoked receipt in production" — anyone, including a skeptical customer
or auditor, can run this themselves against the live URL and see the
same result, rather than trusting a screenshot from one manual session.

Usage:
    python3 production_fixture.py [--base-url https://api.cyraduct.com]

Exits with code 0 if every check passes, 1 otherwise — safe to wire into
a CI job or a scheduled health check later.

SAFETY NOTE: this script creates real receipts and a real (harmless)
kill-switch toggle against whatever URL you point it at. It always
restores the kill switch to inactive when done, including on failure,
so it is safe to run repeatedly against production. It requires your
real CYRADUCT_ADMIN_KEY as an environment variable — it is never
hardcoded or printed.
"""
import argparse
import os
import sys
import time
import uuid

import httpx


class Fixture:
    def __init__(self, base_url: str, admin_key: str):
        self.base_url = base_url.rstrip("/")
        self.admin_key = admin_key
        self.client = httpx.Client(timeout=15.0)
        self.results = []

    def _record(self, name: str, passed: bool, detail: str = ""):
        self.results.append({"name": name, "passed": passed, "detail": detail})
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}" + (f" — {detail}" if detail and not passed else ""))

    def _agent_id(self, label: str) -> str:
        return f"prodfix-{label}-{uuid.uuid4().hex[:8]}"

    def _post(self, path: str, **kwargs):
        return self.client.post(f"{self.base_url}{path}", **kwargs)

    def _get(self, path: str, **kwargs):
        return self.client.get(f"{self.base_url}{path}", **kwargs)

    # ---- individual checks -------------------------------------------------

    def check_health(self):
        r = self._get("/healthz")
        self._record("API is reachable and healthy", r.status_code == 200 and r.json().get("status") == "ok",
                      f"status={r.status_code}")

    def check_public_key_present(self):
        r = self._get("/v1/public-key")
        ok = r.status_code == 200 and r.json().get("alg") == "Ed25519" and len(r.json().get("public_key_b64", "")) > 0
        self._record("Public key endpoint returns a real Ed25519 key", ok, f"status={r.status_code}")

    def check_published_conformance_suite(self):
        r = self._post("/v1/conformance/run")
        ok = r.status_code == 200 and r.json().get("all_passed") is True
        negatives = [x for x in r.json().get("results", []) if x.get("type") == "negative"]
        ok = ok and len(negatives) >= 3
        self._record("Published fixture suite passes (positive + negative cases)", ok,
                      f"status={r.status_code}, all_passed={r.json().get('all_passed') if r.status_code==200 else 'n/a'}")

    def check_attested_issues_valid_receipt(self):
        agent_id = self._agent_id("attested")
        r = self._post("/v1/attested/evaluate", json={
            "agent_id": agent_id, "action_type": "read_public_doc",
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
        })
        body = r.json() if r.status_code == 200 else {}
        receipt = body.get("receipt")
        ok = r.status_code == 200 and body.get("decision", {}).get("decision") == "allow" and receipt is not None
        self._record("Attested tier issues a signed receipt on allow", ok, f"status={r.status_code}")
        return receipt

    def check_receipt_verifies(self, receipt):
        if not receipt:
            self._record("Receipt verifies as valid", False, "no receipt from prior step")
            return
        r = self._get(f"/v1/attested/verify/{receipt['receipt_id']}")
        ok = r.status_code == 200 and r.json().get("valid") is True
        self._record("Receipt verifies as valid immediately after issuance", ok, f"status={r.status_code}")

    def check_broker_accepts_valid_receipt(self, receipt):
        if not receipt:
            self._record("Broker accepts a valid, matching receipt", False, "no receipt from prior step")
            return
        # Use example.com — a real, IANA-owned, always-resolvable domain
        # reserved for documentation use — as the sink. It's real enough to
        # pass the SSRF check and prove an execution attempt actually
        # happens, but harmless: nobody's real infrastructure sits behind
        # it, and it returns a simple static page rather than doing anything.
        r = self._post("/v1/broker/execute", params={
            "receipt_id": receipt["receipt_id"],
            "execution_webhook": "https://example.com/",
        }, json={
            "agent_id": receipt["agent"]["agent_id"], "action_type": receipt["action"]["type"],
            "consequence_class": receipt["action"]["consequence_class"], "policy_pack": "generic", "payload": {}
        })
        body = r.json() if r.status_code == 200 else {}
        # It should pass every validation gate and attempt execution (which then
        # fails at the network level against example.invalid — that's expected
        # and is what proves this tested authorization, not delivery).
        reached_execution_attempt = body.get("execution_result") is not None
        self._record("Valid receipt reaches an execution attempt (authorization proven, not delivery)",
                      r.status_code == 200 and reached_execution_attempt, f"status={r.status_code}")

    def check_broker_rejects_revoked_receipt(self):
        agent_id = self._agent_id("revoke")
        ev = self._post("/v1/attested/evaluate", json={
            "agent_id": agent_id, "action_type": "read_public_doc",
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
        }).json()
        receipt = ev.get("receipt")
        if not receipt:
            self._record("Broker rejects a revoked receipt", False, "could not issue receipt to revoke")
            return

        revoke_r = self._post(f"/v1/attested/revoke/{receipt['receipt_id']}",
                               headers={"X-Cyraduct-Admin-Key": self.admin_key})
        if revoke_r.status_code != 200:
            self._record("Broker rejects a revoked receipt", False, f"revoke call failed: {revoke_r.status_code}")
            return

        r = self._post("/v1/broker/execute", params={
            "receipt_id": receipt["receipt_id"],
            "execution_webhook": "https://example.invalid/sink",
        }, json={
            "agent_id": agent_id, "action_type": "read_public_doc",
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
        })
        body = r.json() if r.status_code == 200 else {}
        ok = r.status_code == 200 and body.get("executed") is False and body.get("reason") == "receipt_revoked"
        self._record("Broker rejects a revoked receipt before execution", ok,
                      f"status={r.status_code}, reason={body.get('reason')}")

    def check_broker_rejects_action_mismatch(self):
        agent_id = self._agent_id("mismatch")
        ev = self._post("/v1/attested/evaluate", json={
            "agent_id": agent_id, "action_type": "read_public_doc",
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
        }).json()
        receipt = ev.get("receipt")
        if not receipt:
            self._record("Broker rejects action/agent mismatch", False, "could not issue receipt")
            return

        r = self._post("/v1/broker/execute", params={
            "receipt_id": receipt["receipt_id"],
            "execution_webhook": "https://example.invalid/sink",
        }, json={
            "agent_id": agent_id, "action_type": "wire_transfer",  # deliberately different from the receipt
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
        })
        body = r.json() if r.status_code == 200 else {}
        ok = r.status_code == 200 and body.get("executed") is False and body.get("reason") == "action_binding_mismatch"
        self._record("Broker rejects a receipt presented against a mismatched action", ok,
                      f"status={r.status_code}, reason={body.get('reason')}")

    def check_broker_rejects_unsafe_webhook(self):
        agent_id = self._agent_id("ssrf")
        ev = self._post("/v1/attested/evaluate", json={
            "agent_id": agent_id, "action_type": "read_public_doc",
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
        }).json()
        receipt = ev.get("receipt")
        if not receipt:
            self._record("Broker rejects an unsafe (private-network) webhook", False, "could not issue receipt")
            return

        r = self._post("/v1/broker/execute", params={
            "receipt_id": receipt["receipt_id"],
            "execution_webhook": "https://169.254.169.254/latest/meta-data/",
        }, json={
            "agent_id": agent_id, "action_type": "read_public_doc",
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
        })
        body = r.json() if r.status_code == 200 else {}
        ok = r.status_code == 200 and body.get("executed") is False and "unsafe_execution_webhook" in str(body.get("reason", ""))
        self._record("Broker rejects a webhook pointing at a private/reserved address (SSRF)", ok,
                      f"status={r.status_code}, reason={body.get('reason')}")

    def check_kill_switch_blocks_and_restores(self):
        if not self.admin_key:
            self._record("Kill switch blocks attested evaluation while active", False, "no admin key provided — skipped")
            return
        on = self._post("/v1/admin/kill-switch", json={"active": True, "reason": "production_fixture_test"},
                         headers={"X-Cyraduct-Admin-Key": self.admin_key})
        if on.status_code != 200:
            self._record("Kill switch blocks attested evaluation while active", False, f"could not activate: {on.status_code}")
            return

        blocked = self._post("/v1/attested/evaluate", json={
            "agent_id": self._agent_id("killswitch"), "action_type": "read_public_doc",
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
        })
        ok = blocked.status_code == 503

        # ALWAYS restore, regardless of the check result above.
        off = self._post("/v1/admin/kill-switch", json={"active": False, "reason": None},
                          headers={"X-Cyraduct-Admin-Key": self.admin_key})
        restored = off.status_code == 200 and off.json().get("active") is False

        self._record("Kill switch blocks attested evaluation while active", ok, f"blocked_status={blocked.status_code}")
        self._record("Kill switch correctly restored to inactive afterward", restored, f"status={off.status_code}")

    def check_audit_chain_valid(self):
        if not self.admin_key:
            self._record("Audit log hash chain is unbroken", False, "no admin key provided — skipped")
            return
        r = self._get("/v1/admin/audit-log", headers={"X-Cyraduct-Admin-Key": self.admin_key})
        ok = r.status_code == 200 and r.json().get("chain_valid") is True
        self._record("Audit log hash chain is unbroken", ok, f"status={r.status_code}")

    # ---- runner --------------------------------------------------------

    def run_all(self):
        print(f"Running Cyraduct production conformance fixture against {self.base_url}\n")

        self.check_health()
        self.check_public_key_present()
        self.check_published_conformance_suite()

        receipt = self.check_attested_issues_valid_receipt()
        self.check_receipt_verifies(receipt)
        self.check_broker_accepts_valid_receipt(receipt)

        self.check_broker_rejects_revoked_receipt()
        self.check_broker_rejects_action_mismatch()
        self.check_broker_rejects_unsafe_webhook()

        self.check_kill_switch_blocks_and_restores()
        self.check_audit_chain_valid()

        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        print(f"\n{passed}/{total} checks passed against {self.base_url}")

        if passed != total:
            print("\nFailures:")
            for r in self.results:
                if not r["passed"]:
                    print(f"  - {r['name']}: {r['detail']}")

        return passed == total


def main():
    parser = argparse.ArgumentParser(description="Cyraduct production conformance fixture")
    parser.add_argument("--base-url", default=os.environ.get("CYRADUCT_BASE_URL", "https://api.cyraduct.com"))
    args = parser.parse_args()

    admin_key = os.environ.get("CYRADUCT_ADMIN_KEY", "")
    if not admin_key:
        print("WARNING: CYRADUCT_ADMIN_KEY not set — kill-switch and audit-log checks will be skipped.\n"
              "Set it as an environment variable (never on the command line) to run the full suite:\n"
              "  export CYRADUCT_ADMIN_KEY=your-real-key   (Mac/Linux/Git Bash)\n")

    fixture = Fixture(args.base_url, admin_key)
    all_passed = fixture.run_all()
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
