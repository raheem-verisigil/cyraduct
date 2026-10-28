# Live LangGraph E2E validation

This is a manual validation procedure for the optional LangGraph adapter. It must use a dedicated runtime credential and an Ed25519 public key/key ID obtained through a separately trusted channel.

## Safety boundary

- Use only the dedicated low-risk test identity and the `generic` policy pack.
- The executor must be an in-memory test sink. Do not connect a CRM, ticketing system, payment system, shell, or other external side-effecting tool.
- Never paste runtime credentials into chat, commit them, print them, or include them in artifacts.
- Do not trust a key solely because it was retrieved from the same endpoint being tested.
- Stop if the pinned key identity/fingerprint cannot be independently confirmed.

## Required cases

1. **Authenticated ALLOW:** Submit a low-risk test action to the production runtime endpoint through the LangGraph guarded tool. Confirm the response is `allow`, the receipt signature verifies against the independently pinned Ed25519 public key, the receipt binds to the exact action, and the in-memory executor runs exactly once.
2. **HOLD:** Submit the same harmless action with authority set to `missing`. Confirm the decision is `hold` and the executor call count does not increase.
3. **Unauthenticated request:** Send a harmless evaluation request without the runtime credential. Confirm HTTP 401 and no executor call.
4. **Tampered evidence:** In the existing local integration test suite, tamper with the receipt/action binding or signature and confirm the guarded executor is not called. Do not tamper with production responses or attempt production execution.
5. **Key pinning:** Independently compare the key ID and SHA-256 fingerprint against an owner-controlled source outside the production endpoint before trusting the key for remote receipt verification.

## Evidence to record

Record the tested main commit SHA, deployment ID, timestamp (UTC), API base URL, pinned key ID and fingerprint, case outcomes, receipt ID for the ALLOW case, and limitations. Never record the runtime API key or private signing material.

## Current status

The repository's automated integration tests run the app in-process and use a harmless executor. The production smoke workflow checks health, the public-key response structure, and that missing runtime credentials are rejected. These checks are not, by themselves, proof of a live authenticated LangGraph ALLOW/HOLD round trip.

A completed E2E claim requires the above live cases to actually run and their results to be retained. Do not mark the system production-certified based on this procedure alone.
