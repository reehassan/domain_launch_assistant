# `api-contract.md`

> What API does the backend expose?

Domain Launch Assistant is an API-first Django REST Framework app. React talks to Django exclusively through versioned JSON, under `/api/v1/`. Django owns auth, authorization, business logic, AI (Gemini) and domain-provider (name.com) integration, persistence, and Celery background processing. React owns UI, routing, JWT storage, and polling. React never holds provider credentials or business/ownership rules.

---

## 1. Conventions

- All endpoints are under `/api/v1/`.
- Requests/responses are `application/json`.
- Protected endpoints require `Authorization: Bearer <access_token>` (JWT). Unauthenticated → `401 AUTHENTICATION_REQUIRED`.
- List endpoints return `{"results": [...]}`.
- Async endpoints (a background Celery task) return `202 Accepted` with `{..., "status": "PROCESSING", "task_id": "..."}`. Poll `GET /tasks/{task_id}/` for the outcome (§9).

### Error envelope

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid data.",
    "details": { "field": ["This field is required."] }
  }
}
```

`details` is omitted for simple errors (401/403/404/409/etc.) and only present for multi-field validation errors.

### Standard error codes

| Code | HTTP | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Bad request body/params |
| `AUTHENTICATION_REQUIRED` | 401 | Missing/invalid credentials |
| `TOKEN_INVALID` / `TOKEN_EXPIRED` | 401 | Bad refresh/access token |
| `PERMISSION_DENIED` | 403 | Authenticated, not authorized |
| `NOT_FOUND` | 404 | Resource doesn't exist or isn't yours |
| `CONFLICT` | 409 | State precondition not met (task already running, project not READY, domain not selectable, etc.) |
| `EXTERNAL_API_TIMEOUT` | 502 | name.com/Gemini didn't respond in time |
| `EXTERNAL_API_ERROR` | 503 | name.com/Gemini call failed |
| `AI_GENERATION_FAILED` | 502 | Gemini returned invalid/empty structured output — never persisted |
| `INTERNAL_ERROR` | 500 | Unexpected server error, or a safety-guard trip (e.g. sandbox base-URL guard) |

Every endpoint below only calls out errors **beyond** the obvious `401`/`404` and its own specific cases.

---

## 2. Auth (`accounts` app, `User` model from `users` app)

| Method | Endpoint | Auth | Notes |
|---|---|---|---|
| `POST` | `/auth/register/` | — | Body: `username, email, password, first_name, last_name`. → `201 {"user": {...}}`. Duplicate username/email → **`400 VALIDATION_ERROR`** (DRF's default `UniqueValidator` — no custom 409 handling). |
| `POST` | `/auth/login/` | — | Body: `username, password`. → `200 {access, refresh, user}`. `user` is injected by a custom `LoginSerializer` — the frontend uses it directly and does **not** call `/auth/me/` again right after login. |
| `POST` | `/auth/token/refresh/` | refresh token | → `200 {access}`. Errors: `401 TOKEN_INVALID`/`TOKEN_EXPIRED`. |
| `POST` | `/auth/logout/` | ✓ | Body: `{refresh}`. Blacklists it. → `204`. |
| `GET` | `/auth/me/` | ✓ | → `200` user object. Used on app mount to hydrate an existing session from a stored token — this is the one legitimate use of a separate `/me/` call. |

---

## 3. Projects (`launches` app)

Create/List/Retrieve only — no `PUT`/`PATCH`/`DELETE`. All mutation happens through the action endpoints below.

| Method | Endpoint | Notes |
|---|---|---|
| `POST` | `/projects/` | Body: `name, business_description`. → `201`, `status: "DRAFT"`. |
| `GET` | `/projects/` | → `{"results": [...]}`, scoped to `request.user`, ordered `-created_at`. |
| `GET` | `/projects/{id}/` | Includes nested `selected_brand`/`selected_domain` (or `null`). |

---

## 4. Brands (`brands` app)

| Method | Endpoint | Notes |
|---|---|---|
| `POST` | `/projects/{id}/generate-brands/` | Body: `{"count": 5}` (optional). Also the **regenerate** call — same endpoint, no separate route; regenerating deletes the prior unselected batch. → `202 {task_id, status: "PROCESSING"}`. Errors: `409` if a task is already running for this project. Task result on `SUCCESS`: array of `BrandIdea`. |
| `GET` | `/projects/{id}/brands/` | → `{"results": [...]}`. |
| `POST` | `/projects/{id}/select-brand/` | Body: `{"brand_id"}`. → `200 {project_id, selected_brand, status: "BRANDS_READY"}`. |

---

## 5. Domains & Search (`domains` app)

| Method | Endpoint | Notes |
|---|---|---|
| `POST` | `/projects/{id}/domain-search/` | Body: `{brand_idea_id, extensions: [...]}`. `extensions` — any of `.com .ai .io .net .org .co .dev .app`. Also the regenerate call. → `202 {search_id, project_id, status: "PROCESSING", task_id}`. Errors: `409` if a task is already running. |
| `GET` | `/projects/{id}/domain-searches/` | Search history, `{"results": [...]}`. |
| `GET` | `/projects/{id}/domains/` | `{"results": [...]}`, optional `?available=`/`?extension=`/`?search=`. Scoped to the project's **latest COMPLETED** search only — older results stay reachable by ID but drop out of this list once a newer search completes (no duplicates on reload). Includes `purchase_price`/`renewal_price`/`premium`/`purchase_type` (from the same `checkAvailability` call, no extra provider hit) and `registered_at`/`registration_order_id`/`privacy_enabled` (populated after §7 registration). |
| `POST` | `/projects/{id}/select-domain/` | Body: `{"domain_id"}`. → `200 {project_id, selected_domain, status: "DOMAIN_SELECTED"}`. Requires: belongs to project, `status=AVAILABLE`, not stale, no active trademark claim on record. Errors: `409` on any of those failing. |
| `POST` | `/projects/{id}/recommend-domain/` | No body — picks from current `AVAILABLE` results via Gemini. Also the regenerate call (creates a new row, doesn't overwrite). → `202 {task_id, status: "PROCESSING"}`. Errors: `400` no available domains; `409` no completed search yet, or a task already running. Task result on `SUCCESS`: single `DomainRecommendation`. |
| `GET` | `/projects/{id}/domain-recommendations/` | Full history, newest first, `{"results": [...]}`. |
| `POST` | `/domains/{id}/check-claims/` | `{id}` = `DomainResult.id`. No body. TMCH claims check via name.com. → `202 {domain_id, status, task_id}`. Concurrency lock is **per-domain**, not per-project (multiple domains can be checked at once). Task result: single `DomainClaim` (append-only history). |
| `GET` | `/domains/{id}/claims/` | Newest first, `{"results": [...]}`. |

---

## 6. DNS Verification & Records (`dns` app)

### 6.1 Launch-readiness checks

| Method | Endpoint | Notes |
|---|---|---|
| `POST` | `/domains/{id}/check/` | Body: `{check_types: [...], expected_value?}`. Valid types: `DNS_CONFIGURATION` (rejected, `400`, no handler yet), `DNS_RESOLUTION`, `DOMAIN_READINESS`. **`expected_value` is required whenever `DNS_RESOLUTION` is requested** — the check verifies the domain resolves to that specific value, not merely that it resolves to *something* (closes a gap where an unrelated third-party host could false-PASS the check). The frontend only ever requests `DOMAIN_READINESS`. → `202 {domain_id, status, task_id}`. Task result: `{"results": [DomainCheck, ...]}`. |
| `GET` | `/domains/{id}/checks/` | `{"results": [...]}`. |

### 6.2 DNS records — live proxy to name.com, no local model

Gated on `LaunchProject.status == READY` for every endpoint below (a domain only exists on name.com's sandbox once registered there). name.com's `UpdateRecord` is a **full replace**, not a patch — Update must supply the complete desired record.

| Method | Endpoint | Notes |
|---|---|---|
| `POST` | `/domains/{id}/create-dns-record/` | Body: `{host?, type, answer, ttl?, priority?}`. `type` ∈ `A AAAA ANAME CNAME MX NS SRV TXT` (frontend UI narrows to `A`/`CNAME`). `priority` required for `MX`/`SRV`. → `202`. Task result: the created record dict from name.com. |
| `GET` | `/domains/{id}/dns-records/` | `{"results": [...]}` — the one **synchronous** name.com call in this app; can fail `502`/`503` directly on the request. |
| `POST` | `/domains/{id}/dns-records/{record_id}/update/` | Same body shape as create — full replacement. → `202`. Task result: updated record dict. |
| `POST` | `/domains/{id}/dns-records/{record_id}/delete/` | No body. → `202`. Task result: `{"record_id": ..., "deleted": true}`. |

All five: `409` if `project.status != READY`.

---

## 7. Registration & Privacy (sandbox-only)

| Method | Endpoint | Notes |
|---|---|---|
| `POST` | `/domains/{id}/simulate-registration/` | No body — pulls a fresh sandbox price itself. Gated on `status == READY`. Calls name.com's real Create Domain endpoint against the **test/sandbox base URL only**; refuses to run against production. → `202`. Task result: `{simulated: true, order_id, privacy_enabled, message}`. On success, also persists `registered_at`/`registration_order_id`/`privacy_enabled` onto the `DomainResult`. |
| `POST` | `/domains/{id}/toggle-privacy/` | Body: `{"enabled": bool}`. Gated on `status == READY`. Wired into `DomainCheckoutPanel.jsx`. → `202`. Task result: `{domain, privacy_enabled, message}`. A `409` from name.com means this TLD doesn't support WHOIS privacy — surfaced as `EXTERNAL_API_ERROR`, not retried. |

> **"Buy on name.com"** has no backend endpoint — a frontend-only outbound link built from `selected_domain.domain`.

---

## 8. Launch Report

```http
GET /projects/{id}/launch-report/
```

Pure aggregation of existing local data — no new provider calls, reachable at any project status (not just `READY`), so a founder mid-flow sees partial progress. Deliberately excludes live DNS records (§6.2 is a live provider call; baking it in would make this endpoint secretly slow/failable) and a "was this registered" flag (nothing in the data model persists one beyond `DomainResult.registered_at`, which the domain object here already carries).

```json
{
  "project": { "id": "uuid", "name": "LedgerFlow", "status": "READY" },
  "brand": { "...full BrandIdea, or null" },
  "domain": { "...full DomainResult, or null" },
  "claims": { "...latest DomainClaim, or null" },
  "checks": [
    { "id": "uuid", "check_type": "DOMAIN_READINESS", "status": "PASS", "message": "...", "checked_at": "..." }
  ],
  "readiness": {
    "ready": true,
    "score": 100,
    "blocking_issues": []
  }
}
```

`readiness.score` = % of `DOMAIN_READINESS`-type checks that are `PASS`. `blocking_issues` lists everything currently stopping the project from being launch-ready (no brand, no domain, active claim, failed/missing readiness check).

---

## 9. Background Task Status

```http
GET /tasks/{task_id}/
```

```json
{
  "task_id": "uuid",
  "status": "SUCCESS",
  "result": { "...task-specific, see each endpoint above" },
  "error": null
}
```

`status` ∈ `PENDING | PROCESSING | SUCCESS | FAILURE`. `error` is `null` unless `status == FAILURE`, in which case `{"code": "...", "message": "..."}`.

---

## 10. Ownership

Every protected endpoint requires `request.user.is_authenticated`, enforced by JWT auth — never by React. For project-scoped resources: `project.user == request.user`. For nested resources, the same rule chains through the FK: `BrandIdea/DomainSearch/DomainResult/DomainCheck.project.user`, `DomainClaim.domain_result.project.user`, `DomainRecommendation.project.user`. DNS records have no local model — ownership for all `/domains/{id}/...` DNS/registration/privacy endpoints is enforced via `domain_result.project.user`, since they hang off the domain, not the project, in the URL. A resource that isn't yours returns `404`, not `403` — existence is not leaked.

---

## 11. Key Rules

1. Only available (`status=AVAILABLE`), non-stale, unclaimed domains can be selected.
2. Provider errors (timeout, 5xx) must never be interpreted as "domain unavailable" / "no claims" / etc. — a failed check reports failure, not a false negative.
3. AI output is schema-validated before persistence; invalid Gemini output is never saved as a `BrandIdea`/`DomainRecommendation`.
4. Long-running external calls (Gemini, name.com) always run through Celery, polled via §9.
5. Postgres is the source of truth for everything **except** DNS records (§6.2), where name.com itself is authoritative.
6. Simulate Registration and Toggle Privacy must only ever target name.com's sandbox base URL — the client refuses to construct itself against production.
7. React never holds provider credentials or makes ownership/business-rule decisions.

---

## 12. End-to-end flow

`POST /projects/` → `generate-brands/` (Celery → Gemini → `BrandIdea[]`) → `select-brand/` → `domain-search/` (Celery → name.com → `DomainResult[]`) → optional `recommend-domain/` / `check-claims/` → `select-domain/` → `check/` with `DOMAIN_READINESS` (Celery) → project reaches `READY` → optional `simulate-registration/` → `toggle-privacy/` → `create-dns-record/` / `dns-records/` (+ update/delete) → `launch-report/` ties it all together for the final screen.

---

## 13. Endpoint Summary

| Method | Endpoint | Async |
|---|---|---|
| `POST` | `/auth/register/` | No |
| `POST` | `/auth/login/` | No |
| `POST` | `/auth/token/refresh/` | No |
| `POST` | `/auth/logout/` | No |
| `GET` | `/auth/me/` | No |
| `POST` | `/projects/` | No |
| `GET` | `/projects/` | No |
| `GET` | `/projects/{id}/` | No |
| `POST` | `/projects/{id}/generate-brands/` | Yes |
| `GET` | `/projects/{id}/brands/` | No |
| `POST` | `/projects/{id}/select-brand/` | No |
| `POST` | `/projects/{id}/domain-search/` | Yes |
| `GET` | `/projects/{id}/domain-searches/` | No |
| `GET` | `/projects/{id}/domains/` | No |
| `POST` | `/projects/{id}/select-domain/` | No |
| `POST` | `/projects/{id}/recommend-domain/` | Yes |
| `GET` | `/projects/{id}/domain-recommendations/` | No |
| `POST` | `/domains/{id}/check-claims/` | Yes |
| `GET` | `/domains/{id}/claims/` | No |
| `POST` | `/domains/{id}/check/` | Yes |
| `GET` | `/domains/{id}/checks/` | No |
| `POST` | `/domains/{id}/create-dns-record/` | Yes |
| `GET` | `/domains/{id}/dns-records/` | No |
| `POST` | `/domains/{id}/dns-records/{record_id}/update/` | Yes |
| `POST` | `/domains/{id}/dns-records/{record_id}/delete/` | Yes |
| `POST` | `/domains/{id}/simulate-registration/` | Yes |
| `POST` | `/domains/{id}/toggle-privacy/` | Yes |
| `GET` | `/projects/{id}/launch-report/` | No |
| `GET` | `/tasks/{task_id}/` | No |