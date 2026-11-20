# Reproduce 20261120T135507Z-offline

All metrics render from immutable cases.jsonl and provider-calls.jsonl.

```sh
python -m evals.runner reports --run-id 20261120T135507Z-offline
python -m evals.runner validate --run-id 20261120T135507Z-offline
```

Use a new run ID for new inference. Rebuilding reports never calls a model or alters execution timestamps. Source hashes, selected cases, exact commands, model, prompts, RAG and dataset revisions are in manifest.json.
