#!/usr/bin/env python3
"""validate.py — STUB (milestone M2). Standard library only.

Usage: python tools/validate.py <project> <spec-id> [--allow-mutations] [--only STEP_ID ...] [--dry-run]

Behaviour to implement:
- Load <project>/.env, then specs/<id>/draft/validation-plan.json and openapi.json.
- Resolve {{env.X}} / {{vars.x}}; apply auth (bearer | apiKey header/query | basic).
- Run steps in order (setup → test → teardown; teardown always runs). Skip mutating steps unless --allow-mutations.
- Per step: status check, response-schema conformance (type/required/properties/items/enum/allOf/anyOf/oneOf, $ref),
  undocumented response fields, rate-limit headers (x-ratelimit-*, ratelimit-*, retry-after).
- Redact secrets and PII (keys matching token|secret|password|auth|cookie|session|email|phone; JWT-shaped values);
  truncate arrays in samples to 3 items.
- Write draft/validation/results.json, draft/validation/runs/<ts>.json, draft/samples/<operationId>.json.
- Update findings.operations[].validation; promote documented/inferred → verified on pass. Never auto-mark contradicted.
- Exit non-zero if any step is not 'pass'.
"""
raise SystemExit("validate.py is a stub — see milestone M2 in PLAN.md")
