#!/usr/bin/env bash
# Verify opt-in application supervision and state across container replacement.
set -euo pipefail
cd "$(dirname "$0")/.."
image=${DEVPOD_IMAGE:-$(./bake.sh --print 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["target"]["testpod"]["tags"][0])')}
docker image inspect "$image" >/dev/null
name="testpod-service-$(python3 -c 'import uuid;print(uuid.uuid4().hex[:16])')"
volume="$name"
created=false
cleanup() {
 if $created; then
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
 fi
}
trap cleanup EXIT
mkdir -p evidence/service-recovery
docker volume create "$volume" >/dev/null
created=true
docker run --pull=never --rm --entrypoint chmod --mount "type=volume,source=$volume,target=/workspace,volume-nocopy" "$image" 1777 /workspace
docker run --pull=never --rm --entrypoint runuser --mount "type=volume,source=$volume,target=/workspace,volume-nocopy" "$image" -u dev -- /usr/bin/python3 /opt/devpod/bootstrap.py
docker run --pull=never --rm --entrypoint runuser --mount "type=volume,source=$volume,target=/workspace,volume-nocopy" "$image" -u dev -- bash -lec '
 mkdir -p /workspace/state/services
 cat > /workspace/state/services/fixture.conf <<"EOF"
[program:application-fixture]
command=/bin/sh -c "echo service-started >> /workspace/state/app-starts; exec sleep 3600"
autorestart=true
stdout_logfile=/workspace/state/app-fixture.log
stderr_logfile=/workspace/state/app-fixture-error.log
EOF
'
for expected in 1 2; do
 docker run --pull=never -d --name "$name" --mount "type=volume,source=$volume,target=/workspace,volume-nocopy" "$image" >/dev/null
 found=false
 for _ in {1..20}; do
  if docker exec -u dev "$name" bash -lc 'test -f /workspace/state/app-starts && test "$(wc -l </workspace/state/app-starts)" = "$1"' _ "$expected" 2>/dev/null; then found=true; break; fi
  sleep 1
 done
 if ! $found; then
  docker logs "$name" > evidence/service-recovery/failure.log 2>&1
  echo "Application was not supervised at boot $expected" >&2
  exit 1
 fi
 docker rm -f "$name" >/dev/null
done
# A malformed optional application must not take down the primary SSH supervisor.
docker run --pull=never --rm --entrypoint runuser --mount "type=volume,source=$volume,target=/workspace,volume-nocopy" "$image" -u dev -- bash -lec 'printf "not-valid-ini\n" > /workspace/state/services/broken.conf'
docker run --pull=never -d --name "$name" --mount "type=volume,source=$volume,target=/workspace,volume-nocopy" "$image" >/dev/null
ssh_ready=false
for _ in {1..15}; do
 if docker exec "$name" bash -lc 'ss -lnt | grep -q ":22 "' 2>/dev/null; then ssh_ready=true; break; fi
 sleep 1
done
if ! $ssh_ready; then
 echo 'Malformed application configuration prevented SSH startup' >&2
 exit 1
fi
docker rm -f "$name" >/dev/null
printf '%s\n' 'APPLICATION_SUPERVISION_AND_REPLACEMENT_PASSED' | tee evidence/service-recovery/result.txt
