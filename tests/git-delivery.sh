#!/usr/bin/env bash
# Local-only integration fixture: no cloud launch, implicit pull, or real project data.
set -euo pipefail
cd "$(dirname "$0")/.."
image=${DEVPOD_IMAGE:-ghcr.io/gobo-99/test-pod:2026.11.02-r4.2}
docker image inspect "$image" >/dev/null
fixture=$(mktemp -d)
fixture_id=$(python3 -c 'import uuid;print(uuid.uuid4().hex[:16])')
name="testpod-git-$fixture_id"
volume="$name"
created_volume=false
created_container=false
cleanup() {
 if $created_container; then docker rm -f "$name" >/dev/null 2>&1 || true; fi
 if $created_volume; then docker volume rm "$volume" >/dev/null 2>&1 || true; fi
 rm -rf -- "$fixture"
}
trap cleanup EXIT
mkdir -p evidence/testpod-git
git init -q -b main "$fixture/source"
printf '%s\n' 'selected revision A' > "$fixture/source/index.html"
git -C "$fixture/source" add index.html
git -C "$fixture/source" -c user.name='Delivery fixture' -c user.email=fixture@example.invalid commit -qm 'fixture A'
revision_a=$(git -C "$fixture/source" rev-parse HEAD)
printf '%s\n' 'selected revision B' > "$fixture/source/index.html"
git -C "$fixture/source" add index.html
git -C "$fixture/source" -c user.name='Delivery fixture' -c user.email=fixture@example.invalid commit -qm 'fixture B'
revision_b=$(git -C "$fixture/source" rev-parse HEAD)
git clone -q --bare "$fixture/source" "$fixture/origin.git"
chmod -R a+rX "$fixture"
docker volume create --label devpod.fixture="$fixture_id" "$volume" >/dev/null
created_volume=true
docker run --pull=never --rm --entrypoint chmod \
 --mount "type=volume,source=$volume,target=/workspace,volume-nocopy" "$image" 1777 /workspace
start() {
 docker run --pull=never -d --name "$name" --label devpod.fixture="$fixture_id" \
  --mount "type=volume,source=$volume,target=/workspace,volume-nocopy" \
  --mount "type=bind,source=$fixture/origin.git,target=/fixture/origin.git,readonly" "$image" >/dev/null
 created_container=true
 for _ in {1..30}; do
  if docker exec -u dev "$name" bash -lc 'test -d "$HOME" && test -w /workspace/state' 2>/dev/null; then return 0; fi
  sleep 1
 done
 docker logs "$name" >&2
 return 1
}
start
docker exec -u dev "$name" bash -lec 'mkdir -p /workspace/apps/demo/releases; git clone --no-checkout /fixture/origin.git /workspace/apps/demo/repo'
deploy() {
 docker exec -u dev "$name" bash -lec '
  set -euo pipefail
  root=/workspace/apps/demo
  revision=$1
  git -C "$root/repo" cat-file -e "$revision^{commit}"
  if [[ ! -d "$root/releases/$revision" ]]; then
   mkdir "$root/releases/$revision"
   git -C "$root/repo" archive "$revision" | tar -x -C "$root/releases/$revision"
  fi
  ln -s "releases/$revision" "$root/.next"
  mv -Tf "$root/.next" "$root/current"
  git -C "$root/repo" rev-parse "$revision"
 ' _ "$1"
}
serve() {
 docker exec -d -u dev "$name" bash -lc 'exec caddy file-server --listen 127.0.0.1:8080 --root /workspace/apps/demo/current >/workspace/state/demo-http.log 2>&1'
}
assert_http() {
 local expected="$1"
 for _ in {1..30}; do
  if response=$(docker exec -u dev "$name" curl --fail --silent http://127.0.0.1:8080/index.html 2>/dev/null); then
   [[ "$response" == "$expected" ]] || { printf 'Unexpected response: %s\n' "$response" >&2; return 1; }
   return 0
  fi
  sleep 1
 done
 return 1
}
deploy "$revision_a" > evidence/testpod-git/revision-a.txt
serve
assert_http 'selected revision A'
deploy "$revision_b" > evidence/testpod-git/revision-b.txt
assert_http 'selected revision B'
deploy "$revision_a" > evidence/testpod-git/rollback.txt
assert_http 'selected revision A'
# Replace the writable layer. Application data and selected source persist; the
# demo server is explicitly relaunched, not claimed to have automatic startup.
docker rm -f "$name" >/dev/null
created_container=false
start
docker exec -u dev "$name" bash -lec 'test -s /workspace/apps/demo/repo/.git/HEAD; test -L /workspace/apps/demo/current; test -s /workspace/apps/demo/current/index.html'
serve
assert_http 'selected revision A'
printf '%s\n' 'LOCAL_GIT_DELIVERY_SELECTED_A_B_ROLLBACK_A_AND_REPLACEMENT_PASSED' | tee evidence/testpod-git/result.txt
