#!/usr/bin/env python3
"""proxy.py — STUB (milestone M2). Standard library only.

Usage: python tools/proxy.py <project> [--port 8787]

Localhost-only CORS proxy for the site's try-it console: GET/POST/... http://127.0.0.1:8787/<absolute-upstream-url>.
- Bind 127.0.0.1 only. Allowlist upstream hosts from every spec's openapi servers + validation-plan baseUrl.
- Answer preflight; reflect Origin only if it is localhost/127.0.0.1; expose all response headers.
- Strip Origin/Referer/Host before forwarding. Never log Authorization or request bodies.
"""
raise SystemExit("proxy.py is a stub — see milestone M2 in PLAN.md")
