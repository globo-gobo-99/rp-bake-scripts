# CPU templates

Portable Runpod v2 container defaults. Launch choices and private bindings stay separate.

- [Dev-Pod](devpod.json) — Developer image container defaults.
- [Test-Pod](testpod.json) — Smaller application image defaults.
- [Storage contract](contract.json) — Durable paths and launch requirements.

Before creating templates, replace each `image` with the verified published release digest.
Use category CPU, no CUDA constraints, no Jupyter, and only TCP 22. CPU flavor/count and region
belong to deployment, not container-template configuration. The CPU launch must attach a
HIGH_PERFORMANCE network volume at `/workspace`; templates do not contain account volume IDs.
