# NCS OpenAI Provider Runbook (v0.1)

Status: adapter implementation present in the NCS experiment harness; live provider execution is pending a user-created API key and exact model selection.

## Provider contract

The harness uses the OpenAI-compatible Chat Completions interface:
- Base URL: `https://api.openai.com/v1`
- Request path: `/chat/completions`
- Authentication: server-side `Authorization: Bearer $OPENAI_API_KEY`
- Model identifier: explicit CLI argument; record the exact returned model identifier in the run evidence.

The adapter must never write the API key to run manifests, transcripts, logs, or Git.

## Required environment

Set these only in the runner's secure environment:
- `OPENAI_API_KEY` — secret API key created in the OpenAI API Platform.
- Do not commit a `.env` containing the key.
- Do not pass the key as a command-line argument.

## First live smoke test

Use a small development-only subset first. Do not use the held-out set for adapter debugging.

```bash
export OPENAI_API_KEY='(set securely in your shell or secret manager)'
python -m ncs_exp run \
  --provider openai \
  --base-url https://api.openai.com/v1 \
  --model '<exact model identifier>' \
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

Then inspect transcripts and verify the evidence:

```bash
python -m ncs_exp verify runs/openai-smoke --cases build/dev_cases.jsonl
python -m ncs_exp summarize runs/openai-smoke
```

A successful smoke test only establishes that the adapter can execute this limited sample and produce verifiable run evidence. It does not validate the policy oracles, establish model safety, or count as the preregistered experiment.

## Before the full experiment

1. Confirm model access, exact model ID, project budget/spend limit and API rate limits.
2. Run the smoke test and inspect errors, tool calls, transcripts, output truncation and observed model ID.
3. Validate heuristic oracles against hand-labelled outputs. Keep judge-required rules unresolved until their separate validation threshold is met.
4. Freeze and hash the arms, case suite, runner version and configuration before any held-out evaluation.
5. Use the preregistration's held-out protocol only after all development and adapter debugging are complete.

## Safety and evidence boundaries

- Never store API keys in the repository, experiment records or evidence manifests.
- Do not include raw prompts, customer data or raw model outputs in learner Experiment Records.
- Do not describe a smoke test as a completed benchmark.
- Do not set `--pinned` unless the provider/model version is genuinely pinned. Otherwise the evidence must disclose that limitation.
- OpenAI API usage is billed separately from a ChatGPT subscription; set a project budget/alert before running.
