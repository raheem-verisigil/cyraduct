# NCS terminology reconciliation — v0.1

This note prevents adjacent drafts from silently creating competing names for the same measurement.

## Canonical terms for the runner milestone
- **Native Conduct Baseline (NCB):** observed conduct under the documented baseline condition. Provider-native instructions and safeguards remain in place and are recorded.
- **Policy-Fit Assessment:** comparison of observed conduct against a versioned organisation policy and its testable requirements.
- **Conduct Delta:** measured change between comparable baseline and policy-configured conditions. Attempt-level and effect-level outcomes remain distinct.
- **Effective-System Assessment:** observed outcome with the declared controls and execution environment in place.
- **Experiment Record:** privacy-minimised, signed record of run identity, aggregate outcomes, uncertainty and evidence-manifest linkage. A signature authenticates the record's origin/integrity, not the truth of the observations.

## Earlier draft labels
The existing NCP design uses NBB (Native Behavior Baseline), PDP (Policy Delta Profile) and ECP (Effective Conduct Profile). These are treated as legacy draft labels pending a formal terminology decision. They must not be mixed into public APIs or schemas as aliases without a versioned migration decision.

## Capability separation
The broad ten-dimension NCP is not part of the first runner's mandatory grading scope. The Assessment Learner decision controls: capability-lite features may be retained only when empirically shown to improve policy-failure prediction over the conduct profile alone. Capability and conduct remain separate tracks; capability cannot raise or erase a conduct result.

## Important boundary
"Native" does not mean removal or bypass of provider-native safeguards. The assessment records the actual provider baseline. A runner digest is not a digital signature, and a local test pass is not an assurance certificate.
