# Suhail bounded agent model card

## Executed candidate

- Provider: Groq, official SDK / compatible chat-completions endpoint.
- Exact candidate and adapted rubric grader: `openai/gpt-oss-120b`. Account access also exposed120b/20bcandidates; only the configured120b was benchmarked. No silent model substitution occurred.
- Sampling: temperature0; no streaming. Owner output cap1500tokens. Provider-managed quantization and internal serving configuration are not disclosed.
- Structured proposal/extraction uses strict JSON Schema without tools. Local tool mode uses a separate prompt/request and a sequential, role/case-version checked allowlist. The final schema request is separate. No provider browsing, arbitrary code, SQL, shell or remote MCP is enabled for clinical functions.
- Functions: intake, pathway router, safety/escalation, patient navigator, coordination and closure-evidence assistance. They prepare proposals, drafts and source references. They do not diagnose, prescribe, resolve uncertain identity, authorize urgency disposition, waive evidence or close care.
- PostgreSQL LangGraph checkpoints preserve a human-review pause. Recording review does not mutate clinical state; an authorized application command rechecks the current case independently.

## Structured patient identifiers

The bounded proposal route replaces the structured patient name and ID with stable, organization-scoped tokens before sending the initial case snapshot or a `read_case` tool response to the model. Structured patient IDs in evidence and experience records use the same mapping, which preserves equality checks against the case. This control covers those structured fields on the proposal path. Clinical free text needs its own minimization and review before deployment. [Proposal route](../services/agents/routes.py) · [Agent tests](../tests/test_agents.py)

## Actual evaluation evidence

The immutable primary run is `reports/runs/groq-smoke-holdout-v1/`. It selected36standalone function cases,18A/B/Carmrecords(sixselectedCjourneys), and12public adapted HealthBench conversations. Terminal primary counts are66selected,52attempted,44evaluated,8execution/scoringfailed and14skipped. All36standalone candidate responses exist; sixArabic scoring errors are retained in primary results and re-evaluated in a separately versioned audit with zero new inference. That audit observed five correct and one incorrect result; the intake example failed to flag an empty order identifier in missing_fields. Authoritative intake requires a valid nonempty order and never infers identity from the proposal.

One valid independent A/B/Cpair completed allsixCfunction calls and the actual persisted care endpoint. An earlier shared-store comparison failed because backend patient/order deduplication correctly coupled its arms; those failed attempts remain visible. Two adapted HealthBench conversations have actual candidate and rubric-grader responses. These are limited conformance observations and rubric estimates, not clinical performance or patient outcome evidence.

The original cap remained300reservedrequestattempts/300000conservativetokens. The run recorded69reservedattempts,67confirmed network dispatches,280049conservativelychargedtokens and146772knownactualtokens. Unknown usage reservations remain charged and totalcurrencycost remains null. Provider429s exposed an8000TPMlimit;30seconddispatchpacing was added without resetting budgets, removing failed caseIDs or changing model/prompts/RAG. Rescoring reuses explicitly linked original responses and is not new inference.

## Limits

- V1 patient IDs/seeds are disjoint, but template/scenario structures overlap development/validation; do not claim unseen-family generalization. The future v2 generator is prepared/tested separately and was not used for new live scores in this delivery.
- Groq candidate and grader share the same model/family. Public thematic subset selection, batched grading, possible benchmark contamination and absence of independent human scoring limit interpretation. It is not the official HealthBench overall score.
- Initial RAG hashing omitted the actualknowledge file. A transparent late-capture erratum verifies exact retrieved sections against actual provider-input records and retains the original metadata. Backend execution phases, scheduler changes, harness failures and scorer repairs are versioned in the run.
- Model latency after pacing includes local queue waits. Provider cost/usage omissions are unknown, not zero. A completed response can still be incorrect.
- English/Arabic wording, operational windows and clinical pathways have not received independent institutional review. Synthetic role actions are not an external clinical consultation or volunteer study.

Deterministic backend authorization, ownership, source verification, urgent routing, deadlines, closure checks and human decisions remain the safety boundary. The application continues through labelled fixed templates when inference is unavailable. Real deployment needs the approvals, identity/access configuration, connector permissions and local clinical review described in DEPLOYMENT.md.
