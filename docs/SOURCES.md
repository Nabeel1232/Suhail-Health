# Implementation sources

Checked 14 November 2026. Recheck model availability and capability documentation when implementing. Dataset access, software license and permission to send data to a hosted model are separate questions.

| Topic | Primary source | Implementation consequence |
| --- | --- | --- |
| Groq tool calling | https://console.groq.com/docs/tool-use/overview | Application-controlled local tool loop; verify each model's capabilities. |
| Structured outputs | https://console.groq.com/docs/structured-outputs | Current docs exclude combining strict structured outputs with tools/streaming; use separate modes. |
| Models | https://console.groq.com/docs/models | Verify actual account access and pin the selected model; do not silently substitute a benchmark model. |
| Rate limits | https://console.groq.com/docs/rate-limits | Respect actual limits, finite backoff and retry-after; budget every call. |
| Provider data handling | https://console.groq.com/docs/your-data | Check actual settings and terms; do not infer restricted-data permission from API access. |
| HealthBench data | https://huggingface.co/datasets/openai/healthbench | Public dataset card is MIT; pin files/revision and retain notices. |
| HealthBench evaluator | https://github.com/openai/simple-evals/blob/main/healthbench_eval.py | Preserve signed rubric weights and aggregation. Different grader/subset means adapted evaluation. |
| Synthea | https://github.com/synthetichealth/synthea | Apache 2.0 software generating synthetic records; integration fixtures are not clinical efficacy evidence. |
| MedAgentBench implementation | https://github.com/stanfordmlgroup/MedAgentBench | Research FHIR environment; code license does not settle data/container cloud-processing permissions. |
| MedAgentBench provenance | https://stanfordmlgroup.github.io/projects/medagentbench/ | Describes real-case profiles from deidentified STARR records with jittered timestamps. Do not label all data synthetic. |
| Restricted MIMIC data | https://physionet.org/news/post/llm-responsible-use/ | Restricted data stay outside the default Groq path; processing conditions must be established separately. |
| MIMIC-IV-ED | https://physionet.org/content/mimic-iv-ed/2.2/ | Optional credentialed retrospective research, not the default application benchmark. |
| Competition | https://hack2skill.com/event/futurehealthchallenge/ | Verify submission formats and cutoff; no particular model platform is mandatory on the public page. |

The owner-supplied Challenge 05 statement controls the product. `PRODUCT_SPEC.md` preserves its six requirements and acceptance contracts. Benchmarks are research/evaluation resources, not endorsements, certifications or regulatory approvals.

Before distributing external benchmark data or code, save the exact upstream license/notices and release conditions. Store code and data licenses separately in the dataset manifest. Do not assign an open-source license to the owner's application or logo unless the owner chooses one.
