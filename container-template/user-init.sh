#!/bin/bash
set -euo pipefail
umask 077
source /etc/devpod-env
mkdir -p "$HOME/.ssh" /workspace/state/ssh
 touch "$HOME/.ssh/authorized_keys"
if [[ -n "${PUBLIC_KEY:-}" ]]; then
 while IFS= read -r key; do
  [[ -n "$key" ]] || continue
  grep -qxF -- "$key" "$HOME/.ssh/authorized_keys" || printf '%s\n' "$key" >> "$HOME/.ssh/authorized_keys"
 done <<< "$PUBLIC_KEY"
fi
chmod 700 "$HOME/.ssh"
chmod 600 "$HOME/.ssh/authorized_keys"
if [[ ! -f /workspace/state/ssh/ssh_host_ed25519_key ]]; then
 ssh-keygen -q -t ed25519 -N '' -f /workspace/state/ssh/ssh_host_ed25519_key
fi
[[ -f /workspace/state/image-manifest.json ]] || cp /opt/devpod/image-manifest.json /workspace/state/image-manifest.json
