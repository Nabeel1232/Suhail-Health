# Suhail Health Codex build package

Use this package to have Codex implement the complete Challenge 05 application, verify the patient and staff journeys, and generate reports from actual benchmark execution. It contains requirements, implementation prompts, dataset instructions and reusable branding assets. It is not a built application or a claim that any model evaluation has already run.

## Start

1. Extract this package into, or next to, your application repository.
2. Open that repository in Codex. Provide the absolute paths to this package, the project directory, your existing `.env` file and your logo. The original logo is also included at `brand/logo-original.png`.
3. Replace the path placeholders at the top of `CODEX_BUILD_PROMPT.md`, then give Codex its complete contents. That prompt authorizes implementation, local execution, fixes and bounded live Groq evaluations. The API key belongs only in your environment file.
4. Codex should continue through all build stages. If a new session is needed, use the resume prompt in `docs/BUILD_STAGES.md`.

The shortest launch instruction is:

```text
Implement the complete Suhail Health application using CODEX_BUILD_PROMPT.md in this package.
PROJECT_ROOT: /absolute/path/to/application
BUILD_PACK_PATH: /absolute/path/to/Suhail_Codex_Build_Pack
ENV_FILE_PATH: /absolute/path/to/private/.env
LOGO_FILE_PATH: /absolute/path/to/logo.png
Read the prompt and its referenced specifications, then build, run, verify and benchmark the application. Continue through the checkpoints; do not stop after planning. Keep secrets server-side and produce measured reports with explicit blocked or partial statuses when necessary.
```

## Package map

- `CODEX_BUILD_PROMPT.md`: the main end-to-end implementation instruction.
- `docs/PRODUCT_SPEC.md`: the Challenge 05 product contract, updated for Groq.
- `docs/BUILD_STAGES.md`: staged build, resume, repair and final-audit prompts.
- `docs/CUSTOMER_EXPERIENCE.md`: complete patient, clinician, navigator, provider and operator journeys.
- `docs/BENCHMARK_PROTOCOL.md`: six agent evaluations, end-to-end comparisons, actual report requirements and budget rules.
- `evals/dataset-registry.yaml`: intended data sources, access conditions and matching agent tasks.
- `evals/report.schema.json`: an example machine-readable report contract for Codex to implement and extend.
- `brand/BRAND_GUIDE.md`, `brand/theme.css`, `brand/tokens.json`: the visual system and usage guidance.
- `brand/*.svg`: additional navigation-star icons, journey motif and share card; these are not vector recreations of the supplied logo.
- `brand/logo-original.png`: unchanged supplied logo.
- `.env.example`: secret-free configuration template.
- `docs/SOURCES.md`: checked documentation and benchmark provenance.

## Expected result

A working local web application with a database, authentication, roles, provider simulators, Groq-backed agents, RAG, complete patient/staff flows, executable tests and actual benchmark/report commands. A public URL requires a deployment destination; without one, Codex should provide a tested container deployment and explicit hosting instructions rather than claim the application is published.

Expert review remains optional and separate. Synthetic workflow results, adapted public-benchmark scores, software tests and future clinical evidence must remain distinguishable.
