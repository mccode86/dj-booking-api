# 🗺️ Architecture — DJ Booking API

> A reference for myself. This is the **sketch made before writing any code** — the
> *way of thinking*, not the syntax. Deliberately **no code**. Every box has an
> **"Under the hood"** note so the reasoning is reusable in the next project.
>
> **Status:** core CRUD + business rule ✅ built & tested · AI agent layer ✅ built ·
> **Auth (login + roles) 📐 designed 2026-06-27 — build next.**

**Goal:** an outlet (a Holywings club) wants a specific DJ to play on a specific
date. The system records the booking — but only if that DJ is still free on that
date — and keeps the **full history** of every gig (done or cancelled).

**Pattern:** classic **CRUD backend** + one **business rule** (the availability
check). No LLM, no RAG — a *plain* backend. (Deliberate choice: to learn the kind
of backend most jobs actually are, not just AI/RAG.)

---

## 🧭 Phase roadmap (what we do, in order)

| Phase | What we do | Status |
|---|---|---|
| **1 — Data model** | Decide the tables, columns, relationships (the *nouns*). | ✅ done |
| **2 — Operations** | Decide the endpoints / what the system can *do* (the *verbs*). | ✅ done (Create-Booking flow being finalized) |
| **3 — Build** | Code it: project setup → create tables → seed / prepare data → implement endpoints → tests. | ✅ done |
| **4 — AI layer** | NL `/chat` → agent (tool use) wrapping the endpoints. | ✅ done |
| **5 — Auth** | Login + roles (admin vs outlet), a layer ON TOP. | 📐 designed — build next |
| **Later — LLM extras** | More AI features (Q&A, reschedule suggestions). | 🔮 optional |

> Principle: **design early, implement late.** Design the whole thing first, then
> code top-to-bottom (dependencies already resolved). Auth & LLM are *layers on
> top* — build the core first, harden / enrich after.

---

## The one non-obvious decision (read this first)

**Availability is NOT stored. It is computed from the bookings.**

- A date is "available" for a DJ **only if no booking row exists** for that
  `(dj, date)` pair.
- We never keep a separate "available dates" list.

*Under the hood:* storing availability separately = **two copies of the same
truth** → they can **drift** (you book a date but forget to remove it from the
"available" list → bug, silent). One source of truth = the **Booking table**.
Same lesson as the `MODEL` constant in the capstone (CAP.4): "works ≠ correct."

---

## Data model — three tables

```
   DJ  ──<  BOOKING  >──  OUTLET
 (1 DJ has         ▲          (1 outlet has
  many bookings)   │           many bookings)
        BOOKING sits in the middle and points to BOTH.
```

### Table: `DJ`  — an entity (identity; changes rarely)
| column | note |
|---|---|
| `id` | **primary key** — unique tag for each row |
| `name` | |
| `price` | fee per gig — stored **once** here, never copied into bookings |
| `active` | soft-delete flag (`true`/`false`) — a DJ who quits is set `false`, never deleted |

### Table: `OUTLET`  — an entity (the Holywings club that requests)
| column | note |
|---|---|
| `id` | primary key |
| `name` | |
| `location` | optional |
| `active` | soft-delete flag — a closed outlet is set `false`, never deleted |

### Table: `BOOKING`  — the events (grows over time; a *junction table*)
| column | note |
|---|---|
| `id` | primary key |
| `dj_id` | **foreign key** → `DJ.id` (which DJ) |
| `outlet_id` | **foreign key** → `OUTLET.id` (which club) |
| `date` | the gig date |
| `status` | `Booked` → `Done` or `Cancelled` |
| `cancel_reason` | `NULL` unless `status = Cancelled` |

*Under the hood — why three tables, not one:*
- **Entity vs attribute:** `name` / `price` are *facts about a DJ* → columns in
  `DJ`, not separate tables. A booking is a *different kind of thing* (an event) →
  its own table.
- **One-to-many → child table + foreign key:** one DJ has many bookings.
  "Many + changing" data can't be columns (you'd grow sideways forever) and can't
  be crammed into the parent row → it becomes a separate table where each **row**
  is one booking, pointing back via `dj_id`. Exact same shape as a blog's
  Post → Comment.
- **Grow DOWN, not RIGHT:** more bookings = more **rows**, never more columns.
  Columns are the fixed skeleton; rows are the data.
- **One Booking table for ALL DJs** (not one table per DJ) — `dj_id` says which
  DJ owns each row. (Just like one Comment table for all posts via `post_id`.)
- **`price` lives only in `DJ`:** if it were copied into every booking, a price
  change would mean editing dozens of rows → drift.

---

## The booking lifecycle (`status`)

```
        (created)
           │
           ▼
        Booked ──────(gig day goes fine)──────▶  Done
           │
           └─────────(cancelled on the day)────▶  Cancelled  (+ cancel_reason)
```

**Business rules that shaped this (how Holywings actually works):**
- Bookings are **first-come, first-served & internal** → **no "rejected" state
  needed**. A failed request (date already taken) simply **creates no row**; the
  system just answers "taken, pick another date."
- Cancellations *do* happen (missed / delayed flights; rarely illness; outlets
  only for force majeure) and always **on the day (hari-H)**.
- **A cancelled date does NOT free up** (too late to rebook). So on cancel we
  **do not delete the row** — we keep it and mark it `Cancelled`. Availability
  treats a row as "taken" **regardless of status**.
- Why keep cancelled rows → **history & reporting** (how many gigs done, how many
  cancelled, and why). That need is exactly what makes the `status` column earn
  its place — see below.

> **Requirements drive design:** earlier we correctly decided `status` was *not*
> needed (instant, no-rejection flow). The moment the rule "remember cancellations
> for history" appeared, `status` became necessary. The schema follows the rules,
> not a textbook.

---

## Data lifecycle

**The Booking table IS the permanent history. It is never reset.**

*Under the hood:* the database is a **file on disk** (like the capstone's
`chat_logs.db`) — it *is* the durable store, so there's no need to "archive to a
document." Databases handle millions of rows comfortably; at agency scale this is
tiny. Resetting would throw away the business records.

> YAGNI: if it ever got truly massive, you'd archive old rows to a separate
> table. Don't build that now.

---

## PHASE 2 — Operations / endpoints  ✅ designed

An **endpoint** = one labelled **door** into the system (a URL + an action). The
frontend (a *separate* project — this repo is API-only) knocks on a door to either
*get data* (**READ**) or *make something happen* (**WRITE**). Trick for finding the
doors: imagine the screens (the "cinema booking" flow) — every screen that shows
data needs a **read** door; every confirm button needs a **write** door.

**The CRUD checklist** — for each entity, ask which of the 4 standard doors you
actually need: **C**reate · **R**ead · **U**pdate · **D**elete. Build only what's
needed (**YAGNI**).

### DJ
| Door | Type | What it does |
|---|---|---|
| Create DJ | write | register a DJ (name, price) |
| List DJs | read | the pick-list (booking screen shows only `active = true`) |
| Update DJ | write | change data (e.g. the fee went up) |
| "Delete" DJ | write | **soft delete** = Update `active = false`. No hard delete. |

### Outlet  (same shape as DJ)
| Door | Type | What it does |
|---|---|---|
| Create Outlet | write | a new club opens |
| List Outlets | read | e.g. to pick an outlet when booking |
| Update Outlet | write | rebrand / rename / renovate |
| "Delete" Outlet | write | **soft delete** = Update `active = false`. No hard delete. |

### Booking
| Door | Type | What it does |
|---|---|---|
| **Create Booking** ⭐ | write | the star — runs the **availability check** first (see below) |
| View bookings / calendar | read | a DJ's bookings (frontend greys out the booked dates) |
| Cancel Booking | write | really an Update: `status = Cancelled` + `cancel_reason`. Row stays. |
| Mark Done | write | really an Update: `status = Done`. |
| ~~hard Delete~~ | — | not needed |

**Recurring pattern — soft delete:** anything that is referenced by history (DJ,
Outlet) or that *is* history (Booking) is **never hard-deleted** — you flip a flag
(`active = false`, or `status = Cancelled / Done`). The row stays, so foreign keys
& reports never break. Same root insight as Phase 1's "Booking table is permanent."

### ⭐ Create Booking — the flow  ⏳ (being finalized in the design session)
Receives `dj_id`, `outlet_id`, `date`. High level:
1. **Availability check FIRST** — is there already a booking row for this
   `(dj_id, date)`? (a row of *any* status counts as taken).
2. If **taken** → reject; tell the outlet "pick another date" (no row created).
3. If **free** → insert the new booking with `status = Booked`.

> This is where the one business rule actually lives. The detailed step-by-step is
> being worked out now.

---

## Components — the technology that fills each box

| Box | Technology |
|---|---|
| API / endpoints | FastAPI |
| Database | SQLite (→ Postgres if it ever grows) |
| Request / response types | Pydantic |
| Tests | pytest |

Notice how short this list is vs the capstone: **no Chroma, no embeddings, no
LLM.** That's the whole point — this is a *plain* backend.

---

## 🔐 Auth — login + roles  📐 designed 2026-06-27 (build next)

> Designed via Socratic interview. The API currently has **no auth** — anyone can
> book / cancel / delete. Add **authentication** (who are you?) + **authorization**
> (what may you do?) as a layer ON TOP of the working core. Planned from day one
> ("design early, implement late").

### Roles — **role-based access control (RBAC)**
Three audiences, not just "logged in / out":
| Audience | May do |
|---|---|
| **Public** (no login) | **read only**: list DJs, list outlets, view bookings |
| **Admin — DJ management** | add / update / delete DJ · **create** booking · cancel booking |
| **Admin — Outlet** | add / update / delete outlet |

*Under the hood:* `update DJ price` and `create booking` belong to DJ management
(decided explicitly — they were the easy-to-miss ones). Outlet admins touch outlets
only.

### The non-obvious decision — **no public sign-up**
You **never** let someone choose their own privileged role (everyone would pick
"admin DJ" → auth becomes meaningless). The **2 admin accounts are fixed**,
identified by **email**, and provisioned by whoever runs the system — they can't be
added to. → **Seed them**, exactly like `seed.py` does for DJs/outlets: the `ADMIN`
table *structure* lives in `database.py` (`CREATE TABLE`), the 2 *rows* in
`seed.py` (`INSERT`).

*Under the hood:* role assignment must come from a **trusted source, never the
user's own claim.** For a tiny fixed set, seeding beats a "super-admin creates
admins" endpoint — simpler, zero extra attack surface. Add super-admin later only
if the set must grow (**YAGNI**).

### Table: `ADMIN`  (same shape as `DJ` — id + attributes)
| column | note |
|---|---|
| `id` | primary key |
| `email` | **unique** login id — just a string; **not** wired to real email sending |
| `password` | stored **HASHED**, never plaintext |
| `role` | `dj_management` or `outlet` (the "wristband colour") |

### Authentication — the **token** (wristband analogy)
HTTP is **stateless** — the server doesn't remember you between requests (same shape
as Stage 7.6: the LLM has no memory, you resend the whole history each call). So
each request must **carry proof**:
1. Login once (email + password) → server verifies → returns a **token**.
2. Every later request **carries that token** (in a header).
3. Server reads the token → knows the **role** → allows / denies.

The role rides **inside** the token (VIP vs regular wristband).

### Password **hashing**
Never store the raw password. Store a **one-way hash** (blender: steak → mince is
easy, mince → steak is impossible). At login, hash what they just typed and
**compare the hashes** — the original is never needed. If the DB is stolen, only
useless hashes leak. (A library does the hashing; you don't write the algorithm.)

### `/chat` — closing the AI back-door
The agent can only call the tools you **hand** it → **filter the tools list
per-request by role:**
| Caller | Tools given |
|---|---|
| Public (no login) | read only: `get_djs`, `get_outlets`, `get_bookings` → **cannot** book |
| DJ management | the above **+ `book_dj`** |

*Under the hood:* the agent's power = the tools given to it; scope that list by who
is asking. (`get_bookings` tool isn't built yet — add during build.)

### Still fuzzy — settle at build time (design-meets-code)
- **How the token is made & verified** — the **JWT** standard (a *signed* token).
- **How each endpoint checks it** — FastAPI's **dependency** pattern (`Depends`).

### Build order (dependency-first)
1. `ADMIN` table (`database.py`) + **seed 2 admins** (`seed.py`, hashed passwords).
2. **Login** endpoint → verify hash → issue token.
3. **Protect** endpoints → check token + role (dependency).
4. **Filter `/chat` tools** by role (+ add the `get_bookings` tool).

---

## 🔮 Future (optional) — an LLM layer ON TOP

Not now. Build the plain backend first, *then* maybe add AI on top — that ordering
is itself correct (solid deterministic core first, AI later).

**Principle: the LLM must earn its place** (same rule as the `status` column).
- ❌ Never use the LLM for the availability check or any core rule — that logic is
  deterministic, cheap, and must always be right. The LLM can be wrong; bookings
  can't.
- ✅ Use the LLM where humans speak messily (needs translating) or where you need
  generation / summary / recommendation.

**Key shape:** the LLM sits **on top of** the backend, never inside it. The core
booking logic stays plain and reliable; the LLM only translates human language
into calls to the existing API — the **tool use / function calling** pattern
(Stage 10). The AI may be flaky; the core stays deterministic and trustworthy.

**Candidate features:**
1. ⭐ **Natural-language booking** — outlet types *"I want DJ Andre next Saturday
   night"* → LLM parses it into structured fields (`dj`, `date`) → the *backend*
   executes and runs the availability check. (Reuses Pydantic + tool use.)
2. **Q&A assistant over the data** — *"which DJs are free next weekend?"*, *"how
   many gigs did Andre do this month?"* → an agent that calls the DB. (Agent +
   tool use, grounded in the live DB, not documents.)
3. **Reschedule suggestions** — when a date is taken: *"Andre is booked the 11th
   but free the 12th & 18th; or DJ Mike is free the 11th, similar style."*

---

## ❌ Deliberately NOT decided at the sketch stage
Syntax, function / endpoint names, exact column types, exact arguments. Handled
**while coding** (docs / AI / autocomplete). The "high-pass at 100hz" details.

---

## 🧩 Pattern-library entry
This is the **CRUD + business-rule** pattern. Swap "DJ booking" for "hotel rooms",
"appointment slots", or "equipment rental" and the skeleton is identical: a few
**entities** + a **junction table** for the events + **one rule that guards
writes** (here: availability). Most backends in the wild are a variant of this.

**Principles this design came from (the real takeaways):**
entity vs attribute · one-to-many (child table + foreign key) · grow down, not
right · **derived data is computed, not stored** (anti-drift) · DB = permanent
history · **YAGNI** · **requirements drive the design**.

**Coding order = follow the sketch top to bottom** once Phase 2 is designed — the
dependencies will already be resolved.
