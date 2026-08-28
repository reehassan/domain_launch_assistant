# Data Model

> **What data does our application store?**

The Domain Launch Assistant stores the minimum persistent data required to move a founder from a business idea to a selected, launch-ready domain.

The application is **API-first**. The backend is built with Django + Django REST Framework, while the frontend is a separate React application communicating with the REST API.

The core entities are:

```text
User
  │
  └── LaunchProject
        │
        ├── BrandIdea
        │
        ├── DomainSearch
        │      │
        │      └── DomainResult
        │              │
        │              └── DomainClaim
        │
        ├── DomainCheck
        │
        └── DomainRecommendation
```

---

# 1. User

Represents a founder using the application.

The application uses Django's custom user model based on `AbstractUser`.

The User model is defined in the `users` Django app. Authentication operations (login, logout, registration, token refresh) that act on this model are implemented in a separate `accounts` app and have no models of their own.

## Fields

| Field         | Type     | Required | Description                   |
| ------------- | -------- | -------: | ----------------------------- |
| `id`          | UUID     |      Yes | Primary key                   |
| `username`    | String   |      Yes | Unique username               |
| `email`       | Email    |      Yes | User email                    |
| `first_name`  | String   |       No | First name                    |
| `last_name`   | String   |       No | Last name                     |
| `password`    | String   |      Yes | Hashed password               |
| `is_active`   | Boolean  |      Yes | Whether the account is active |
| `date_joined` | DateTime |      Yes | Account creation time         |
| `last_login`  | DateTime |       No | Last login time               |
| `created_at`  | DateTime |      Yes | Record creation time          |
| `updated_at`  | DateTime |      Yes | Last modification time        |

> `AbstractUser` provides `date_joined` and `last_login` out of the box, but not `created_at`/`updated_at`. These two fields must be added explicitly on the model: `created_at = DateTimeField(auto_now_add=True)` and `updated_at = DateTimeField(auto_now=True)`.

## Relationships

```text
User
 │
 └── 1:N ── LaunchProject
```

A user can own multiple launch projects.

## Constraints

* `id` is the primary key.
* `username` must be unique.
* `email` must be valid.
* `password` must use Django's password hashing.
* Inactive users cannot authenticate.
* A user cannot access another user's projects.

## Indexes

| Index             | Purpose                    |
| ----------------- | --------------------------- |
| Unique `username` | Fast lookup and uniqueness |
| `email`           | Email lookup               |
| `created_at`      | Time-based queries         |

---

# 2. LaunchProject

Represents a single business launch being worked on by a founder.

This is the **central domain model**.

## Fields

| Field                  | Type      | Required | Description                 |
| ---------------------- | --------- | -------: | ---------------------------- |
| `id`                   | UUID      |      Yes | Primary key                 |
| `user_id`              | UUID / FK |      Yes | Project owner                |
| `name`                 | String    |      Yes | Internal project name        |
| `business_description` | Text      |      Yes | Description of the business  |
| `status`               | Enum      |      Yes | Current workflow status      |
| `selected_brand_id`    | UUID / FK |       No | Selected brand idea          |
| `selected_domain_id`   | UUID / FK |       No | Selected domain              |
| `created_at`           | DateTime  |      Yes | Creation time                |
| `updated_at`           | DateTime  |      Yes | Last modification time       |

## Status

```text
DRAFT
GENERATING_BRANDS
BRANDS_READY
CHECKING_DOMAINS
DOMAIN_SELECTED
CONFIGURING_DNS
VERIFYING_DNS
READY
FAILED
```

> None of the six Day 7+ features (live pricing, regenerate brands/domains, AI domain recommendation, trademark claims check, simulate registration, buy on name.com) add a new status. Pricing, claims, and the AI recommendation are informational overlays on the existing `BRANDS_READY → DOMAIN_SELECTED` flow. Simulate Registration is a sandbox demo action logged through `TaskRecord`; it does not transition `status` and does not imply the domain has actually been registered.

## Relationships

```text
User
 │
 └── 1:N ── LaunchProject
                 │
                 ├── 1:N ── BrandIdea
                 │
                 ├── 1:N ── DomainSearch
                 │              │
                 │              └── 1:N ── DomainResult
                 │                             │
                 │                             └── 1:N ── DomainClaim
                 │
                 ├── 1:N ── DomainCheck
                 │
                 └── 1:N ── DomainRecommendation
```

## Constraints

* Every project must have exactly one owner.
* `name` cannot be empty.
* `business_description` cannot be empty.
* `status` must be a valid enum value.
* `selected_brand_id`, when present, must belong to the same project.
* `selected_domain_id`, when present, must belong to the same project.
* A project cannot be marked `READY` unless required launch checks pass.
* Users can only access projects they own.

## Indexes

| Index                   | Purpose                   |
| ------------------------ | --------------------------- |
| `(user_id, created_at)` | List user's projects      |
| `(user_id, status)`     | Filter projects by status |
| `updated_at`            | Recently updated projects |

---

# 3. BrandIdea

Represents a brand name generated by Gemini for a launch project.

## Fields

| Field           | Type      | Required | Description               |
| --------------- | --------- | -------: | --------------------------- |
| `id`            | UUID      |      Yes | Primary key                |
| `project_id`    | UUID / FK |      Yes | Parent project              |
| `name`          | String    |      Yes | Generated brand name        |
| `description`   | Text      |      Yes | AI explanation              |
| `generation_id` | String    |       No | AI generation identifier    |
| `is_selected`   | Boolean   |      Yes | Whether user selected it    |
| `created_at`    | DateTime  |      Yes | Creation time                |

> **Regenerate Brands** does not add a field or model here. It re-invokes the same generation flow, producing a new batch of `BrandIdea` rows with a later `created_at`; the frontend reads the latest batch by `created_at`, same as today.

## Relationships

```text
LaunchProject
      │
      └── 1:N ── BrandIdea
```

## Constraints

* `name` cannot be empty.
* `description` cannot be empty.
* A brand idea must belong to a project.
* A selected brand must belong to its project.
* At most one brand can be selected per project.

Recommended constraint:

```text
UniqueConstraint(
    project,
    is_selected=True
)
```

The brand name should also be unique case-insensitively within a project.

## Indexes

| Index                       | Purpose                 |
| ----------------------------- | -------------------------- |
| `(project_id, created_at)`  | Retrieve project brands |
| `(project_id, is_selected)` | Find selected brand     |
| `(project_id, name)`        | Brand lookup             |

---

# 4. DomainSearch

Represents one domain availability search performed for a project.

A search can contain multiple domain results.

## Fields

| Field                  | Type      | Required | Description          |
| ---------------------- | --------- | -------: | ---------------------- |
| `id`                   | UUID      |      Yes | Primary key            |
| `project_id`           | UUID / FK |      Yes | Parent project          |
| `brand_idea_id`        | UUID / FK |       No | Brand being searched    |
| `status`               | Enum      |      Yes | Search status           |
| `requested_extensions` | JSON      |      Yes | Requested extensions    |
| `started_at`           | DateTime  |       No | Search start time       |
| `completed_at`         | DateTime  |       No | Completion time         |
| `error_message`        | Text      |       No | Error information       |
| `created_at`           | DateTime  |      Yes | Creation time            |

> **Regenerate Domains** does not add a field or model here either — it re-invokes the same search flow, producing a new `DomainSearch` (and its own `DomainResult[]`) with a later `created_at`.

## Status

```text
PENDING
PROCESSING
COMPLETED
FAILED
```

## Relationships

```text
LaunchProject
      │
      └── 1:N ── DomainSearch
                     │
                     └── 1:N ── DomainResult

BrandIdea
      │
      └── 1:N ── DomainSearch
```

## Constraints

* `project_id` is required.
* `status` must be a valid enum value.
* `completed_at` is set when the search completes.
* `error_message` is populated for failed searches.
* A search cannot reference a brand from another project.
* Requested extensions must be valid domain extensions.

## Delete Behavior

```text
LaunchProject
      ↓ CASCADE
DomainSearch
      ↓ CASCADE
DomainResult
```

## Indexes

| Index                         | Purpose                |
| -------------------------------- | -------------------------- |
| `(project_id, created_at)`    | Search history          |
| `(project_id, status)`        | Active/failed searches  |
| `(brand_idea_id, created_at)` | Brand search history    |

---

# 5. DomainResult

Represents one domain returned by a domain search.

Example:

```text
ledgerflow.ai
```

## Fields

| Field            | Type      | Required | Description                                                  |
| ---------------- | --------- | -------: | -------------------------------------------------------------- |
| `id`             | UUID      |      Yes | Primary key                                                    |
| `search_id`      | UUID / FK |      Yes | Parent search                                                   |
| `project_id`     | UUID / FK |      Yes | Project reference                                               |
| `domain`         | String    |      Yes | Complete domain name                                            |
| `extension`      | String    |      Yes | Domain extension                                                |
| `available`      | Boolean   |      Yes | Whether domain is available                                     |
| `status`         | Enum      |      Yes | Availability state                                              |
| `provider`       | String    |      Yes | Provider name                                                   |
| `checked_at`     | DateTime  |      Yes | Availability check time                                         |
| `raw_metadata`   | JSON      |       No | Relevant provider metadata                                      |
| `purchase_price` | Decimal   |       No | Discovery purchase price from name.com, USD                     |
| `renewal_price`  | Decimal   |       No | Discovery renewal price from name.com, USD                      |
| `premium`        | Boolean   |       No | Whether this is a premium-priced result                         |
| `purchase_type`  | String    |       No | e.g. `registration` — passed through to a later create-domain call |
| `created_at`     | DateTime  |      Yes | Creation time                                                    |

`purchase_price`, `renewal_price`, `premium`, and `purchase_type` (feature: **Live Domain Pricing**) are populated from the *existing* `checkAvailability` provider call — no new provider call is introduced. All four are nullable; `CHECK_FAILED` results won't have pricing.

## Status

```text
AVAILABLE
TAKEN
UNKNOWN
CHECK_FAILED
```

`CHECK_FAILED` must never be interpreted as `TAKEN`.

## Relationships

```text
DomainSearch
      │
      └── 1:N ── DomainResult
                       │
                       └── 1:N ── DomainClaim
```

## Constraints

* `domain` must be normalized to lowercase.
* `domain` cannot be empty.
* `extension` cannot be empty.
* `provider` cannot be empty.
* `checked_at` is required.
* `available=True` corresponds to `status=AVAILABLE`.
* A result must belong to the same project as its parent search.

## Domain Normalization

```text
LedgerFlow.AI
```

becomes:

```text
ledgerflow.ai
```

## Indexes

| Index                     | Purpose                |
| --------------------------- | -------------------------- |
| `(project_id, domain)`    | Project-domain lookup  |
| `(search_id, domain)`     | Search results          |
| `(project_id, available)` | Find available domains |
| `(domain, checked_at)`    | Availability/freshness  |
| `(project_id, extension)` | Filter by extension     |

## Uniqueness

```text
UNIQUE(search_id, domain)
```

A search cannot contain the same domain twice.

---

# 6. DomainCheck

Represents a technical DNS/domain check used to determine launch readiness.

A project can have multiple checks over time.

## Fields

| Field              | Type      | Required | Description           |
| -------------------- | --------- | -------: | -------------------------- |
| `id`               | UUID      |      Yes | Primary key            |
| `project_id`       | UUID / FK |      Yes | Parent project          |
| `domain_result_id` | UUID / FK |      Yes | Domain being checked    |
| `check_type`       | Enum      |      Yes | Type of check           |
| `status`           | Enum      |      Yes | Check result            |
| `record_type`      | String    |       No | DNS record type         |
| `record_name`      | String    |       No | DNS record name         |
| `expected_value`   | Text      |       No | Expected DNS value      |
| `actual_value`     | Text      |       No | Detected DNS value      |
| `message`          | Text      |       No | Human-readable result   |
| `checked_at`       | DateTime  |      Yes | Check time               |
| `created_at`       | DateTime  |      Yes | Creation time             |

## Check Types

```text
DNS_CONFIGURATION
DNS_RESOLUTION
DOMAIN_READINESS
```

## Status

```text
PENDING
PASS
FAIL
ERROR
```

The distinction is important:

```text
FAIL
→ Check completed successfully but configuration is incorrect.

ERROR
→ Check could not be completed.
```

## Relationships

```text
LaunchProject
      │
      └── 1:N ── DomainCheck
                       │
                       └── N:1 ── DomainResult
```

## Constraints

* A check must belong to a project.
* A check must reference a domain from the same project.
* `check_type` must be valid.
* `status` must be valid.
* `checked_at` is required.
* DNS-specific fields should only be populated for DNS checks.
* Provider failures use `ERROR`, not `FAIL`.

---

# 7. DomainClaim

Represents one on-demand Trademark Clearinghouse (TMCH) claims check against a domain, run through name.com. Supports the **Trademark Claims Check** feature.

Mirrors the existing `DomainCheck` pattern: append-only history rather than overwriting, so a founder can see when a claims check was last run and what it found.

## Fields

| Field               | Type      | Required | Description                                            |
| -------------------- | --------- | -------: | -------------------------------------------------------- |
| `id`                | UUID      |      Yes | Primary key                                              |
| `domain_result_id`  | UUID / FK |      Yes | Domain being checked                                     |
| `has_claims`        | Boolean   |      Yes | Whether any TMCH claims matched                          |
| `claims_data`       | JSON      |       No | Raw claim records (mark name, holder) when `has_claims=True` |
| `checked_at`        | DateTime  |      Yes | When the check ran                                        |
| `created_at`        | DateTime  |      Yes | Row creation time                                          |

## Relationships

```text
DomainResult
      │
      └── 1:N ── DomainClaim
```

## Constraints

* A claim check must reference a `DomainResult`.
* `has_claims` is required.
* `claims_data` is only meaningful when `has_claims=True`.
* `checked_at` is required.
* Each check creates a new row — an existing `DomainClaim` is never updated in place.

## Delete Behavior

```text
DomainResult
      ↓ PROTECT
DomainClaim
```

Same reasoning as `DomainResult → DomainCheck`: claim history must not silently disappear if the parent domain result is ever deleted.

## Indexes

| Index                              | Purpose                        |
| ------------------------------------ | --------------------------------- |
| `(domain_result_id, checked_at)`   | Latest claims result for a domain |
| `(domain_result_id, has_claims)`   | Filter domains with active claims |

---

# 8. DomainRecommendation

Represents one AI-generated pick of the best *available* domain result for a project, with reasoning. Supports the **AI Domain Recommendation** feature.

Persisted (not just returned once) so a page refresh still shows the AI's pick — same reasoning as why brand ideas and domain searches are re-fetched from the backend rather than kept only in React state.

## Fields

| Field                     | Type      | Required | Description               |
| --------------------------- | --------- | -------: | ---------------------------- |
| `id`                      | UUID      |      Yes | Primary key                  |
| `project_id`               | UUID / FK |      Yes | Parent project                |
| `recommended_domain_id`    | UUID / FK |      Yes | The pick (a `DomainResult`)   |
| `reasoning`                | Text      |      Yes | AI's explanation              |
| `created_at`               | DateTime  |      Yes | When generated                 |

No `is_selected` flag is needed. Regenerating the recommendation (calling the endpoint again) simply creates a new row; the frontend reads the latest by `created_at` — the same convention used for `BrandIdea` and `DomainSearch`.

## Relationships

```text
LaunchProject
      │
      └── 1:N ── DomainRecommendation
                       │
                       └── N:1 ── DomainResult (recommended_domain_id)
```

## Constraints

* `recommended_domain_id` must reference a `DomainResult` belonging to the same project.
* `recommended_domain_id` must reference a result with `status=AVAILABLE` at the time of generation.
* `reasoning` cannot be empty.
* AI output must be schema-validated before being persisted as a `DomainRecommendation` — invalid Gemini output is never stored (same discipline as `BrandIdea` generation).

## Delete Behavior

```text
LaunchProject
      ↓ CASCADE
DomainRecommendation
```

```text
DomainResult
      ↓ PROTECT
DomainRecommendation
```

A recommended domain result cannot be deleted out from under a stored recommendation that still points to it.

## Indexes

| Index                          | Purpose                              |
| --------------------------------- | ---------------------------------------- |
| `(project_id, created_at)`      | Latest recommendation for a project    |
| `(recommended_domain_id)`       | Find recommendations pointing at a domain |

---

# 9. Simulate Registration — no new model

**Simulate Registration** (sandbox-only call to name.com's real `Create Domain` endpoint) intentionally does **not** get a new model.

It is a demo action, not new persistent workflow state — it doesn't change `LaunchProject.status` and doesn't create a "the domain is registered" fact that the data model would otherwise have to un-say later if the sandbox call is repeated or the founder later registers for real elsewhere. It is logged through the existing `TaskRecord` (background task status) only, the same as any other Celery-backed action whose outcome is transient.

**Buy on name.com** is a frontend-only outbound link and has no backend data footprint at all.

---

# 10. Complete Relationship Model

```text
User
 │
 │ 1:N
 ↓
LaunchProject
 │
 ├──────── 1:N ────────→ BrandIdea
 │
 ├──────── 1:N ────────→ DomainSearch
 │                           │
 │                           │ 1:N
 │                           ↓
 │                      DomainResult
 │                           │
 │                           │ 1:N
 │                           ↓
 │                      DomainClaim
 │
 ├──────── 1:N ────────→ DomainCheck
 │
 └──────── 1:N ────────→ DomainRecommendation ──→ N:1 ──→ DomainResult
```

Selected entities:

```text
LaunchProject.selected_brand
        ↓
BrandIdea

LaunchProject.selected_domain
        ↓
DomainResult
```

Both selected entities must belong to the same `LaunchProject`.

---

# 11. Delete Behavior

| Relationship                       | Behavior           | Reason                          |
| ------------------------------------- | -------------------- | ----------------------------------- |
| User → LaunchProject               | CASCADE            | Projects belong to the user       |
| LaunchProject → BrandIdea          | CASCADE            | Ideas belong to project            |
| LaunchProject → DomainSearch       | CASCADE            | Searches belong to project         |
| DomainSearch → DomainResult        | CASCADE            | Results belong to search           |
| LaunchProject → DomainCheck        | CASCADE            | Checks belong to project           |
| DomainResult → DomainCheck         | PROTECT / RESTRICT | Preserve check history              |
| DomainResult → DomainClaim         | PROTECT            | Preserve claims-check history       |
| LaunchProject → DomainRecommendation | CASCADE           | Recommendations belong to project   |
| DomainResult → DomainRecommendation  | PROTECT           | Preserve the domain a pick pointed to |

---

# 12. Database Constraints

Required fields:

```text
User.username
User.email

LaunchProject.user
LaunchProject.name
LaunchProject.business_description

BrandIdea.project
BrandIdea.name

DomainSearch.project
DomainSearch.status

DomainResult.search
DomainResult.project
DomainResult.domain
DomainResult.available

DomainCheck.project
DomainCheck.domain_result
DomainCheck.check_type
DomainCheck.status

DomainClaim.domain_result
DomainClaim.has_claims
DomainClaim.checked_at

DomainRecommendation.project
DomainRecommendation.recommended_domain
DomainRecommendation.reasoning
```

## Uniqueness

Globally:

```text
User.username
```

Within a project:

```text
(project, LOWER(brand_name))
```

Within a search:

```text
(search, domain)
```

---

# 13. Ownership Integrity

The backend must enforce project ownership on every API operation.

The following relationships must remain valid:

```text
BrandIdea.project
        =
DomainSearch.project
```

```text
DomainResult.project
        =
DomainSearch.project
```

```text
DomainCheck.project
        =
DomainResult.project
```

```text
DomainClaim.domain_result.project
        =
DomainResult.project
```

```text
DomainRecommendation.project
        =
DomainRecommendation.recommended_domain.project
```

This prevents cross-project data access.

For example, a user must never be able to manipulate another user's domain by changing an ID in an API request.

---

# 14. Index Strategy

Indexes should support actual application queries.

## Foreign Keys

```text
LaunchProject.user_id

BrandIdea.project_id

DomainSearch.project_id
DomainSearch.brand_idea_id

DomainResult.search_id
DomainResult.project_id

DomainCheck.project_id
DomainCheck.domain_result_id

DomainClaim.domain_result_id

DomainRecommendation.project_id
DomainRecommendation.recommended_domain_id
```

## Workflow Indexes

```text
LaunchProject(user_id, status)

DomainSearch(project_id, status)

DomainResult(project_id, available)

DomainCheck(project_id, status)

DomainClaim(domain_result_id, checked_at)

DomainRecommendation(project_id, created_at)
```

These support the primary API queries efficiently.

---

# 15. Data Freshness

Domain availability is time-sensitive.

Every `DomainResult` therefore stores:

```text
checked_at
```

The API should expose freshness information to the React frontend.

Example:

```text
Fresh
  ↓
Display availability

Stale
  ↓
Show "Refresh availability"
```

The freshness TTL should be configured at the application level rather than stored as a database rule.

`DomainClaim.checked_at` and `DomainRecommendation.created_at` follow the same "read the latest row" pattern — freshness for these is about surfacing the most recent check/recommendation, not a TTL-driven refresh prompt.

---

# 16. Source of Truth

PostgreSQL is the source of truth for persistent application state.

External APIs are integration providers, not sources of application workflow state.

```text
Gemini / name.com
       ↓
Integration Client
       ↓
Application Service
       ↓
Validation
       ↓
PostgreSQL
```

Redis is used for caching and Celery messaging.

Redis is **not** the source of truth.

---

# 17. API Data Flow

Because the frontend is React, all frontend communication goes through the REST API.

```text
React
  │
  │ JSON / HTTPS
  ↓
Django REST Framework
  │
  ↓
Application Services
  │
  ├── Gemini
  │
  ├── name.com
  │
  └── PostgreSQL
```

For asynchronous operations:

```text
React
  ↓
POST API endpoint
  ↓
Django
  ↓
Celery Task
  ↓
Redis
  ↓
Celery Worker
  ↓
External API
  ↓
PostgreSQL
  ↓
React polls/status API
```

The database model therefore remains independent of the React frontend.

---

# 18. MVP Data Flow

```text
Business Idea
      ↓
LaunchProject
      ↓
Gemini Generation
      ↓
BrandIdea[]  ←── regenerate reuses the same generation flow
      ↓
DomainSearch
      ↓
DomainResult[]  ←── now carries purchase_price / renewal_price / premium
      │            ←── regenerate reuses the same search flow
      │
      ├── DomainRecommendation  (AI pick + reasoning)
      ├── DomainClaim           (on-demand TMCH check)
      ↓
User Selects Domain
      ↓
LaunchProject.selected_domain
      ↓
DomainCheck[]
      ↓
Launch Readiness
      ↓
READY
      ↓
Simulate Registration (sandbox only — no new model, logged via TaskRecord)
```

The data model now covers **eight core entities**: `User`, `LaunchProject`, `BrandIdea`, `DomainSearch`, `DomainResult`, `DomainCheck`, `DomainClaim`, and `DomainRecommendation`.

The MVP still does not introduce separate models for payments, teams, websites, email hosting, social media accounts, or full (non-sandbox) domain registration.