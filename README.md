# DJ Booking API

A backend REST API for managing DJ bookings across multiple venues, built around a real-world scenario: an outlet wants to book a DJ for a specific date, and the system has to make sure that DJ isn't already booked that night.

Beyond the CRUD booking core, it has two more layers, planned from the start and built in phases:

- an **AI agent** (`/chat`) that turns natural language into real API actions via Claude tool-use, and
- **JWT auth + role-based access control (RBAC)** so only the right people (or the right agent) can change data.

Built with **FastAPI + SQLite + Pydantic + Anthropic (Claude) + JWT**. No frontend; it's API-only, fully explorable through the auto-generated Swagger UI at `/docs`.

---

## Live demo

Deployed on Google Cloud Run:

- **API + Swagger UI:** https://dj-booking-api-210763038293.asia-southeast2.run.app/docs
- **AI agent:** `POST /chat` on the same host

Try it **without logging in**: the `/chat` agent answers in read-only mode (list DJs, check availability, look up bookings), and every `GET` endpoint is public. To try booking and other write actions, log in as a demo admin and click **Authorize** in Swagger:

- DJ admin: `admin.dj@gmail.com` / `dj123`
- Outlet admin: `admin.outlet@gmail.com` / `outlet123`

> The database is SQLite baked into the container, so writes (new bookings, etc.) reset when the instance recycles; the seeded data (2 admins, 30 DJs, 60 outlets) always comes back.

---

## Features

**Core booking system**

- **DJ management**: create, list, update price, soft-delete
- **Outlet management**: create, list, update name, soft-delete
- **Bookings** with an **availability guard**: a DJ can't be double-booked on the same date
- **Soft-delete / soft-cancel everywhere**: rows are marked inactive/cancelled, never physically removed, so booking history never breaks
- **Cancellations know who is at fault**: if the DJ pulls out he breaks his contract and the date is closed for him everywhere; if the outlet cancels the DJ is blameless and can be moved to another outlet on the same date
- **Seed script**: loads 2 admins, 30 DJs, and 60 outlets for instant test data

**AI agent layer**

- **`/chat` natural-language endpoint**: talk to the system in plain English ("book DJ Rayhan at Lights Senayan on 2026-07-02") and the agent calls the right endpoints for you
- **Tool use + chaining**: every endpoint is exposed as a tool; to book by name, the agent first calls `get_djs` to find the ID, then `book_dj`
- **Honest by design**: a system prompt stops the agent from pretending to do things it has no tool for; it refuses clearly and says what it *can* do instead
- **Safe agent loop**: handles every `stop_reason` plus a hard iteration cap, so it can't run away
- **Conversation memory**: `/chat` is stateful per `conversation_id`, so the agent remembers earlier turns in the same conversation. Omit the id on the first message and the server generates one (returned in the response) for the client to reuse on follow-ups
- **Confirms before changing data**: before any create/update/delete/cancel, the agent restates exactly what it's about to do (the specific record, by name and id) and waits for an explicit "yes", so a name typo can't silently hit the wrong record

**Auth & access control (RBAC)**

- **JWT login** (`/login`) with **bcrypt-hashed** passwords
- **Two admin roles**: `admin_dj` (DJ + booking management) and `admin_outlet` (outlet management); all reads are public
- **Role-protected endpoints** via FastAPI dependencies
- **Per-role agent tools**: the `/chat` agent only receives the tools the caller's role is allowed, so it can't be used as a back-door around the HTTP permissions
- **Token expiry**: login tokens expire after 30 minutes

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Web framework | FastAPI |
| Validation | Pydantic (request bodies) |
| Database | SQLite (raw `sqlite3`, parameterized queries, foreign keys enforced) |
| AI agent | Anthropic SDK (Claude `claude-sonnet-4-6`), tool use |
| Auth | PyJWT (HS256) + bcrypt (password hashing) |
| Tests | pytest |
| Server | Uvicorn |
| Language | Python 3.12 |

---

## Data model

Four tables in one SQLite database:

**ADMIN**

| column | type | notes |
|--------|------|-------|
| `id` | INTEGER | primary key (auto) |
| `role` | TEXT | `admin_dj` or `admin_outlet` |
| `email` | TEXT | unique login id |
| `password` | TEXT | bcrypt hash (never stored in plaintext) |

**DJ**

| column | type | notes |
|--------|------|-------|
| `id` | INTEGER | primary key (auto) |
| `name` | TEXT | |
| `price` | INTEGER | fee per booking |
| `active` | INTEGER | `1` = active, `0` = soft-deleted (default `1`) |

**OUTLET**

| column | type | notes |
|--------|------|-------|
| `id` | INTEGER | primary key (auto) |
| `name` | TEXT | |
| `location` | TEXT | |
| `active` | INTEGER | `1` = active, `0` = soft-deleted (default `1`) |

**BOOKING**

| column | type | notes |
|--------|------|-------|
| `id` | INTEGER | primary key (auto) |
| `dj_id` | INTEGER | foreign key -> `DJ(id)` |
| `outlet_id` | INTEGER | foreign key -> `OUTLET(id)` |
| `date` | TEXT | ISO date, e.g. `2026-07-05` |
| `status` | TEXT | `Booked` (default) or `Cancelled` |
| `cancel_reason` | TEXT | filled only when cancelled, otherwise `null` |
| `cancelled_by` | TEXT | `dj` or `outlet`; filled only when cancelled. Which *side* pulled out, not who made the call: cancelling is always done by `admin_dj`. Decides whether the date frees up |

> **Design note:** a DJ's *availability* is never stored as a column. It's **derived** at request time from the booking rows for that DJ on that date: a single source of truth that can't drift out of sync. `cancelled_by` exists because `status` alone can't answer it: a cancelled booking blocks the date when the DJ walked away, but frees it when the outlet did.

---

## API endpoints

`Auth` shows who may call each endpoint. Reads are public; writes require a JWT for the matching role.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | public | Health check |
| `POST` | `/login` | public | Log in, returns a JWT (valid 30 min) |
| `POST` | `/chat` | public* | Natural-language agent (stateful per `conversation_id`); tools filtered by the caller's role |
| `POST` | `/djs` | admin_dj | Create a DJ |
| `GET` | `/djs` | public | List active DJs |
| `PUT` | `/djs/{dj_id}` | admin_dj | Update a DJ's price |
| `DELETE` | `/djs/{dj_id}` | admin_dj | Soft-delete a DJ (`active = 0`) |
| `POST` | `/outlets` | admin_outlet | Create an outlet |
| `GET` | `/outlets` | public | List active outlets |
| `PUT` | `/outlets/{outlet_id}` | admin_outlet | Update an outlet's name |
| `DELETE` | `/outlets/{outlet_id}` | admin_outlet | Soft-delete an outlet (`active = 0`) |
| `POST` | `/bookings` | admin_dj | Create a booking (**rejected if the DJ is already booked that date**) |
| `GET` | `/bookings` | public | List all bookings (including cancelled, for full history) |
| `PUT` | `/bookings/{booking_id}` | admin_dj | Cancel a booking (sets `Cancelled` + records a reason and whether the `dj` or the `outlet` pulled out) |

\* `/chat` is open to everyone, but the agent's available tools are filtered by the caller's role, so an anonymous user only gets the read tools.

---

## How it works

- **No double-booking.** Before inserting a booking, the API pulls every existing row for that `dj_id` + `date`. If any is still `Booked`, the request is rejected. The check always runs *before* the insert.
- **A cancelled date only frees up if the outlet was at fault.** What the company sells is the DJ's exclusivity for a date, locked in when the contract is signed. If the **DJ** pulls out he has broken that contract, so the date is closed for him everywhere: he cannot play it at another outlet, ours or not. If the **outlet** cancels, the DJ is blameless and gets moved to another one of our outlets, so the same date is bookable again. That is why `cancelled_by` is stored: without it the two cases look identical.
- **History is permanent.** Nothing is ever hard-deleted. DJs and outlets are soft-deleted (`active = 0`), and bookings are soft-cancelled (`status = 'Cancelled'`). A cancelled booking keeps its row, so the availability check can still see what happened and why.
- **The agent never touches the database directly.** `/chat` only translates language into tool calls; each tool maps to an existing endpoint function. The agent runs in a loop (call a tool, read the result, decide the next step) until it has an answer.
- **The agent is never a back-door.** The tools handed to the agent are filtered by the caller's role, mirroring the HTTP permissions exactly. A not-logged-in user literally has *no* booking tool, so even if the model "talks" like it booked, the database stays untouched. Security lives in the **tool filter (hard layer)**; the **system prompt (soft layer)** only shapes honest messaging.
- **The agent remembers the conversation.** Each `/chat` request carries a `conversation_id`; the server keeps that conversation's message history and replays it on the next call, so follow-up questions have context. History is stored per id, so separate conversations never bleed into each other. Send no id on the first message and the server mints one, returned in the response for the client to reuse.
- **It confirms before changing data.** Before any create/update/delete/cancel, the system prompt makes the agent restate exactly what it's about to do (naming the exact record by name and id) and act only after an explicit confirmation. If the request is ambiguous (e.g. two similar names), it lists the candidates instead of guessing. (This is a soft layer for *messaging*; the real security stays in the role-based tool filter.)
- **Tokens expire.** JWTs carry a 30-minute `exp` claim; PyJWT rejects expired tokens automatically, so a leaked or stale token stops working on its own.

---

## Running locally

```bash
# 1. clone, then create + activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. create a .env file with your secrets
#    ANTHROPIC_API_KEY=sk-ant-...
#    JWT_SECRET=any-long-random-string
#    ADMIN_DJ_PASSWORD=...
#    ADMIN_OUTLET_PASSWORD=...

# 4. create the tables and load sample data (2 admins, 30 DJs, 60 outlets)
python seed.py

# 5. start the server
python -m uvicorn main:app --reload
```

Then open **http://localhost:8000/docs** to explore every endpoint interactively.

**Trying protected actions / the agent:**

1. `POST /login` with a seeded admin (`admin.dj@gmail.com` or `admin.outlet@gmail.com`, password = whatever you set in `.env`), then copy the returned token.
2. Click **Authorize** in Swagger and paste the token.
3. Now write endpoints and the role-aware `/chat` agent unlock for that role.

**Run the tests:**

```bash
pytest
```

> The tests run against the seeded database, so create `.env` and run `python seed.py` (steps 3-4) first. The booking test logs in as a seeded admin to reach the role-protected `/bookings` endpoint.
>
> The SQLite database (`*.db`) is git-ignored: it's derived data, rebuilt from `database.py` + `seed.py` on first run.

---

## Project structure

```
dj_booking_api/
|-- main.py            # FastAPI app, organized by concern:
|                      #   setup -> models -> auth -> agent -> endpoints
|-- database.py        # DB path + schema + get_connection() (FK enforcement)
|-- seed.py            # loads 2 admins + sample DJs/outlets
|-- test_main.py       # pytest (availability guard)
|-- data/
|   `-- seed-data.json # 30 DJs + 60 outlets
|-- requirements.txt
`-- ARCHITECTURE.md    # data model, endpoint, agent & auth design notes
```

---

## Possible improvements

- A token **refresh** flow so users don't have to re-login every 30 minutes
- Dedicated tests for the auth and LLM-agent layers: the availability guard is covered (and now logs in to reach a protected endpoint), but nothing yet targets auth behavior itself (401/403, role mismatch, token expiry) or the non-deterministic agent
- Pagination + filtering on the list endpoints as data grows
