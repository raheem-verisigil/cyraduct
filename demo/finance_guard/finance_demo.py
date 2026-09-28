#!/usr/bin/env python3
"""
Finance Guard demo: vendor-bank-detail change fraud (BEC) and payment holds.

  python finance_demo.py --base-url http://localhost:8000

Exit code != 0 if any scene misbehaves. Writes finance_evidence.md/.json.
HONEST SCOPE: humans (reviewer, approvers, callback result) are simulated records; the ERP and bank
are in-memory stand-ins; no email is parsed. This proves the boundary, not the extraction.
"""
import argparse, json, os, sys
from datetime import datetime, timedelta, timezone
from finance_guard import (CyraductClient, ActionDenied, FinanceGuard, ReviewRecord, Vendor,
                           VendorMaster, fingerprint, PACK)
from cyraduct_guard import verify_signature

COLOR = sys.stdout.isatty()
c = lambda k, s: f"\033[{k}m{s}\033[0m" if COLOR else s
events, failures = [], 0


def scene(n, t):
    print(f"\n{c('1', f'== Scene {n}: {t}')}")
    events.append({"scene": n, "title": t, "steps": []})


def step(label, got, want, detail=""):
    global failures
    good = got == want
    failures += 0 if good else 1
    print(f"  [{c('32', 'PASS') if good else c('31', 'FAIL')}] {label}: {got}" + (f"  ({detail})" if detail else ""))
    events[-1]["steps"].append({"label": label, "outcome": str(got), "detail": detail, "as_expected": good})


def outcome(x):
    return ("deny" if isinstance(x, ActionDenied) else x.decision)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.getenv("CYRADUCT_URL", "http://localhost:8000"))
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    cy = CyraductClient(a.base_url)
    old = datetime.now(timezone.utc) - timedelta(days=200)
    master = VendorMaster([
        Vendor("V-ACME", "Acme Supplies Ltd", "acme.com", "+1-555-0100", fingerprint("021000021", "111222333"), old),
        Vendor("V-GLBX", "Globex Cloud Inc", "globex.com", "+1-555-0200", fingerprint("021000089", "444555666"), old),
    ], cy)
    fg = FinanceGuard(cy, master)

    scene(1, "Legitimate vendor bank change (known domain, callback to pre-existing number, two humans)")
    res, new_fp = fg.vendor_change_request("V-ACME", "ap@acme.com", "026009593", "999888777",
                                           ReviewRecord("u_391", "+1-555-0100", True, ["u_204"]))
    step("decision", outcome(res), "allow", f"receipt {res.receipt['receipt_id']}" if outcome(res) == "allow" else "")
    ok, why = master.apply_bank_change(res, new_fp)
    step("ERP applies change against receipt", (ok, why), (True, "ok"))
    step("receipt verifies offline with public key only", verify_signature(res.receipt, master.pub)[0], True)
    good_res, good_fp = res, new_fp

    scene(2, "BEC attack: lookalike domain, callback to number from the email, one rushed reviewer")
    before = master.v["V-GLBX"].account_fp
    res, atk_fp = fg.vendor_change_request("V-GLBX", "billing@globex-payments.co", "011000015", "000111222",
                                           ReviewRecord("u_391", "+1-555-6666", True, []))
    step("decision", outcome(res), "deny")
    step("matched rules", sorted(res.result["decision"]["matched_rules"]) if isinstance(res, ActionDenied) else [],
         ["fin.vendor.conditional.sender_domain_mismatch", "fin.vendor.deny.callback_channel_from_request",
          "fin.vendor.deny.new_beneficiary_no_dual_approval"],
         "; ".join(res.result["decision"]["reasons"]) if isinstance(res, ActionDenied) else "")
    ok, why = master.apply_bank_change(None, atk_fp)
    step("ERP refuses change with no receipt", (ok, why), (False, "no_receipt_presented"))
    step("vendor master unchanged", master.v["V-GLBX"].account_fp == before, True)

    scene(3, "Fail-closed: a caller omits the verification facts entirely")
    raw = dict(agent_id="test-finance-guard", action_type="update_vendor_bank_details",
               consequence_class="vendor_master_change", purpose="supplier payment-account update",
               jurisdiction="US", policy_pack=PACK, payload={"vendor_id": "V-GLBX", "new_account_fingerprint": atk_fp})
    r = cy.evaluate(raw)
    step("decision", r["decision"]["decision"], "deny", f"{len(r['decision']['matched_rules'])} required facts missing")
    step("no receipt issued", r["receipt"], None)

    scene(4, "Payment right after a bank change is held for a human")
    pay = fg.payment_request("V-ACME", 20000, "INV-4471", ["u_391", "u_204"])
    step("decision", outcome(pay), "conditional", "; ".join(pay.result["decision"]["reasons"]))
    step("bank refuses without escalation", master.pay(pay), (False, "conditional_receipt_requires_human_approval"))
    step("bank pays after named human escalation (stub)", master.pay(pay, human_approved=True), (True, "ok"))

    scene(5, "Normal payments flow; large wires need two people")
    step("20,000 wire to long-standing vendor", outcome(fg.payment_request("V-GLBX", 20000, "INV-77", ["u_391"])), "allow")
    step("150,000 wire, one approver", outcome(fg.payment_request("V-GLBX", 150000, "INV-78", ["u_391"])), "deny")
    step("150,000 wire, two approvers", outcome(fg.payment_request("V-GLBX", 150000, "INV-78", ["u_391", "u_204"])), "allow")

    scene(6, "Tampering: reuse the legitimate change receipt to redirect to a different account")
    forged = json.loads(json.dumps(good_res.request))
    forged["payload"]["new_account_fingerprint"] = atk_fp
    from cyraduct_guard import verify_at_sink
    step("sink rejects altered action", verify_at_sink(good_res.receipt, forged, master.pub, cy)[1], "action_binding_mismatch")

    receipts = cy.receipts_for("test-finance-guard")
    verified = sum(verify_signature(x, master.pub)[0] for x in receipts)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    md = [f"# Finance Guard evidence - {now}", f"Pack `{PACK}`  Agent `test-finance-guard`", ""]
    for e in events:
        md += [f"## Scene {e['scene']}: {e['title']}"] + [
            f"- {'OK' if s['as_expected'] else 'UNEXPECTED'} **{s['label']}**: {s['outcome']} {s['detail']}".rstrip() for s in e["steps"]] + [""]
    md += [f"{verified}/{len(receipts)} issued receipts verify against the public key. Raw bank details never left the adapter (fingerprints only).",
           "This is decision evidence, not a compliance certification."]
    open(os.path.join(a.out, "finance_evidence.md"), "w").write("\n".join(md) + "\n")
    json.dump({"generated": now, "events": events, "receipts": receipts, "public_key_b64": master.pub},
              open(os.path.join(a.out, "finance_evidence.json"), "w"), indent=2)
    print(f"\n{c('32', 'All scenes behaved as expected.') if not failures else c('31', f'{failures} unexpected result(s)')}"
          f"  Report: {a.out}/finance_evidence.md")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
