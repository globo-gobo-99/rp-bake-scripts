# Test-Pod preview fixture

A static page for proving selected Git revisions and rollback over private HTTP.

- [Preview page](index.html) — Visible revision and deployment marker.

Serve this directory through loopback Caddy and a private tailnet route. It contains no
personal data, provider credentials or external assets. A successful page load proves this
fixture's delivery; it does not validate another application's build or database migrations.
