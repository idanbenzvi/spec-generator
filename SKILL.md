---
name: spec-generator
description: Turn PRDs, ERDs, or lower-level requirements into a researched, versioned, live-validated API integration spec. Researches authentication and authorization first (methods, scopes, permissions, roles, user/account types) and offers the options, then finds every API request the requirements need, with quotas and rate limits, sample data, and scripts plus instructions for setting up or reusing a test account. Publishes an Astro + React Bits site with a Swagger-like try-it console, all findings, explicit gaps (what could not be found), every source used, a version timeline and a diff comparator. Accepts multiple sources and multiple APIs as input and cross-validates them: claims are corroborated across sources with conflicts surfaced, alternative APIs for the same requirement are compared side by side, and APIs that work together are checked for data compatibility. Sources can be provided docs, specific websites, OpenAPI files, SDK repos, or the open web. Use this whenever someone hands over product or engineering requirements and wants to know which APIs to call and how, asks to "spec out", research or document an integration, map a PRD to endpoints/scopes/limits, or validate an API spec against a test account, even if they never say "spec generator". Not for implementation plans or code tied to an existing codebase.
---

# Spec Generator

Turns requirements into an **evidence-backed API spec**: auth/authz options, the exact requests needed,
limits, sample data, test-account setup, and live validation, with every claim traced to a source or
marked as a gap. The output is a versioned spec bundle plus a static docs/try-it site.

**Boundary:** the skill stops at "here is what the API offers, how to authenticate, and proof each request
works." It does not produce implementation plans, tasks, or code tied to the user's codebase.

**Reader:** the site and every explanation are for a very technical reader. Be dense and precise: state
mechanisms, edge cases, tradeoffs and rationale, and skip basics (no "an API key is a secret string…").
Keep the structure navigable for anyone: status at a glance, clear headings, consistent badges.

---

## Core rules (why the skill works)

1. **Provenance on every claim.** Each auth method, scope, operation, quota and finding carries a `status`
   and `sourceRefs`. Status vocabulary:
   `documented` (an official source says so) · `inferred` (reasoned, with a `basis`) ·
   `verified` (confirmed by a live call) · `contradicted` (a source or live call disagrees) · `not-found`.
   Models confidently invent endpoints and limits. Provenance is what makes the output trustworthy.
2. **Gaps are first-class output.** Anything sought but not found becomes a `gap` entry with the question,
   why it matters, `whereLooked` (actual URLs and queries), and a suggested resolution. Never fill a gap with a guess.
3. **Auth before endpoints.** The available auth model decides which endpoints, scopes and account types
   are even reachable. Research it first and let the user choose before going deeper.
4. **Files are the source of truth, and the site is a rendering.** The model writes JSON
   (`openapi.json`, `findings.json`, `validation-plan.json`). Scripts handle versioning, diffing,
   validation and site generation, so results stay deterministic and diffable.
5. **Done means validated.** A request is finished only when a live call against a test account
   passed and its response was captured.
6. **Cross-validate, don't trust a single source.** A claim backed by one page is weaker than one backed by
   independent sources or a live call. Record every source that speaks to a claim, surface disagreements as
   conflicts, and never silently pick a winner. When several APIs are in play, compare alternatives on the same
   axes, and check that the data from one API is actually accepted by the next.
7. **Secrets never land in artifacts.** Tokens live in `.env` (git-ignored) or in memory in the browser.
   Results, samples and the site are redacted.

---

## Project layout

```
<project>/
  manifest.json                 requirements, specs, relations between them
  requirements/                 input PRDs/ERDs, copied verbatim
  specs/<spec-id>/
    draft/                      editable working copy
      openapi.json              OpenAPI 3.1 for the operations this spec needs
      findings.json             provenance, auth, quotas, findings, gaps, sources, coverage
      validation-plan.json      ordered live-validation steps
      SETUP.md                  test-account setup / reuse instructions
      samples/<operationId>.json  captured, redacted responses
      validation/results.json   latest run (+ runs/ history)
      scripts/                  spec-specific helpers (e.g. token acquisition)
    versions/vN/                immutable snapshots + meta.json (semver, bump, message)
  cross/
    comparisons/<group-id>.json alternative APIs for the same requirements: matrix + recommendation
    checks/plan.json            cross-API data-compatibility checks (chained live steps across specs)
    checks/results.json
  tools/                        validate.py, proxy.py, oauth_token.py (copied in by init)
  site/                         Astro site generated from assets/site-template
  .env.example / .env
```

Schemas for every file: `references/schemas.md`.

---

## How stages are defined

Every stage below uses the same six fields, and any new stage you add should too:

| Field | Meaning |
|---|---|
| **Goal** | One sentence: what is true when the stage is finished. |
| **Inputs** | Files and decisions the stage consumes (outputs of earlier stages). |
| **Actions** | Ordered steps. Point to a reference file for the "how" rather than inlining it. |
| **Produces** | Concrete files and fields written. Nothing outside this list is touched. |
| **Exit gate** | A checkable condition, preferably a script command with a zero exit code. |
| **User touchpoint** | What the user is asked or shown, or "none". A stage with a question **stops** until it is answered. |

Rules for stages:
- **Gates are hard.** Do not start stage N+1 until stage N's exit gate holds. If the gate can't be met,
  report what is blocking it and stop. Don't skip ahead.
- **Stages are per spec.** Independent specs move through the stages separately (and in parallel via
  subagents when available). Merged specs move as one unit.
- **Going back is normal.** Validation can contradict research. Go back to the earliest affected stage,
  fix the draft, and re-run forward. Each pass that changes the spec ends in a new version.
- **Batch user questions.** Each touchpoint asks everything it needs at once, across all specs at that stage.

---

## Stages

### Stage 0: Intake and decomposition
- **Goal:** each requirement is mapped to a spec, related requirements are merged, and the source mode is settled.
- **Inputs:** the user's PRDs/ERDs/requirements (files, pasted text, URLs), any sources they named (several per API
  is normal and encouraged), and any APIs they named (several allowed).
- **Actions:**
  1. `specgen.py init <project> --title … --source-mode web|docs|sites|mixed`, then copy the inputs into `requirements/`.
  2. Split the input into requirement units (R1, R2, …) with a one-line technical summary each.
  3. Register **APIs** in `manifest.apis`. Each API is either a **candidate** (one of several alternatives that could
     satisfy the same requirement, e.g. Twilio vs Vonage for SMS) or a **component** (needed alongside others,
     e.g. GitHub *and* Slack). Candidates for the same requirement form a **comparison group**. If the user gave one
     API but the requirement is commodity, ask whether they want alternatives compared.
  4. Register **provided sources** in `manifest.sources` and tie each one to an API (docs files, URLs, OpenAPI files,
     SDK repos, Postman collections).
  5. Detect relations. Requirements are **related** when they share an API provider, a data entity,
     or an auth principal, or when one's output is another's input. Related requirements are researched
     together as **one spec**; unrelated ones each get their own spec. Record each decision and its reason in
     `manifest.relations`. Each candidate API gets its own spec, so alternatives stay separate and comparable.
  6. Settle the source mode: `docs` (provided documents only), `sites` (named websites), `web`
     (open search, ranked by `references/source-research.md`), or `mixed`. Ask once whether research may go beyond
     the provided sources when something is missing (default yes, and such sources are flagged). Going beyond is
     also how independent corroboration is found, so say that when asking.
  7. `specgen.py new-spec` for each spec.
- **Produces:** `manifest.json` (requirements, apis, sources, relations, comparison groups), `requirements/*`, empty spec drafts.
- **Exit gate:** every requirement has a `specId` (or a comparison group); every API is a candidate or a component;
  every merge has a recorded reason.
- **User touchpoint:** show the requirement → spec/API mapping, comparison groups and merges, and confirm the source mode
  and web-extension permission.

### Stage 1: Authentication and authorization research → offer
- **Goal:** the user has chosen an auth method per spec, based on a researched comparison.
- **Inputs:** spec drafts, source mode.
- **Actions:** (checklist in `references/auth-research.md`)
  1. Look for a machine-readable spec first (`securitySchemes` often answers half of this).
  2. Catalogue every **auth method**: API key, OAuth 2.0 (each flow), OIDC, service account / JWT bearer,
     mTLS, HMAC request signing, Basic, and so on. For each, record endpoints, token lifetime, refresh and rotation,
     PKCE requirement, redirect-URI rules, and the app registration and review process.
  3. Catalogue **authorization**: the scope catalogue, roles and permissions in the provider's account model,
     **user/account types** (personal, org, enterprise, sandbox vs production, plan tiers that gate endpoints),
     consent model (admin vs user consent, incremental), and sensitive scopes that need app verification.
  4. Derive a provisional **least-privilege scope set** for the requirements. It is finalised in Stage 2.
  5. Write it all into `findings.auth` with provenance, and record anything missing as gaps.
  6. **Several APIs:** research auth separately for each API's spec. For component APIs, also state the combined
     credential picture (how many tokens/apps, whose identity each one acts as, and where consent happens). For candidates,
     auth friction becomes a comparison axis in Stage 3. Don't choose for a group the user hasn't seen yet.
- **Produces:** `findings.auth.{methods,scopes,roles,accountTypes,minimalScopes}`, sources, gaps; `components.securitySchemes`.
- **Exit gate:** `auth.methods` is non-empty with provenance, and `auth.chosenMethod` is set **by the user**.
- **User touchpoint (stops here):** an options table per spec with columns method · fits the requirement? ·
  scopes needed · account type needed · setup cost · security posture · token lifecycle, plus your recommendation and why.
  The user chooses. Record the choice in `auth.chosenMethod`.

### Stage 2: Request research
- **Goal:** every requirement maps to concrete operations (or to an explicit gap), with schemas, limits and sample data.
- **Inputs:** the chosen auth method, requirements, sources.
- **Actions:** (how-to in `references/source-research.md`)
  1. Map each requirement to the operations it needs, including setup and lookup calls the PRD doesn't mention
     (e.g. "resolve user id" before "list user's items").
  2. For each operation, capture method, path, params, request/response schemas, pagination, error model,
     idempotency, API-version headers, deprecation and sunset dates, and required scopes.
  3. Hunt quotas: global, per-endpoint, per-user, per-app, and per-plan limits; window; headers; retry semantics; cost or pricing tiers.
  4. Collect sample data from doc examples and spec `examples`. Live captures come in Stage 7.
  5. Fill `requirementsCoverage` (full/partial/none per requirement) and finalise `auth.minimalScopes`.
  6. Read **every** relevant source for a claim, not just the first that answers it, and list all of them in
     `sourceRefs`, including ones that disagree. Stage 3 needs that raw material.
- **Produces:** `openapi.json` (paths, components), `findings.{operations,quotas,findings,gaps,requirementsCoverage}`.
- **Exit gate:** `specgen.py lint <project> --spec <id>` reports no errors related to research (validation-plan errors are fine until Stage 5).
- **User touchpoint:** none, unless coverage is `none` for a requirement. Then show the gap and ask whether to widen the sources.

### Stage 3: Cross-validation
- **Goal:** every important claim has a corroboration level, every conflict is recorded, alternatives are compared,
  and data passed between component APIs has defined compatibility checks.
- **Inputs:** all Stage 1–2 drafts across specs, `manifest.apis` and comparison groups.
- **Actions:** (how-to in `references/cross-validation.md`)
  1. **Source corroboration (within one API).** For each claim, set `corroboration`:
     `single` (one source) · `corroborated` (≥2 *independent* sources agree) · `conflicting` (sources disagree).
     Two pages rendered from the same upstream spec are **not** independent. Note the shared origin.
     Critical claims (auth flows, scopes, required params, quotas) that remain `single` get a warning finding.
  2. **Conflicts.** Each disagreement becomes a `findings[]` entry with `category: conflict`, each side's value and source,
     a provisional resolution following the precedence in the reference file (provider OpenAPI > reference docs > SDK
     behaviour > guides > community, with newer changelog entries overriding older docs), and `resolution: provisional`.
     The live call in Stage 7 settles it for good.
  3. **Candidate comparison (alternative APIs).** For each comparison group, write `cross/comparisons/<group>.json`:
     a matrix with one row per requirement and axes coverage, auth model and consent friction, minimal scopes,
     account type/plan needed, quotas, pricing signals, data-model fit, deprecation risk and evidence strength, each cell
     with sourceRefs. Add a recommendation with rationale.
  4. **Component compatibility (APIs that work together).** For every data hand-off (A's output → B's input), add a check
     to `cross/checks/plan.json`: source field path, target param, expected type/format/length/enum, transformation
     needed, and the chained live steps that prove it (e.g. GitHub issue title → Slack `text`, 40k-char limit).
- **Produces:** `corroboration` on claims, conflict findings, `cross/comparisons/*.json`, `cross/checks/plan.json`.
- **Exit gate:** `specgen.py lint` clean for cross-validation rules: no critical claim missing `corroboration`, every
  conflict has both sides sourced, every comparison cell sourced or marked as a gap, every hand-off has a check.
- **User touchpoint (stops here when there are comparison groups):** show each matrix and recommendation; the user picks
  which candidates go on to live validation (validating all of them costs one test account each). Unchosen candidates
  stay in the site as researched-but-not-validated, and their gate is marked `not-selected` rather than open.
  Conflicts that need a human (e.g. contradictory pricing) are listed in the same message.

### Stage 4: Assemble and commit v1
- **Goal:** a coherent, linted, versioned spec exists before anything touches a live API.
- **Inputs:** Stage 1–3 drafts.
- **Actions:** reconcile `openapi.json` ↔ `findings.operations` (same operationIds, methods, paths), then lint and
  `specgen.py commit <project> <id> -m "research v1"`.
- **Produces:** `versions/v1/` + `meta.json` (semver `0.1.0`).
- **Exit gate:** commit succeeds (it refuses to commit while lint errors remain).
- **User touchpoint:** none.

### Stage 5: Test account and validation scripts
- **Goal:** the user can get or reuse credentials, and every operation has a runnable validation step.
- **Inputs:** chosen auth method, account types, operations.
- **Actions:**
  1. Write `SETUP.md`: create the test account or reuse an existing one, the required account type or plan, app registration,
     exact redirect URI (`http://127.0.0.1:8788/callback` for `tools/oauth_token.py`), scopes to grant, the env var names,
     and how to revoke afterwards. Note steps only a human can do (CAPTCHA, ToS, email verification, app review).
  2. Write `validation-plan.json`: one or more steps per operation, ordered, with `{{env.X}}` and `{{vars.x}}`
     substitution, `extract` for chaining ids, explicit `mutating: true|false`, and teardown steps that clean up anything
     the run created.
  3. Add spec-specific helpers to `draft/scripts/` only when the shared tools don't cover something (e.g. HMAC signing).
  4. Add the env var names to `.env.example`.
- **Produces:** `SETUP.md`, `validation-plan.json`, optional `scripts/*`, `.env.example`.
- **Exit gate:** `specgen.py lint` is fully clean; commit a new version.
- **User touchpoint:** none yet. The token request happens in Stage 7, after the docs exist.
- Selected candidates and component APIs get a setup and a plan. Unselected candidates don't.

### Stage 6: Docs and try-it site
- **Goal:** a browsable site shows everything researched so far.
- **Actions:** `specgen.py site <project> --build`. The site (see `references/site.md`) has an overview, per-spec pages
  (auth & authz, endpoint explorer with try-it, quotas, findings incl. conflicts, gaps, coverage, sources with
  corroboration badges, setup), a version timeline, a version comparator, a candidate comparison page per group,
  and a cross-API checks page.
- **Produces:** `site/src/data/project.json`, `site/dist/`.
- **Exit gate:** build succeeds.
- **User touchpoint:** point the user at the site (`npm --prefix site run preview`) as context for the next request.

### Stage 7: Live validation → done
- **Goal:** every request has passed against a real test account and has a captured response; the spec and site reflect that.
- **Actions:**
  1. **Ask the user for credentials.** Tell them to put the token in `<project>/.env` under the variable names from
     `SETUP.md`, which keeps it out of the chat transcript. If they paste it anyway, use it for this run only and don't
     write it anywhere except `.env` if they ask you to.
  2. **Ask separately before any mutating step** (POST/PUT/PATCH/DELETE): list exactly what will be created, changed or
     deleted on the test account. Run with `--allow-mutations` only after an explicit yes.
  3. `python tools/validate.py <project> <spec-id>`. It runs the steps, checks status and response-schema conformance,
     records undocumented fields and rate-limit headers, saves redacted samples, and promotes passing operations to `verified`.
  4. For each failure, diagnose whether the **research** was wrong (fix the draft and mark the original claim `contradicted`
     with the live evidence) or the **plan** was wrong (fix the step). Re-run. Reconcile observed rate-limit headers with `quotas`.
  5. **Settle conflicts with live evidence.** For each `conflict` finding the run touched, set `resolution: live`, record
     which side the API agreed with, and mark the losing claim `contradicted`. Conflicts the run can't reach (pricing,
     plan limits) stay `provisional` and are listed in the final report.
  6. **Run cross-API checks** once every component spec passes: `python tools/validate.py <project> --cross`. A failed
     hand-off is a finding on both specs (e.g. "GitHub title can exceed Slack block text limit; truncate at 3000").
  7. Commit each changed spec (`-m "validated against live API"`), then rebuild the site.
- **Exit gate:** `specgen.py status <project> --gate` exits 0: for every selected spec, every operation `verified`, every step
  passing, a sample per operation, auth chosen, no uncommitted draft changes; every cross-API check passing; the site
  rebuilt. Unselected candidates are reported as `not-selected` and don't block.
- **User touchpoint:** token request, mutation approval, and the final report.

---

## Versioning (cross-cutting)

- Versions are integers (`v1`, `v2`, …) with a semver label computed from the diff:
  **major** = operation removed, param became required or changed type, security changed, chosen auth changed, or minimal
  scope set grew (re-consent needed); **minor** = operations, scopes or quotas added; **patch** = everything else
  (status changes, findings, sources, docs).
- Corroboration and conflict-resolution changes show up in the diff (patch level), so the timeline shows confidence
  increasing over time, not only the API surface changing.
- Commit at the end of Stage 4 and Stage 5, after every Stage 7 fix loop, and whenever the user asks to re-research
  (e.g. after docs change). Each commit message says *why* the spec changed.
- `specgen.py diff <project> <id> v1 v3` gives the structural diff. The site's comparator also shows a unified
  line diff of each file.

## Script reference

| Command | Purpose |
|---|---|
| `scripts/specgen.py init / new-spec` | scaffold project and spec drafts |
| `scripts/specgen.py lint` | provenance, cross-file consistency, plan coverage |
| `scripts/specgen.py commit / diff` | immutable versions, semver bump, structural + text diff |
| `scripts/specgen.py status --gate` | the done gate |
| `scripts/specgen.py site --build` | generate site data and build the Astro site |
| `tools/validate.py` | run the validation plan, capture redacted samples, update provenance; `--cross` runs cross-API checks |
| `tools/proxy.py` | localhost CORS proxy for the site's try-it console |
| `tools/oauth_token.py` | client-credentials / auth-code + PKCE / device-code / refresh helper |

## Project tooling

Standard tools the skill uses at specific stages. They replace homegrown logic wherever a mature tool exists,
because the "verified" label is only as trustworthy as the checks behind it.

| Stage | Tool | Use it for |
|---|---|---|
| 1–3 | **WebSearch / WebFetch** (built-in) | Primary research: finding and reading docs, specs, changelogs, pricing and limits pages. |
| 1–3 | **Subagents** (Agent tool) | Parallel research of independent specs. For cross-validation, give one agent the docs and another the SDK/OpenAPI, and don't show either one the other's answer; the agreement or disagreement is the evidence. |
| 1–2 | **APIs.guru** (`api.apis.guru/v2/list.json`) | First step of spec discovery: check for an existing published OpenAPI document before reading prose docs. Record it as a source (it is a mirror, so set `derivedFrom` to the provider's original). |
| 2, 4–5 | **Spectral** (`npx @stoplight/spectral-cli lint openapi.json`) | Structural and style lint of `openapi.json`. `specgen.py lint` still owns provenance, cross-file and cross-validation rules; run both. |
| Versioning | **oasdiff** (`oasdiff breaking` / `oasdiff changelog`) | Breaking-change detection on the OpenAPI part of a version diff. `specgen.py diff` keeps ownership of findings, auth, quotas, corroboration and validation changes, and takes the larger bump of the two. |
| 7 | **jsonschema** (Python) / **ajv** (Node) | Response-schema validation in `validate.py` (full `$ref`, `oneOf`/`anyOf`/`allOf`, formats). The built-in subset checker is only a fallback. |
| 7, gate | **gitleaks** or **trufflehog** | Secret scan of the whole project (samples, results, site data, `site/dist`) before the done gate. A hit fails the gate. |
| 6 | **Shiki** (built into Astro) + **Pagefind** | Syntax highlighting for payloads and schemas; static full-text search across specs, findings and sources, with no server. |

**Detect, then fall back.** Teammates won't all have every tool installed, so each script checks for its tool
(`shutil.which`, `npx --no-install`, importable module). If the tool is there, the script uses it; if not, it falls back
to the built-in check and says so in its output. Record what actually ran in `meta.json` (`tooling: {lint: "spectral"|"builtin", schema: "jsonschema"|"builtin", ...}`),
so a reviewer can tell a version checked by Spectral and jsonschema from one checked only by the fallbacks. The site
shows this per version. Never install tools on the user's machine without asking; suggest the install command instead.

## Final report to the user

Per spec: version and semver, validated X/Y operations, chosen auth method + minimal scopes, the top findings
(blockers first), gaps with their impact, and the path to the site. Across specs: the comparison recommendation and
which candidates were selected, conflicts settled live vs still provisional, critical claims still backed by a single
source, and cross-API check results. If the gate is not met, say so plainly
and list what is blocking it. Never describe an open spec as done.
