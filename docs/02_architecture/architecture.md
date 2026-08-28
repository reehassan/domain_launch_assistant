# Architecture

## 1. Architecture Overview

Domain Launch Assistant is a **modular Django monolith with an API-first architecture** that combines AI-powered brand generation, real-time domain availability, and DNS configuration into one workflow.

The system uses:

- **Django + Django REST Framework** for the backend API
- **Cookiecutter Django** as the project foundation
- **React** for the frontend
- **Tailwind CSS** for styling
- **PostgreSQL** for persistent data
- **Redis** for caching and Celery messaging
- **Celery** for background jobs
- **Gemini 3.5 Flash-Lite** for AI-powered brand generation and domain recommendation
- **name.com API** for domain availability, pricing, trademark claims, DNS operations, and sandbox registration
- **Oracle Cloud Compute** for deployment
- **Docker** for application packaging

The backend is **API-only**. Django does not render the product's frontend pages.

The frontend communicates with Django exclusively through the REST API.

The architecture deliberately avoids microservices. A modular monolith provides clear application boundaries while remaining realistic and achievable within the hackathon timeframe.

```text
                         ┌─────────────────────────┐
                         │        Browser          │
                         │    React + Tailwind     │
                         └────────────┬────────────┘
                                      │
                              HTTPS / JSON
                                      │
                                      ↓
                         ┌─────────────────────────┐
                         │         Django          │
                         │   Django REST Framework │
                         │                         │
                         │      API Layer          │
                         └────────────┬────────────┘
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                         ↓                         ↓
                ┌─────────────────┐       ┌─────────────────┐
                │ Application     │       │ Application     │
                │ Services        │       │ Services        │
                └────────┬────────┘       └────────┬────────┘
                         │                         │
                         ↓                         ↓
                ┌─────────────────┐       ┌─────────────────┐
                │ Gemini 3.5       │       │    name.com     │
                │ Flash-Lite       │       │      API        │
                │                  │       │ Domain + DNS +  │
                │                  │       │ Pricing/Claims/ │
                │                  │       │ Sandbox Reg.    │
                └─────────────────┘       └────────┬────────┘
                                                   │
                                                   ↓
                                                  DNS

                         ┌─────────────────────────┐
                         │       PostgreSQL        │
                         │    Persistent Data      │
                         └─────────────────────────┘

                         ┌─────────────────────────┐
                         │          Redis          │
                         │   Cache + Celery Broker  │
                         └────────────┬────────────┘
                                      │
                                      ↓
                         ┌─────────────────────────┐
                         │      Celery Worker      │
                         │    Background Jobs      │
                         └─────────────────────────┘
```

---

# 2. Architecture Style

The project follows a:

> **Modular monolith + API-first + service layer architecture**

The main request flow is:

```text
React
   ↓
Django REST API
   ↓
Application Services
   ↓
Domain Models
   ↓
PostgreSQL
```

External operations follow:

```text
Application Service
        ↓
Integration Client
        ↓
External API
```

Background operations follow:

```text
Django REST API
        ↓
Celery Task
        ↓
Redis
        ↓
Celery Worker
        ↓
Application Service
        ↓
External API
        ↓
PostgreSQL
```

This gives the application clear boundaries without introducing unnecessary distributed-system complexity.

---

# 3. Project Foundation

The Django project will be generated using **Cookiecutter Django**.

Cookiecutter Django provides the initial production-oriented project structure and configuration.

The project will then be extended with domain-specific Django apps and services.

High-level structure:

```text
domain-launch-assistant/
│
├── config/
│   ├── settings/
│   ├── urls.py
│   ├── celery_app.py
│   └── wsgi.py
│
├── domain_launch_assistant/
│   ├── accounts/
│   ├── launches/
│   ├── brands/
│   ├── domains/
│   ├── dns/
│   └── core/
│       └── integrations/
│           └── gemini/
│               └── client.py
│
├── tests/
│
├── docker/
│
├── manage.py
└── pyproject.toml
```

The frontend is maintained separately from Django:

```text
domain-launch-assistant/
│
├── backend/
│   └── Django project
│
└── frontend/
    ├── React
    ├── Tailwind CSS
    └── package.json
```

The exact repository structure may vary depending on implementation decisions, but the separation between frontend and API backend remains intentional.

---

# 4. Django Apps

The backend is divided into focused Django apps.

| Django App | Responsibility                      | Main Models                    |
| ---------- | ------------------------------------ | -------------------------------- |
| `accounts` | Authentication operations only: register, login, logout, token refresh, current-user endpoint | — |
| `users`    | User identity and profile data       | `User`                          |
| `launches` | Core launch-project workflow        | `LaunchProject`                |
| `brands`   | AI-generated brand ideas            | `BrandIdea`                    |
| `domains`  | Domain searches, availability, pricing, AI recommendation, trademark claims, and sandbox registration simulation | `DomainSearch`, `DomainResult`, `DomainRecommendation`, `DomainClaim` |
| `dns`      | DNS configuration and verification  | `DomainCheck`                  |
| `core`     | Shared utilities and infrastructure, including the shared `GeminiClient` | Shared/base models             |

The apps represent business domains rather than technical layers.

> **Note on URL structure:** although `domains` and `dns` are separate Django apps, the public API groups their endpoints under a shared `/api/v1/domains/{id}/...` URL prefix (see api-contract.md: `configure-dns/`, `check/`, `checks/`, `simulate-registration/`) rather than giving `dns` its own `/api/v1/dns/...` prefix. This is a deliberate client-facing choice — from the frontend's perspective, a domain's DNS state and registration actions are part of that domain resource — and does not change the app boundary: the `dns` app's views are simply registered under the shared `domains/{id}/` URL path in `config/api_router.py`. `simulate-registration/` is registered the same way, but its view lives in `domains`.

> **Note on `GeminiClient` ownership:** `GeminiClient` originally lived under `brands/clients/gemini.py`, owned by the `brands` app. Once `DomainRecommendationService` (in the `domains` app) also needed Gemini access, that ownership stopped being accurate — `core` already exists specifically to hold "shared utilities and infrastructure" (this section), so `GeminiClient` moves to `core/integrations/gemini/client.py`. Both `brands` and `domains` import it from there. This is decided now, before `DomainRecommendationService` is implemented, rather than having `domains` reach across into `brands` and needing to migrate the import later.

---

# 5. Frontend Architecture

The frontend uses:

* **React**
* **Tailwind CSS**
* REST/JSON communication with Django

Django does not render the application's frontend pages.

```text
Browser
   │
   ↓
React
   │
   │ HTTPS / JSON
   ↓
Django REST API
```

React is responsible for:

* User interface
* Form handling
* Client-side state
* Loading states
* Error states
* Displaying generated brands
* Displaying domain availability, live pricing, and premium status
* Regenerate Brands / Regenerate Domains actions (calling the existing generate/search endpoints again)
* Displaying the AI domain recommendation and reasoning
* Displaying trademark claims results
* Sandbox "Simulate Registration" demo action
* Outbound "Buy on name.com" link
* DNS configuration UI
* Launch-readiness dashboard

Example workflow:

```text
User clicks "Generate Names"
          ↓
React sends POST request
          ↓
Django REST API
          ↓
Application Service
          ↓
Gemini
          ↓
JSON response
          ↓
React updates UI
```

Tailwind CSS provides the styling system.

The interface should prioritize:

* Clear workflow states
* Strong visual hierarchy
* Domain availability indicators, including live pricing and premium flags
* Launch-readiness checklist
* Responsive layout
* Fast feedback during API operations

---

# 6. API Architecture

Django REST Framework is the primary interface between the frontend and backend.

```text
React
   │
   │ REST / JSON
   ↓
Django REST Framework
   ↓
Application Services
   ↓
Models / External Integrations
```

The backend is **API-only**.

There is no parallel:

```text
HTMX → Django HTML endpoints
```

architecture.

The API is also independently usable by:

* React
* Automated tests
* Future mobile applications
* Third-party clients
* Hackathon API demonstrations

This makes the API a first-class product boundary rather than an internal implementation detail.

---

# 7. Core Domain Model

The central entity is `LaunchProject`.

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

### User

Represents the founder using the application.

### LaunchProject

Represents one business launch.

Stores:

* Business description
* Current workflow status
* Selected brand
* Selected domain
* Launch readiness
* Owner

### BrandIdea

Represents an AI-generated brand name.

Stores:

* Name
* Explanation
* Generation metadata
* Project

### DomainSearch

Represents a domain availability search.

Stores:

* Project
* Search status
* Requested domains
* Timestamp

### DomainResult

Represents an individual domain result.

Stores:

* Domain name
* Extension
* Availability
* Provider response metadata
* Discovery pricing (`purchase_price`, `renewal_price`, `premium`, `purchase_type`)
* Timestamp

### DomainCheck

Represents a domain/DNS readiness check.

Stores:

* Domain
* Check type
* Status
* Result
* Timestamp

### DomainClaim

Represents one on-demand Trademark Clearinghouse (TMCH) claims check for a domain result.

Stores:

* Domain result
* Whether claims matched
* Raw claim data
* Timestamp

### DomainRecommendation

Represents one AI-generated pick of the best available domain result, with reasoning.

Stores:

* Project
* Recommended domain result
* Reasoning
* Timestamp

---

# 8. Service Layer

Business logic will be implemented through application services.

| Service                               | Responsibility                                              | External Dependency |
| --------------------------------------- | -------------------------------------------------------------- | ---------------------- |
| `BrandGenerationService`              | Generate brand names (also powers Regenerate Brands)         | Gemini                |
| `DomainCandidateService`              | Create domain candidates                                     | Internal               |
| `DomainAvailabilityService`           | Check domain availability (also powers Regenerate Domains), and captures discovery pricing (`purchasePrice`, `renewalPrice`, `premium`) already present in the provider response | name.com |
| `DomainRecommendationService`         | Pick + explain the best available domain                      | Gemini                |
| `DomainClaimsService`                 | Trademark claims check                                        | name.com               |
| `DomainSelectionService`              | Select a domain                                               | Internal               |
| `DomainRegistrationSimulationService` | Sandbox-only registration demo                                 | name.com (sandbox)     |
| `DNSConfigurationService`             | Configure DNS                                                  | name.com               |
| `DNSVerificationService`              | Verify DNS state                                                | DNS / name.com         |
| `LaunchReadinessService`              | Calculate launch status                                         | Internal               |

There is no separate service for "Regenerate Brands"/"Regenerate Domains" or "Buy on name.com" — the former two simply re-invoke `BrandGenerationService`/`DomainAvailabilityService` through their existing endpoints, and the latter is a frontend-only outbound link with no service involved.

API views should remain thin.

Example:

```text
DRF View
    ↓
Validate request
    ↓
Application Service
    ↓
Business operation
    ↓
Serializer
    ↓
JSON Response
```

The view should not contain:

* Provider-specific API calls
* Complex business rules
* AI prompt logic
* DNS logic

---

# 9. AI Integration

The AI provider is **Gemini 3.5 Flash-Lite**.

Gemini is responsible for:

* Understanding the business description
* Generating brand names
* Explaining why names fit
* Producing structured brand suggestions
* Ranking available domain results and producing a short natural-language justification for one recommended pick (`DomainRecommendationService`)

Architecture:

```text
BrandGenerationService              DomainRecommendationService
        ↓                                       ↓
        └───────────────→ GeminiClient ←────────┘
                                ↓
                    Gemini 3.5 Flash-Lite
                                ↓
                    Structured AI Response
                                ↓
                          Validation
                          ↙          ↘
                  BrandIdea     DomainRecommendation
```

The AI client is isolated from business logic and lives in `core`, shared by both `brands` and `domains`:

```text
core/
└── integrations/
    └── gemini/
        └── client.py
```

The API key is stored as an environment variable and never committed to source control.

AI output must be validated before it is stored. Same validation discipline applies to `DomainRecommendationService`: AI output must be schema-validated before being persisted as a `DomainRecommendation`.

AI is responsible for **creative generation and reasoning**.

It is not responsible for determining real domain availability, pricing, or trademark status.

---

# 10. name.com Integration

The **name.com API is a core product dependency**.

The integration must be functionally central to the application.

Primary responsibilities:

* Domain availability checks
* Domain information
* Discovery pricing (already part of the availability response, now surfaced to the frontend)
* Trademark Clearinghouse claims check
* Sandbox-only registration simulation (**never production** — see section 19)
* DNS operations
* DNS record configuration where supported
* Domain/DNS status

Architecture:

```text
DomainAvailabilityService
        ↓
NameComClient
        ↓
name.com API

DomainClaimsService
        ↓
NameComClient
        ↓
name.com API

DomainRegistrationSimulationService
        ↓
NameComClient (constructed from NAMECOM_TEST_* settings — a separate instance)
        ↓
name.com API (sandbox base URL only)
```

DNS:

```text
DNSConfigurationService
        ↓
NameComDNSClient
        ↓
name.com DNS API
        ↓
DNS
```

All name.com communication must go through dedicated integration clients.

The rest of the application should not depend directly on name.com's HTTP implementation.

`DomainAvailabilityService` and `DomainClaimsService` share the production `NameComClient` instance. `DomainRegistrationSimulationService` must never reuse that instance — see section 19 for why this is a hard requirement rather than a style preference.

---

# 11. Authentication

The application will use authentication suitable for a separate React frontend and REST API backend.

The MVP will use **JWT authentication**.

```text
React
   ↓
Login
   ↓
Django REST API
   ↓
JWT
   ↓
Authenticated API Requests
```

The API will use:

```text
Authorization: Bearer <access_token>
```

Every `LaunchProject` belongs to a user.

Authorization must ensure that users can only access their own:

* Launch projects
* Brand ideas
* Domain searches
* Domain results
* Domain claims checks
* Domain recommendations
* DNS checks

Object ownership must always be checked server-side.

JWT authentication is used because the frontend is a separate React client rather than Django-rendered HTML.

---

# 12. Background Jobs

Celery will handle operations that are slow or depend on external APIs.

Redis will act as the Celery broker.

```text
Django REST API
       ↓
Celery Task
       ↓
Redis
       ↓
Celery Worker
       ↓
Application Service
       ↓
External API
       ↓
PostgreSQL
```

Potential tasks:

| Task                     | Purpose                                    |
| -------------------------- | --------------------------------------------- |
| `generate_brand_ideas`   | Generate AI brand suggestions (also used by Regenerate Brands) |
| `check_domains`          | Check multiple domains (also used by Regenerate Domains) |
| `recommend_domain`       | AI pick + reasoning over available results  |
| `check_domain_claims`    | Trademark claims check                       |
| `configure_dns`          | Configure DNS records                        |
| `verify_dns`             | Verify DNS readiness                         |
| `refresh_domain_status`  | Refresh stale domain information             |
| `simulate_registration`  | Sandbox-only Create Domain call              |

The React frontend can poll a status endpoint while background jobs are running.

Example:

```text
User starts domain search
        ↓
Celery task created
        ↓
API returns job/status information
        ↓
React displays "Checking..."
        ↓
React polls status endpoint
        ↓
Task completes
        ↓
React requests results
        ↓
Results displayed
```

---

# 13. Caching

Redis will be used for caching as well as Celery messaging.

Potential cached information includes:

### Domain Availability

```text
domain:availability:{domain}
```

Availability results should have a short TTL because domain availability (and pricing) can change.

### AI Generation

Identical generation requests may optionally be cached using a request hash.

```text
brand:generation:{request_hash}
```

### Temporary Job State

Redis may also store short-lived background-job information, including for `recommend_domain`, `check_domain_claims`, and `simulate_registration`.

PostgreSQL remains the source of truth for persistent application data.

---

# 14. Database

PostgreSQL is the primary database.

It stores:

* Users
* Launch projects
* Brand ideas
* Domain searches
* Domain results, including discovery pricing
* Selected domains
* Trademark claims history
* AI domain recommendations
* DNS checks
* Launch readiness state

The database preserves workflow state even when external APIs are temporarily unavailable.

Sandbox registration simulations are **not** persisted as a distinct model — they are demo actions logged only through the existing task/`TaskRecord` mechanism (see data-model.md section 9), since they don't represent a real, durable "domain registered" fact.

---

# 15. Main Product Flow

The complete system flow is:

```text
Founder
   ↓
React Frontend
   ↓
Django REST API
   ↓
Create LaunchProject
   ↓
BrandGenerationService  ←── Regenerate Brands re-calls this
   ↓
Gemini 3.5 Flash-Lite
   ↓
Brand Ideas
   ↓
DomainCandidateService
   ↓
Domain Candidates
   ↓
DomainAvailabilityService  ←── Regenerate Domains re-calls this
   ↓
name.com API
   ↓
Real-Time Availability + Pricing
   │
   ├── DomainRecommendationService → Gemini → DomainRecommendation
   ├── DomainClaimsService → name.com → DomainClaim
   ↓
Founder Selects Domain
   ↓
DNSConfigurationService
   ↓
name.com DNS API
   ↓
DNSVerificationService
   ↓
LaunchReadinessService
   ↓
LAUNCH READY
   │
   ├── DomainRegistrationSimulationService → name.com (sandbox only)
   └── "Buy on name.com" → outbound link (frontend-only)
```

---

# 16. Failure Handling

External APIs can fail, timeout, or return unexpected responses.

The application must:

* Set request timeouts
* Validate external responses
* Handle provider errors gracefully
* Retry safe background operations
* Record failed operations
* Avoid exposing raw provider errors
* Clearly communicate temporary failures
* Never treat an API failure as a domain being unavailable

Example:

```text
name.com request
      ↓
API timeout
      ↓
Domain status = CHECK_FAILED
      ↓
API response:
{
    "status": "check_failed",
    "message": "Unable to check domain availability."
}
      ↓
React displays retry option
```

It must never become:

```text
API timeout
      ↓
Domain = Taken
```

This applies equally to the new `DomainClaimsService` and `DomainRegistrationSimulationService` calls — a name.com timeout on a claims check or a sandbox registration attempt must surface as `EXTERNAL_API_TIMEOUT`/`EXTERNAL_API_ERROR`, never as a false negative/positive result.

---

# 17. Deployment Architecture

The application will be deployed on **Oracle Cloud Compute**.

Docker containers will provide reproducible application environments.

| Component         | Technology            | Responsibility                  |
| ------------------ | ---------------------- | ---------------------------------- |
| Compute           | Oracle Cloud Compute  | Runs application infrastructure |
| Reverse Proxy     | Nginx                 | HTTPS termination and routing   |
| Backend           | Gunicorn + Django     | Runs REST API                   |
| Frontend          | React + Tailwind      | User interface                  |
| Worker            | Celery                | Background processing           |
| Database          | PostgreSQL            | Persistent data                 |
| Cache/Broker      | Redis                 | Caching and Celery messaging    |
| AI Provider       | Gemini 3.5 Flash-Lite | Brand generation, domain recommendation |
| Domain Provider   | name.com API          | Domain, pricing, claims, DNS, and sandbox registration operations |
| Container Runtime | Docker                | Application packaging           |
| TLS               | Let's Encrypt / Nginx | HTTPS                           |
| Source Control    | Git                   | Version control                 |

Deployment topology:

```text
                         Internet
                            │
                            ↓
                    ┌───────────────┐
                    │     Nginx     │
                    │ HTTPS / TLS   │
                    └───────┬───────┘
                            │
                 ┌──────────┴──────────┐
                 │                     │
                 ↓                     ↓
        ┌─────────────────┐   ┌─────────────────┐
        │ React Frontend  │   │ Django REST API │
        │ + Tailwind      │   │ + Gunicorn      │
        └─────────────────┘   └────────┬────────┘
                                       │
                         ┌─────────────┼─────────────┐
                         ↓             ↓             ↓
                    PostgreSQL       Redis      Celery Worker
                                                    │
                                         ┌──────────┴──────────┐
                                         ↓                     ↓
                                      Gemini                name.com
                                                          (production +
                                                          sandbox base URLs)
```

---

# 18. Oracle Cloud Deployment

The MVP will run on a single Oracle Cloud Compute instance to keep deployment simple.

Docker Compose will manage the infrastructure:

```text
docker-compose.yml

services:
    frontend
    api
    worker
    postgres
    redis
    nginx
```

Conceptually:

```text
Oracle Cloud Compute Instance
│
├── Nginx
│
├── React Frontend
│
├── Django / Gunicorn
│
├── Celery Worker
│
├── PostgreSQL
│
└── Redis
```

For the hackathon, a single compute instance is sufficient.

The architecture can later be separated into managed database, managed Redis, and multiple compute instances if production scale requires it.

---

# 19. Security

Secrets are provided through environment variables.

Required secrets include:

```text
DJANGO_SECRET_KEY
DATABASE_URL
REDIS_URL
GEMINI_API_KEY
NAMECOM_API_USERNAME
NAMECOM_API_TOKEN
JWT_SIGNING_KEY
```

Simulate Registration requires its own, separate sandbox credentials — distinct from the production credentials above — so that a "sandbox" call can never accidentally be wired to the live client:

```text
NAMECOM_TEST_USERNAME
NAMECOM_TEST_API_TOKEN
NAMECOM_TEST_BASE_URL   # must resolve to api.dev.name.com
```

`DomainRegistrationSimulationService` must construct its own `NameComClient` instance from the `NAMECOM_TEST_*` settings — it must never reuse the production client instance used by `DomainAvailabilityService` or `DomainClaimsService`. This is the actual safety mechanism, not just a naming convention: a shared client instance is exactly how a "sandbox" call ends up hitting production. The client must also refuse to run if `NAMECOM_TEST_BASE_URL` resolves to a non-sandbox host.

Secrets must:

* Never be committed to Git
* Never be hard-coded
* Never be returned in API responses
* Be provided through the deployment environment

The Oracle Cloud instance should expose only required public ports.

Recommended public access:

```text
80   HTTP
443  HTTPS
```

Database, Redis, and internal application ports must not be publicly exposed.

The Gemini and name.com credentials (both production and sandbox) must remain server-side and must never be sent to React.

---

# 20. Testing Architecture

Testing will be divided into several levels.

### Unit Tests

Test:

* Application services
* Business rules
* Domain validation
* Launch readiness logic
* AI response validation, including `DomainRecommendationService` schema validation
* `DomainRegistrationSimulationService` refuses to run against a non-sandbox base URL

### API Tests

Test:

* Authentication
* Request validation
* Response schemas
* HTTP status codes
* Permissions
* Complete API workflows
* `recommend-domain/`, `check-claims/`, and `simulate-registration/` endpoints

### Integration Tests

Test:

* Gemini client (shared from `core`)
* name.com client — both the production client and the sandbox-only client used for registration simulation
* Database interactions
* Celery tasks, including `recommend_domain`, `check_domain_claims`, and `simulate_registration`

External APIs should normally be mocked in automated tests.

### End-to-End Tests

The complete workflow should be tested as:

```text
Login
    ↓
Create project
    ↓
Generate names
    ↓
Check domains
    ↓
Select domain
    ↓
Configure DNS
    ↓
Verify readiness
    ↓
Simulate registration (sandbox)
```

The final hackathon demonstration should use real external integrations.

---

# 21. Architectural Decisions

| Decision              | Choice                          | Reason                                        |
| ----------------------- | ---------------------------------- | -------------------------------------------------- |
| Backend               | Django                            | Strong Python backend foundation                 |
| Project Template      | Cookiecutter Django               | Production-oriented starting structure           |
| API                   | Django REST Framework             | API-first backend boundary                        |
| Frontend              | React                              | Natural client for REST API                       |
| CSS                   | Tailwind CSS                       | Rapid polished UI development                     |
| Architecture          | Modular monolith                   | Simple and maintainable                            |
| AI                    | Gemini 3.5 Flash-Lite               | Fast, cost-efficient AI generation and ranking    |
| `GeminiClient` location | `core`, shared by `brands` and `domains` | `core` already owns shared infrastructure; avoids `domains` reaching into `brands` |
| Domain API            | name.com                           | Core hackathon integration                        |
| Sandbox registration   | Separate `NameComClient` from `NAMECOM_TEST_*` settings | Guarantees a "demo" action can never hit production |
| Database              | PostgreSQL                         | Reliable relational persistence                    |
| Background Jobs       | Celery                              | Handles slow external operations                   |
| Cache/Broker          | Redis                               | Caching + Celery messaging                          |
| Deployment            | Oracle Cloud Compute                | Cloud-hosted deployment                             |
| Containers            | Docker                              | Reproducible deployment                             |
| Web Server            | Gunicorn + Nginx                    | Production-style serving                            |
| Authentication        | JWT                                 | Appropriate for separate React frontend            |
| Microservices         | Not used                            | Unnecessary complexity for MVP                      |

---

# 22. Final Architecture

The final architecture is intentionally simple while maintaining a clear API boundary.

```text
                         FOUNDER
                            │
                            ↓
                 ┌────────────────────┐
                 │      Browser       │
                 │ React + Tailwind   │
                 └─────────┬──────────┘
                           │
                       HTTPS / JSON
                           │
                           ↓
                 ┌────────────────────┐
                 │      Django       │
                 │       DRF         │
                 │    REST API       │
                 └─────────┬──────────┘
                           │
                           ↓
                 ┌────────────────────┐
                 │ Application        │
                 │ Services            │
                 └──────┬──────┬──────┘
                        │      │
             ┌──────────┘      └───────────┐
             ↓                             ↓
      ┌───────────────┐             ┌───────────────┐
      │ Gemini 3.5    │             │ name.com      │
      │ Flash-Lite    │             │ API (prod +   │
      │ (via core)    │             │ sandbox)      │
      └───────────────┘             └───────┬───────┘
                                            │
                                            ↓
                                           DNS

                    ┌─────────────────────────┐
                    │       PostgreSQL        │
                    │    Persistent Data      │
                    └─────────────────────────┘

                    ┌─────────────────────────┐
                    │          Redis          │
                    │   Cache + Celery Broker  │
                    └────────────┬────────────┘
                                 │
                                 ↓
                    ┌─────────────────────────┐
                    │      Celery Worker      │
                    │    Background Jobs      │
                    └─────────────────────────┘

                         ALL DEPLOYED ON
                    ORACLE CLOUD COMPUTE
```

The architectural goal is:

> **Keep the system simple enough to finish, but structured enough to demonstrate real production-oriented Django, API, cloud, AI, and external API engineering.**

The core technical story is:

**React + Tailwind → Django REST API → Application Services → PostgreSQL / Redis / Celery → Gemini + name.com (production and sandbox) → Oracle Cloud Compute.**