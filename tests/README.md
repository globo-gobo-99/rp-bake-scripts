# Verification

Fixture tests plus real container and SSH replacement recovery.

- [Runtime seed](test_runtime_install.py) — Pinned transport without agent installation.
- [Bootstrap tests](test_bootstrap.py) — Mount rejection and state preservation.
- [Container smoke](smoke.sh) — SSH, tools and replacement persistence.
- [Application recovery](service-recovery.sh) — Private services survive container replacement.
- [Git delivery](git-delivery.sh) — Selected revisions, HTTP and rollback.

Run `python3 -m unittest discover -s tests -v`, then after `./bake.sh --load` run
`bash tests/smoke.sh` and `bash tests/smoke.sh testpod`. The smoke image is resolved from
Bake, must already exist locally, and is never pulled implicitly. Evidence is disposable
and excluded from Git; CI uploads it separately.

`bash tests/git-delivery.sh` uses the already-loaded Bake-selected Test-Pod image, a public synthetic
Git fixture and loopback-only HTTP inside local Docker. It proves selected A→B→A revision
delivery and persistence after replacement. It uses an immutable Git bundle (safe across host UID differences) as file transport and explicitly relaunches
the demo server after replacement; it does not prove provider transport, private preview
networking, automatic application startup or real-device display. No cloud resource is created.
