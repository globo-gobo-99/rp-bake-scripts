#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
exec docker buildx bake -f shared/versions.hcl -f docker-bake.hcl "$@"
