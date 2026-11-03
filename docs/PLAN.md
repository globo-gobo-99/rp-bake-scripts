# Recoverable CPU Dev-Pod execution

Accepted outcome: versioned public image source, shared Bake targets, persistent developer
home/tools, provider CPU templates, and replacement recovery evidence.

1. Verify tools/authentication, interrupted source and independent absolute cutoff.
2. Test bootstrap rejection of missing mounts and preservation of human state; implement image.
3. Validate Bake, build and smoke both variants; publish immutable images and manifests.
4. Read back provider templates, deploy minimum CPU resources on a fresh high-performance volume.
5. Verify SSH, paths, tools and provider stop/start replacement; preserve durable state.
6. Stop compute before the absolute commissioning deadline and record provider read-back.

Human checkpoints: fresh Obsidian enrollment/E2EE, agent logins, Microsoft license/login,
Rootshell device controls. Continue independent work while awaiting those checkpoints.

Review focus: missing mounts, interrupted bootstrap, unchanged user files, fresh SSH keys,
registry pull authorization, and deadline reconciliation after an interrupted create request.

## Test-Pod runtime repair and supervision verification

- A fresh smaller Test-Pod lacked Tailscale despite needing an independent private URL.
  Added checksum-verified runtime-only installation of tailscale/tailscaled and Caddy;
  agent/Node installation remains Dev-Pod-only. Five fixture tests pass including artifact
  rejection, and the old image failed the strengthened actual runtime smoke as expected.
- Runtime review found no Important implementation defect; verification was strengthened
  to execute daemon and Caddy from the persistent seed rather than allow an apt fallback.
- Opt-in application configuration is isolated in its own supervised process. A malformed
  app definition previously prevented SSH startup in a red fixture; the repair keeps the
  primary SSH/Tailscale/Sync supervisor independent. Existing user configuration is preserved.
- Git delivery fixture uses an immutable bundle rather than trusting a host-owned bare
  repository across UID boundaries. The original CI failure and a controlled different-owner
  reproduction establish the need; bundle cloning succeeds without global trust exceptions.
- Provider migration preserves the verified-empty older Test-Pod seed and current-link
  metadata explicitly. Ordinary bootstrap still does not upgrade/select a new toolchain.

Runtime and supervision review: no Critical implementation defect. Explicit daemon/persistent
Caddy checks address the runtime verification gap. The malformed-app/SSH impact was treated as
Important and reproduced RED→GREEN using a separate application supervisor. All five unit
fixtures, both SSH/tool replacement smokes, private application replacement/malformed-config
isolation and Git A→B→A/replacement tests passed before publication. Real device acceptance,
actual native enrollment and arbitrary application migrations remain distinct human/runtime checks.
