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
````

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
  "brand_id": "uuid",
  "extensions": [
    ".com",
    ".ai",
    ".io"
  ]
}
```

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
      "brand_id": "uuid",
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
      "checked_at": "2026-08-22T14:10:04Z"
    },
    {
      "id": "uuid",
      "domain": "ledgerflow.com",
      "extension": ".com",
      "available": false,
      "status": "TAKEN",
      "provider": "name.com",
      "checked_at": "2026-08-22T14:10:04Z"
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

# 18. Select Domain

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

### Errors

```text
400 VALIDATION_ERROR

401 AUTHENTICATION_REQUIRED

403 PERMISSION_DENIED

404 NOT_FOUND

409 CONFLICT
```

---

# 19. Check Domain / DNS

```http
POST /api/v1/domains/{id}/check/
```

### Authentication

Required.

### Request

```json
{
  "check_types": [
    "DNS_CONFIGURATION",
    "DNS_RESOLUTION",
    "DOMAIN_READINESS"
  ]
}
```

### Response

```http
202 Accepted
```

```json
{
  "domain_id": "uuid",
  "status": "PENDING",
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

# 20. Get Domain Checks

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
      "check_type": "DNS_CONFIGURATION",
      "status": "PASS",
      "record_type": "A",
      "record_name": "@",
      "expected_value": "203.0.113.10",
      "actual_value": "203.0.113.10",
      "message": "DNS configuration is correct.",
      "checked_at": "2026-08-22T14:15:00Z"
    },
    {
      "id": "uuid",
      "check_type": "DNS_RESOLUTION",
      "status": "PASS",
      "record_type": "A",
      "record_name": "@",
      "expected_value": "203.0.113.10",
      "actual_value": "203.0.113.10",
      "message": "Domain resolves correctly.",
      "checked_at": "2026-08-22T14:15:01Z"
    }
  ]
}
```

---

# 21. Get Launch Report

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
      "type": "DNS_CONFIGURATION",
      "status": "PASS",
      "message": "DNS configuration is correct."
    },
    {
      "type": "DNS_RESOLUTION",
      "status": "PASS",
      "message": "Domain resolves correctly."
    },
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
      "DNS resolution has not completed."
    ]
  }
}
```

---

# 22. Background Task Status

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

# 23. Endpoint Summary

| Method | Endpoint                                 | Purpose                    | Async |
| ------ | ----------------------------------------- | --------------------------- | ----- |
| `POST` | `/api/v1/auth/register/`                 | Register user              | No    |
| `POST` | `/api/v1/auth/login/`                    | Authenticate user          | No    |
| `POST` | `/api/v1/auth/token/refresh/`            | Refresh access token       | No    |
| `POST` | `/api/v1/auth/logout/`                   | Logout                     | No    |
| `GET`  | `/api/v1/auth/me/`                       | Get current user           | No    |
| `POST` | `/api/v1/projects/`                      | Create project             | No    |
| `GET`  | `/api/v1/projects/`                      | List projects              | No    |
| `GET`  | `/api/v1/projects/{id}/`                 | Get project                | No    |
| `POST` | `/api/v1/projects/{id}/generate-brands/` | Generate AI brands         | Yes   |
| `GET`  | `/api/v1/projects/{id}/brands/`          | Get brands                 | No    |
| `POST` | `/api/v1/projects/{id}/select-brand/`    | Select brand               | No    |
| `POST` | `/api/v1/projects/{id}/domain-search/`   | Search domains             | Yes   |
| `GET`  | `/api/v1/projects/{id}/domain-searches/` | Search history             | No    |
| `GET`  | `/api/v1/projects/{id}/domains/`         | Get domain results         | No    |
| `POST` | `/api/v1/projects/{id}/select-domain/`   | Select domain              | No    |
| `POST` | `/api/v1/domains/{id}/check/`            | Check DNS/domain           | Yes   |
| `GET`  | `/api/v1/domains/{id}/checks/`           | Get domain checks          | No    |
| `GET`  | `/api/v1/projects/{id}/launch-report/`   | Get launch report          | No    |
| `GET`  | `/api/v1/tasks/{task_id}/`               | Get background task status | No    |

---

# 24. Authentication and Ownership Rules

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
```

The API must never rely on React to enforce ownership.

Authorization is always enforced by Django.

---

# 25. External API Failure Contract

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

The API must **not** expose raw provider responses or credentials.

---

# 26. AI Failure Contract

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

Invalid AI output must never be stored as a valid `BrandIdea`.

---

# 27. Important API Rules

The API must enforce the following rules:

1. Users can only access their own projects.
2. A brand must belong to the project where it is selected.
3. A domain must belong to the project where it is selected.
4. Only available domains can be selected.
5. Stale domain availability must be refreshed before selection.
6. Provider errors must not be interpreted as domain unavailability.
7. AI output must be validated before persistence.
8. Long-running external operations should run through Celery.
9. PostgreSQL remains the source of truth.
10. React must never communicate directly with Gemini or name.com.
11. Provider credentials must remain server-side.
12. All API responses must use the documented JSON contract.
13. Protected endpoints require a valid JWT access token.
14. Access tokens must not be accepted from unauthenticated requests.
15. API routes must remain versioned under `/api/v1/`.

---

# 28. Complete Application Flow

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
  │ POST /api/v1/projects/{id}/generate-brands/
  ↓
Celery
  │
  ↓
Gemini
  │
  ↓
BrandIdea[]
  │
  │ POST /api/v1/projects/{id}/domain-search/
  ↓
Celery
  │
  ↓
name.com
  │
  ↓
DomainResult[]
  │
  │ POST /api/v1/projects/{id}/select-domain/
  ↓
LaunchProject.selected_domain
  │
  │ POST /api/v1/domains/{id}/check/
  ↓
Celery
  │
  ├── name.com
  └── DNS
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
        │ GET /api/v1/projects/{id}/launch-report/
        ↓
      React
        │
        ↓
  Launch-ready UI
```

---

# 29. React Integration

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