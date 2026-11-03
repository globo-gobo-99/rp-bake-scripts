# Verification

Fixture tests plus real container and SSH replacement recovery.

- [Bootstrap tests](test_bootstrap.py) — Mount rejection and state preservation.
- [Container smoke](smoke.sh) — SSH, tools and replacement persistence.

Run `python3 -m unittest discover -s tests -v`, then after `./bake.sh --load` run
`bash tests/smoke.sh` and `bash tests/smoke.sh testpod`. The smoke image is resolved from
Bake, must already exist locally, and is never pulled implicitly. Evidence is disposable
and excluded from Git; CI uploads it separately.
