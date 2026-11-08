# Cross-validation — STUB (milestone M1)

Outline:

## 1. Source corroboration (one API, many sources)
- `corroboration` on every claim: `single` | `corroborated` | `conflicting`, plus `agreeRefs[]`, `disagreeRefs[]`.
- Independence test: same upstream origin (docs generated from the provider's own OpenAPI, mirrored pages, SDK generated
  from the spec) counts as ONE source. Record `derivedFrom` on the source entry.
- Critical claims: auth flows/endpoints, scopes per operation, required params, quotas. A critical claim backed by a
  single source gets a warning finding.
- Precedence for provisional resolution: live > provider OpenAPI > reference docs > SDK behaviour > guides/tutorials >
  community. Newer changelog/deprecation notices override older docs regardless of tier. Always record why.

## 2. Conflict findings
- `category: conflict`, `sides[] {value, sourceRefs}`, `resolution: provisional|live|user|unresolved`, `winner`, `rationale`.
- Typical conflicts: rate limit numbers, scope names renamed across versions, pagination style, field nullability,
  max lengths, error codes.

## 3. Candidate comparison (alternative APIs, same requirement)
- File: `cross/comparisons/<group>.json` → { group, requirementIds, candidates[specId], axes[], rows[], recommendation{specId, rationale}, userSelection[] }.
- Axes: requirement coverage · auth model & consent friction · minimal scopes · account type/plan · quotas ·
  pricing signals · data-model fit · deprecation/stability · evidence strength (share of claims corroborated/verified).
- Every cell: value + sourceRefs (refs are specId:sourceId) or a gap id. No unsourced cells.
- Recommendation must name what would change it (e.g. "if volume > 10k/day, Vonage's quota wins").

## 4. Component compatibility (APIs that hand data to each other)
- File: `cross/checks/plan.json` → checks[] { id, from {specId, operationId, jsonPath}, to {specId, operationId, param|bodyPath},
  expect {type, format, maxLength, enum, encoding}, transform, steps[] (chained, cross-spec, mutating flag) }.
- Static check (Stage 3): compare declared schemas on both sides → mismatches become findings immediately.
- Live check (Stage 7): `validate.py --cross` runs the chain with real data, including boundary values where safe
  (longest title, unicode, empty optional fields).
