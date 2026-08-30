# Architecture

## 1. Overview

Domain Launch Assistant is a **modular Django monolith, API-first**, combining AI brand generation, real-time domain availability, and DNS/registration operations into one workflow.

Stack:

- **Django + Django REST Framework** — API backend
- **React + Tailwind** — frontend, communicates only via REST/JSON
- **PostgreSQL** — persistent data
- **Redis** — Celery broker/result backend (see §9 — not currently used for caching, despite earlier plans)
- **Celery** — background jobs
- **Gemini** (model set via `GEMINI_MODEL` env var) — brand generation, domain recommendation
- **name.com API** — availability, pricing, trademark claims, DNS records, sandbox registration
- **Oracle Cloud Compute + Docker** — deployment


```text
Browser (React) ──HTTPS/JSON──► Django REST Framework
                                        │
                              ┌─────────┴─────────┐
                              ▼                   ▼
                      Application Services   PostgreSQL
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
                 Gemini              name.com API
                                   (prod + sandbox)

                Redis (Celery broker) ──► Celery Worker
```

---

## 2. Architecture Style

**Modular monolith, service-layer pattern.** Each Django app owns its models, views, serializers, and services; cross-app shared code (Gemini client, AI-recommendation service) lives in `core`.

```text
React → DRF View → Application Service → Models → PostgreSQL
                          │
                          ▼
                 Integration Client → External API
```

Async operations:

```text
DRF View → creates TaskRecord (PENDING) + PENDING model row(s)
    → dispatches Celery task
        → task sets TaskRecord PROCESSING
        → calls Application Service → External API → PostgreSQL
        → task sets TaskRecord SUCCESS/FAILURE
React polls GET /api/v1/tasks/{task_id}/
```

---

## 3. Django Apps

| App | Responsibility | Main Models |
|---|---|---|
| `accounts` | Register/login/logout/refresh/me | — |
| `users` | User identity | `User` |
| `launches` | Core project workflow (no separate `services/`; selection/readiness logic lives in views/serializers) | `LaunchProject` |
| `brands` | AI brand generation | `BrandIdea` |
| `domains` | Search, availability, pricing, trademark claims, sandbox registration | `DomainSearch`, `DomainResult`, `DomainClaim` |
| `dns` | DNS/domain readiness checks, DNS record CRUD (sandbox-only, see §7) | `DomainCheck` |
| `tasks` | Celery task status tracking, polled by the frontend | `TaskRecord` |
| `core` | Shared infra: `GeminiClient`, and `DomainRecommendationService` (see note) | — (model `DomainRecommendation` lives in `domains`) |

> **`DomainRecommendationService` lives in `core/services/`**, not `domains/services/`, even though its model (`DomainRecommendation`) belongs to `domains`. Same reasoning as the `GeminiClient` move: it's Gemini-dependent shared logic, and `core` already owns the client it calls.

> **`dns` endpoints share the `/api/v1/domains/{id}/...` URL prefix** with the `domains` app — a deliberate client-facing grouping, not a merged app boundary.

---

## 4. Core Domain Model

Full field-level detail lives in `data-model.md` — this is just the shape:

```text
User → LaunchProject → BrandIdea
                     → DomainSearch → DomainResult → DomainClaim
                     → DomainCheck
                     → DomainRecommendation → DomainResult
                     → TaskRecord (also FK'd from DomainResult, optional)
```

---

## 5. Service Layer

Real service classes, by module — several service names used in earlier planning docs (`DomainAvailabilityService`, `DomainCandidateService`, `DomainSelectionService`, `DNSConfigurationService`, `LaunchReadinessService`) don't exist; this table reflects the actual code:

| Service | Module | Responsibility | External Dep |
|---|---|---|---|
| `BrandGenerationService` | `brands.services.brand_generation` | Generate/regenerate brand ideas | Gemini |
| `DomainSearchService` | `domains.services.domain_search` | Orchestrates a domain search (creates pending row, runs it) | — |
| `AvailabilityService` | `domains.services.availability` | Slugify + check availability + pricing | name.com |
| `DomainClaimsService` | `domains.services.domain_claims` | TMCH trademark claims check | name.com |
| `DomainRecommendationService` | `core.services.domain_recommendation` | AI pick + reasoning over available results | Gemini |
| `DomainRegistrationSimulationService` | `domains.services.registration_simulation` | Sandbox `Create Domain` + privacy toggle | name.com (sandbox only) |
| `CheckDomainService` | `dns.services.check_domain` | DNS_RESOLUTION / DOMAIN_READINESS checks. **DNS_CONFIGURATION is explicitly unsupported** (`UNSUPPORTED_CHECK_TYPES`) | — |
| `DnsRecordsService` | `dns.services.dns_records` | DNS record list/create/update/delete. **Sandbox-only** — guarded the same way as registration simulation | name.com (sandbox only) |

Views stay thin: validate → service → serializer → response (or dispatch a Celery task for anything provider-dependent).

---

## 6. AI Integration

`GeminiClient` (`core/integrations/gemini/client.py`) is the only code that talks to Gemini; called by `BrandGenerationService` and `DomainRecommendationService`. Model name comes from `GEMINI_MODEL` (env-configured, no hardcoded default). All output is schema-validated (Pydantic) before persistence — invalid output is never stored.

```text
BrandGenerationService ─┐
DomainRecommendationService ─┴─► GeminiClient → Gemini → validated structured output
```

---

## 7. name.com Integration

`NameComClient` is a thin HTTP client (`domains/clients/namecom.py`) with retry/backoff on timeouts and 5xx only — never on 4xx. All name.com calls go through it or through `DomainClaimsService`/`AvailabilityService`/`DomainRegistrationSimulationService`/`DnsRecordsService`.

**Two separate credential sets, two separate client instances — never shared:**

| Client instance | Built by | Credentials | Base URL |
|---|---|---|---|
| Production | `AvailabilityService`, `DomainClaimsService` | `NAMECOM_USERNAME`/`NAMECOM_API_TOKEN` | `NAMECOM_BASE_URL` |
| Sandbox | `DomainRegistrationSimulationService`, `DnsRecordsService` | `NAMECOM_TEST_USERNAME`/`NAMECOM_TEST_API_TOKEN` | `NAMECOM_TEST_BASE_URL` |

Both sandbox-only services refuse to construct a client at all unless the base URL's hostname matches `NAMECOM_SANDBOX_HOST` — this guard, not naming convention, is what prevents a "sandbox" call from ever hitting production. **DNS record management is sandbox-only for the same reason registration is**: a domain in this app only exists as a real name.com object in the sandbox, so managing its DNS records against production would 404.

---

## 8. Authentication

JWT via `rest_framework_simplejwt`. Access tokens: 30 min. Refresh tokens: 7 days, rotated and blacklisted after use. Every protected view requires `IsAuthenticated` by default (`REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES`); object-level ownership (project → user) is checked in views/querysets.

---

## 9. Background Jobs & Caching

Celery, Redis as broker + result backend. Real tasks:

| Task | Module |
|---|---|
| `generate_brand_ideas_task` | `brands.tasks` |
| `check_domains_task` | `domains.tasks` |
| `check_domain_claims_task` | `domains.tasks` |
| `recommend_domain_task` | `domains.tasks` |
| `simulate_registration_task` | `domains.tasks` |
| `toggle_domain_privacy_task` | `domains.tasks` |
| `run_domain_checks_task` | `dns.tasks` |
| `create_dns_record_task` / `update_dns_record_task` / `delete_dns_record_task` | `dns.tasks` |

Every task follows the same shape: set `PROCESSING` → run service → on any failure, set `FAILURE` with a typed `error_code` (`VALIDATION_ERROR`, `EXTERNAL_API_TIMEOUT`, `EXTERNAL_API_ERROR`, `AI_GENERATION_FAILED`, `INTERNAL_ERROR`) and persist nothing else → on success, set `SUCCESS` and store the serialized result on `TaskRecord.result`.

**Caching:** `REDIS_URL` currently backs Celery only. There is no `CACHES` setting and no cache read/write in any service shown — domain-availability/generation caching described in earlier planning is not implemented. Flag this as either a TODO or remove the idea from planning docs.

---

## 10. API Architecture

DRF is API-only — no server-rendered HTML. `corsheaders` is the first middleware (`CORS_ALLOWED_ORIGINS`, since React runs on a separate origin/port in dev). Errors are normalized through a single custom `EXCEPTION_HANDLER` (`utils/exceptions.py`), which is what produces the consistent `error_code`/message shape every task and view relies on. List endpoints default to `PageNumberPagination`, page size 20.

Failure discipline (unchanged from original intent): a provider timeout or error must never be recorded as `TAKEN`, `CLAIMED`, or any other false-negative/positive result — it becomes `CHECK_FAILED` / a task `FAILURE`, always.

---

## 11. Deployment

Single Oracle Cloud Compute instance, Docker Compose: `frontend`, `api`, `worker`, `postgres`, `redis`, `nginx`. Nginx terminates TLS and routes to the React build and to Gunicorn+Django. Not currently multi-region or auto-scaled — appropriate for the hackathon scope.

---

## 12. Security

Required secrets: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `NAMECOM_USERNAME`/`NAMECOM_API_TOKEN`, plus sandbox-only `NAMECOM_TEST_USERNAME`/`NAMECOM_TEST_API_TOKEN`/`NAMECOM_TEST_BASE_URL`/`NAMECOM_SANDBOX_HOST`. None are hardcoded, returned in API responses, or shared between production/sandbox client instances (§7). Only ports 80/443 should be public; DB, Redis, and internal app ports stay private.

---

## 13. Testing

- **Unit:** services, validation logic, the sandbox-guard refusal path.
- **API:** auth, permissions, status codes, full endpoint set including recommend/claims/simulate-registration/DNS record CRUD.
- **Integration:** Gemini client, both name.com client instances (mocked), Celery tasks.
- **E2E:** login → project → generate brands → search domains → select → verify → sandbox register → configure DNS.

External APIs are mocked in automated tests; the final demo uses real integrations.

---

## 14. Architectural Decisions

| Decision | Choice | Reason |
|---|---|---|
| Architecture | Modular monolith | Simple, maintainable, no unneeded distributed complexity |
| `GeminiClient` + `DomainRecommendationService` location | `core` | Shared by `brands` and `domains`; avoids cross-app reach-in |
| Sandbox isolation | Separate `NameComClient` instance + host guard, for both registration and DNS records | A shared client instance is exactly how a "sandbox" call would hit production |
| DNS_CONFIGURATION check type | Explicitly unsupported | Not yet implemented — don't imply it works |
| Caching | Not implemented | Redis currently serves only as the Celery broker |
| Auth | JWT (rotated, blacklisted) | Separate React client, not Django-rendered HTML |

---

**Core technical story:** React + Tailwind → Django REST API (thin views) → Application Services → PostgreSQL / Redis+Celery → Gemini (validated structured output) + name.com (production for search/claims, sandbox-only for registration and DNS) → Oracle Cloud Compute.