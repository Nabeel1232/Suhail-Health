# Data and evidence card

| Source | Actual use | Revision/license | Interpretation |
|---|---|---|---|
| Project synthetic v1 | Named demo records, FHIR fixtures, software trajectories, agent/conversation context and known scenario truth | Project-generated; exact generator/source hashes and seeds in each run | Fictional participants; operational demonstration, not clinical ground truth. IDs/seeds differ but known family/template structures overlap. |
| Project synthetic v2 | Future family-separated generator and software checks | Explicit v2 module/version, independent source-format/context-family splits | Prepared/tested; no new live v2 model score claimed in this delivery. |
| Public HealthBench | Declared twelve-example selection; two candidate+grader conversations completed in original smoke budget | `openai/healthbench` revision `40ee1968852fc57f625934251ac22be47077a8fb`; MIT card; file SHA256 `e99dd3c6372c10d6fcc5e385c5fae69d0dd40392dae56836ef9493ae324ecd2f` | Original IDs/conversations/signed rubrics retained; candidate never receives rubric answers. Adapted subset/Groq grader estimate. |
| Reference HealthBench evaluator | Signed-weight and aggregate-clipping method inspected; MIT notice retained | `openai/simple-evals` commit `652c89d0ca9df547706735883097e9537d40dc47` | Batched Groq grading differs from the original protocol. |
| Synthea | Not run; project-generated FHIR used instead | Apache2software; current source inspected, not an evaluated pinned dataset | HostJava11does not satisfy current upstreamJava17+requirement. Optional future step: provide supportedJava, pin release/commit and retain notices before generation. |
| MedAgentBench | BLOCKED, no remote records used | Separate data/cloud rights, original FHIR container and scoring dependency unverified | Do not assume real-record-derived profiles are wholly synthetic or that code licensing grants data-processing rights. |
| MIMIC-IV-ED | Disabled, no remote records used | Credentialing/training/data-use conditions not supplied | Outside the default Groq data path. |

Knowledge retrieval uses a small versioned source pack with authority, jurisdiction, effective/expiry dates, language, access scope and exact section citations. Published colorectal guidance is separated from synthetic operational windows and unreviewed English/Arabic templates. Source filtering precedes FTS indexing/ranking. The pack does not supply diagnoses or inferred clinical deadlines.

Download caches are ignored. Dataset manifests, selected IDs, licenses/notices and checksums are preserved in `evals/third-party/` and report artifacts. Provider-call ledgers contain only permitted synthetic/public inputs and sanitized outputs/errors. Owner credentials, runtime application credentials and restricted records are excluded from source snapshots and reports. Private database backup files stay in ignored `.runtime/`.

No live EHR, Malaffi, NABIDH or Riayati data, real patient notification, external expert review, clinical outcome study or medical/regulatory approval is claimed.
