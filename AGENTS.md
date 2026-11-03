# Dev-Pod source

Public, portable container source only. Never add credentials, personal vault contents,
account/region selections, device bindings, or copied host configuration.

Use `./bake.sh` for builds. Run `python3 -m unittest discover -s tests -v`,
`./bake.sh --print`, `./bake.sh --check`, and `bash tests/smoke.sh` before release.
Keep tool versions and artifact hashes in `shared/tools.lock.json`.
Do not update active toolchains at boot. Cloud launches require their own budget and cutoff.
