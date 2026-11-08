#!/usr/bin/env python3
"""specgen — project scaffolding, linting, versioning, diffing, gating and site data
for the spec-generator skill. Standard library only.

Subcommands
  init      <project> --title T [--source-mode web|docs|sites|mixed] [--git]
  new-spec  <project> <spec-id> --title T --requirements R1,R2 [--provider P]
  lint      <project> [--spec ID] [--draft-only]
  commit    <project> <spec-id> -m MESSAGE
  diff      <project> <spec-id> <from> <to> [--json]      (versions: 1, v1, draft)
  status    <project> [--gate] [--spec ID]
  site      <project> [--build] [--refresh-template]

Layout of a project
  manifest.json
  requirements/                 source PRDs/ERDs (copied verbatim)
  specs/<id>/draft/             editable working copy
      openapi.json findings.json validation-plan.json SETUP.md
      samples/<operationId>.json validation/results.json validation/runs/*.json
      scripts/                  spec-specific helpers (token acquisition etc.)
  specs/<id>/versions/vN/       immutable snapshots + meta.json
  tools/                        validate.py proxy.py oauth_token.py (copied from the skill)
  site/                         Astro site (copied from the skill template)
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_DIR / "assets" / "site-template"
TOOLS = ["validate.py", "proxy.py", "oauth_token.py"]

STATUSES = {"documented", "inferred", "verified", "contradicted", "not-found"}
HTTP_METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}
SPEC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


# ───────────────────────── helpers ─────────────────────────

def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load(p: Path, default=None):
    if not p.exists():
        if default is not None:
            return default
        sys.exit(f"error: missing {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"error: {p} is not valid JSON: {e}")


def dump(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def canonical(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


def spec_dir(project: Path, spec_id: str) -> Path:
    d = project / "specs" / spec_id
    if not d.exists():
        sys.exit(f"error: no spec '{spec_id}' in {project}")
    return d


def versions(sd: Path) -> list[int]:
    vd = sd / "versions"
    if not vd.exists():
        return []
    return sorted(int(p.name[1:]) for p in vd.iterdir() if p.is_dir() and re.fullmatch(r"v\d+", p.name))


def resolve_version_dir(sd: Path, ref: str) -> Path:
    if ref == "draft":
        return sd / "draft"
    if ref in ("latest", "head"):
        vs = versions(sd)
        if not vs:
            sys.exit("error: no committed versions")
        return sd / "versions" / f"v{vs[-1]}"
    n = ref[1:] if ref.startswith("v") else ref
    p = sd / "versions" / f"v{int(n)}"
    if not p.exists():
        sys.exit(f"error: version {ref} not found")
    return p


def load_bundle(d: Path) -> dict:
    samples = {}
    sdir = d / "samples"
    if sdir.exists():
        for f in sorted(sdir.glob("*.json")):
            try:
                samples[f.stem] = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                samples[f.stem] = {"_unparseable": f.read_text(encoding="utf-8")[:2000]}
    return {
        "openapi": load(d / "openapi.json", {}),
        "findings": load(d / "findings.json", {}),
        "plan": load(d / "validation-plan.json", {}),
        "results": load(d / "validation" / "results.json", {}),
        "setup": (d / "SETUP.md").read_text(encoding="utf-8") if (d / "SETUP.md").exists() else "",
        "samples": samples,
        "meta": load(d / "meta.json", {}),
    }


def iter_operations(openapi: dict):
    for path, item in (openapi.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for m, op in item.items():
            if m.lower() in HTTP_METHODS and isinstance(op, dict):
                yield m.upper(), path, op


def op_key(method: str, path: str) -> str:
    return f"{method.upper()} {path}"


# ───────────────────────── init / new-spec ─────────────────────────

def cmd_init(a):
    project = Path(a.project).resolve()
    if (project / "manifest.json").exists():
        sys.exit(f"error: {project} already initialised")
    for sub in ("requirements", "specs", "tools"):
        (project / sub).mkdir(parents=True, exist_ok=True)
    dump(project / "manifest.json", {
        "project": {"title": a.title, "createdAt": now(), "sourceMode": a.source_mode,
                     "sourcesProvided": [], "mayExtendToWeb": True},
        "requirements": [],
        "specs": [],
        "relations": [],
    })
    for t in TOOLS:
        shutil.copy2(SKILL_DIR / "scripts" / t, project / "tools" / t)
    (project / ".gitignore").write_text(
        ".env\n.env.*\n!.env.example\nsite/node_modules/\nsite/dist/\nsite/.astro/\n__pycache__/\n", encoding="utf-8")
    (project / ".env.example").write_text(
        "# Copy to .env and fill in. .env is git-ignored and is never copied into the site or results.\n",
        encoding="utf-8")
    if a.git and shutil.which("git"):
        subprocess.run(["git", "init", "-q"], cwd=project, check=False)
    print(f"initialised {project}")


def cmd_new_spec(a):
    project = Path(a.project).resolve()
    if not SPEC_ID_RE.match(a.spec_id):
        sys.exit("error: spec id must be lowercase kebab-case, 2-63 chars")
    man = load(project / "manifest.json")
    if any(s["id"] == a.spec_id for s in man["specs"]):
        sys.exit(f"error: spec {a.spec_id} exists")
    reqs = [r.strip() for r in (a.requirements or "").split(",") if r.strip()]
    draft = project / "specs" / a.spec_id / "draft"
    (draft / "samples").mkdir(parents=True, exist_ok=True)
    (draft / "validation" / "runs").mkdir(parents=True, exist_ok=True)
    (draft / "scripts").mkdir(parents=True, exist_ok=True)
    dump(draft / "openapi.json", {
        "openapi": "3.1.0",
        "info": {"title": a.title, "version": "0.0.0",
                  "description": "Generated by spec-generator. Provenance for every element lives in findings.json."},
        "servers": [], "paths": {}, "components": {"schemas": {}, "securitySchemes": {}}, "security": [],
    })
    dump(draft / "findings.json", {
        "spec": {"id": a.spec_id, "title": a.title, "provider": a.provider or "", "requirementIds": reqs,
                  "summary": "", "apiVersion": "", "researchedAt": now()},
        "sources": [], "auth": {"methods": [], "scopes": [], "roles": [], "accountTypes": [],
                                 "chosenMethod": None, "minimalScopes": [], "notes": []},
        "operations": [], "quotas": [], "findings": [], "gaps": [], "requirementsCoverage": [],
    })
    dump(draft / "validation-plan.json", {"baseUrl": "", "auth": {"type": "none"}, "defaultHeaders": {}, "steps": []})
    (draft / "SETUP.md").write_text(f"# {a.title} — test account setup\n\n_TODO_\n", encoding="utf-8")
    man["specs"].append({"id": a.spec_id, "title": a.title, "provider": a.provider or "",
                          "requirementIds": reqs, "relatedSpecs": []})
    for r in man["requirements"]:
        if r["id"] in reqs:
            r["specId"] = a.spec_id
    dump(project / "manifest.json", man)
    print(f"created spec {a.spec_id} at {draft}")


# ───────────────────────── lint ─────────────────────────

def lint_bundle(b: dict, label: str, manifest: dict | None = None) -> tuple[list[str], list[str]]:
    E, W = [], []
    oa, f, plan = b["openapi"], b["findings"], b["plan"]
    if not oa.get("openapi", "").startswith("3."):
        E.append("openapi.json: 'openapi' must be 3.x")
    if not oa.get("servers"):
        E.append("openapi.json: no servers[] — the try-it console and validator need a base URL")

    src_ids = set()
    for s in f.get("sources", []):
        sid = s.get("id")
        if not sid:
            E.append("sources: entry without id"); continue
        if sid in src_ids:
            E.append(f"sources: duplicate id {sid}")
        src_ids.add(sid)
        for k in ("url", "title", "kind", "retrievedAt"):
            if not s.get(k):
                E.append(f"sources[{sid}]: missing {k}")

    def check_claim(where: str, c: dict, need_status=True):
        st = c.get("status")
        if need_status and st not in STATUSES:
            E.append(f"{where}: status '{st}' not in {sorted(STATUSES)}")
        refs = c.get("sourceRefs") or []
        for r in refs:
            if r not in src_ids:
                E.append(f"{where}: sourceRef {r} not in sources[]")
        if st in ("documented", "contradicted") and not refs:
            E.append(f"{where}: status {st} requires sourceRefs")
        if st == "inferred" and not (c.get("basis") or c.get("notes")):
            E.append(f"{where}: inferred claims need 'basis' explaining the inference")

    auth = f.get("auth", {})
    method_ids = set()
    for m in auth.get("methods", []):
        method_ids.add(m.get("id"))
        check_claim(f"auth.methods[{m.get('id')}]", m)
    if not auth.get("methods"):
        E.append("auth.methods is empty — auth research comes first")
    if auth.get("chosenMethod") and auth["chosenMethod"] not in method_ids:
        E.append(f"auth.chosenMethod {auth['chosenMethod']} not in auth.methods")
    if not auth.get("chosenMethod"):
        W.append("auth.chosenMethod not set — the user has not picked an auth method yet")
    scope_names = set()
    for s in auth.get("scopes", []):
        scope_names.add(s.get("name"))
        check_claim(f"auth.scopes[{s.get('name')}]", s)
    for s in auth.get("minimalScopes", []):
        if s not in scope_names:
            E.append(f"auth.minimalScopes: {s} not described in auth.scopes")
    for k in ("roles", "accountTypes"):
        for x in auth.get(k, []):
            check_claim(f"auth.{k}[{x.get('name')}]", x)

    oa_ops = {}
    for m, p, op in iter_operations(oa):
        oid = op.get("operationId")
        if not oid:
            E.append(f"openapi {m} {p}: missing operationId")
            continue
        if oid in oa_ops:
            E.append(f"openapi: duplicate operationId {oid}")
        oa_ops[oid] = (m, p, op)
    f_ops = {}
    for o in f.get("operations", []):
        oid = o.get("operationId")
        f_ops[oid] = o
        where = f"operations[{oid}]"
        check_claim(where, o)
        if oid not in oa_ops and o.get("status") != "not-found":
            E.append(f"{where}: not present in openapi.json")
        if oid in oa_ops:
            m, p, _ = oa_ops[oid]
            if (o.get("method", "").upper(), o.get("path")) != (m, p):
                E.append(f"{where}: method/path {o.get('method')} {o.get('path')} != openapi {m} {p}")
        for s in o.get("scopes", []):
            if scope_names and s not in scope_names:
                W.append(f"{where}: scope {s} not described in auth.scopes")
        if not o.get("requirementRefs"):
            W.append(f"{where}: no requirementRefs — why is this request in the spec?")
    for oid in oa_ops:
        if oid not in f_ops:
            E.append(f"openapi operation {oid} has no provenance entry in findings.operations")

    for q in f.get("quotas", []):
        check_claim(f"quotas[{q.get('id')}]", q)
        for oid in q.get("appliesTo", []):
            if oid != "*" and oid not in oa_ops:
                W.append(f"quotas[{q.get('id')}]: appliesTo unknown operation {oid}")
    if not f.get("quotas"):
        W.append("quotas is empty — if none were found, record a gap saying where you looked")
    for x in f.get("findings", []):
        check_claim(f"findings[{x.get('id')}]", x)
    for g in f.get("gaps", []):
        if not g.get("whereLooked"):
            E.append(f"gaps[{g.get('id')}]: whereLooked is required (URLs/queries actually tried)")
        if not g.get("question"):
            E.append(f"gaps[{g.get('id')}]: question is required")

    req_ids = set(f.get("spec", {}).get("requirementIds", []))
    covered = {c.get("requirementId") for c in f.get("requirementsCoverage", [])}
    if req_ids and not f.get("requirementsCoverage"):
        E.append("requirementsCoverage is empty")
    if manifest:
        known = {r["id"] for r in manifest.get("requirements", [])}
        for r in req_ids - known:
            W.append(f"spec.requirementIds: {r} not in manifest.requirements")
    for c in f.get("requirementsCoverage", []):
        for oid in c.get("coveredBy", []):
            if oid not in oa_ops:
                E.append(f"requirementsCoverage[{c.get('requirementId')}]: coveredBy unknown op {oid}")

    plan_ops = set()
    step_ids = set()
    for st in plan.get("steps", []):
        sid = st.get("id")
        if sid in step_ids:
            E.append(f"validation-plan: duplicate step id {sid}")
        step_ids.add(sid)
        oid = st.get("operationId")
        plan_ops.add(oid)
        if oid not in oa_ops:
            E.append(f"validation-plan step {sid}: operationId {oid} not in openapi")
        elif (st.get("method", "").upper(), st.get("path")) != oa_ops[oid][:2]:
            E.append(f"validation-plan step {sid}: method/path disagree with openapi")
        if st.get("method", "").upper() in ("POST", "PUT", "PATCH", "DELETE") and "mutating" not in st:
            E.append(f"validation-plan step {sid}: write method must declare mutating true/false explicitly")
    for oid in oa_ops:
        if oid not in plan_ops:
            E.append(f"validation-plan: operation {oid} has no validation step")
    if not plan.get("baseUrl"):
        E.append("validation-plan: baseUrl missing")
    if "TODO" in b.get("setup", "") or not b.get("setup", "").strip():
        W.append("SETUP.md still has TODO / is empty")

    return [f"[{label}] {e}" for e in E], [f"[{label}] {w}" for w in W]


def cmd_lint(a):
    project = Path(a.project).resolve()
    man = load(project / "manifest.json")
    ids = [a.spec] if a.spec else [s["id"] for s in man["specs"]]
    E, W = [], []
    for sid in ids:
        sd = spec_dir(project, sid)
        e, w = lint_bundle(load_bundle(sd / "draft"), f"{sid}/draft", man)
        E += e; W += w
    for w in W:
        print("warn ", w)
    for e in E:
        print("ERROR", e)
    print(f"{len(E)} error(s), {len(W)} warning(s)")
    sys.exit(1 if E else 0)


# ───────────────────────── diff ─────────────────────────

def _param_sig(op: dict) -> dict:
    out = {}
    for prm in op.get("parameters", []) or []:
        if "$ref" in prm:
            out[prm["$ref"]] = {"ref": True}
            continue
        out[f"{prm.get('in')}:{prm.get('name')}"] = {
            "required": bool(prm.get("required")),
            "type": (prm.get("schema") or {}).get("type"),
        }
    return out


def _h(x) -> str:
    return hashlib.sha1(canonical(x).encode()).hexdigest()[:10]


def _by(items, key):
    return {i.get(key): i for i in items or [] if isinstance(i, dict)}


def structural_diff(A: dict, B: dict) -> dict:
    """Semantic diff between two bundles. Returns changes + recommended semver bump."""
    ch = {"operations": {"added": [], "removed": [], "changed": []},
          "auth": {"methodsAdded": [], "methodsRemoved": [], "scopesAdded": [], "scopesRemoved": [],
                   "chosenMethod": None, "minimalScopes": None, "rolesChanged": False, "accountTypesChanged": False},
          "quotas": {"added": [], "removed": [], "changed": []},
          "findings": {"added": [], "removed": [], "statusChanged": []},
          "gaps": {"added": [], "resolved": []},
          "sources": {"added": [], "removed": []},
          "statusChanges": [],
          "validation": None}
    breaking, additive = [], []

    ao = {op_key(m, p): op for m, p, op in iter_operations(A["openapi"])}
    bo = {op_key(m, p): op for m, p, op in iter_operations(B["openapi"])}
    for k in sorted(bo.keys() - ao.keys()):
        ch["operations"]["added"].append(k); additive.append(f"operation added: {k}")
    for k in sorted(ao.keys() - bo.keys()):
        ch["operations"]["removed"].append(k); breaking.append(f"operation removed: {k}")
    for k in sorted(ao.keys() & bo.keys()):
        x, y = ao[k], bo[k]
        details = []
        px, py = _param_sig(x), _param_sig(y)
        for pk in sorted(py.keys() - px.keys()):
            details.append(f"param added {pk}{' (required)' if py[pk].get('required') else ''}")
            if py[pk].get("required"):
                breaking.append(f"{k}: new required param {pk}")
        for pk in sorted(px.keys() - py.keys()):
            details.append(f"param removed {pk}"); breaking.append(f"{k}: param removed {pk}")
        for pk in sorted(px.keys() & py.keys()):
            if px[pk] != py[pk]:
                details.append(f"param changed {pk}: {px[pk]} → {py[pk]}")
                if py[pk].get("required") and not px[pk].get("required"):
                    breaking.append(f"{k}: param {pk} became required")
                if px[pk].get("type") != py[pk].get("type"):
                    breaking.append(f"{k}: param {pk} type changed")
        if _h(x.get("requestBody")) != _h(y.get("requestBody")):
            details.append("request body changed")
        rx, ry = set((x.get("responses") or {}).keys()), set((y.get("responses") or {}).keys())
        if rx != ry:
            details.append(f"response codes {sorted(rx)} → {sorted(ry)}")
        elif _h(x.get("responses")) != _h(y.get("responses")):
            details.append("response schema changed")
        sx, sy = canonical(x.get("security")), canonical(y.get("security"))
        if sx != sy:
            details.append("security requirements changed"); breaking.append(f"{k}: security changed")
        if details:
            ch["operations"]["changed"].append({"op": k, "details": details})

    fa, fb = A["findings"], B["findings"]
    aa, ab = fa.get("auth", {}), fb.get("auth", {})
    ma, mb = _by(aa.get("methods"), "id"), _by(ab.get("methods"), "id")
    ch["auth"]["methodsAdded"] = sorted(mb.keys() - ma.keys())
    ch["auth"]["methodsRemoved"] = sorted(ma.keys() - mb.keys())
    sa, sb = _by(aa.get("scopes"), "name"), _by(ab.get("scopes"), "name")
    ch["auth"]["scopesAdded"] = sorted(sb.keys() - sa.keys())
    ch["auth"]["scopesRemoved"] = sorted(sa.keys() - sb.keys())
    if aa.get("chosenMethod") != ab.get("chosenMethod"):
        ch["auth"]["chosenMethod"] = {"from": aa.get("chosenMethod"), "to": ab.get("chosenMethod")}
        if aa.get("chosenMethod"):
            breaking.append("chosen auth method changed")
    msa, msb = set(aa.get("minimalScopes") or []), set(ab.get("minimalScopes") or [])
    if msa != msb:
        ch["auth"]["minimalScopes"] = {"added": sorted(msb - msa), "removed": sorted(msa - msb)}
        if msb - msa:
            breaking.append("minimal scope set grew (re-consent required)")
    ch["auth"]["rolesChanged"] = _h(aa.get("roles")) != _h(ab.get("roles"))
    ch["auth"]["accountTypesChanged"] = _h(aa.get("accountTypes")) != _h(ab.get("accountTypes"))
    if ch["auth"]["methodsAdded"] or ch["auth"]["scopesAdded"]:
        additive.append("auth methods/scopes documented")

    qa, qb = _by(fa.get("quotas"), "id"), _by(fb.get("quotas"), "id")
    ch["quotas"]["added"] = sorted(qb.keys() - qa.keys())
    ch["quotas"]["removed"] = sorted(qa.keys() - qb.keys())
    for k in sorted(qa.keys() & qb.keys()):
        x, y = qa[k], qb[k]
        diffs = {f: {"from": x.get(f), "to": y.get(f)} for f in ("limit", "window", "status", "observed", "scope")
                 if canonical(x.get(f)) != canonical(y.get(f))}
        if diffs:
            ch["quotas"]["changed"].append({"id": k, "fields": diffs})
    if ch["quotas"]["added"]:
        additive.append("quotas added")

    xa, xb = _by(fa.get("findings"), "id"), _by(fb.get("findings"), "id")
    ch["findings"]["added"] = sorted(xb.keys() - xa.keys())
    ch["findings"]["removed"] = sorted(xa.keys() - xb.keys())
    for k in sorted(xa.keys() & xb.keys()):
        if xa[k].get("status") != xb[k].get("status"):
            ch["findings"]["statusChanged"].append({"id": k, "from": xa[k].get("status"), "to": xb[k].get("status")})

    ga, gb = _by(fa.get("gaps"), "id"), _by(fb.get("gaps"), "id")
    ch["gaps"]["added"] = sorted(gb.keys() - ga.keys())
    ch["gaps"]["resolved"] = sorted(ga.keys() - gb.keys())
    ra, rb = _by(fa.get("sources"), "id"), _by(fb.get("sources"), "id")
    ch["sources"]["added"] = sorted(rb.keys() - ra.keys())
    ch["sources"]["removed"] = sorted(ra.keys() - rb.keys())

    oa_, ob_ = _by(fa.get("operations"), "operationId"), _by(fb.get("operations"), "operationId")
    for k in sorted(oa_.keys() & ob_.keys()):
        if oa_[k].get("status") != ob_[k].get("status"):
            ch["statusChanges"].append({"operationId": k, "from": oa_[k].get("status"), "to": ob_[k].get("status")})

    def vsum(r):
        return (r or {}).get("summary") or {}
    va, vb = vsum(A.get("results")), vsum(B.get("results"))
    if va != vb:
        ch["validation"] = {"from": va, "to": vb}

    bump = "major" if breaking else "minor" if additive else "patch"
    return {"bump": bump, "breaking": breaking, "additive": additive, "changes": ch,
            "counts": {
                "opsAdded": len(ch["operations"]["added"]), "opsRemoved": len(ch["operations"]["removed"]),
                "opsChanged": len(ch["operations"]["changed"]), "statusChanges": len(ch["statusChanges"]),
                "quotasChanged": len(ch["quotas"]["added"]) + len(ch["quotas"]["removed"]) + len(ch["quotas"]["changed"]),
                "gapsAdded": len(ch["gaps"]["added"]), "gapsResolved": len(ch["gaps"]["resolved"]),
                "sourcesAdded": len(ch["sources"]["added"]),
            }}


def text_diff(A: dict, B: dict, la: str, lb: str) -> dict:
    out = {}
    for name in ("openapi", "findings", "plan"):
        a = canonical(A.get(name) or {}).splitlines()
        b = canonical(B.get(name) or {}).splitlines()
        fname = {"openapi": "openapi.json", "findings": "findings.json", "plan": "validation-plan.json"}[name]
        out[fname] = "\n".join(difflib.unified_diff(a, b, f"{la}/{fname}", f"{lb}/{fname}", n=3, lineterm=""))
    a, b = (A.get("setup") or "").splitlines(), (B.get("setup") or "").splitlines()
    out["SETUP.md"] = "\n".join(difflib.unified_diff(a, b, f"{la}/SETUP.md", f"{lb}/SETUP.md", n=3, lineterm=""))
    return out


def has_changes(d: dict, t: dict) -> bool:
    return any(t.values())


def bump_semver(prev: str, bump: str) -> str:
    try:
        M, m, p = (int(x) for x in prev.split("."))
    except Exception:
        M, m, p = 0, 0, 0
    if bump == "major":
        return f"{M + 1}.0.0"
    if bump == "minor":
        return f"{M}.{m + 1}.0"
    return f"{M}.{m}.{p + 1}"


def cmd_diff(a):
    project = Path(a.project).resolve()
    sd = spec_dir(project, a.spec_id)
    A, B = load_bundle(resolve_version_dir(sd, a.frm)), load_bundle(resolve_version_dir(sd, a.to))
    d = structural_diff(A, B)
    if a.json:
        d["text"] = text_diff(A, B, a.frm, a.to)
        print(json.dumps(d, indent=2))
        return
    print(f"{a.spec_id}: {a.frm} → {a.to}  (bump: {d['bump']})")
    for b in d["breaking"]:
        print("  BREAKING ", b)
    for k, v in d["counts"].items():
        if v:
            print(f"  {k}: {v}")
    for c in d["changes"]["operations"]["changed"]:
        print(f"  ~ {c['op']}: {'; '.join(c['details'])}")
    for s in d["changes"]["statusChanges"]:
        print(f"  status {s['operationId']}: {s['from']} → {s['to']}")
    if d["changes"]["validation"]:
        print(f"  validation: {d['changes']['validation']['from']} → {d['changes']['validation']['to']}")


# ───────────────────────── commit ─────────────────────────

def cmd_commit(a):
    project = Path(a.project).resolve()
    man = load(project / "manifest.json")
    sd = spec_dir(project, a.spec_id)
    draft = sd / "draft"
    b = load_bundle(draft)
    E, W = lint_bundle(b, f"{a.spec_id}/draft", man)
    for w in W:
        print("warn ", w)
    if E:
        for e in E:
            print("ERROR", e)
        sys.exit("commit refused: fix lint errors first")
    vs = versions(sd)
    n = (vs[-1] + 1) if vs else 1
    if vs:
        prev_dir = sd / "versions" / f"v{vs[-1]}"
        P = load_bundle(prev_dir)
        d = structural_diff(P, b)
        t = text_diff(P, b, f"v{vs[-1]}", "draft")
        if not has_changes(d, t) and _h(P["samples"]) == _h(b["samples"]):
            sys.exit("commit refused: draft is identical to latest version")
        semver = bump_semver(P["meta"].get("semver", "0.1.0"), d["bump"])
        parent = vs[-1]
    else:
        d = {"bump": "initial", "breaking": [], "additive": [], "counts": {}}
        semver, parent = "0.1.0", None
    dest = sd / "versions" / f"v{n}"
    shutil.copytree(draft, dest, ignore=shutil.ignore_patterns("runs", "__pycache__"))
    res = b.get("results") or {}
    meta = {"version": n, "semver": semver, "parent": parent, "createdAt": now(), "message": a.message,
            "bump": d["bump"], "breaking": d.get("breaking", []), "counts": d.get("counts", {}),
            "validationSummary": res.get("summary"), "validatedAt": res.get("runAt")}
    dump(dest / "meta.json", meta)
    oa = load(dest / "openapi.json")
    oa.setdefault("info", {})["version"] = semver
    dump(dest / "openapi.json", oa)
    for p in dest.rglob("*"):
        if p.is_file():
            p.chmod(0o444)
    print(f"committed {a.spec_id} v{n} ({semver}, {d['bump']})")


# ───────────────────────── status / gate ─────────────────────────

def gate_for(project: Path, spec_id: str) -> tuple[bool, list[str], dict]:
    sd = spec_dir(project, spec_id)
    reasons = []
    vs = versions(sd)
    draft = load_bundle(sd / "draft")
    if not vs:
        return False, ["no committed version"], {}
    latest = load_bundle(sd / "versions" / f"v{vs[-1]}")
    if canonical(latest["findings"]) != canonical(draft["findings"]) or \
       canonical({**latest["openapi"], "info": {}}) != canonical({**draft["openapi"], "info": {}}):
        reasons.append("draft has uncommitted changes — commit after validation")
    f = latest["findings"]
    if not f.get("auth", {}).get("chosenMethod"):
        reasons.append("auth method not chosen by the user")
    ops = [op.get("operationId") for _, _, op in iter_operations(latest["openapi"])]
    res = latest.get("results") or {}
    by_op = {}
    for s in res.get("steps", []):
        by_op.setdefault(s.get("operationId"), []).append(s)
    passed = 0
    for oid in ops:
        steps = by_op.get(oid, [])
        if not steps:
            reasons.append(f"{oid}: never validated"); continue
        if not all(s.get("result") == "pass" for s in steps):
            bad = [f"{s['id']}={s.get('result')}" for s in steps if s.get("result") != "pass"]
            reasons.append(f"{oid}: not passing ({', '.join(bad)})"); continue
        if oid not in latest["samples"]:
            reasons.append(f"{oid}: no captured response sample"); continue
        passed += 1
    fo = _by(f.get("operations"), "operationId")
    for oid in ops:
        st = fo.get(oid, {}).get("status")
        if st != "verified":
            reasons.append(f"{oid}: provenance status is '{st}', expected 'verified' after a passing run")
    site_data = project / "site" / "src" / "data" / "project.json"
    dist = project / "site" / "dist" / "index.html"
    if not dist.exists():
        reasons.append("site not built (specgen.py site --build)")
    elif site_data.exists() and site_data.stat().st_mtime < (sd / "versions" / f"v{vs[-1]}" / "meta.json").stat().st_mtime:
        reasons.append("site data older than latest version — rebuild the site")
    elif dist.stat().st_mtime < site_data.stat().st_mtime:
        reasons.append("site dist older than site data — rebuild the site")
    return (not reasons), reasons, {"version": vs[-1], "ops": len(ops), "passed": passed,
                                    "gaps": len(f.get("gaps", []))}


def cmd_status(a):
    project = Path(a.project).resolve()
    man = load(project / "manifest.json")
    ids = [a.spec] if a.spec else [s["id"] for s in man["specs"]]
    all_ok = True
    for sid in ids:
        ok, reasons, info = gate_for(project, sid)
        all_ok &= ok
        head = f"{sid}: v{info.get('version', '-')}  ops {info.get('passed', 0)}/{info.get('ops', 0)} validated  gaps {info.get('gaps', 0)}"
        print(("DONE   " if ok else "OPEN   ") + head)
        for r in reasons:
            print("       -", r)
    if a.gate:
        sys.exit(0 if all_ok else 1)


# ───────────────────────── site ─────────────────────────

def build_site_data(project: Path) -> dict:
    man = load(project / "manifest.json")
    out = {"generatedAt": now(), "manifest": man, "specs": []}
    for s in man["specs"]:
        sd = project / "specs" / s["id"]
        vs = versions(sd)
        bundles = {n: load_bundle(sd / "versions" / f"v{n}") for n in vs}
        ok, reasons, info = gate_for(project, s["id"]) if vs else (False, ["no committed version"], {})
        entry = {"id": s["id"], "title": s.get("title"), "versions": [], "diffs": {},
                 "gate": {"done": ok, "reasons": [r for r in reasons if "site" not in r]}}
        for n in vs:
            b = bundles[n]
            entry["versions"].append({"n": n, "meta": b["meta"], "openapi": b["openapi"], "findings": b["findings"],
                                      "plan": b["plan"], "results": b["results"], "setup": b["setup"],
                                      "samples": b["samples"]})
        for i, x in enumerate(vs):
            for y in vs[i + 1:]:
                d = structural_diff(bundles[x], bundles[y])
                d["text"] = text_diff(bundles[x], bundles[y], f"v{x}", f"v{y}")
                entry["diffs"][f"{x}..{y}"] = d
        out["specs"].append(entry)
    return out


def cmd_site(a):
    project = Path(a.project).resolve()
    site = project / "site"
    if not site.exists() or a.refresh_template:
        if site.exists():
            for p in TEMPLATE_DIR.rglob("*"):
                rel = p.relative_to(TEMPLATE_DIR)
                if rel.parts[0] in ("node_modules", "dist") or rel.as_posix() == "src/data/project.json":
                    continue
                dest = site / rel
                if p.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    shutil.copy2(p, dest)
        else:
            shutil.copytree(TEMPLATE_DIR, site, ignore=shutil.ignore_patterns("node_modules", "dist", ".astro"))
    for p in site.rglob("*"):
        if p.is_file() and not os.access(p, os.W_OK):
            p.chmod(0o644)
    data = build_site_data(project)
    dump(site / "src" / "data" / "project.json", data)
    print(f"wrote {site / 'src/data/project.json'} ({len(data['specs'])} spec(s))")
    if a.build:
        npm = shutil.which("npm")
        if not npm:
            sys.exit("error: npm not found — install Node 20+ to build the site")
        if not (site / "node_modules").exists():
            subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=site, check=True)
        subprocess.run([npm, "run", "build"], cwd=site, check=True)
        print(f"built {site / 'dist'} — view with: npm --prefix {site} run preview")


# ───────────────────────── main ─────────────────────────

def main():
    ap = argparse.ArgumentParser(prog="specgen", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("init"); p.add_argument("project"); p.add_argument("--title", required=True)
    p.add_argument("--source-mode", default="web", choices=["web", "docs", "sites", "mixed"])
    p.add_argument("--git", action="store_true"); p.set_defaults(fn=cmd_init)
    p = sp.add_parser("new-spec"); p.add_argument("project"); p.add_argument("spec_id")
    p.add_argument("--title", required=True); p.add_argument("--requirements", default="")
    p.add_argument("--provider", default=""); p.set_defaults(fn=cmd_new_spec)
    p = sp.add_parser("lint"); p.add_argument("project"); p.add_argument("--spec"); p.set_defaults(fn=cmd_lint)
    p = sp.add_parser("commit"); p.add_argument("project"); p.add_argument("spec_id")
    p.add_argument("-m", "--message", required=True); p.set_defaults(fn=cmd_commit)
    p = sp.add_parser("diff"); p.add_argument("project"); p.add_argument("spec_id")
    p.add_argument("frm"); p.add_argument("to"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_diff)
    p = sp.add_parser("status"); p.add_argument("project"); p.add_argument("--spec")
    p.add_argument("--gate", action="store_true"); p.set_defaults(fn=cmd_status)
    p = sp.add_parser("site"); p.add_argument("project"); p.add_argument("--build", action="store_true")
    p.add_argument("--refresh-template", action="store_true"); p.set_defaults(fn=cmd_site)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
