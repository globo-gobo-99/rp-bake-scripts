# devpod-infra

- Reproducible Ubuntu CPU **Dev-Pod** and **Test-Pod** images.
- Persistent home/toolchains; Docker Buildx Bake; portable Runpod templates.
- [Build and recovery](docs/RUNBOOK.md) · [Detailed overview](OVERVIEW.md).
- [Image manifest](release-manifest.json) · [Releases](releases/README.md) · [Templates](templates/README.md).
- [Startup](container-template/README.md) · [Versions](shared/README.md) · [Tests](tests/README.md) · [Examples](examples/README.md).
- Existing GHCR image names and digest pins remain unchanged by this repository rename.

```bash
./bake.sh --print
./bake.sh --check
./bake.sh --load
```
