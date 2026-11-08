#!/usr/bin/env python3
"""oauth_token.py — STUB (milestone M2). Standard library only.

Usage:
  python tools/oauth_token.py client-credentials --token-url U --client-id ID [--client-secret-env VAR] [--scope S]
  python tools/oauth_token.py auth-code --auth-url U --token-url U --client-id ID [--scope S] [--port 8788] [--no-pkce]
  python tools/oauth_token.py device-code --device-url U --token-url U --client-id ID [--scope S]
  python tools/oauth_token.py refresh --token-url U --client-id ID --refresh-env VAR
  common: [--extra k=v ...] [--write-env VAR] [--project DIR] [--print]

- auth-code: PKCE S256 by default, local callback http://127.0.0.1:<port>/callback, state check, opens or prints the URL.
- Prints a summary (expiry, granted scopes); prints the token itself only with --print; --write-env writes <project>/.env.
"""
raise SystemExit("oauth_token.py is a stub — see milestone M2 in PLAN.md")
