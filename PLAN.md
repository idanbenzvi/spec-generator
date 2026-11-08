# spec-generator: build plan

This file plans how to build the skill. What the skill does at runtime (its stages) is in `SKILL.md`.

## 1. Scope

| In | Out |
|---|---|
| PRD / ERD / lower-level requirements → one spec per unrelated requirement, one merged spec per related cluster | Implementation plans, tickets, code tied to a codebase |
| Auth & authz research first, offered to the user as a choice | Creating accounts on the user's behalf (CAPTCHA/ToS steps stay human) |
| Requests, schemas, quotas, sample data, test-account setup, validation scripts | Load testing, security testing of the provider |
| Multiple sources per API (corroboration + conflicts) and multiple APIs (candidate comparison, component hand-off checks) | Choosing a vendor for the user — the skill recommends; the user selects |
| Astro + React Bits site: try-it, findings, gaps, sources, timeline, comparator | Hosting/deploying the site (local preview; publishing is optional) |
| Versioning with semver bump + structural/line diff | Watching docs for changes automatically (re-run is manual) |

**Definition of done (per spec):** every operation `verified` by a passing live call with a captured sample, the docs
built, the user's token used, and `specgen.py status --gate` exits 0.

## 2. Architecture

```
requirements ──► Stage 0 intake ──► manifest.json
                        │ (one spec per unrelated requirement, merged spec per related cluster)
                        ▼
               Stage 1 auth/authz ──► findings.auth ──► USER CHOOSES METHOD (gate)
                        ▼
               Stage 2 requests ──► openapi.json + findings.{operations,quotas,findings,gaps,coverage}
                        ▼
               Stage 3 cross-validate ──► corroboration, conflicts, cross/comparisons, cross/checks
                        │                 ──► USER SELECTS CANDIDATES (gate, if comparison groups)
                        ▼
               Stage 4 commit v1 ──► versions/v1  (lint gate)
                        ▼
               Stage 5 setup ──► SETUP.md + validation-plan.json  (lint clean) ──► commit
                        ▼
               Stage 6 site ──► site/dist
                        ▼
               Stage 7 validate ◄── USER TOKEN (.env) + MUTATION APPROVAL
                        │  settles conflicts live; runs cross-API checks (--cross)
                        │  fail → back to earliest affected stage → new version
                        ▼
                    DONE gate (status --gate)
```

The model writes only JSON/Markdown under `specs/<id>/draft/`. Everything deterministic (lint, version, diff, validate,
redact, site data) is a script, so runs stay consistent and the output is diffable.

## 3. Repository scaffold (current state)

```
spec-generator/
  SKILL.md                     ✅ full description + stage definitions
  PLAN.md                      ✅ this file
  references/
    schemas.md                 🟡 outline — needs full JSON examples (M1)
    auth-research.md           🟡 outline (M1)
    source-research.md         🟡 outline (M1)
    cross-validation.md        🟡 outline (M1)
    site.md                    🟡 outline (M3)
  scripts/
    specgen.py                 ✅ implemented (init/new-spec/lint/commit/diff/status/site), untested;
                                  needs cross-validation support (M2): manifest apis/sources/groups, corroboration
                                  + conflict lint rules, cross/ diffing, not-selected gate state, cross checks in gate
    validate.py                🟡 stub with interface contract (M2), incl. --cross mode
    proxy.py                   🟡 stub (M2)
    oauth_token.py             🟡 stub (M2)
  assets/site-template/
    package.json, astro.config.mjs   🟡 pinned versions, untested build (M3)
    src/pages/…                🟡 stubs: index, specs/[id], specs/[id]/v/[n], timeline, compare, compare/[group], cross
    src/components/explorer/   🟡 stubs: ApiExplorer, TryIt, SchemaView
    src/components/compare/    🟡 stubs: Comparator, ComparisonMatrix
    src/components/rb/         ✅ React Bits: SpotlightCard, Counter, StarBorder, SplitFlapText
  evals/
    single-prd-github-sync/    🟡 prompt + placeholder grader
    two-unrelated-erds/        🟡 prompt + placeholder grader
    sparse-docs-gaps/          🟡 prompt + placeholder grader
    candidates-and-conflicts/  🟡 prompt + placeholder grader
```

## 4. Milestones

| # | Deliverable | Acceptance |
|---|---|---|
| **M1** References | `schemas.md` with a complete worked example per file; `auth-research.md`, `source-research.md` and `cross-validation.md` checklists | A fresh model can fill every file for a real API (e.g. GitHub) without asking about field meaning |
| **M2** Scripts | `validate.py`, `proxy.py`, `oauth_token.py`; tests for `specgen.py`; tool detection + fallbacks (Spectral, oasdiff, jsonschema, gitleaks/trufflehog) with `meta.json.tooling` | Fixture project: lint catches each injected error; commit → diff gives the expected bump; validate against a public no-auth API passes and redacts; proxy rejects non-allowlisted hosts; lint flags an unsourced conflict side and a single-source critical claim; `--cross` runs a chained two-spec fixture |
| **M3** Site | Layout + tokens, overview, SpecView, ApiExplorer/TryIt/SchemaView, timeline, comparator | `site --build` succeeds on the fixture; try-it works through the proxy; comparison matrix and cross page render from fixture; token never in storage/URL; dark + light; 375px width usable |
| **M4** End-to-end | Run the three eval cases with and without the skill (skill-creator loop) | With-skill runs stop at the auth gate, record gaps instead of inventing, and reach the done gate when given a token |
| **M5** Hardening | Description trigger optimisation (20 should/shouldn't-trigger queries), size pass on SKILL.md | ≥ 90% trigger accuracy on the held-out set |

## 5. Key decisions (and why)

- **OpenAPI 3.1 JSON + findings.json, not prose.** Tooling-friendly, diffable, and other tools can import it. Provenance
  lives beside the spec rather than inside it, so `openapi.json` stays standard.
- **Status vocabulary** `documented / inferred / verified / contradicted / not-found`. Separates "a doc says" from
  "we proved", which is the whole point of the deliverable.
- **Related requirements → one spec.** "Related" means shared provider, entity, or auth principal, or a data dependency. The decision is recorded
  in `manifest.relations` so a reviewer can disagree.
- **Integer versions + computed semver.** Integers for the timeline; semver tells a reader whether a change breaks
  consumers (removed op, new required param, grown scope set → major).
- **Own explorer instead of embedding Swagger UI/Scalar.** We need provenance badges, scopes, recorded responses and gaps
  inline per operation. Embedded tools also route try-it through third-party proxies by default, which would leak tokens.
- **Localhost CORS proxy.** Browsers block most third-party APIs from a static page. The proxy is allowlisted to the
  spec's hosts and bound to 127.0.0.1.
- **Token via `.env`, not chat.** Keeps credentials out of transcripts. Mutating calls need separate, explicit approval
  because they change a real account.
- **Cross-validation as its own stage (3), not folded into research.** Research collects every source; a separate pass
  judges them. That separation stops the model from settling on the first answer it finds. Live validation (Stage 7) is
  the final arbiter for conflicts.
- **One spec per candidate API.** Keeps alternatives independently versioned and validatable; the comparison lives in
  `cross/` and references the specs instead of duplicating them.
- **Independence is explicit (`derivedFrom`).** Docs generated from the provider's own OpenAPI agreeing with that
  OpenAPI doesn't count as corroboration.
- **Stdlib-first Python, standard tools when present.** Scripts run with no install step; Spectral, oasdiff,
  jsonschema/ajv, gitleaks/trufflehog and Pagefind are used when detected (see SKILL.md "Project tooling"), with
  built-in fallbacks and the tooling actually used recorded in `meta.json`. Node is already required for the site.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Hallucinated endpoints/limits | Lint requires sourceRefs/basis; the validation gate catches the rest |
| Docs stale vs live API | Live validation marks claims `contradicted`; changelog check in source research |
| Test account can't reach an endpoint (plan tier, app review) | Reported as a blocker finding; the gate stays open and says why. Never faked |
| Mutating calls damage a real account | `mutating` flag is mandatory for writes; `--allow-mutations` only after user approval; teardown steps |
| False confidence from "corroborated" claims that share an origin | `derivedFrom` + independence test; live verification outranks any agreement |
| Comparison cost explodes with many candidates | User selects which candidates get test accounts; others stay research-only (`not-selected`) |
| PII in captured samples | Key/value redaction + array truncation in `validate.py` |
| Site build friction (Node missing) | Data and spec files are useful without the site; build failure is reported, not hidden |

## 7. Open questions for the requester

1. Should the site be published (e.g. as a shared artifact or internal static hosting), or is a local preview enough?
2. Is there an internal API catalogue / existing OpenAPI registry to check before going to the web?
3. Should an existing company auth standard (e.g. "service accounts only") pre-filter the Stage 1 options?
