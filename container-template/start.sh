#!/bin/bash
set -euo pipefail
umask 077
python3 /opt/devpod/bootstrap.py
source /etc/devpod-env
mkdir -p "$HOME/.ssh" /workspace/state/ssh /run/sshd
if [[ -n "${PUBLIC_KEY:-}" ]]; then
  touch "$HOME/.ssh/authorized_keys"
  while IFS= read -r key; do
    [[ -n "$key" ]] || continue
    grep -qxF -- "$key" "$HOME/.ssh/authorized_keys" || printf '%s\n' "$key" >> "$HOME/.ssh/authorized_keys"
  done <<< "$PUBLIC_KEY"
fi
chmod 700 "$HOME/.ssh"
chmod 600 "$HOME/.ssh/authorized_keys" 2>/dev/null || true
chown -R dev:dev "$HOME/.ssh"
if [[ ! -f /workspace/state/ssh/ssh_host_ed25519_key ]]; then
 ssh-keygen -q -t ed25519 -N '' -f /workspace/state/ssh/ssh_host_ed25519_key
fi
# Runpod's basic SSH proxy can land as root. Keep keys, never copy private account state.
mkdir -p /root/.ssh
[[ ! -f "$HOME/.ssh/authorized_keys" ]] || cp "$HOME/.ssh/authorized_keys" /root/.ssh/authorized_keys
cat > /etc/ssh/sshd_config <<'EOF'
Port 22
HostKey /workspace/state/ssh/ssh_host_ed25519_key
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
UsePAM yes
Subsystem sftp internal-sftp
AcceptEnv LANG LC_*
EOF
if [[ ! -f /workspace/state/image-manifest.json ]]; then
 cp /opt/devpod/image-manifest.json /workspace/state/image-manifest.json
 chown dev:dev /workspace/state/image-manifest.json
fi
cp /opt/devpod/supervisord.conf /run/devpod-supervisord.conf
if [[ -x /workspace/toolchains/current/bin/tailscaled ]]; then
 cat /opt/devpod/tailscaled.conf >> /run/devpod-supervisord.conf
fi
if [[ -f /workspace/state/obsidian-sync.conf ]]; then
 cat /workspace/state/obsidian-sync.conf >> /run/devpod-supervisord.conf
fi
exec /usr/bin/supervisord -n -c /run/devpod-supervisord.conf
