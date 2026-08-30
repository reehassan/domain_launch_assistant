# Data Model

> What data does the application store?

API-first: Django + DRF backend, PostgreSQL as source of truth, separate React frontend. Nine core entities:

```text
User ── LaunchProject ── BrandIdea ── DomainSearch ── DomainResult ── DomainClaim
                      │                                    │
                      ├── DomainCheck                      └── TaskRecord (optional)
                      ├── DomainRecommendation ──→ DomainResult
                      └── TaskRecord
```

All FK ownership must trace back to a single `LaunchProject.user` — enforced by a mix of DB constraints and `clean()` methods (noted per entity below). Cross-project access via a spoofed ID must never be possible.

---

## 1. User (`users` app)

| Field | Type | Req | Notes |
|---|---|---|---|
| `id` | UUID | Y | PK |
| `username` | String | Y | Unique |
| `email` | Email | Y | Unique, indexed — redeclared from `AbstractUser` default, which is neither |
| `first_name` / `last_name` | String | N | |
| `password` | String | Y | Django-hashed |
| `is_active` | Boolean | Y | Inactive users cannot authenticate |
| `date_joined` / `last_login` | DateTime | Y/N | From `AbstractUser` |
| `created_at` / `updated_at` | DateTime | Y | Added explicitly — not on `AbstractUser` |

**Indexes:** unique `username`, unique `email`, `created_at`. **Auth** (register/login/logout/refresh) lives in the separate `accounts` app with no models of its own.

---

## 2. LaunchProject — central model

| Field | Type | Req | Notes |
|---|---|---|---|
| `id` | UUID | Y | PK |
| `user` | FK→User | Y | CASCADE |
| `name` | String | Y | Not empty (`CheckConstraint`) |
| `business_description` | Text | Y | Not empty (`CheckConstraint`) |
| `status` | Enum | Y | See below |
| `selected_brand` | FK→BrandIdea | N | SET_NULL; must belong to this project (`clean()`, not DB-enforced) |
| `selected_domain` | FK→DomainResult | N | SET_NULL; must belong to this project (`clean()`) |
| `created_at` / `updated_at` | DateTime | Y | |

**Status:** `DRAFT → GENERATING_BRANDS → BRANDS_READY → CHECKING_DOMAINS → DOMAIN_SELECTED → CONFIGURING_DNS → VERIFYING_DNS → READY / FAILED`. Pricing, claims, and AI recommendation are informational overlays — none add a status. Simulate Registration doesn't transition status either.

**Indexes:** `(user, created_at)`, `(user, status)`, `updated_at`.

---

## 3. BrandIdea (`brands`)

| Field | Type | Req | Notes |
|---|---|---|---|
| `id` | UUID | Y | PK |
| `project` | FK | Y | CASCADE |
| `name` | String | Y | Not empty; unique case-insensitively per project |
| `description` | Text | Y | Not empty |
| `generation_id` | String | N | |
| `is_selected` | Boolean | Y | At most one `True` per project |
| `created_at` | DateTime | Y | |

**DB constraints:** `UniqueConstraint(project, condition=Q(is_selected=True))`, `UniqueConstraint(Lower(name), project)`, not-empty checks on `name`/`description`.

**Indexes:** `(project, created_at)`, `(project, is_selected)`, `(project, name)`.

Regenerate re-invokes the same generation flow; frontend reads the latest batch by `created_at`. No new field/model for it.

---

## 4. DomainSearch (`domains`)

| Field | Type | Req | Notes |
|---|---|---|---|
| `id` | UUID | Y | PK |
| `project` | FK | Y | CASCADE |
| `brand_idea` | FK | N | CASCADE; must belong to same project (`clean()`) |
| `status` | Enum | Y | `PENDING / PROCESSING / COMPLETED / FAILED` |
| `requested_extensions` | JSON | Y | Defaults `[]` |
| `started_at` / `completed_at` | DateTime | N | |
| `error_message` | Text | N | |
| `created_at` | DateTime | Y | |

**Indexes:** `(project, created_at)`, `(project, status)`, `(brand_idea, created_at)`.

**Delete:** `Project → CASCADE`, `BrandIdea → CASCADE`. Since `DomainResult` is `PROTECT`ed downstream (by `DomainCheck`/`DomainClaim`/`DomainRecommendation`), deleting a `BrandIdea` with checked/claimed/recommended results underneath will raise `ProtectedError` rather than cascading all the way through.

Regenerate creates a new `DomainSearch` + its own `DomainResult[]`; no new field/model.

---

## 5. DomainResult (`domains`)

| Field | Type | Req | Notes |
|---|---|---|---|
| `id` | UUID | Y | PK |
| `search` | FK | Y | CASCADE |
| `project` | FK | Y | Direct FK, must match `search.project` (`clean()`) |
| `domain` | String | Y | Lowercased/stripped on save |
| `extension` | String | Y | |
| `available` | Boolean | Y | `True` ⇔ `status=AVAILABLE`, enforced both directions in `clean()` |
| `status` | Enum | Y | `AVAILABLE / TAKEN / UNKNOWN / CHECK_FAILED` — `CHECK_FAILED` ≠ `TAKEN`, ever |
| `provider` | String | Y | |
| `checked_at` | DateTime | Y | |
| `raw_metadata` | JSON | N | |
| `purchase_price`, `renewal_price`, `premium`, `purchase_type` | Decimal/Bool/String | N | **Live Pricing** — from the existing `checkAvailability` response, no extra provider call. Null when `CHECK_FAILED`. |
| `registered_at`, `registration_order_id`, `privacy_enabled` | DateTime/String/Bool | N | **Sandbox registration state**, persisted here (see §9) so it survives reload — previously only lived in an unpersisted task result / frontend state |
| `created_at` | DateTime | Y | |

**Unique:** `(search, domain)`. **Indexes:** `(project, domain)`, `(search, domain)`, `(project, available)`, `(domain, checked_at)`, `(project, extension)`.

---

## 6. DomainCheck (`dns`)

| Field | Type | Req | Notes |
|---|---|---|---|
| `id` | UUID | Y | PK |
| `project` | FK | Y | CASCADE; must match `domain_result.project` (`clean()`) |
| `domain_result` | FK | Y | **PROTECT** — preserve check history |
| `check_type` | Enum | Y | `DNS_CONFIGURATION` (unsupported — service layer rejects it), `DNS_RESOLUTION`, `DOMAIN_READINESS` |
| `status` | Enum | Y | `PENDING / PASS / FAIL / ERROR` — `FAIL` = ran and configuration is wrong; `ERROR` = couldn't complete |
| `record_type`, `record_name`, `expected_value`, `actual_value` | String/Text | N | DNS-specific; left null for `DOMAIN_READINESS` (convention, not DB-enforced) |
| `message` | Text | N | |
| `checked_at` | DateTime | N | Null until the Celery task actually runs |
| `created_at` | DateTime | Y | |

**Indexes:** `(project)`, `(domain_result)`, `(project, status)`.

---

## 7. DomainClaim (`domains`) — Trademark Claims Check

Append-only, mirrors `DomainCheck`'s history pattern — never updated in place.

| Field | Type | Req | Notes |
|---|---|---|---|
| `id` | UUID | Y | PK |
| `domain_result` | FK | Y | **PROTECT** |
| `has_claims` | Boolean | Y | |
| `claims_data` | JSON | N | Meaningful only when `has_claims=True` |
| `checked_at` | DateTime | Y | |
| `created_at` | DateTime | Y | |

**Indexes:** `(domain_result, checked_at)`, `(domain_result, has_claims)`.

---

## 8. DomainRecommendation (`core`) — AI Domain Recommendation

Persisted so a refresh still shows the pick — same reasoning as `BrandIdea`/`DomainSearch`. No `is_selected`; regenerating creates a new row, frontend reads latest by `created_at`.

| Field | Type | Req | Notes |
|---|---|---|---|
| `id` | UUID | Y | PK |
| `project` | FK | Y | CASCADE |
| `recommended_domain` | FK→DomainResult | Y | **PROTECT**; must belong to same project (`clean()`); must be `AVAILABLE` at generation time (service-layer check, not model-level) |
| `reasoning` | Text | Y | Not empty |
| `created_at` | DateTime | Y | |

AI output is schema-validated before persistence — invalid Gemini output is never stored. **Indexes:** `(project, created_at)`, `(recommended_domain)`.

---

## 9. TaskRecord (`tasks`) — Celery task tracking

Backs `GET /api/v1/tasks/{task_id}/`. Every async action (brand gen, domain search, DNS checks, claims, recommendation, sandbox registration) logs through this.

| Field | Type | Req | Notes |
|---|---|---|---|
| `task_id` | UUID | Y | PK — **is** the Celery task's own `.delay().id`, not a separate generated id |
| `project` | FK | Y | CASCADE |
| `domain_result` | FK | N | SET_NULL; set only for domain-scoped actions (e.g. claims-check) |
| `status` | Enum | Y | `PENDING / PROCESSING / SUCCESS / FAILURE` |
| `result` | JSON | N | |
| `error_code`, `error_message` | String/Text | N | |
| `created_at` / `updated_at` | DateTime | Y | |

No `user` FK — ownership checked via `project.user`, same as other apps.

**Locking classmethods:**
- `has_active_task(project)` — blocks a second generate/search/check/recommend/simulate call while one is in flight project-wide.
- `has_active_task_for_domain(domain_result)` — narrower lock for domain-scoped actions (claims-check), so N domain cards can each dispatch concurrently without 409ing each other. Only trusts explicitly-tagged rows; project-wide actions stay invisible to it.

> Gap: `TaskRecord.project == TaskRecord.domain_result.project` (when set) is an assumed invariant, not enforced by `clean()` or a DB constraint — unlike every other cross-FK ownership rule in this doc.

---

## 10. Sandbox registration — no new model

Simulate Registration (name.com's real `Create Domain` endpoint, sandbox-only) persists its outcome on the **existing** `DomainResult` row (`registered_at`, `registration_order_id`, `privacy_enabled` — §5), not a new model. This replaced an earlier design that kept this state only in an unpersisted task result / frontend `useState`, both of which reset on reload despite the registration being real and durable on name.com's side. Still logged through `TaskRecord` for polling; still does not transition `LaunchProject.status`; still not a real, billable registration.

"Buy on name.com" is a frontend-only outbound link — no backend footprint.

---

## 11. Delete Behavior (full table)

| Relationship | Behavior | Reason |
|---|---|---|
| User → LaunchProject | CASCADE | |
| LaunchProject → BrandIdea / DomainSearch / DomainCheck / DomainRecommendation / TaskRecord | CASCADE | Owned by project |
| BrandIdea → DomainSearch | CASCADE | Search scoped to brand |
| DomainSearch → DomainResult | CASCADE | |
| DomainResult → DomainCheck | PROTECT | Preserve check history |
| DomainResult → DomainClaim | PROTECT | Preserve claims history |
| DomainResult → DomainRecommendation | PROTECT | Preserve the domain a pick pointed to |
| DomainResult → TaskRecord | SET_NULL | Task log isn't "history" in the same sense; outlives the domain result |
| LaunchProject → selected_brand / selected_domain | SET_NULL | Losing the reference shouldn't delete the project |

---

## 12. Ownership Integrity

Every downstream FK must trace back to the same project as its parent, enforced via `clean()` unless noted:

```text
BrandIdea.project = DomainSearch.project
DomainResult.project = DomainSearch.project      (direct FK check, not via search.project)
DomainCheck.project = DomainResult.project
DomainClaim.domain_result.project = DomainResult.project
DomainRecommendation.project = DomainRecommendation.recommended_domain.project
TaskRecord.project = TaskRecord.domain_result.project   ← NOT enforced (see §9 gap note)
```

---

## 13. Freshness, Source of Truth, and Data Flow

**Freshness:** `DomainResult.checked_at` drives a "Fresh / show Refresh availability" UI split; TTL is app-config, not a DB rule. `DomainClaim.checked_at` / `DomainRecommendation.created_at` follow the same "read latest row" pattern, not TTL-driven.

**Source of truth:** PostgreSQL only. External APIs (Gemini, name.com) are integration providers, not workflow-state holders. Redis is Celery broker + result backend only — not a source of truth, not currently used for caching.

**Async data flow:**

```text
React → POST endpoint → Django creates TaskRecord (PENDING) + PENDING model row(s)
      → Celery task: PROCESSING → calls service → external API → PostgreSQL → SUCCESS/FAILURE
React polls GET /api/v1/tasks/{task_id}/
```

**End-to-end flow:** `LaunchProject → BrandIdea[] → DomainSearch → DomainResult[] (+ DomainRecommendation, DomainClaim) → selected_domain → DomainCheck[] → READY → Simulate Registration (sandbox, persisted on DomainResult)`.

No models exist yet for payments, teams, websites, email hosting, social accounts, or real (non-sandbox) registration.