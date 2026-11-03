#!/bin/bash
set -euo pipefail
umask 077
source /etc/devpod-env
cp /opt/devpod/supervisord.conf /workspace/state/supervisord-active.conf
if [[ -x /workspace/toolchains/current/bin/tailscaled ]]; then
 cat /opt/devpod/tailscaled.conf >> /workspace/state/supervisord-active.conf
fi
if [[ -f /workspace/state/obsidian-sync.conf ]]; then
 cat /workspace/state/obsidian-sync.conf >> /workspace/state/supervisord-active.conf
fi
exec /usr/bin/supervisord -n -c /workspace/state/supervisord-active.conf
