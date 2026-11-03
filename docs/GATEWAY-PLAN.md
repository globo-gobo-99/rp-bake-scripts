# Bounded text gateway implementation plan

**Checkpoint:** Source and synthetic fixtures only. Not deployed; real Runpod/client acceptance and private enrollment remain pending. The broader implementation goal is paused. This checkpoint grants no paid lease or runtime activation.

> Use executing-plans; implement and verify inline, then one independent review.

**Goal:** Prepare the accepted first Rootshell text/command-help capability without exposing a provider management key to the client or cloud application Pod.

**Architecture:** Standard-library Python HTTP transport binds loopback on the existing operator host. An existing authenticated SSH connection forwards one loopback port from the task-owned Test-Pod; native private Tailscale HTTPS exposes that route. Provider key stays in its approved host store; client gets a fresh purpose-scoped token. No shell execution, conversation orchestration, MCP or voice route.

**Spec:** README and runbook commissioning/recovery contract plus this concrete transport contract.

## Constraints

- The pinned Rootshell executable source uses a 44,096-token custom-model standard ceiling (the nearby 4096 comment is stale). Preserve that request limit; private configuration permits it and a bounded 64KiB body, with conservative cost admission. Do not silently clamp the client.

- Existing live lease/cumulative cap remains authoritative; external guard reserves the entire small inference quota before activation and stops only this task's units/compute.
- One selected token-priced native Runpod public model, fixed upstream HTTPS host/path, no redirects, no caller-supplied upstream credentials or URLs.
- Constant-time bearer authentication; private configuration/state/token files outside source/vault.
- Bounded body, message count, output tokens, concurrency, response size and timeout. Preserve supported tool schemas/tool-role messages and SSE; reject unsupported fields explicitly.
- Conservative per-request cost reservation is durable before dispatch and never refunded, including ambiguous failures. No automatic paid retry; request IDs prevent replay without deduplicating separate prompts.
- Cached model discovery is not inference readiness. Health is allowlisted; successful inference expires after five minutes and the immutable lease expiry always wins. Never generate on a health poll.
- No request/response content logging. Only synthetic fixtures during verification. Actual Rootshell/client build, UI, login and device acceptance remain separate.

## Required before activation

The wrap-up review cleared this branch for source checkpoint publication only. Do not activate
this transport until accepted-connection concurrency is bounded before worker creation and
request headers/body have an absolute read deadline; the existing socket timeout only limits
inactivity. Also return an explicit authentication failure for non-ASCII bearer text instead
of allowing string `hmac.compare_digest` to raise `TypeError`. Preserve regression fixtures for
both behaviors when implementing the fixes. Real provider/client/security acceptance remains
pending; passing synthetic tests is not approval to deploy.

## Tasks

1. Write failing HTTP fixtures for authentication, expiry/quota rejection before upstream, tool-role preservation, SSE, durable replay rejection and stale readiness. Implement `tools/inference_gateway.py` with standard-library HTTP, atomic private admission state and fixed Runpod transport.
2. Run all unit fixtures and an independent review. Fix demonstrated Important issues with red→green coverage. Prepare exact private configuration and client enrollment instructions; publish generic source only.
3. Within the active lease, verify the guard/quota, bind an unused host loopback port, start two task-owned transient units (gateway and SSH reverse tunnel), and add only one HTTPS port to the new Test-Pod's native Serve config. Provider key never leaves host. Copy only the fresh client token into private Dev-Pod state for human terminal retrieval; never print it to chat/tool output.
4. Prove unauthenticated denial, authorized models/health, one synthetic command suggestion and protocol fixtures. Record real usage/readiness/cost limits. At cutoff stop the two exact units plus commissioned compute and read provider state; preserve source and volumes. Human configuration uses Chat Completions, no duplicated v1, Responses off, text-only initial test.
