# Dev-Pod runbook

## Build and release

Use `./bake.sh --print`, `./bake.sh --check`, then `./bake.sh --load`.
Run `python3 -m unittest discover -s tests -v` and `bash tests/smoke.sh`.
Publish with `./bake.sh --push --metadata-file metadata.json` after registry login.
Keep the metadata and `/opt/devpod/image-manifest.json`; deploy by digest.
Refresh vendor URLs/hashes and npm versions in `shared/tools.lock.json` and the npm lockfile in `shared/npm/`, increment
`RELEASE_VERSION` in shared versions, rebuild and test. Never refresh on ordinary boot.
OS package versions are recorded in the manifest; apt repositories are rolling, so an exact
release is reproduced by pulling its digest, while a source rebuild may update OS packages.

## Durable storage and access

Attach a new private HIGH_PERFORMANCE network volume at `/workspace`; boot fails if no
mount exists. CPU Pods cannot use the GPU Pod persistent-volume-disk setting.
Keep region, volume IDs, SSH account keys and login credentials in private launch config.
Use UID/GID 1000 (`dev`), whose real passwd HOME is `/workspace/home/dev`.
OS/runtime packages are in the image; mutable agent tools are seeded once into
`/workspace/toolchains/<release>` and selected by `current`. Existing `current` is preserved.
No tools/config/source depend on the disposable writable layer.

Connect with provider direct TCP SSH as `dev` using an account-registered key. The image
honors Runpod `PUBLIC_KEY`, supervises OpenSSH, and persists host keys. The provider basic
SSH proxy can land as root; run `sudo -iu dev`. Re-read the direct IP/port after every restart.
No passwords, auth tokens, host account bindings or personal vault notes are in this image.

## Human login checkpoints

Run these directly in a private terminal on Dev-Pod; do not send credentials to an agent:

```bash
# As dev; inspect each tool's help if vendor syntax changes.
codex login --device-auth
claude auth login
pi                         # then /login and choose your provider
ob login
ob sync-setup --vault YOUR_EXISTING_REMOTE_ID --path /workspace/vaults/gobo-vault
```

Enter the existing vault encryption password interactively; omit `--json` and password flags.
Inspect `ob sync-config --path /workspace/vaults/gobo-vault --json`; preserve existing file
lists when adding `unsupported` for code. Hidden files remain excluded. Start exactly one
managed Sync writer and finish its initial download before source edits. Never copy another
host's live Sync tokens/database. GPUs remain off during enrollment.

After binding, enable the opt-in Sync supervisor using `devpod-enable-sync`; it refuses an
unbound replica. Verify logs and a harmless authorized round trip before claiming Sync ready.

Microsoft VS Code CLI is deliberately downloaded into private persistent HOME on demand,
not redistributed in the public image. Run `devpod-install-vscode`, inspect its license,
then use `code tunnel` for the supported Microsoft login/license prompt. Desktop Remote-SSH
installs its matching server commit under persistent HOME; terminal transport and real editor
connection are separate checks. No code-server substitution.

Tailscale runs in userspace mode without adding container privileges. For fresh enrollment:

```bash
/workspace/toolchains/current/bin/tailscale --socket=/workspace/state/tailscale/tailscaled.sock up --hostname=dev-pod
# Complete the displayed login link yourself, then:
/workspace/toolchains/current/bin/tailscale --socket=/workspace/state/tailscale/tailscaled.sock serve --bg --tcp=22 tcp://127.0.0.1:22
```

The tailnet state persists on the private volume. No copied old-node identity or policy changes.
Private previews should bind loopback and use an authenticated tailnet Serve route; no wildcard
HTTP ports are exposed by the reusable template. Caddy is available for reviewed private routes.

## Container build/run access

Current Runpod Docker-runtime CPU Pods do not support Docker-in-Docker. Do not mount Dev-Box's
Docker socket or add privileges. Docker CLI/Buildx are available; public repository Actions
is the supported build/publish route. Use Git to deliver selected image/source revisions to
Test-Pod and keep a previous digest for rollback. Running a nested container locally inside
Dev-Pod is unavailable on this platform; remote Docker requires a separately authorized builder.

## Recovery

Write valuable state only below `/workspace`. Record the image digest and private volume ID.
Stop the CPU Pod, read back EXITED, then start or recreate it with the same digest and volume.
Verify `getent passwd dev`, HOME, tool executable paths, marker files, source and SSH host key.
Boot must not run apt. `bash tests/smoke.sh` proves replacement of the entire writable layer
while preserving home, tool state and source, and separately proves missing-mount rejection.
Do not attach one live writable replica to two simultaneously active writing Pods.

Rootshell: connect through SSH, then `tmux -CC new-session -A -s dev`. Windows are tabs;
panes are panes. Prefix Left/Right or n/p cycle tabs; Up/Down follow numeric pane order;
Option-number selects the current session's tab. `|` splits left/right, `-` top/bottom;
new splits inherit cwd. Existing prefix is unchanged. Verify device key delivery separately.
TUIOS/herdr are alternatives; their tmux control-mode compatibility is unverified.

## Commissioning cutoff

Every deployment needs an independently verified stop guard outside this disposable Pod,
an absolute deadline and total cost bound. A reusable template grants no spending authority.
Stopped compute does not cancel retained network storage. Never infer stop success from a timer
alone: read provider status and verify runtime is gone. Source and private volume survive.

## NFS ownership contract

HIGH_PERFORMANCE NFS rejects runtime chown. The r4.2 bootstrap creates persistent user
files directly as UID 1000, keeps HOME/state/vault directories private, and uses a separate
writable user-tool prefix. It never recursively changes an existing volume owner. Local
named-volume tests prepare a fresh writable volume and verify initialization without the
chown capability. Existing root-owned factory state requires an explicit reviewed repair;
there is no automatic ownership sweep. Image release and immutable toolchain release are
separate, so the fixed image reuses the same known tool versions without upgrading agents.
