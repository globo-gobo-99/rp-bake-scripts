#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
role=${1:-devpod}
image=${DEVPOD_IMAGE:-$(./bake.sh --print 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["target"][sys.argv[1]]["tags"][0])' "$role")}
docker image inspect "$image" >/dev/null # Never silently pull a prior release.
out="evidence/$role"
mkdir -p "$out"
name="devpod-smoke-$$"; volume="$name"; temp=$(mktemp -d)
trap 'docker rm -f "$name" >/dev/null 2>&1 || true; docker volume rm "$volume" >/dev/null 2>&1 || true; rm -rf "$temp"' EXIT
ssh-keygen -q -t ed25519 -N '' -f "$temp/key"
public_key=$(cat "$temp/key.pub")
ssh-keygen -q -t ed25519 -N '' -f "$temp/human-key"
docker volume create "$volume" >/dev/null
if docker run --pull=never --rm "$image" >"$out/missing-mount.log" 2>&1; then
 echo 'ERROR: unmounted bootstrap unexpectedly succeeded' >&2; exit 1
fi
grep -F 'Expected durable mount' "$out/missing-mount.log"
start() {
 docker run --pull=never -d --name "$name" -p 127.0.0.1::22 -e PUBLIC_KEY="$public_key" -v "$volume:/workspace" "$image" >/dev/null
 port=$(docker port "$name" 22/tcp | cut -d: -f2)
 for i in {1..60}; do
  if ssh -i "$temp/key" -o BatchMode=yes -o ConnectTimeout=1 -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$temp/known-$port" -p "$port" dev@127.0.0.1 'test "$(id -un)" = dev; test "$HOME" = /workspace/home/dev' 2>/dev/null; then return 0; fi
  sleep 1
 done
 docker logs "$name" >&2; return 1
}
start
ssh -i "$temp/key" -o BatchMode=yes -o UserKnownHostsFile="$temp/known-$port" -p "$port" dev@127.0.0.1 'set -eu; echo AUTHENTICATED_SSH_PASSED' > "$out/ssh.log"
docker exec -u dev -e HUMAN_KEY="$(cat "$temp/human-key.pub")" "$name" bash -lec 'printf "%s\n" "$HUMAN_KEY" >> "$HOME/.ssh/authorized_keys"'
docker exec "$name" ssh-keygen -lf /workspace/state/ssh/ssh_host_ed25519_key.pub > "$temp/host-before"
docker exec -u dev "$name" bash -lec 'test -r /etc/devpod-env; test "$HOME" = /workspace/home/dev; test "$(getent passwd dev | cut -d: -f6)" = "$HOME"; echo durable > "$HOME/recovery-marker"; echo toolstate > /workspace/toolchains/recovery-marker; mkdir -p /workspace/vaults/gobo-vault/Projects/recovery; echo source > /workspace/vaults/gobo-vault/Projects/recovery/probe.txt; touch /tmp/ephemeral-marker; if command -v codex >/dev/null; then codex --version; claude --version; pi --version; ob --version; ob sync-list-local --json; uv --version; gh --version; herdr --version; tuios --version; docker buildx version; fi; python3 --version; tmux -V; ss -lnt | grep :22' > "$out/tools.log"
docker cp "$name:/opt/devpod/image-manifest.json" "$out/image-manifest.json"
docker rm -f "$name" >/dev/null
start
docker exec "$name" ssh-keygen -lf /workspace/state/ssh/ssh_host_ed25519_key.pub > "$temp/host-after"
cmp "$temp/host-before" "$temp/host-after"
ssh -i "$temp/human-key" -o BatchMode=yes -o UserKnownHostsFile="$temp/known-$port" -p "$port" dev@127.0.0.1 'echo HUMAN_KEY_RECOVERY_PASSED' >> "$out/ssh.log"
docker exec -u dev "$name" bash -lec 'test ! -e /tmp/ephemeral-marker; test "$(cat "$HOME/recovery-marker")" = durable; test "$(cat /workspace/toolchains/recovery-marker)" = toolstate; test "$(cat /workspace/vaults/gobo-vault/Projects/recovery/probe.txt)" = source; test -s "$HOME/.ssh/authorized_keys"; echo REPLACEMENT_RECOVERY_PASSED' > "$out/recovery.log"
printf '%s\n' "$image" > "$out/tested-image.txt"
cat "$out/ssh.log" "$out/tools.log" "$out/recovery.log"
