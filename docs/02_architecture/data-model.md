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
        │
        └── DomainCheck
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
                 │
                 └── 1:N ── DomainCheck
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

| Field          | Type      | Required | Description                 |
| -------------- | --------- | -------: | ------------------------------ |
| `id`           | UUID      |      Yes | Primary key                    |
| `search_id`    | UUID / FK |      Yes | Parent search                  |
| `project_id`   | UUID / FK |      Yes | Project reference               |
| `domain`       | String    |      Yes | Complete domain name            |
| `extension`    | String    |      Yes | Domain extension                |
| `available`    | Boolean   |      Yes | Whether domain is available     |
| `status`       | Enum      |      Yes | Availability state              |
| `provider`     | String    |      Yes | Provider name                   |
| `checked_at`   | DateTime  |      Yes | Availability check time         |
| `raw_metadata` | JSON      |       No | Relevant provider metadata      |
| `created_at`   | DateTime  |      Yes | Creation time                    |

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

# 7. Complete Relationship Model

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
 └──────── 1:N ────────→ DomainCheck
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

# 8. Delete Behavior

| Relationship                 | Behavior           | Reason                       |
| ------------------------------- | -------------------- | ------------------------------- |
| User → LaunchProject         | CASCADE            | Projects belong to the user  |
| LaunchProject → BrandIdea    | CASCADE            | Ideas belong to project       |
| LaunchProject → DomainSearch | CASCADE            | Searches belong to project    |
| DomainSearch → DomainResult  | CASCADE            | Results belong to search      |
| LaunchProject → DomainCheck  | CASCADE            | Checks belong to project      |
| DomainResult → DomainCheck   | PROTECT / RESTRICT | Preserve check history        |

---

# 9. Database Constraints

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

# 10. Ownership Integrity

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

This prevents cross-project data access.

For example, a user must never be able to manipulate another user's domain by changing an ID in an API request.

---

# 11. Index Strategy

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
```

## Workflow Indexes

```text
LaunchProject(user_id, status)

DomainSearch(project_id, status)

DomainResult(project_id, available)

DomainCheck(project_id, status)
```

These support the primary API queries efficiently.

---

# 12. Data Freshness

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

---

# 13. Source of Truth

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

# 14. API Data Flow

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

# 15. MVP Data Flow

```text
Business Idea
      ↓
LaunchProject
      ↓
Gemini Generation
      ↓
BrandIdea[]
      ↓
DomainSearch
      ↓
DomainResult[]
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
```

The data model is intentionally limited to these **six core entities**.

The MVP does not introduce separate models for payments, teams, websites, email hosting, social media accounts, or full domain registration.