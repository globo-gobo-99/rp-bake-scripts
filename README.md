# Dev-Pod

Reproducible Ubuntu 24.04 CPU development and application containers, using Runpod's
container-template startup and shared Buildx Bake conventions. Independent public source;
not an upstream Runpod fork and no copied machine/account state.

- [Container startup](container-template/README.md) — Persistent home and supervised services.
- [Shared versions](shared/README.md) — Resolved vendor versions and hashes.
- [Templates](templates/README.md) — Portable provider container definitions.
- [Runbook](docs/RUNBOOK.md) — Build, enrollment, recovery and limitations.
- [Examples](examples/README.md) — Small Git delivery and recovery fixtures.
- [Tests](tests/README.md) — Bootstrap and replacement recovery checks.
- [Execution plan](docs/PLAN.md) — Stages and human checkpoints.

```bash
./bake.sh --print
./bake.sh --check
./bake.sh --load
python3 -m unittest discover -s tests -v
bash tests/smoke.sh
# Authenticate to your chosen registry separately; never pass credentials as build args.
./bake.sh --push --metadata-file metadata.json
```

Public GitHub Actions builds and publishes GHCR releases. New GHCR packages may require
the owner to set package visibility to public; repository visibility alone does not prove
anonymous pull access. Consume a verified `@sha256:...` digest for provider templates.

Upstream reviewed: runpod/containers `d16ed4df6a254fb87932cfae81551240dd8791cd`.
Image OS packages are rebuildable layers; valuable home/tools/source live on a separately
mounted private `/workspace`. Fresh image boots never run apt or upgrade active agents.

Release `2026.11.02-r4.2` passed [CI build, UID initialization and SSH replacement recovery](https://github.com/gobo-99/dev-pod/actions/runs/41557483597). See the [resolved image/software manifest](release-manifest.json).

Persistent files are created directly as developer UID 1000; HIGH_PERFORMANCE NFS rejects
runtime chown. The immutable toolchain release is reused across image repairs, with a separate
writable user-tool prefix. The older r4.1 image has the NFS ownership defect and is superseded.

GHCR supports private pulls through Runpod's native registry credentials. Keep the account's
registry ID in private launch configuration; never check it into these portable definitions.
The owner can separately make packages public for anonymous reuse.

The r4.3 source adds a small pinned Test-Pod private-network/HTTP seed and isolated optional
application supervision. Existing toolchain selections remain unchanged at boot. Its release
manifest and provider verification are recorded after the immutable CI publication.
