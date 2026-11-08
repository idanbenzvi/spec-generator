# Schemas — STUB (to be written in milestone M1)

Every file the model writes. Keep field names stable: lint, diff, validate and the site all depend on them.

## manifest.json
- `project`: title, createdAt, sourceMode (web|docs|sites|mixed), sourcesProvided[], mayExtendToWeb
- `requirements[]`: id (R1…), title, file, summary, specId
- `specs[]`: id, title, provider, requirementIds[], relatedSpecs[{id, reason}]
- `relations[]`: between[R…], reason, decision (merged|linked)
- `apis[]`: id, name, provider, role (candidate|component), specId, comparisonGroup
- `sources[]` (user-provided at intake): id, apiId, kind (docs-file|url|site|openapi|sdk-repo|postman), location, note
- `comparisonGroups[]`: id, requirementIds[], candidates[apiId], selected[apiId]

## findings.json
- `spec`: id, title, provider, requirementIds, summary, apiVersion, researchedAt
- `sources[]`: id (S1…), url, title, kind (official-docs|openapi|sdk|repo|changelog|community|user-provided), trust (primary|secondary|tertiary), retrievedAt, outsideProvidedSet, derivedFrom (source id — same origin ⇒ not independent)
- `auth`: methods[] {id, type, name, flows, endpoints, tokenLifetime, refresh, pkce, redirectRules, registration, recommended, rationale, status, sourceRefs}
         scopes[] {name, description, sensitive, requiresReview, requiredBy[], status, sourceRefs}
         roles[] / accountTypes[] {name, description, capabilities, limitations, status, sourceRefs}
         chosenMethod, minimalScopes[], notes[]
- `operations[]`: operationId, method, path, requirementRefs[], purpose, scopes[], status, sourceRefs, basis, notes, validation{result, httpStatus, at, schemaErrors, undocumentedFields, rateLimit}
- `quotas[]`: id, scope (global|per-endpoint|per-user|per-app|per-plan), limit, window, plan, headers[], retry, appliesTo[], status, sourceRefs, observed
- `findings[]`: id, category (auth|endpoint|quota|data|pagination|errors|webhooks|versioning|compliance|pricing|other), severity (info|warning|blocker), title, detail, status, sourceRefs
- `gaps[]`: id, question, whySought, whereLooked[], impact, suggestedResolution
- `requirementsCoverage[]`: requirementId, coverage (full|partial|none), coveredBy[operationId], notes

Status vocabulary: documented · inferred (needs basis) · verified · contradicted · not-found

Every claim (auth method, scope, operation, quota, finding) also carries:
- `corroboration`: single | corroborated | conflicting, with `agreeRefs[]` and `disagreeRefs[]`
- conflict findings add: `sides[] {value, sourceRefs}`, `resolution` (provisional|live|user|unresolved), `winner`, `rationale`

## cross/comparisons/<group>.json and cross/checks/plan.json, results.json
See references/cross-validation.md §3–4.

## validation-plan.json
- baseUrl (may use {{env.X}}), auth {type: bearer|apiKey|basic|none, tokenEnv, in, name}, defaultHeaders
- steps[]: id, operationId, method, path, pathParams, query, headers, body, mutating (required for writes),
  phase (setup|test|teardown), dependsOn[], expect {status[], responseSchema: bool, jsonPaths[]}, extract {var: path}

## validation/results.json
- runAt, baseUrl, summary {pass, fail, error, skipped}
- steps[]: id, operationId, result, httpStatus, durationMs, checks[], schemaErrors[], undocumentedFields[], rateLimit{}, responseHeaders (redacted), sample

## versions/vN/meta.json
- version, semver, parent, createdAt, message, bump (initial|major|minor|patch), breaking[], counts{}, validationSummary, validatedAt

TODO: full JSON example per file.
