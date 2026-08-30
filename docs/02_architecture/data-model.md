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
        ├── DomainRecommendation
        │
        └── TaskRecord
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
| `email`       | Email    |      Yes | User email (unique, indexed)  |
| `first_name`  | String   |       No | First name                    |
| `last_name`   | String   |       No | Last name                     |
| `password`    | String   |      Yes | Hashed password               |
| `is_active`   | Boolean  |      Yes | Whether the account is active |
| `date_joined` | DateTime |      Yes | Account creation time         |
| `last_login`  | DateTime |       No | Last login time               |
| `created_at`  | DateTime |      Yes | Record creation time          |
| `updated_at`  | DateTime |      Yes | Last modification time        |

> `AbstractUser` provides `date_joined` and `last_login` out of the box, but not `created_at`/`updated_at`. These two fields are added explicitly on the model: `created_at = DateTimeField(auto_now_add=True)` and `updated_at = DateTimeField(auto_now=True)`. `email` is also redeclared as `unique=True, db_index=True` (AbstractUser's default `email` is neither unique nor indexed).

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
* `email` must be unique and valid.
* `password` must use Django's password hashing.
* Inactive users cannot authenticate.
* A user cannot access another user's projects.

## Indexes

| Index             | Purpose                    |
| ----------------- | --------------------------- |
| Unique `username` | Fast lookup and uniqueness |
| `email` (unique)  | Email lookup               |
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

> None of the Day 7+ features (live pricing, regenerate brands/domains, AI domain recommendation, trademark claims check, simulate registration, buy on name.com) add a new status. Pricing, claims, and the AI recommendation are informational overlays on the existing `BRANDS_READY → DOMAIN_SELECTED` flow. Simulate Registration is a sandbox demo action; it does not transition `status`.

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
                 ├── 1:N ── DomainRecommendation
                 │
                 └── 1:N ── TaskRecord
```

## Constraints

* Every project must have exactly one owner.
* `name` cannot be empty.
* `business_description` cannot be empty.
* `status` must be a valid enum value.
* `selected_brand_id`, when present, must belong to the same project (enforced in `clean()`, not a DB constraint).
* `selected_domain_id`, when present, must belong to the same project (enforced in `clean()`, not a DB constraint).
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
                       │
                       └── 1:N ── DomainSearch
```

Note: `BrandIdea` is also referenced by `DomainSearch.brand_idea` (optional) and by `LaunchProject.selected_brand`.

## Constraints

* `name` cannot be empty.
* `description` cannot be empty.
* A brand idea must belong to a project.
* A selected brand must belong to its project.
* At most one brand can be selected per project.
* Brand name must be unique, case-insensitively, within a project.

Actual DB constraints:

```text
UniqueConstraint(project, condition=Q(is_selected=True))
UniqueConstraint(Lower(name), project)
CheckConstraint(~Q(name=""))
CheckConstraint(~Q(description=""))
```

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
| `requested_extensions` | JSON      |      Yes | Requested extensions (defaults to `[]`) |
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
* A search cannot reference a brand from another project (enforced in `clean()`).
* Requested extensions must be valid domain extensions.

## Delete Behavior

```text
LaunchProject
      ↓ CASCADE
DomainSearch
      ↓ CASCADE
DomainResult
```

```text
BrandIdea
      ↓ CASCADE
DomainSearch
```

> Because `brand_idea` cascades, deleting a `BrandIdea` deletes every `DomainSearch` that was scoped to it — and, transitively, every `DomainResult` under those searches. Since `DomainResult` is `PROTECT`ed by `DomainCheck`, `DomainClaim`, and `DomainRecommendation`, deleting a `BrandIdea` with checked/claimed/recommended results underneath it will raise a `ProtectedError` rather than silently cascading all the way down.

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

| Field                     | Type      | Required | Description                                                  |
| -------------------------- | --------- | -------: | -------------------------------------------------------------- |
| `id`                      | UUID      |      Yes | Primary key                                                    |
| `search_id`               | UUID / FK |      Yes | Parent search                                                   |
| `project_id`              | UUID / FK |      Yes | Project reference                                               |
| `domain`                  | String    |      Yes | Complete domain name                                            |
| `extension`               | String    |      Yes | Domain extension                                                |
| `available`               | Boolean   |      Yes | Whether domain is available                                     |
| `status`                  | Enum      |      Yes | Availability state                                              |
| `provider`                | String    |      Yes | Provider name                                                   |
| `checked_at`              | DateTime  |      Yes | Availability check time                                         |
| `raw_metadata`            | JSON      |       No | Relevant provider metadata                                      |
| `purchase_price`          | Decimal   |       No | Discovery purchase price from name.com, USD                     |
| `renewal_price`           | Decimal   |       No | Discovery renewal price from name.com, USD                      |
| `premium`                 | Boolean   |       No | Whether this is a premium-priced result                         |
| `purchase_type`           | String    |       No | e.g. `registration` — passed through to a later create-domain call |
| `registered_at`           | DateTime  |       No | When this domain was registered in the sandbox                  |
| `registration_order_id`   | String    |       No | name.com sandbox order id from Simulate Registration              |
| `privacy_enabled`         | Boolean   |       No | Whether WHOIS privacy was enabled at registration                 |
| `created_at`              | DateTime  |      Yes | Creation time                                                    |

`purchase_price`, `renewal_price`, `premium`, and `purchase_type` (feature: **Live Domain Pricing**) are populated from the *existing* `checkAvailability` provider call — no new provider call is introduced. All four are nullable; `CHECK_FAILED` results won't have pricing.

`registered_at`, `registration_order_id`, and `privacy_enabled` (feature: **Simulate Registration**, persistence fix post-Ticket 15) persist the outcome of a sandbox registration directly on the domain result. They replace an earlier design where this state lived only in an unpersisted Celery task result / frontend `useState`, both of which reset on any page reload or route navigation even though the sandbox registration was real and durable on name.com's side. See §10.

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
                       ├── 1:N ── DomainClaim
                       │
                       └── 1:N ── TaskRecord (optional)
```

## Constraints

* `domain` must be normalized to lowercase.
* `domain` cannot be empty.
* `extension` cannot be empty.
* `provider` cannot be empty.
* `checked_at` is required.
* `available=True` requires `status=AVAILABLE`, and `status=AVAILABLE` requires `available=True` (enforced both directions in `clean()`).
* A result must belong to the same project as its parent search (enforced in `clean()`).

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
| `checked_at`       | DateTime  |       No | Check time — null until the Celery task actually runs the check |
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
* A check must reference a domain from the same project (enforced in `clean()`).
* `check_type` must be valid.
* `status` must be valid.
* DNS-specific fields should only be populated for DNS checks (application-level convention, not DB-enforced).
* Provider failures use `ERROR`, not `FAIL`.

## Indexes

| Index                        | Purpose                        |
| ------------------------------- | --------------------------------- |
| `(project_id)`                | List checks for a project        |
| `(domain_result_id)`          | List checks for a domain result  |
| `(project_id, status)`        | Workflow / readiness queries     |

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

* `recommended_domain_id` must reference a `DomainResult` belonging to the same project (enforced in `clean()`).
* `recommended_domain_id` must reference a result with `status=AVAILABLE` at the time of generation (enforced in the service layer — a model-level `clean()` cannot check "at the time of generation" after the fact).
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

# 9. TaskRecord

Tracks the lifecycle of a Celery task dispatched from an API view, so `GET /api/v1/tasks/{task_id}/` has something to read. Every async action in the app (brand generation, domain search, DNS checks, claims check, AI recommendation, simulate registration) is logged through this model.

## Fields

| Field               | Type      | Required | Description                                                        |
| -------------------- | --------- | -------: | --------------------------------------------------------------------- |
| `task_id`           | UUID      |      Yes | Primary key — this **is** the Celery task's own id (`.delay().id`), not a separately generated model id |
| `project_id`        | UUID / FK |      Yes | Parent project                                                        |
| `domain_result_id`  | UUID / FK |       No | The specific domain this task concerns (only set for domain-scoped actions, e.g. claims-check) |
| `status`            | Enum      |      Yes | Task lifecycle status                                                 |
| `result`            | JSON      |       No | Task result payload                                                    |
| `error_code`        | String    |       No | Machine-readable error code                                            |
| `error_message`     | Text      |       No | Human-readable error detail                                            |
| `created_at`        | DateTime  |      Yes | Creation time                                                          |
| `updated_at`        | DateTime  |      Yes | Last modification time                                                 |

> There is no `user` FK on `TaskRecord`. Ownership is checked via `project.user`, consistent with `brands`/`domains`/`dns`, rather than introducing a second, independently-driftable ownership pointer.

## Status

```text
PENDING
PROCESSING
SUCCESS
FAILURE
```

## Relationships

```text
LaunchProject
      │
      └── 1:N ── TaskRecord

DomainResult
      │
      └── 1:N ── TaskRecord (optional)
```

## Locking Behavior (application-level, not schema)

Two classmethods on `TaskRecord` implement concurrency control for dispatch views:

* **`has_active_task(project)`** — `True` if the project has any `TaskRecord` still `PENDING`/`PROCESSING`. Used to reject a second generate/search/check/recommend/simulate call while one is already in flight for the project, preventing wasted provider calls and write races during regenerate's delete-then-create.
* **`has_active_task_for_domain(domain_result)`** — `True` if that *specific* domain result has a `TaskRecord` still `PENDING`/`PROCESSING`. Narrower than the project-wide lock: used only for actions that don't touch shared project state (currently claims-check), so N domain cards can each dispatch a check concurrently without 409ing each other. Only trusts `TaskRecord` rows explicitly tagged via `domain_result` — project-wide actions (search, recommend) remain invisible to this check and keep serializing via `has_active_task`.

## Constraints

* `task_id` is required and is the primary key.
* `project` is required.
* `domain_result`, when set, should belong to the same project as `project` — this is an application-level assumption, not currently enforced by a `clean()` method or DB constraint.

## Delete Behavior

```text
LaunchProject
      ↓ CASCADE
TaskRecord
```

```text
DomainResult
      ↓ SET_NULL
TaskRecord.domain_result
```

Unlike `DomainCheck`/`DomainClaim`/`DomainRecommendation`, deleting a `DomainResult` does **not** block on its `TaskRecord`s — the FK is nullified instead, since a task log entry isn't "history that must be preserved" in the same sense as a check or claim result.

## Indexes

No additional composite indexes are declared beyond Django's automatic indexes on the primary key and on the `project`/`domain_result` foreign keys. Ordering defaults to `-created_at`.

---

# 10. Simulate Registration — persisted via DomainResult

**Simulate Registration** (sandbox-only call to name.com's real `Create Domain` endpoint) does **not** introduce a new model. Its outcome is persisted directly on the existing `DomainResult` row via three fields — `registered_at`, `registration_order_id`, `privacy_enabled` (§5).

This replaced an earlier design where "was this domain registered in the sandbox" and "is WHOIS privacy on" existed only as an unpersisted Celery task result / frontend `useState` — both of which reset to nothing on any page reload or route navigation, even though the sandbox registration itself was real and durable on name.com's side. The three `DomainResult` fields fix that: the frontend and the launch report now read persisted state instead of losing it the moment the owning component unmounts.

The action is still logged through `TaskRecord` (§9) like any other Celery-backed action, so its in-flight/success/failure status can be polled — but `TaskRecord` is not where the durable "is this domain registered" fact lives; `DomainResult` is.

It still does not change `LaunchProject.status` — registering a domain in the sandbox is a demo action, not an MVP workflow milestone, and does not imply the domain has actually been registered outside the sandbox.

**Buy on name.com** is a frontend-only outbound link and has no backend data footprint at all.

---

# 11. Complete Relationship Model

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
 │                           ├── 1:N ──→ DomainClaim
 │                           │
 │                           └── 1:N ──→ TaskRecord (optional)
 │
 ├──────── 1:N ────────→ DomainCheck
 │
 ├──────── 1:N ────────→ DomainRecommendation ──→ N:1 ──→ DomainResult
 │
 └──────── 1:N ────────→ TaskRecord

BrandIdea
 │
 └──────── 1:N ────────→ DomainSearch
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

# 12. Delete Behavior

| Relationship                          | Behavior            | Reason                                |
| ---------------------------------------- | --------------------- | ------------------------------------------ |
| User → LaunchProject                   | CASCADE              | Projects belong to the user               |
| LaunchProject → BrandIdea              | CASCADE              | Ideas belong to project                    |
| LaunchProject → DomainSearch           | CASCADE              | Searches belong to project                 |
| BrandIdea → DomainSearch               | CASCADE              | Search is scoped to the brand it targeted  |
| DomainSearch → DomainResult            | CASCADE              | Results belong to search                   |
| LaunchProject → DomainCheck            | CASCADE              | Checks belong to project                   |
| DomainResult → DomainCheck             | PROTECT / RESTRICT   | Preserve check history                      |
| DomainResult → DomainClaim             | PROTECT              | Preserve claims-check history               |
| LaunchProject → DomainRecommendation   | CASCADE              | Recommendations belong to project           |
| DomainResult → DomainRecommendation    | PROTECT              | Preserve the domain a pick pointed to       |
| LaunchProject → TaskRecord             | CASCADE              | Task log belongs to project                  |
| DomainResult → TaskRecord              | SET_NULL             | Task log entry outlives the domain result; nullify rather than block |
| LaunchProject → selected_brand         | SET_NULL             | Losing the referenced brand shouldn't delete the project |
| LaunchProject → selected_domain        | SET_NULL             | Losing the referenced domain shouldn't delete the project |

---

# 13. Database Constraints

Required fields:

```text
User.username
User.email

LaunchProject.user
LaunchProject.name
LaunchProject.business_description

BrandIdea.project
BrandIdea.name
BrandIdea.description

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

TaskRecord.task_id
TaskRecord.project
TaskRecord.status
```

## Uniqueness

Globally:

```text
User.username
User.email
```

Within a project:

```text
(project, LOWER(brand_name))
```

At most one selected brand per project:

```text
UniqueConstraint(project, condition=is_selected=True)
```

Within a search:

```text
(search, domain)
```

---

# 14. Ownership Integrity

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

```text
TaskRecord.project
        =
TaskRecord.domain_result.project   (when domain_result is set)
```

> Unlike the others, this last rule is currently an application-level convention only — there is no `clean()` check enforcing it on `TaskRecord`. Worth flagging as a gap if strict ownership auditing matters here.

This prevents cross-project data access. For example, a user must never be able to manipulate another user's domain by changing an ID in an API request.

---

# 15. Index Strategy

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

TaskRecord.project_id
TaskRecord.domain_result_id
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

These support the primary API queries efficiently. `TaskRecord` has no additional composite index beyond its automatic FK indexes — task lookups are by `task_id` (PK) or by scanning a project's/domain's in-flight tasks via `has_active_task`.

---

# 16. Data Freshness

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

# 17. Source of Truth

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

# 18. API Data Flow

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
Celery Task  ──→ TaskRecord created (PENDING)
  ↓
Redis
  ↓
Celery Worker  ──→ TaskRecord updated (PROCESSING → SUCCESS/FAILURE)
  ↓
External API
  ↓
PostgreSQL
  ↓
React polls GET /api/v1/tasks/{task_id}/
```

The database model therefore remains independent of the React frontend.

---

# 19. MVP Data Flow

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
Simulate Registration (sandbox only — persisted on DomainResult.registered_at/registration_order_id/privacy_enabled, logged via TaskRecord)
```

Every async step above ( Gemini generation, domain search, DNS checks, claims check, AI recommendation, simulate registration) dispatches through a `TaskRecord`, which the frontend polls for status.

The data model now covers **nine core entities**: `User`, `LaunchProject`, `BrandIdea`, `DomainSearch`, `DomainResult`, `DomainCheck`, `DomainClaim`, `DomainRecommendation`, and `TaskRecord`.

The MVP still does not introduce separate models for payments, teams, websites, email hosting, social media accounts, or full (non-sandbox) domain registration.