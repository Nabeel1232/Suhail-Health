# Evaluation data and scoring provenance

Default datasets contain project-generated fictional participants and permitted public HealthBench conversations only. Credentialed MIMIC data and MedAgentBench records are excluded from the default remote path.

HealthBench repository: https://huggingface.co/datasets/openai/healthbench. Pinned revision `40ee1968852fc57f625934251ac22be47077a8fb`; upstream dataset card declares MIT. Standard `2025-05-07-06-14-12_oss_eval.jsonl`, SHA256 `e99dd3c6372c10d6fcc5e385c5fae69d0dd40392dae56836ef9493ae324ecd2f`, 5,000 examples. Cache contains the exact upstream card and selection/schema inspection manifests; run manifests include revision, checksum, card license, selected original IDs, and actual tags.

Scoring reference: `openai/simple-evals`, pinned commit `652c89d0ca9df547706735883097e9537d40dc47`, `healthbench_eval.py`. Signed-weight aggregation is adapted in `healthbench.py`: sum weights of met criteria divided by total positive weights, with clipping of the aggregate mean only. Preserve negative weights. The MIT notice is preserved in `third-party/SIMPLE_EVALS_LICENSE`.

Groq grading and batched rubric requests make this an adapted HealthBench evaluation. It is not the official overall score. Candidate conversations never contain rubric answers. Automated rubric estimates and deterministic application assertions are separate evidence layers.
