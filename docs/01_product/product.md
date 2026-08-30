# Product

## 1. Problem

Starting a business often begins with: *"What should I call it, and is the domain available?"*

Finding a name that is brandable, relevant, available as a domain, *and* ready for launch is hard — founders bounce between AI naming tools, domain registrars, and DNS dashboards for what is really one workflow.

## 2. Solution

**Domain Launch Assistant** turns a business idea into a brandable, launch-ready domain in one workflow.

A founder describes their business in natural language. The app generates brand names, checks real-time availability via the **name.com API**, surfaces live pricing and an AI-recommended pick, runs a trademark claims check, and carries the founder through DNS readiness and a sandboxed registration — end to end, without leaving the app.

```text
Business idea → AI brand names → real domain availability + pricing
   → AI recommendation + trademark check → domain selected
   → DNS readiness → sandbox registration → launch-ready
```

## 3. Target User

Early-stage founders and solo entrepreneurs turning an idea into a business — indie hackers, freelancers, small business owners, developers launching SaaS products.

They want to answer, in order: *What could I call this? Which names have good domains available? Which one should I pick? Is it actually ready to launch?*

## 4. Core Value Proposition

Connect AI-generated brand ideas to real domain data, so founders discover names that can actually become a digital identity — not just names that sound good.

## 5. Product Flow

1. **Describe the business** — natural-language input, saved as a `LaunchProject`.
2. **Generate brand ideas** — AI-generated names with a short explanation each; regenerate for a new batch.
3. **Search domains** — candidates checked against name.com for real availability, across a founder-selectable set of extensions (`.com .ai .io .net .org .co .dev .app`); regenerate for a new search.
4. **Compare and select** — results show availability, live purchase/renewal pricing, and premium status; an AI-generated recommendation highlights the strongest available pick with reasoning; each available candidate gets an automatic trademark (TMCH) claims check.
5. **Verify readiness** — DNS/domain readiness checks run against the selected domain; claims result is shown alongside.
6. **Launch** — sandbox domain registration (with WHOIS privacy toggle) against name.com's real Create Domain endpoint, followed by DNS record configuration for the now-"registered" domain; a launch report summarizes the completed journey.

The founder needs an account (register/login) to access their own projects; every project, brand, domain, check, and task belongs to exactly one user.

## 6. MVP Objective

> Founders can go from a natural-language business idea to a real, available, launch-ready domain — with pricing, an AI pick, a trademark check, and a working (sandboxed) registration — through one workflow.

### MVP includes

* Business idea input, persisted as a launch project
* AI brand generation, with regenerate
* Domain search across selectable extensions, with regenerate
* Real-time availability via name.com, with live pricing and premium flags
* AI-generated domain recommendation with reasoning
* Trademark (TMCH) claims check, run automatically per available candidate
* Domain selection
* DNS/domain readiness checks
* Sandbox registration (Create Domain) with WHOIS privacy toggle
* DNS record configuration for the sandbox-registered domain
* Launch report
* Simple JWT authentication, one user owns their own projects
* A polished end-to-end web interface (React + Tailwind)

### Success criteria

A user can: enter a business idea → get brand suggestions → see real availability and pricing → see an AI recommendation and claims result → select a domain → verify readiness → sandbox-register and configure DNS → view a launch report — as one coherent demo, with name.com doing meaningful work throughout.

### Explicitly out of scope

Full website builder or hosting · full domain registrar or real (non-sandbox, billable) registration · a general-purpose DNS management platform for domains outside this app's own sandbox-registration flow (DNS record CRUD is full-featured — arbitrary record types, full create/list/update/delete — but only ever against a domain this app itself sandbox-registered, never an arbitrary external domain) · email hosting · payments/billing beyond the sandbox checkout simulation · team/organization accounts · full brand-identity/logo platform · social-username checking · SEO tooling · production-scale infrastructure (multi-region, k8s, etc.).

**Scope rule:** if a feature doesn't move a founder from idea → brand → available domain → launch-ready domain, it doesn't belong in the MVP. Priority: end-to-end workflow > name.com integration > AI generation > availability/pricing/claims > selection/recommendation > launch/DNS readiness > sandbox registration > polish > anything else.

## 7. User Stories

**Business idea**
- US-01 Describe my business in natural language so the app understands what I'm building.
- US-02 Have my idea saved as a launch project so I can return to it later.

**Brand generation**
- US-03 Generate relevant brand names from my business idea.
- US-04 See a short explanation with each name, so I understand why it fits.
- US-05 Regenerate a fresh batch if I'm not happy with the current one.

**Domain discovery**
- US-06 Generate domain candidates for my selected brand, across extensions I choose.
- US-07 Check real-time availability so I don't pick a name with no domain.
- US-08 See a domain's status clearly — available, taken, or check failed (never confused with taken).
- US-09 See live pricing (purchase and renewal) and whether a result is premium-priced.
- US-10 Get an AI-recommended pick among available domains, with reasoning.
- US-11 See a trademark (TMCH) claims result for each available domain, without asking for it manually.
- US-12 Regenerate the domain search if none of the results work.

**Domain selection**
- US-13 Select an available domain as my project's domain.
- US-14 Change my selected domain before launch.

**Launch readiness**
- US-15 See my project's current launch status.
- US-16 Run DNS/domain readiness checks against my selected domain.
- US-17 See a clear pass/fail/error result per check, not just "done."

**Launch**
- US-18 Simulate registering my domain (sandbox) so I can see the registration step work without a real purchase.
- US-19 Toggle WHOIS privacy on my sandbox-registered domain.
- US-20 Configure DNS records for my registered domain so it can point somewhere.
- US-21 View a launch report summarizing the whole journey.

**Account**
- US-22 Register and log in so my projects are mine alone.
- US-23 Only ever see and act on my own projects, brands, and domains.

## 8. MVP User Journey

```text
US-01 Describe business → US-02 Project saved
   → US-03 Generate names (US-05 regenerate)
   → US-06 Domain candidates → US-07 Check availability (US-12 regenerate)
   → US-09 Pricing, US-10 AI recommendation, US-11 Claims check
   → US-13 Select domain
   → US-15 View status → US-16 Run readiness checks
   → US-18 Simulate registration, US-19 Privacy toggle
   → US-20 Configure DNS
   → US-21 Launch report
```

The MVP is complete when a founder can follow this journey end to end, backed by real name.com and Gemini calls throughout.