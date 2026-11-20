# Reproduce groq-smoke-holdout-v1

All metrics render from immutable cases.jsonl and provider-calls.jsonl.

```sh
python -m evals.runner reports --run-id groq-smoke-holdout-v1
python -m evals.runner validate --run-id groq-smoke-holdout-v1
```

Use a new run ID for new inference. Rebuilding reports never calls a model or alters execution timestamps. Source hashes, selected cases, exact commands, model, prompts, RAG and dataset revisions are in manifest.json.
