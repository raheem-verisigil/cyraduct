# NCS OpenAI Provider Runbook (v0.2)

Status: the uploaded `ncs_experiment_harness.zip` already contains a standard-library OpenAI-compatible Chat Completions adapter. Its original adapter had not been tested against a live provider. The hardening patch linked below was applied to a working copy and passed the full local test suite; it has not yet been merged into the uploaded ZIP or the separate provider-neutral `week2_runner` prototype.

## Provider contract

- Base URL: `https://api.openai.com/v1`
- Request path: `/chat/completions`
- Authentication: `Authorization: Bearer $OPENAI_API_KEY`
- Model: pass an exact model ID explicitly; capture the provider-returned model ID.
- The key must never appear in source code, CLI arguments, manifests, transcripts or logs.

## Secret setup

Create an API key at https://platform.openai.com/api-keys. Configure API billing and a project spending limit. Set `OPENAI_API_KEY` in the shell or secret manager used by the runner. Do not paste it into chat or commit it to Git.

## Development-only smoke test

Run from the extracted `ncs_exp/` project root, after setting the secret in the runner environment. Replace the model placeholder with an exact model ID enabled for your API project.

```bash
python -m ncs_exp run \
  --provider openai \
  --base-url https://api.openai.com/v1 \
  --model '<exact-model-id>' \
  --cases build/dev_cases.jsonl \
  --data-dir build \
  --arm arms/none.json \
  --out runs/openai-smoke \
  --rules A1 \
  --conditions normal \
  --limit 5 \
  --temperature 0 \
  --max-tokens 1000 \
  --workers 1
```

Then verify and inspect the run:

```bash
python -m ncs_exp verify runs/openai-smoke --cases build/dev_cases.jsonl
python -m ncs_exp summarize runs/openai-smoke
```

Do not add `--pinned` unless the provider's exact model version is genuinely fixed and evidenced. The model name alone does not prove an immutable backend snapshot.

## Adapter hardening completed in working copy

The patch at [openai-adapter-hardening.patch](patches/openai-adapter-hardening.patch) makes the following changes:
- Fails early if the official OpenAI endpoint is selected without `OPENAI_API_KEY`.
- Validates that the base URL is absolute HTTP(S).
- Treats missing/empty provider choices as a provider error.
- Supports text-block content arrays returned by some compatible endpoints.
- Rejects malformed or non-object tool-call JSON instead of silently converting it to an empty argument object.
- Closes CLI file handles explicitly, eliminating the ResourceWarning observed in the prior test run.
- Adds regression tests for missing credentials, malformed tool arguments and empty provider responses.

Local verification on the modified working copy: **64 tests passed**, including a strict ResourceWarning check. This is adapter/unit and mock verification only; no live OpenAI request has been made.

## Before a full assessment

1. Run the five-case development smoke test.
2. Inspect transcripts, tool-call arguments, provider errors, observed model ID and token/usage metadata where available.
3. Hand-label outputs to validate the heuristic oracles; keep judge-required rules unresolved until their preregistered validation threshold is met.
4. Freeze and hash the suite, policy arms, runner and configuration.
5. Only then begin the preregistered held-out experiment. Do not use held-out cases for adapter debugging.

## Evidence limits

A smoke test verifies only that the limited request/response path works and produces evidence. It is not a model safety result, a policy-fit conclusion, or a completed benchmark. The existing harness still has known oracle limitations and its signed manifest does not by itself establish signer identity.
