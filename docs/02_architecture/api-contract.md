# `api-contract.md`

> **What API does the backend expose?**

The Domain Launch Assistant backend is an **API-first Django application** built with Django REST Framework.

The React frontend communicates with Django exclusively through versioned JSON APIs.

```text
React Frontend
      │
      │ HTTPS + JSON
      ↓
Django REST Framework
      │
      ├── JWT Authentication
      ├── Permissions
      ├── Serializers
      └── Application Services
              │
              ├── Gemini
              ├── name.com
              ├── PostgreSQL
              └── Celery
```

---

# 1. API Conventions

## Base URL

All API endpoints are versioned under:

```text
/api/v1/
```

Example:

```http
POST /api/v1/projects/
```

The `/api/v1/` prefix allows future API versions to be introduced without breaking existing clients.

## Content Type

Requests containing JSON must use:

```http
Content-Type: application/json
```

Responses use:

```http
Content-Type: application/json
```

---

# 2. Authentication

The API uses **JWT (JSON Web Token) authentication**.

Authentication flow:

```text
React
  │
  │ POST /api/v1/auth/login/
  ↓
Django
  │
  ├── Access Token
  └── Refresh Token
       │
       ↓
React stores authentication state
       │
       │ Authorization: Bearer <access_token>
       ↓
Protected API endpoint
```

Protected requests must include:

```http
Authorization: Bearer <access_token>
```

The backend validates the JWT before allowing access to protected resources.

Unauthenticated requests return:

```http
401 Unauthorized
```

Expired access tokens should be refreshed using the refresh-token endpoint.

> Registration, login, logout, and token refresh are owned by the `accounts` Django app. The `GET /api/v1/auth/me/` endpoint is also owned by `accounts`, but returns data from the `User` model defined in the `users` app.

---

# 3. API Response Conventions

Successful responses return JSON.

Errors use a consistent structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid data.",
    "details": {
      "business_description": [
        "This field is required."
      ]
    }
  }
}
```

Common error codes:

```text
VALIDATION_ERROR

AUTHENTICATION_REQUIRED

TOKEN_INVALID

TOKEN_EXPIRED

PERMISSION_DENIED

NOT_FOUND

CONFLICT

EXTERNAL_API_ERROR

EXTERNAL_API_TIMEOUT

AI_GENERATION_FAILED

DOMAIN_CHECK_FAILED

DNS_CHECK_FAILED

INTERNAL_ERROR
```

---

# 4. Authentication Endpoints

## 4.1 Register User

```http
POST /api/v1/auth/register/
```

### Authentication

Not required.

### Request

```json
{
  "username": "areeba",
  "email": "areeba@example.com",
  "password": "secure-password",
  "first_name": "Areeba",
  "last_name": "Hassan"
}
```

### Response

```http
201 Created
```

```json
{
  "user": {
    "id": "uuid",
    "username": "areeba",
    "email": "areeba@example.com",
    "first_name": "Areeba",
    "last_name": "Hassan"
  }
}
```

### Errors

```text
400 VALIDATION_ERROR

409 CONFLICT
```

---

# 5. Login

```http
POST /api/v1/auth/login/
```

### Authentication

Not required.

### Request

```json
{
  "username": "areeba",
  "password": "secure-password"
}
```

### Response

```http
200 OK
```

```json
{
  "access": "jwt-access-token",
  "refresh": "jwt-refresh-token",
  "user": {
    "id": "uuid",
    "username": "areeba",
    "email": "areeba@example.com",
    "first_name": "Areeba",
    "last_name": "Hassan"
  }
}
```

The React frontend uses the access token for authenticated API requests.

```http
Authorization: Bearer <access_token>
```

---

# 6. Refresh Access Token

```http
POST /api/v1/auth/token/refresh/
```

### Authentication

The refresh token is required.

### Request

```json
{
  "refresh": "jwt-refresh-token"
}
```

### Response

```http
200 OK
```

```json
{
  "access": "new-jwt-access-token"
}
```

### Errors

```text
401 TOKEN_INVALID

401 TOKEN_EXPIRED
```

---

# 7. Logout

```http
POST /api/v1/auth/logout/
```

### Authentication

Required.

### Request

```json
{
  "refresh": "jwt-refresh-token"
}
```

### Response

```http
204 No Content
```

Logout invalidates/revokes the refresh token where token blacklisting is enabled.

---

# 8. Current User

```http
GET /api/v1/auth/me/
```

### Authentication

Required.

### Response

```http
200 OK
```

```json
{
  "id": "uuid",
  "username": "areeba",
  "email": "areeba@example.com",
  "first_name": "Areeba",
  "last_name": "Hassan"
}
```

---

# 9. Launch Projects

> `LaunchProjectViewSet` only implements Create, List, and Retrieve (`CreateModelMixin` / `ListModelMixin` / `RetrieveModelMixin`) — Update and Delete are deliberately not wired up yet, so there is no `PUT`/`PATCH`/`DELETE /api/v1/projects/{id}/`. All project mutation happens through the more specific action endpoints below (`select-brand/`, `select-domain/`, etc.), not through a general-purpose project update.

## 9.1 Create Project

```http
POST /api/v1/projects/
```

### Authentication

Required.

### Request

```json
{
  "name": "LedgerFlow",
  "business_description": "An AI-powered bookkeeping platform for small businesses."
}
```

### Response

```http
201 Created
```

```json
{
  "id": "uuid",
  "name": "LedgerFlow",
  "business_description": "An AI-powered bookkeeping platform for small businesses.",
  "status": "DRAFT",
  "selected_brand": null,
  "selected_domain": null,
  "created_at": "2026-08-22T14:00:00Z",
  "updated_at": "2026-08-22T14:00:00Z"
}
```

### Errors

```text
400 VALIDATION_ERROR

401 AUTHENTICATION_REQUIRED
```

---

# 10. List Projects

```http
GET /api/v1/projects/
```

### Authentication

Required.

### Response

```http
200 OK
```

```json
{
  "results": [
    {
      "id": "uuid",
      "name": "LedgerFlow",
      "business_description": "An AI-powered bookkeeping platform.",
      "status": "BRANDS_READY",
      "selected_brand": null,
      "selected_domain": null,
      "created_at": "2026-08-22T14:00:00Z",
      "updated_at": "2026-08-22T14:05:00Z"
    }
  ]
}
```

Only projects belonging to the authenticated user are returned.

---

# 11. Get Project

```http
GET /api/v1/projects/{id}/
```

### Authentication

Required.

### Response

```http
200 OK
```

```json
{
  "id": "uuid",
  "name": "LedgerFlow",
  "business_description": "An AI-powered bookkeeping platform.",
  "status": "BRANDS_READY",
  "selected_brand": {
    "id": "uuid",
    "name": "LedgerFlow",
    "description": "Suggests financial clarity and continuous workflow."
  },
  "selected_domain": null,
  "created_at": "2026-08-22T14:00:00Z",
  "updated_at": "2026-08-22T14:05:00Z"
}
```

### Errors

```text
401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND
```

---

# 12. Generate Brand Ideas

```http
POST /api/v1/projects/{id}/generate-brands/
```

### Authentication

Required.

### Request

```json
{
  "count": 10
}
```

`count` is optional.

If omitted, the backend uses the configured default.

> **Regenerate Brands:** the "Not loving these?" regenerate action in the UI calls this same endpoint again — there is no separate regenerate endpoint. Each call creates a new batch of `BrandIdea` rows; the frontend reads the latest batch by `created_at`.

### Response

Because AI generation is asynchronous:

```http
202 Accepted
```

```json
{
  "project_id": "uuid",
  "status": "GENERATING_BRANDS",
  "task_id": "celery-task-id"
}
```

The project status becomes:

```text
GENERATING_BRANDS
```

The Celery worker performs the AI operation.

After successful completion:

```text
GENERATING_BRANDS
        ↓
BRANDS_READY
```

### Errors

```text
400 VALIDATION_ERROR

401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND

409 CONFLICT
```

---

# 13. Get Brand Ideas 

```http
GET /api/v1/projects/{id}/brands/
```

### Authentication

Required.

### Response

```http
200 OK
```

```json
{
  "results": [
    {
      "id": "uuid",
      "name": "LedgerFlow",
      "description": "A name suggesting continuous and organized financial management.",
      "is_selected": false,
      "created_at": "2026-08-22T14:05:00Z"
    },
    {
      "id": "uuid",
      "name": "Finora",
      "description": "A concise modern name associated with financial technology.",
      "is_selected": false,
      "created_at": "2026-08-22T14:05:00Z"
    }
  ]
}
```

### Errors

```text
401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND
```

---

# 14. Select Brand

```http
POST /api/v1/projects/{id}/select-brand/
```

### Authentication

Required.

### Request

```json
{
  "brand_id": "uuid"
}
```

### Response

```http
200 OK
```

```json
{
  "project_id": "uuid",
  "selected_brand": {
    "id": "uuid",
    "name": "LedgerFlow",
    "description": "A name suggesting continuous financial management."
  },
  "status": "BRANDS_READY"
}
```

The backend must verify that the selected brand belongs to the specified project.

### Errors

```text
400 VALIDATION_ERROR

401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND

409 CONFLICT
```

---

# 15. Start Domain Search

```http
POST /api/v1/projects/{id}/domain-search/
```

### Authentication

Required.

### Request

```json
{
  "brand_idea_id": "uuid",
  "extensions": [
    ".com",
    ".ai",
    ".io"
  ]
}
```

`brand_idea_id` is required — every domain search must originate from a selected brand idea (matches `DomainSearch.brand_idea_id` in data-model.md).

> **Regenerate Domains:** the "Not loving these?" regenerate action for domain results calls this same endpoint again with the same `brand_idea_id`/`extensions` — there is no separate regenerate endpoint.

### Response

```http
202 Accepted
```

```json
{
  "search_id": "uuid",
  "project_id": "uuid",
  "status": "PROCESSING",
  "task_id": "celery-task-id"
}
```

### Workflow

```text
POST /domain-search/
        ↓
DomainSearch created
        ↓
Celery task
        ↓
name.com API
        ↓
DomainResult[]
        ↓
DomainSearch = COMPLETED
```

### Errors

```text
400 VALIDATION_ERROR

401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND

409 CONFLICT
```

---

# 16. Get Domain Searches

```http
GET /api/v1/projects/{id}/domain-searches/
```

### Authentication

Required.

### Response

```http
200 OK
```

```json
{
  "results": [
    {
      "id": "uuid",
      "brand_idea_id": "uuid",
      "status": "COMPLETED",
      "requested_extensions": [
        ".com",
        ".ai",
        ".io"
      ],
      "started_at": "2026-08-22T14:10:00Z",
      "completed_at": "2026-08-22T14:10:04Z",
      "created_at": "2026-08-22T14:10:00Z"
    }
  ]
}
```

---

# 17. Get Domain Results

```http
GET /api/v1/projects/{id}/domains/
```

### Authentication

Required.

### Query Parameters

Optional:

```text
?available=true

?extension=.com

?search=ledger
```

### Response

```http
200 OK
```

```json
{
  "results": [
    {
      "id": "uuid",
      "domain": "ledgerflow.ai",
      "extension": ".ai",
      "available": true,
      "status": "AVAILABLE",
      "provider": "name.com",
      "checked_at": "2026-08-22T14:10:04Z",
      "purchase_price": 69.99,
      "renewal_price": 69.99,
      "premium": false,
      "purchase_type": "registration"
    },
    {
      "id": "uuid",
      "domain": "ledgerflow.com",
      "extension": ".com",
      "available": false,
      "status": "TAKEN",
      "provider": "name.com",
      "checked_at": "2026-08-22T14:10:04Z",
      "purchase_price": null,
      "renewal_price": null,
      "premium": null,
      "purchase_type": null
    }
  ]
}
```

`purchase_price`, `renewal_price`, `premium`, and `purchase_type` are populated directly from the existing `checkAvailability` call to name.com — no additional provider call is made. All four are nullable; `CHECK_FAILED` and `TAKEN` results will not have pricing.

Results are scoped to the project's latest `COMPLETED` `DomainSearch` only — regenerating a search does not resurrect older results in this list (they remain reachable by ID, just not here).

### Errors

```text
401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND
```

---

# 18. Domain Recommendation

Uses Gemini to pick the best of the project's currently `AVAILABLE` domain results and explain the choice.

## 18.1 Generate Recommendation

```http
POST /api/v1/projects/{id}/recommend-domain/
```

### Authentication

Required.

### Request

No body. Uses the project's current `AVAILABLE` domain results.

> **Regenerate:** calling this endpoint again creates a new `DomainRecommendation` row rather than overwriting the previous one — there is no separate regenerate endpoint, same convention as `generate-brands/` and `domain-search/`.

### Response

Because AI generation is asynchronous:

```http
202 Accepted
```

```json
{
  "project_id": "uuid",
  "status": "PROCESSING",
  "task_id": "celery-task-id"
}
```

Task result on `SUCCESS` (fetched via `GET /api/v1/tasks/{task_id}/`):

```json
{
  "id": "uuid",
  "project_id": "uuid",
  "recommended_domain": {
    "id": "uuid",
    "domain": "ledgerflow.ai",
    "extension": ".ai",
    "available": true,
    "status": "AVAILABLE",
    "provider": "name.com",
    "checked_at": "2026-08-22T14:10:04Z",
    "purchase_price": 69.99,
    "renewal_price": 69.99,
    "premium": false,
    "purchase_type": "registration"
  },
  "reasoning": "ledgerflow.ai is short, matches the brand exactly, and the .ai extension signals the product category.",
  "created_at": "2026-08-22T14:22:00Z"
}
```

The result is persisted as a `DomainRecommendation` so it survives a page refresh.

### Errors

```text
400 VALIDATION_ERROR        — no available domains yet

401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND

409 CONFLICT                — no domain search has completed
```

## 18.2 Get Recommendation History

```http
GET /api/v1/projects/{id}/domain-recommendations/
```

Returns every `DomainRecommendation` ever generated for the project, newest first (same `created_at` convention as brands and domain searches). The frontend reads the first entry for the "We'd pick X because Y" panel.

### Authentication

Required.

### Response

```http
200 OK
```

```json
{
  "results": [
    {
      "id": "uuid",
      "project_id": "uuid",
      "recommended_domain": {
        "id": "uuid",
        "domain": "ledgerflow.ai",
        "extension": ".ai",
        "available": true,
        "status": "AVAILABLE",
        "provider": "name.com",
        "checked_at": "2026-08-22T14:10:04Z",
        "purchase_price": 69.99,
        "renewal_price": 69.99,
        "premium": false,
        "purchase_type": "registration"
      },
      "reasoning": "ledgerflow.ai is short, matches the brand exactly, and the .ai extension signals the product category.",
      "created_at": "2026-08-22T14:22:00Z"
    }
  ]
}
```

### Errors

```text
401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND
```

---

# 19. Trademark Claims Check

## 19.1 Check Domain Claims

```http
POST /api/v1/domains/{id}/check-claims/
```

Runs an on-demand check of a domain against the ICANN Trademark Clearinghouse via name.com.

### Authentication

Required.

### Request

No body.

### Response

```http
202 Accepted
```

```json
{
  "domain_id": "uuid",
  "status": "PROCESSING",
  "task_id": "celery-task-id"
}
```

Task result on `SUCCESS`:

```json
{
  "id": "uuid",
  "domain_result_id": "uuid",
  "has_claims": false,
  "claims_data": null,
  "checked_at": "2026-08-22T14:20:00Z",
  "created_at": "2026-08-22T14:20:00Z"
}
```

Each check creates a new `DomainClaim` row (append-only history, same pattern as `DomainCheck`) rather than overwriting a previous result.

### Errors

```text
400 VALIDATION_ERROR

401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND

409 CONFLICT

502 EXTERNAL_API_TIMEOUT

503 EXTERNAL_API_ERROR
```

## 19.2 Get Domain Claims

```http
GET /api/v1/domains/{id}/claims/
```

Returns every claims check ever run for the domain, newest first — same read pattern as `GET /api/v1/domains/{id}/checks/`. The frontend reads the first entry for the "has claims" panel.

### Authentication

Required.

### Response

```http
200 OK
```

```json
{
  "results": [
    {
      "id": "uuid",
      "domain_result_id": "uuid",
      "has_claims": false,
      "claims_data": null,
      "checked_at": "2026-08-22T14:20:00Z",
      "created_at": "2026-08-22T14:20:00Z"
    }
  ]
}
```

### Errors

```text
401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND
```

---

# 20. Select Domain

```http
POST /api/v1/projects/{id}/select-domain/
```

### Authentication

Required.

### Request

```json
{
  "domain_id": "uuid"
}
```

### Response

```http
200 OK
```

```json
{
  "project_id": "uuid",
  "selected_domain": {
    "id": "uuid",
    "domain": "ledgerflow.ai",
    "available": true,
    "status": "AVAILABLE"
  },
  "status": "DOMAIN_SELECTED"
}
```

The selected domain must:

* Belong to the project.
* Have `status=AVAILABLE`.
* Not be stale beyond the configured freshness threshold.
* Have no active trademark claim on record (a claim with `has_claims=true` on its most recent `DomainClaim` row blocks selection).

### Errors

```text
400 VALIDATION_ERROR

401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND

409 CONFLICT
```

---

> **Note on the endpoints below:** `create-dns-record/`, `dns-records/`, `check/`, `checks/`, and `simulate-registration/` are implemented by Django apps other than `domains` (`dns`, and, for simulate-registration/toggle-privacy, `domains`'s registration-simulation service), even though they share the `/api/v1/domains/{id}/...` URL prefix used by the `domains` app's endpoints above. The shared prefix is a deliberate URL-design choice — from the client's perspective, a domain's DNS state and registration actions are part of that domain resource — and does not imply the underlying app boundaries are merged.

---

# 21. DNS Record Management ("Point your domain")

Real DNS record management against name.com's actual DNS Records API (Core API v1: `GET`/`POST /domains/{domainName}/records`) — this is a live proxy to name.com, not a local model. Unlike every other name.com-backed feature in this app, there is no `DomainCheck`/`DomainClaim`-style row to read from the database instead: name.com is the only source of truth for DNS records.

Available once the project has reached launch readiness (`LaunchProject.status == READY`) — the same gate used by Simulate Registration below, since a domain that was never sandbox-registered has nothing there to manage.

## 21.1 Create DNS Record

```http
POST /api/v1/domains/{id}/create-dns-record/
```

`{id}` is `DomainResult.id`.

### Authentication

Required.

### Request

```json
{
  "host": "www",
  "type": "CNAME",
  "answer": "ledgerflow.ai",
  "ttl": 300
}
```

* `host` — optional, defaults to `""` (an empty or `"@"` host is the apex/root record).
* `type` — required. One of `A`, `AAAA`, `ANAME`, `CNAME`, `MX`, `NS`, `SRV`, `TXT`. The frontend's record-type dropdown is narrowed to `A`/`CNAME` only (`DomainDnsPanel.jsx`); the backend and name.com both support the full set.
* `answer` — required.
* `ttl` — optional, defaults to `300` seconds (name.com's minimum).
* `priority` — required for `MX` and `SRV` records only; ignored for all others.

### Response

Asynchronous, for consistency with every other mutating name.com call in this app, even though a single Create Record call is typically fast:

```http
202 Accepted
```

```json
{
  "domain_id": "uuid",
  "status": "PROCESSING",
  "task_id": "celery-task-id"
}
```

Task result on `SUCCESS` — the created record, returned directly from name.com with no `{"results": [...]}` wrapper, since exactly one record is created per call:

```json
{
  "id": 12345,
  "domainName": "ledgerflow.ai",
  "host": "www",
  "fqdn": "www.ledgerflow.ai.",
  "type": "CNAME",
  "answer": "ledgerflow.ai",
  "ttl": 300,
  "priority": null
}
```

### Errors

```text
400 VALIDATION_ERROR

401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND

409 CONFLICT                — project.status != READY

502 EXTERNAL_API_TIMEOUT

503 EXTERNAL_API_ERROR
```

## 21.2 List DNS Records

```http
GET /api/v1/domains/{id}/dns-records/
```

The one `GET` in this app that is **not** a local-database read: it calls name.com directly on every request and can fail with a provider error inline (unlike every other list endpoint in this contract, which only ever reads Postgres).

### Authentication

Required.

### Response

```http
200 OK
```

```json
{
  "results": [
    {
      "id": 12345,
      "domainName": "ledgerflow.ai",
      "host": "www",
      "fqdn": "www.ledgerflow.ai.",
      "type": "CNAME",
      "answer": "ledgerflow.ai",
      "ttl": 300,
      "priority": null
    }
  ]
}
```

### Errors

```text
401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND

409 CONFLICT                — project.status != READY

500 INTERNAL_ERROR          — sandbox-guard tripped (should be unreachable)

502 EXTERNAL_API_TIMEOUT

503 EXTERNAL_API_ERROR
```

---

# 22. Verify DNS / Domain Readiness

```http
POST /api/v1/domains/{id}/check/
```

Corresponds to `DNSVerificationService` in architecture.md. Runs one or more launch-readiness checks against a domain. This is independent of the DNS Record Management feature in §21 above — this endpoint asks "is this domain ready for launch," not "does record X exist."

### Authentication

Required.

### Request

```json
{
  "check_types": [
    "DOMAIN_READINESS"
  ]
}
```

The backend's `check_types` enum has three values: `DNS_CONFIGURATION`, `DNS_RESOLUTION`, `DOMAIN_READINESS`. `DNS_CONFIGURATION` is currently rejected synchronously with `400 VALIDATION_ERROR` — it has no handler implemented yet (`CheckDomainService.UNSUPPORTED_CHECK_TYPES`). The frontend only ever requests `DOMAIN_READINESS`: `DNS_RESOLUTION` is technically supported by the backend but withheld frontend-side, because a real DNS lookup can only ever pass for a domain that's actually registered and pointed somewhere — and in this app, registration happens only after the project reaches `READY`, so requiring `DNS_RESOLUTION` to pass first would make `READY` unreachable.

### Response

```http
202 Accepted
```

```json
{
  "domain_id": "uuid",
  "status": "PROCESSING",
  "task_id": "celery-task-id"
}
```

The checks are executed asynchronously.

### Workflow

```text
POST /domains/{id}/check/
        ↓
Create DomainCheck[]
        ↓
Celery
        ↓
name.com / DNS
        ↓
Normalize results
        ↓
Update DomainCheck[]
        ↓
Calculate launch readiness
```

### Errors

```text
400 VALIDATION_ERROR

401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND

409 CONFLICT
```

---

# 23. Get Domain Checks

```http
GET /api/v1/domains/{id}/checks/
```

### Authentication

Required.

### Response

```http
200 OK
```

```json
{
  "results": [
    {
      "id": "uuid",
      "check_type": "DOMAIN_READINESS",
      "status": "PASS",
      "record_type": null,
      "record_name": null,
      "expected_value": null,
      "actual_value": null,
      "message": "Domain is ready for launch.",
      "checked_at": "2026-08-22T14:15:01Z"
    }
  ]
}
```

---

# 24. Simulate Registration (sandbox-only)

```http
POST /api/v1/domains/{id}/simulate-registration/
```

Calls name.com's real `Create Domain` endpoint against the **test/sandbox environment only**, to prove the registration flow works without spending real money or registering a real domain. Available once the domain has passed launch readiness (`LaunchProject.status = READY`).

### Authentication

Required.

### Request

No body — the service pulls `purchase_price`/`purchase_type` off a fresh sandbox `checkAvailability` call it makes itself, not off the stored `DomainResult` (sandbox and production name.com return different test prices for the same domain, so the production-sourced price on `DomainResult` would be rejected by the sandbox's Create Domain endpoint).

### Response

```http
202 Accepted
```

```json
{
  "domain_id": "uuid",
  "status": "PROCESSING",
  "task_id": "celery-task-id"
}
```

Task result on `SUCCESS`:

```json
{
  "simulated": true,
  "order_id": "sandbox-order-id",
  "privacy_enabled": true,
  "message": "Registered in name.com sandbox — no real domain or charge."
}
```

**Contract rule:** Simulate Registration must only ever call name.com's test/sandbox base URL. The client must refuse to run if configured against the production base URL. See `architecture.md` §19 — `DomainRegistrationSimulationService` must construct its own `NameComClient` from `NAMECOM_TEST_*` settings and must never reuse the production client instance.

### Errors

```text
400 VALIDATION_ERROR

401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND

409 CONFLICT

502 EXTERNAL_API_TIMEOUT

503 EXTERNAL_API_ERROR
```

> **Buy on name.com** has no corresponding backend endpoint. It is a frontend-only outbound `<a href>` built from `project.selected_domain.domain`, linking to name.com's real search page. Nothing is added to this contract for it.

---

# 25. Toggle WHOIS Privacy (sandbox-only)

```http
POST /api/v1/domains/{id}/toggle-privacy/
```

Toggles WHOIS privacy for a domain already registered in the name.com sandbox via §24 Simulate Registration. Reuses that same sandbox-only client and the same `READY` gate — toggling privacy on a domain never sandbox-registered fails as a routine provider error (name.com returns 404 for it), not a special case handled here.

> **Status:** this endpoint currently exists in `domains/urls.py` and is documented here to match reality (the point of this revision). Its future is under review separately (Ticket 12) — if that ticket removes the feature, this section should be deleted in the same change, not left behind as a dangling contract entry.

### Authentication

Required.

### Request

```json
{
  "enabled": true
}
```

### Response

```http
202 Accepted
```

```json
{
  "domain_id": "uuid",
  "status": "PROCESSING",
  "task_id": "celery-task-id"
}
```

Task result on `SUCCESS`:

```json
{
  "domain": "ledgerflow.ai",
  "privacy_enabled": true,
  "message": "WHOIS privacy updated in name.com sandbox — no real domain affected."
}
```

A `409` from name.com specifically means this domain/TLD doesn't support WHOIS privacy — surfaced as `EXTERNAL_API_ERROR`, not a code implying a transient/retryable failure.

### Errors

```text
400 VALIDATION_ERROR

401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND

409 CONFLICT                — project.status != READY, or (from name.com) TLD doesn't support privacy

502 EXTERNAL_API_TIMEOUT

503 EXTERNAL_API_ERROR
```

---

# 26. Get Launch Report

```http
GET /api/v1/projects/{id}/launch-report/
```

### Authentication

Required.

### Response

```http
200 OK
```

```json
{
  "project": {
    "id": "uuid",
    "name": "LedgerFlow",
    "status": "READY"
  },
  "brand": {
    "id": "uuid",
    "name": "LedgerFlow"
  },
  "domain": {
    "id": "uuid",
    "domain": "ledgerflow.ai",
    "available": true
  },
  "checks": [
    {
      "type": "DOMAIN_READINESS",
      "status": "PASS",
      "message": "Domain is ready for launch."
    }
  ],
  "readiness": {
    "ready": true,
    "score": 100
  }
}
```

If the project is not ready:

```json
{
  "readiness": {
    "ready": false,
    "score": 66,
    "blocking_issues": [
      "Domain is not yet ready for launch."
    ]
  }
}
```

---

# 27. Background Task Status

React needs a way to determine whether asynchronous operations have completed.

```http
GET /api/v1/tasks/{task_id}/
```

### Authentication

Required.

### Processing

```json
{
  "task_id": "celery-task-id",
  "status": "PROCESSING",
  "progress": 50
}
```

### Completed

```json
{
  "task_id": "celery-task-id",
  "status": "COMPLETED",
  "progress": 100
}
```

### Failed

```json
{
  "task_id": "celery-task-id",
  "status": "FAILED",
  "progress": 100,
  "error": {
    "code": "EXTERNAL_API_TIMEOUT",
    "message": "The domain provider did not respond."
  }
}
```

---

# 28. Endpoint Summary

| Method | Endpoint                                        | Purpose                       | Async |
| ------ | ------------------------------------------------ | ------------------------------ | ----- |
| `POST` | `/api/v1/auth/register/`                         | Register user                  | No    |
| `POST` | `/api/v1/auth/login/`                            | Authenticate user               | No    |
| `POST` | `/api/v1/auth/token/refresh/`                    | Refresh access token            | No    |
| `POST` | `/api/v1/auth/logout/`                           | Logout                          | No    |
| `GET`  | `/api/v1/auth/me/`                               | Get current user                | No    |
| `POST` | `/api/v1/projects/`                              | Create project                  | No    |
| `GET`  | `/api/v1/projects/`                              | List projects                   | No    |
| `GET`  | `/api/v1/projects/{id}/`                         | Get project                     | No    |
| `POST` | `/api/v1/projects/{id}/generate-brands/`         | Generate AI brands (also used to regenerate) | Yes   |
| `GET`  | `/api/v1/projects/{id}/brands/`                  | Get brands                      | No    |
| `POST` | `/api/v1/projects/{id}/select-brand/`            | Select brand                    | No    |
| `POST` | `/api/v1/projects/{id}/domain-search/`           | Search domains (also used to regenerate) | Yes   |
| `GET`  | `/api/v1/projects/{id}/domain-searches/`         | Search history                  | No    |
| `GET`  | `/api/v1/projects/{id}/domains/`                 | Get domain results (incl. pricing) | No    |
| `POST` | `/api/v1/projects/{id}/recommend-domain/`        | AI picks best available domain (also used to regenerate) | Yes   |
| `GET`  | `/api/v1/projects/{id}/domain-recommendations/`  | Get domain recommendation history | No |
| `POST` | `/api/v1/domains/{id}/check-claims/`             | Trademark claims check          | Yes   |
| `GET`  | `/api/v1/domains/{id}/claims/`                   | Get latest claims result        | No    |
| `POST` | `/api/v1/projects/{id}/select-domain/`           | Select domain                   | No    |
| `POST` | `/api/v1/domains/{id}/create-dns-record/`        | Create a DNS record (live, name.com) | Yes |
| `GET`  | `/api/v1/domains/{id}/dns-records/`              | List DNS records (live, name.com) | No  |
| `POST` | `/api/v1/domains/{id}/check/`                    | Verify DNS/domain readiness      | Yes   |
| `GET`  | `/api/v1/domains/{id}/checks/`                   | Get domain checks                | No    |
| `POST` | `/api/v1/domains/{id}/simulate-registration/`    | Sandbox-only registration demo   | Yes   |
| `POST` | `/api/v1/domains/{id}/toggle-privacy/`           | Toggle WHOIS privacy (sandbox-only; under review, Ticket 12) | Yes |
| `GET`  | `/api/v1/projects/{id}/launch-report/`           | Get launch report                | No    |
| `GET`  | `/api/v1/tasks/{task_id}/`                       | Get background task status       | No    |

---

# 29. Authentication and Ownership Rules

Every protected endpoint must verify:

```text
request.user.is_authenticated
```

JWT authentication is responsible for establishing the authenticated user.

For project resources:

```text
project.user == request.user
```

For nested resources:

```text
BrandIdea.project.user == request.user

DomainSearch.project.user == request.user

DomainResult.project.user == request.user

DomainCheck.project.user == request.user

DomainClaim.domain_result.project.user == request.user

DomainRecommendation.project.user == request.user
```

DNS records have no local model to check ownership against — ownership for `create-dns-record/`/`dns-records/` is enforced the same way as `check-claims/`/`simulate-registration/`/`toggle-privacy/`: via `domain_result.project.user`, since these endpoints hang off `/domains/{id}/`, not `/projects/{id}/...`.

The API must never rely on React to enforce ownership.

Authorization is always enforced by Django.

---

# 30. External API Failure Contract

External provider failures must be normalized into application-level errors.

## name.com timeout

```http
502 Bad Gateway
```

```json
{
  "error": {
    "code": "EXTERNAL_API_TIMEOUT",
    "message": "The domain provider did not respond. Please try again."
  }
}
```

## name.com unavailable

```http
503 Service Unavailable
```

```json
{
  "error": {
    "code": "EXTERNAL_API_ERROR",
    "message": "Domain availability is temporarily unavailable."
  }
}
```

The API must **not** expose raw provider responses or credentials. This applies equally to the claims-check, simulate-registration, toggle-privacy, and DNS record endpoints.

`GET /api/v1/domains/{id}/dns-records/` is the one exception to the usual asynchronous pattern for provider errors: because it's a synchronous live proxy (§21.2), it can return `502`/`503` directly on the request itself rather than through a failed `TaskRecord`.

---

# 31. AI Failure Contract

If Gemini returns invalid structured data:

```text
Gemini
  ↓
Invalid response
  ↓
Schema validation fails
  ↓
AI_GENERATION_FAILED
```

Response:

```http
502 Bad Gateway
```

```json
{
  "error": {
    "code": "AI_GENERATION_FAILED",
    "message": "Brand generation could not be completed. Please try again."
  }
}
```

Invalid AI output must never be stored as a valid `BrandIdea`. The same rule applies to `POST /api/v1/projects/{id}/recommend-domain/`: invalid or unschema'd Gemini output must never be persisted as a `DomainRecommendation`.

---

# 32. Important API Rules

The API must enforce the following rules:

1. Users can only access their own projects.
2. A brand must belong to the project where it is selected.
3. A domain must belong to the project where it is selected.
4. Only available domains can be selected.
5. Stale domain availability must be refreshed before selection.
6. Provider errors must not be interpreted as domain unavailability.
7. AI output must be validated before persistence.
8. Long-running external operations should run through Celery.
9. PostgreSQL remains the source of truth (except DNS records, which have no local model — name.com is the source of truth for those).
10. React must never communicate directly with Gemini or name.com.
11. Provider credentials must remain server-side.
12. All API responses must use the documented JSON contract.
13. Protected endpoints require a valid JWT access token.
14. Access tokens must not be accepted from unauthenticated requests.
15. API routes must remain versioned under `/api/v1/`.
16. Simulate Registration and Toggle WHOIS Privacy must only ever call name.com's test/sandbox base URL. The client must refuse to run if configured against the production base URL.

---

# 33. Complete Application Flow

```text
React
  │
  │ POST /api/v1/projects/
  ↓
Django
  │
  ↓
LaunchProject
  │
  │ POST /api/v1/projects/{id}/generate-brands/  (also: regenerate)
  ↓
Celery
  │
  ↓
Gemini
  │
  ↓
BrandIdea[]
  │
  │ POST /api/v1/projects/{id}/domain-search/  (also: regenerate)
  ↓
Celery
  │
  ↓
name.com
  │
  ↓
DomainResult[]  (now includes purchase_price / renewal_price / premium)
  │
  ├── POST /api/v1/projects/{id}/recommend-domain/  → Gemini → DomainRecommendation
  │       (history: GET .../domain-recommendations/)
  ├── POST /api/v1/domains/{id}/check-claims/        → name.com → DomainClaim
  │
  │ POST /api/v1/projects/{id}/select-domain/
  ↓
LaunchProject.selected_domain
  │
  │ POST /api/v1/domains/{id}/check/   (DOMAIN_READINESS)
  ↓
Celery
  │
  ↓
DomainCheck[]
  │
  ↓
LaunchReadinessService
  │
  ↓
READY
  │
  ├── POST /api/v1/domains/{id}/simulate-registration/   (sandbox only)
  │       │
  │       └── POST /api/v1/domains/{id}/toggle-privacy/  (sandbox only)
  │
  ├── POST /api/v1/domains/{id}/create-dns-record/        (live, name.com — "Point your domain")
  │   GET  /api/v1/domains/{id}/dns-records/               (live, name.com)
  │
  │ GET /api/v1/projects/{id}/launch-report/
  ↓
React
  │
  ↓
Launch-ready UI — incl. "Buy on name.com" outbound link (frontend-only)
```

---

# 34. React Integration

The React frontend is an API consumer.

React is responsible for:

```text
UI
Routing
Forms
Loading states
Error states
JWT authentication state
Displaying API data
Polling background tasks
```

Django is responsible for:

```text
Authentication
Authorization
Validation
Business logic
Database operations
AI integration
Domain provider integration
DNS checks
Celery tasks
Launch readiness
```

React must never contain:

```text
Gemini API keys
name.com API credentials
Database credentials
Business authorization rules
Domain ownership rules
AI provider logic
```

The frontend communicates with Django only:

```text
React
  │
  │ JSON + JWT
  ↓
Django REST API
```

---

> **The REST API is the contract between React and Django. Django owns authentication, authorization, business logic, AI integration, domain-provider integration, persistence, and background processing. React is responsible for the user interface and consuming the versioned API.**