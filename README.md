# Dev-Pod

Reproducible Ubuntu 24.04 CPU development and application containers, using Runpod's
container-template startup and shared Buildx Bake conventions. Independent public source;
not an upstream Runpod fork and no copied machine/account state.

- [Container startup](container-template/README.md) — Persistent home and supervised services.
- [Shared versions](shared/README.md) — Resolved vendor versions and hashes.
- [Templates](templates/README.md) — Portable provider container definitions.
- [Runbook](docs/RUNBOOK.md) — Build, enrollment, recovery and limitations.
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

Release `2026.11.02-r4.1` passed [CI build and SSH replacement recovery](https://github.com/gobo-99/dev-pod/actions/runs/41554192979). See [resolved image/software manifest](release-manifest.json). GHCR package visibility is an owner checkpoint; verify anonymous digest access before deployment.
