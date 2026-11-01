# NCS ↔ Langfuse connector (experimental 0.1)

This is a read-only connector for Langfuse v4+ using the supported Observations API v2. It does not use Langfuse prompt-version webhooks as a substitute for model failure telemetry.

## Data flow

1. Instrument the AI application so Langfuse observations carry an explicit NCS artifact digest in observation metadata: `ncs.artifact.sha256`.
2. The connector polls bounded UTC time windows from `GET /api/public/v2/observations` for ERROR/WARNING spans and `GET /api/public/v3/scores` for explicit evaluation failures. It requests only core/basic/metadata/model/trace-context fields for observations and details/subject for scores.
3. ERROR and WARNING observations, plus explicitly failed boolean/categorical evaluation scores, are normalized to `ncs-failure-evidence/0.1`. Numeric scores are ignored unless a future version defines a validated threshold contract.
4. Rows with no valid artifact digest are quarantined, never guessed from model name, release, or version.
5. Every emitted event remains `source_integrity=unverified`, `grade_eligible=false`. Langfuse API Basic Auth proves permission to read the project, not cryptographic authorship or artifact identity.
6. Evaluation score rows are treated as detector outputs, not proof of a failure. Only explicit failed values are emitted; all remain unverified until separately attested. NCS rule decisions remain recommendations. This connector does not execute containment or change certificate state.

## Install and configure

The repository requirements already include `httpx`. Set these in the poller's secret environment (never commit them):

- `LANGFUSE_BASE_URL` — e.g. `https://cloud.langfuse.com` for EU, `https://us.cloud.langfuse.com` for US, or your self-hosted HTTPS origin.
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`

The API key needs read access to traces/observations. Use a dedicated least-privilege project key. The secret key is never returned in logs or output.

## Instrumentation contract

Attach `ncs.artifact.sha256` to each relevant observation's metadata. It must be the lowercase SHA-256 digest of the exact model artifact assessed by NCS, not a model display name or mutable deployment label. Optional metadata keys:

- `ncs.failure.category`: one of the NCS failure taxonomy values.
- `ncs.failure.severity`: info/low/medium/high/critical.
- `ncs.failure.status`: suspected/observed/confirmed/refuted.

Without the digest, the connector quarantines the observation. Without explicit failure category, it defaults to reliability. It does not read or persist prompts, completions, tool arguments, or raw exception messages. It hashes a minimized identity/metadata projection and retains only a bounded error-type token.

## Run a bounded poll

```bash
export LANGFUSE_BASE_URL="https://cloud.langfuse.com"
export LANGFUSE_PUBLIC_KEY="..."
export LANGFUSE_SECRET_KEY="..."
python -m ncs_harness.langfuse_connector \
  --from 2026-11-01T00:00:00Z \
  --to 2026-11-02T00:00:00Z
```

Output is JSON to stdout. It contains normalized events and quarantine counts. Store it only in a protected evidence store; do not attach raw customer data.

## Production limitations

This first connector is polling-only and read-only. It does not yet provide durable cursor checkpoints, idempotency storage, score API v3 ingestion, a scheduled worker, encrypted event persistence, or independently governed Ed25519 key registration/rotation/revocation. It must be deployed behind a controlled worker identity and tested against a non-production Langfuse project before production use.


## GitHub Actions dry-run connection

The repository includes a separate manual-only workflow at `.github/workflows/ncs-langfuse-readonly.yml`. It does not run on push or pull request and does not write to Langfuse. It requires these GitHub Actions secrets:

- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`

Optional repository variable:

- `LANGFUSE_BASE_URL` (defaults to the Langfuse EU Cloud URL shown above; set the US, Japan, HIPAA or self-hosted HTTPS origin as appropriate).

Add them under GitHub repository **Settings → Secrets and variables → Actions**. Never put the values in source files, issues, pull requests or chat. The workflow takes explicit ISO-8601 start/end bounds, performs a read-only poll, and prints only aggregate counts plus a digest of the event set. It does not print or persist event payloads. Run it first against a dedicated non-production Langfuse project.
