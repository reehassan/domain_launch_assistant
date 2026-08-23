# Scope Freeze

> **What are we building and what are we NOT building?**

This document defines the boundaries of the **Domain Launch Assistant MVP**.

The goal is to build a complete, impressive end-to-end workflow for the hackathon without expanding into a full domain registrar, branding platform, or website builder.

---

# 1. MVP

The following features are **required** for the hackathon submission.

## 1.1 Business Idea Input

The user can describe their business in natural language.

Example:

> "I'm building an AI-powered accounting platform for small businesses."

The application stores this business idea as a launch project.

---

## 1.2 AI Brand Name Generation

The system uses AI to generate relevant and brandable business-name suggestions.

Each suggestion should include:

* Brand name
* Short explanation
* Relevant domain candidates

Example:

```text
LedgerFlow
"Suggests a smooth, automated financial workflow."

LedgerPilot
"Positions the product as an intelligent guide for small-business finances."
```

The MVP should generate a manageable number of suggestions rather than an unlimited list.

---

## 1.3 Domain Candidate Generation

For each selected brand idea, the application generates domain candidates using a predefined set of extensions.

Example:

```text
ledgerflow.com
ledgerflow.ai
ledgerflow.dev
```

The domain candidates must be connected to the real domain-checking workflow.

---

## 1.4 Real-Time Domain Availability

The application uses the **name.com API** to perform real availability checks.

The UI must clearly distinguish:

```text
Available
Taken
Unavailable / Error
```

The name.com integration is a **core MVP requirement**, not an optional integration.

---

## 1.5 Domain Search and Selection

The user can:

* View domain results
* Compare available candidates
* Select a preferred domain

The selected domain becomes part of the user's launch project.

---

## 1.6 Launch Project

The system maintains a simple project representing the user's launch.

A project should contain information such as:

```text
Business idea
Generated brand names
Domain candidates
Selected brand name
Selected domain
Launch status
```

This allows the application to demonstrate a complete workflow rather than isolated API calls.

---

## 1.7 Launch Readiness

After selecting a domain, the application provides a basic launch-readiness stage.

It should communicate:

```text
Domain selected       ✓
Domain available      ✓
DNS configured        ✓ / Pending
Launch status         Ready / Needs attention
```

Where practical and supported by the API, the application should perform actual DNS/domain operations.

---

## 1.8 Basic DNS Configuration

The MVP may support a focused DNS configuration flow for the selected domain.

For example:

```text
Selected domain
      ↓
Choose DNS configuration
      ↓
Create/update required DNS record
      ↓
Verify configuration
      ↓
Launch-ready
```

The MVP should support only the DNS operations necessary for the demonstrated launch scenario.

---

## 1.9 Simple Authentication

If authentication is required by the final architecture, users can have a basic account and access their own launch projects.

Authentication must remain simple.

We are **not** building a full account-management platform.

---

## 1.10 End-to-End UI

The MVP must provide a polished workflow:

```text
Idea
 ↓
AI names
 ↓
Domain availability
 ↓
Domain selection
 ↓
Launch configuration
 ↓
Launch-ready
```

The primary goal is a convincing end-to-end demonstration.

---

# 2. Nice-to-Have

These features can be implemented **only after the complete MVP works**.

They must never delay the core workflow.

## 2.1 Brandability Scoring

Give each generated name a score based on factors such as:

* Memorability
* Simplicity
* Relevance
* Pronunciation
* Domain availability

Example:

```text
LedgerFlow
Brandability: 91/100
```

---

## 2.2 AI Name Refinement

Allow the user to request changes such as:

> "Make the names shorter."

> "Give me more technical names."

> "Make them sound more premium."

The AI generates a refined batch.

---

## 2.3 Multiple Domain Extensions

Support additional extensions beyond the initial MVP set.

Examples:

```text
.com
.ai
.dev
.io
.co
```

---

## 2.4 Domain Recommendations

Instead of simply showing availability, the application can recommend the strongest option.

Example:

> **Recommended:** ledgerflow.ai

Reason:

> Short, memorable, strongly aligned with an AI product, and currently available.

---

## 2.5 DNS Verification

Automatically verify whether the configured DNS record is resolving correctly.

Example:

```text
DNS configuration       ✓
Record detected         ✓
Domain resolving        ✓
Launch readiness        ✓
```

---

## 2.6 Launch Checklist

Provide a simple checklist:

```text
✓ Brand name selected
✓ Domain selected
✓ Domain available
✓ DNS configured
○ Website connected
○ Email configured
```

---

## 2.7 Domain Search History

Allow users to revisit previous domain searches and generated names.

---

## 2.8 Domain Registration

If the API access and hackathon constraints make it practical, allow the user to proceed toward domain registration.

This is **not required for MVP**.

---

## 2.9 Social Username Suggestions

Suggest corresponding usernames for platforms such as:

```text
@ledgerflow
```

This is useful for branding but is not part of the core domain workflow.

---

# 3. Out of Scope

The following features are explicitly **not being built for the hackathon MVP**.

They should not be added unless the core MVP is already complete and there is substantial remaining time.

## 3.1 Full Website Builder

We are not building:

* Website templates
* Drag-and-drop page builders
* Full CMS functionality
* Website hosting platform

The product helps prepare the domain for launch; it does not build the entire website.

---

## 3.2 Full Domain Registrar

We are not attempting to compete with domain registrars.

The application will not become a complete:

* Domain marketplace
* Registrar dashboard
* Domain portfolio manager
* Domain auction platform

---

## 3.3 Complete DNS Management Platform

We are not building a general-purpose DNS management system.

No attempt will be made to support every possible DNS record type and advanced DNS workflow.

Only the DNS operations required for the demonstrated launch scenario belong in the MVP.

---

## 3.4 Email Hosting

We are not building:

* Custom email hosting
* Mailboxes
* SMTP infrastructure
* Email administration

---

## 3.5 Payments and Billing

No:

* Subscription system
* Checkout
* Invoicing
* Credit management
* Payment processing

---

## 3.6 Advanced Team Collaboration

We are not building:

* Organizations
* Teams
* Roles and permissions
* Shared projects
* Approval workflows

---

## 3.7 Full Brand Identity Platform

The application will not become a complete branding suite.

Out of scope:

* Logo generation platform
* Full brand guidelines
* Typography systems
* Color-system generator
* Marketing asset generator

AI-generated names are part of the product, but comprehensive brand identity creation is not.

---

## 3.8 Social Media Availability Platform

We are not building a system that checks username availability across every social network.

---

## 3.9 SEO Platform

We are not building:

* Keyword research
* SEO auditing
* Competitor analysis
* Search-ranking tracking
* Content generation systems

---

## 3.10 Production-Scale Infrastructure

The hackathon project does not need:

* Multi-region deployment
* Complex Kubernetes infrastructure
* High-scale distributed systems
* Enterprise observability
* Advanced disaster recovery

The architecture should be clean and production-minded, but implementation should remain appropriate for an MVP.

---

# 4. Scope Rule

The following rule governs development:

> **If a feature does not directly help a founder move from business idea → brand name → available domain → launch-ready domain, it does not belong in the MVP.**

Priority order:

```text
1. End-to-end workflow
2. name.com API integration
3. AI name generation
4. Domain availability
5. Domain selection
6. Launch/DNS readiness
7. UI polish
8. Nice-to-have features
```

**No nice-to-have feature may be started until the complete MVP workflow works end-to-end.**

The hackathon objective is not to build the largest product.

It is to build the **clearest, most convincing demonstration of a real problem solved through AI + API + cloud infrastructure.**
