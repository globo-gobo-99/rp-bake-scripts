#!/bin/bash
set -euo pipefail
umask 077
# Parse optional application definitions in a separate supervisor so a typo cannot
# prevent the primary SSH/Tailscale/Sync supervisor from starting.
cat > /workspace/state/supervisord-applications.conf <<'EOF'
[supervisord]
nodaemon=true
logfile=/workspace/state/app-supervisor.log
pidfile=/workspace/state/app-supervisor.pid
childlogdir=/workspace/state
[include]
files=/workspace/state/services/*.conf
EOF
exec /usr/bin/supervisord -n -c /workspace/state/supervisord-applications.conf
