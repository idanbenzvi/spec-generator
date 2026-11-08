# Auth & authorization research — STUB (milestone M1)

Outline:
1. Where to look first: OpenAPI securitySchemes, "Authentication"/"Authorization" doc pages, OAuth discovery
   (/.well-known/openid-configuration, /.well-known/oauth-authorization-server), official SDK auth modules.
2. Per-method checklist
   - API key: where issued, header/query name, per-environment keys, key restrictions (IP/referrer/scope), rotation.
   - OAuth 2.0: supported flows, authorize/token/revoke endpoints, PKCE required?, redirect URI rules (localhost allowed?),
     public vs confidential clients, token lifetime, refresh rotation, incremental consent.
   - OIDC, service accounts / JWT bearer, domain-wide delegation, mTLS, HMAC signing (e.g. SigV4), Basic, session cookies (flag as unsuitable).
   - Webhook signature secrets, if the requirements need inbound events.
3. Authorization model: scope catalogue → which operations need which scope; roles/permissions inside the
   provider's account; user/account types (personal/org/enterprise, sandbox/prod, plan tiers); admin vs user consent;
   sensitive scopes that need app verification/review and how long that takes.
4. Least-privilege derivation: minimal scope set per spec, with the operation that justifies each scope.
5. The offer table (columns and recommendation format) shown to the user at the Stage 1 gate.
