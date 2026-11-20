# Reproduce software-delivery-final

All metrics render from immutable cases.jsonl and provider-calls.jsonl.

```sh
python -m evals.runner reports --run-id software-delivery-final
python -m evals.runner validate --run-id software-delivery-final
```

Use a new run ID for new inference. Rebuilding reports never calls a model or alters execution timestamps. Source hashes, selected cases, exact commands, model, prompts, RAG and dataset revisions are in manifest.json.
