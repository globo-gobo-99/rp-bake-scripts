#!/bin/bash
set -euo pipefail
umask 077
# NFS may reject chown even for container root. Create user state as its final UID.
runuser -u dev -- /usr/bin/python3 /opt/devpod/bootstrap.py
runuser -u dev -- /bin/bash /opt/devpod/user-init.sh
mkdir -p /root/.ssh /run/sshd
runuser -u dev -- cat /workspace/home/dev/.ssh/authorized_keys > /root/.ssh/authorized_keys
runuser -u dev -- cat /workspace/state/ssh/ssh_host_ed25519_key > /run/sshd/devpod_host_key
chmod 600 /run/sshd/devpod_host_key /root/.ssh/authorized_keys
cat > /etc/ssh/sshd_config <<'EOF'
Port 22
HostKey /run/sshd/devpod_host_key
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
UsePAM yes
Subsystem sftp internal-sftp
AcceptEnv LANG LC_*
EOF
exec runuser -u dev -- /bin/bash /opt/devpod/run-services.sh
