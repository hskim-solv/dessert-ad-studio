# Agentic RAG Pending Decision Register

Date: 2026-06-17

No external calls were made. No paid API calls were made. This register keeps
the portfolio boundary explicit: pending items are not production claims, and
provider-quality image editing remains unproven until the latency strategy is
resolved and a later paid gate passes.

## Summary

- `agentic_rag_decision_register`: `passed`
- Decision count: `9`
- Decisions requiring user approval: `9`
- Production claim added: `false`

## Decisions

| ID | Approval reason | Current boundary | Decision needed | Next evidence |
|---|---|---|---|---|
| `ragas_live_eval` | `paid_api_or_eval_llm` | Local Ragas-compatible proxy and promptfoo package gates are complete. | Approve paid/API-key evaluator execution and trace/result payload review. | `docs/evidence/agentic-rag-eval-guardrail.md` |
| `live_web_search_provider_smoke` | `credentialed_external_service` | Live web search runtime policy is defined without credentials. | Select provider/API key, domain allowlist, and retention boundary. | `docs/evidence/agentic-rag-tools-summary.json` |
| `credentialed_production_db_smoke` | `credentialed_external_service` | Production DB access/audit policy first gate is complete without credentials. | Approve database target, readonly role, network path, audit retention, and rollback. | `docs/evidence/agentic-rag-tools-summary.json` |
| `production_mcp_remote_auth` | `production_auth_security_boundary` | Loopback transport/auth boundary and remote client auth contract are defined. | Choose auth provider, token issuance path, TLS/origin boundary, and client allowlist. | `docs/evidence/agentic-rag-mcp-server-summary.json` |
| `live_provider_cross_process_resume` | `production_storage_or_retention` | Same-process resume and mock-only redacted SQLite cross-process resume are complete. | Approve durable request/provider payload storage policy or keep live-provider resume unclaimed. | `docs/evidence/agentic-rag-cross-process-resume.md` |
| `production_replay_audit_storage` | `production_storage_or_retention` | Redacted local replay, approval metadata, and 7-day trace contract first gates are complete. | Approve storage location, retention period, deletion behavior, and user/project/entity scope. | `docs/evidence/agentic-rag-retention-policy.md` |
| `external_trace_backend_customer_capture` | `production_storage_or_retention` | Deployment trace retention contract is complete; no external backend is configured. | Select backend, retention above or equal to 7 days, and customer trace capture policy. | `docs/evidence/agentic-rag-retention-policy-summary.json` |
| `image_edit_latency_strategy` | `provider_quality_claim_boundary` | Latest paid canary passed API/cost/ROI/text checks but failed the 30s latency threshold; provider-quality image editing remains unproven. | Keep 30s target, relax portfolio threshold with rationale, or switch model/quality. | `docs/evidence/openai-image-edit-preservation.md` |
| `cloud_deployment_and_recorded_demo` | `cloud_or_public_deployment` | Docker, GitHub Actions, K8s/kind, architecture diagram, eval report, and storyboard are complete. | Select AWS/GCP/Azure or keep kind-only evidence, then approve final recording/link policy. | `docs/evidence/demo-video-storyboard.md` |

## Reproduce

```bash
.venv/bin/python scripts/build_agentic_rag_decision_register.py \
  --date 2026-06-17 \
  --summary-output docs/evidence/agentic-rag-decision-register-summary.json \
  --report-output docs/evidence/agentic-rag-decision-register.md
```
