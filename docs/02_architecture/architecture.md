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
- **Gemini 3.5 Flash-Lite** for AI-powered brand generation
- **name.com API** for domain availability and DNS operations
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
                │                  │       │ Domain + DNS    │
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
| `domains`  | Domain searches and availability    | `DomainSearch`, `DomainResult` |
| `dns`      | DNS configuration and verification  | `DomainCheck`                  |
| `core`     | Shared utilities and infrastructure | Shared/base models             |

The apps represent business domains rather than technical layers.

> **Note on URL structure:** although `domains` and `dns` are separate Django apps, the public API groups their endpoints under a shared `/api/v1/domains/{id}/...` URL prefix (see api-contract.md sections 19–21: `configure-dns/`, `check/`, `checks/`) rather than giving `dns` its own `/api/v1/dns/...` prefix. This is a deliberate client-facing choice — from the frontend's perspective, a domain's DNS state is part of that domain resource — and does not change the app boundary: the `dns` app's views are simply registered under the shared `domains/{id}/` URL path in `config/api_router.py`.

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
* Displaying domain availability
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
* Domain availability indicators
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
       │
       └── DomainCheck
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
* Timestamp

### DomainCheck

Represents a domain/DNS readiness check.

Stores:

* Domain
* Check type
* Status
* Result
* Timestamp

---

# 8. Service Layer

Business logic will be implemented through application services.

| Service                     | Responsibility            | External Dependency |
| ---------------------------- | -------------------------- | -------------------- |
| `BrandGenerationService`    | Generate brand names      | Gemini               |
| `DomainCandidateService`    | Create domain candidates  | Internal             |
| `DomainAvailabilityService` | Check domain availability | name.com             |
| `DomainSelectionService`    | Select a domain           | Internal             |
| `DNSConfigurationService`   | Configure DNS             | name.com             |
| `DNSVerificationService`    | Verify DNS state          | DNS / name.com       |
| `LaunchReadinessService`    | Calculate launch status   | Internal             |

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

Gemini is responsible primarily for:

* Understanding the business description
* Generating brand names
* Explaining why names fit
* Producing structured brand suggestions

Architecture:

```text
BrandGenerationService
        ↓
GeminiClient
        ↓
Gemini 3.5 Flash-Lite
        ↓
Structured AI Response
        ↓
Validation
        ↓
BrandIdea
```

The AI client is isolated from business logic:

```text
integrations/
└── gemini/
    └── client.py
```

The API key is stored as an environment variable and never committed to source control.

AI output must be validated before it is stored.

AI is responsible for **creative generation and reasoning**.

It is not responsible for determining real domain availability.

---

# 10. name.com Integration

The **name.com API is a core product dependency**.

The integration must be functionally central to the application.

Primary responsibilities:

* Domain availability checks
* Domain information
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

| Task                    | Purpose                          |
| ------------------------ | ---------------------------------- |
| `generate_brand_ideas`  | Generate AI brand suggestions    |
| `check_domains`         | Check multiple domains           |
| `configure_dns`         | Configure DNS records            |
| `verify_dns`            | Verify DNS readiness             |
| `refresh_domain_status` | Refresh stale domain information |

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

Availability results should have a short TTL because domain availability can change.

### AI Generation

Identical generation requests may optionally be cached using a request hash.

```text
brand:generation:{request_hash}
```

### Temporary Job State

Redis may also store short-lived background-job information.

PostgreSQL remains the source of truth for persistent application data.

---

# 14. Database

PostgreSQL is the primary database.

It stores:

* Users
* Launch projects
* Brand ideas
* Domain searches
* Domain results
* Selected domains
* DNS checks
* Launch readiness state

The database preserves workflow state even when external APIs are temporarily unavailable.

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
BrandGenerationService
   ↓
Gemini 3.5 Flash-Lite
   ↓
Brand Ideas
   ↓
DomainCandidateService
   ↓
Domain Candidates
   ↓
DomainAvailabilityService
   ↓
name.com API
   ↓
Real-Time Availability
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
| AI Provider       | Gemini 3.5 Flash-Lite | Brand generation                |
| Domain Provider   | name.com API          | Domain and DNS operations       |
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

The Gemini and name.com credentials must remain server-side and must never be sent to React.

---

# 20. Testing Architecture

Testing will be divided into several levels.

### Unit Tests

Test:

* Application services
* Business rules
* Domain validation
* Launch readiness logic
* AI response validation

### API Tests

Test:

* Authentication
* Request validation
* Response schemas
* HTTP status codes
* Permissions
* Complete API workflows

### Integration Tests

Test:

* Gemini client
* name.com client
* Database interactions
* Celery tasks

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
```

The final hackathon demonstration should use real external integrations.

---

# 21. Architectural Decisions

| Decision         | Choice                | Reason                                  |
| ------------------ | ---------------------- | ------------------------------------------ |
| Backend          | Django                | Strong Python backend foundation        |
| Project Template | Cookiecutter Django   | Production-oriented starting structure  |
| API              | Django REST Framework | API-first backend boundary              |
| Frontend         | React                 | Natural client for REST API             |
| CSS              | Tailwind CSS          | Rapid polished UI development           |
| Architecture     | Modular monolith      | Simple and maintainable                 |
| AI               | Gemini 3.5 Flash-Lite | Fast, cost-efficient AI generation      |
| Domain API       | name.com              | Core hackathon integration              |
| Database         | PostgreSQL            | Reliable relational persistence         |
| Background Jobs  | Celery                | Handles slow external operations        |
| Cache/Broker     | Redis                 | Caching + Celery messaging              |
| Deployment       | Oracle Cloud Compute  | Cloud-hosted deployment                 |
| Containers       | Docker                | Reproducible deployment                 |
| Web Server       | Gunicorn + Nginx      | Production-style serving                |
| Authentication   | JWT                   | Appropriate for separate React frontend |
| Microservices    | Not used              | Unnecessary complexity for MVP          |

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
      │ Flash-Lite    │             │ API           │
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

**React + Tailwind → Django REST API → Application Services → PostgreSQL / Redis / Celery → Gemini + name.com → Oracle Cloud Compute.**