# 2026 AI Agent Engineer Hiring and Productionization Notes

Date: 2026-06-12

## Positioning

This project should be positioned as a production-oriented multimodal AI application, not an image-model research project.

Recommended title:

> Multimodal AI Application Engineer / AI Agent Engineer

Resume framing:

> Built a product-photo-preserving ad generation service for small business owners by combining VLM analysis, RAG-based marketing context, agent workflow orchestration, image generation, Korean text overlay, evaluation, observability, and production deployment.

## Hiring Signals

The strongest 2026 hiring signal is not "used an LLM." It is the ability to turn an AI workflow into a reliable service.

Repeated requirements from current job descriptions and reports:

- Agent orchestration: LangGraph, LangChain, CrewAI, AutoGen, ADK
- RAG: embeddings, vector DB, hybrid retrieval, reranking, retrieval evaluation
- Tool use: function calling, typed tool contracts, MCP/FastMCP, least-privilege tool access
- AgentOps: tracing, evals, failure analysis, regression testing, prompt/version management
- Backend: Python, FastAPI, async workflows, task queues, streaming responses
- Deployment: Docker, Kubernetes, CI/CD, health checks, monitoring
- Serving: vLLM, Triton, ONNX Runtime, TensorRT/TensorRT-LLM where justified
- Security: prompt injection handling, tool allowlists, audit logs, secret handling, container scanning

## Best Fit for This Project

Use this priority order:

1. LangGraph-style workflow for `VLM analysis -> RAG retrieval -> copy generation -> image prompt -> image generation -> overlay -> evaluation`.
2. OpenTelemetry + Langfuse + DeepEval for tracing and reproducible evals.
3. FastMCP tool server for typed agent tools such as `search_marketing_guides`, `check_ad_policy`, `generate_banner_prompt`, and `save_asset`.
4. Redis/RQ or Celery for async image generation jobs and progress polling.
5. Docker Compose and Kubernetes manifests with NGINX/Ingress, probes, metrics, ConfigMap, Secret template, PVC, and GPU limits.
6. Keep Triton/ONNX as the concrete model-serving proof; add TensorRT benchmark only where it produces measurable latency evidence.
7. Add vLLM only as an optional LLM/VLM serving lane for copy generation or evaluation. Do not replace the existing FastAPI/Triton baseline just for novelty.
8. Add security and guardrails: prompt injection checks, tool allowlist, audit logs, policy checks for prohibited ad claims.

## What Not to Overbuild

- TensorRT-LLM is strong for NVIDIA-first LLM infrastructure roles, but too heavy for the MVP unless there is a focused benchmark.
- KServe is good for Kubernetes-native ML platforms, but not required before basic K8s manifests and health checks exist.
- Ray Serve and BentoML are useful alternatives, but adopting them now would dilute the already chosen FastAPI/Triton architecture.
- A2A and AG-UI are worth mentioning as protocol awareness, but MCP has the better immediate project fit.

## Portfolio Evidence to Produce

Minimum strong evidence:

- Architecture diagram showing Agent workflow, tool layer, serving, queue, storage, and observability.
- `/livez`, `/readyz`, `/metrics`.
- Eval suite with golden inputs and regression output.
- Trace screenshots or exported sample traces from Langfuse/OpenTelemetry.
- Docker Compose smoke test.
- Kubernetes manifests and a short runbook.
- Triton/ONNX latency smoke result.
- Failure-case report: hallucinated copy, bad product preservation, policy violation, slow generation, and recovery behavior.

## Source Snapshot

- LangChain State of Agent Engineering: https://www.langchain.com/state-of-agent-engineering
- Cognizant ML Ops / Agent Ops Engineer: https://careers.cognizant.com/uki-en/jobs/00069014281/ml-ops-agent-ops-engineer/
- Intellias AWS Agentic Framework Engineer / DevOps: https://career.intellias.com/vacancy/aws-agentic-framework-engineer-devops-langgraph-focus-30161/
- MCP server concepts: https://modelcontextprotocol.io/docs/learn/server-concepts
- OpenTelemetry GenAI observability: https://opentelemetry.io/blog/2026/genai-observability/
- Langfuse evaluation docs: https://langfuse.com/docs/evaluation/overview
- DeepEval docs: https://deepeval.com/docs/introduction
- vLLM production metrics: https://docs.vllm.ai/en/stable/usage/metrics/
- KServe docs: https://kserve.github.io/website/
- NVIDIA Triton docs: https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/
- Kubernetes GPU scheduling: https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/
- Docker Compose startup order and health checks: https://docs.docker.com/compose/how-tos/startup-order/
