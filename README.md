# DJ Booking API

A backend REST API for managing DJ bookings across multiple venues — built around a real-world scenario: an outlet wants to book a DJ for a specific date, and the system has to make sure that DJ isn't already booked that night.

Built with **FastAPI + SQLite + Pydantic**. No frontend — this is an API-only backend, fully explorable through the auto-generated Swagger UI at `/docs`.

> A non-AI backend project: plain CRUD plus one real business rule (availability check). Built to round out a portfolio beyond AI/LLM work.

---

## Features

- **DJ management** — create, list, update price, soft-delete
- **Outlet management** — create, list, update name, soft-delete
- **Bookings** with an **availability guard** — a DJ can't be double-booked on the same date
- **Soft-delete** everywhere — DJs/Outlets are marked inactive, never physically removed, so existing booking history never breaks
- **Soft-cancel** for bookings — a cancelled booking keeps its row (with a reason); the date stays blocked, mirroring the real "cancellations are day-of, the slot is gone" rule
- **Seed script** — loads 30 DJs and 60 outlets from a JSON file for instant test data

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Web framework | FastAPI |
| Validation | Pydantic (request bodies) |
| Database | SQLite (raw `sqlite3`, parameterized queries) |
| Server | Uvicorn |
| Language | Python 3.12 |

---

## Data model

Three tables in one SQLite database:

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
| `dj_id` | INTEGER | foreign key → `DJ(id)` |
| `outlet_id` | INTEGER | foreign key → `OUTLET(id)` |
| `date` | TEXT | ISO date, e.g. `2026-07-05` |
| `status` | TEXT | `Booked` (default) or `Cancelled` |
| `cancel_reason` | TEXT | filled only when cancelled, otherwise `null` |

> **Design note:** a DJ's *availability* is never stored as a column. It's **derived** at request time by checking whether a booking row already exists for that DJ on that date — a single source of truth that can't drift out of sync.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/djs` | Create a DJ |
| `GET` | `/djs` | List active DJs |
| `PUT` | `/djs/{dj_id}` | Update a DJ's price |
| `DELETE` | `/djs/{dj_id}` | Soft-delete a DJ (`active = 0`) |
| `POST` | `/outlets` | Create an outlet |
| `GET` | `/outlets` | List active outlets |
| `PUT` | `/outlets/{outlet_id}` | Update an outlet's name |
| `DELETE` | `/outlets/{outlet_id}` | Soft-delete an outlet (`active = 0`) |
| `POST` | `/bookings` | Create a booking — **rejected if the DJ is already booked that date** |
| `GET` | `/bookings` | List all bookings (including cancelled — full history) |
| `PUT` | `/bookings/{booking_id}` | Cancel a booking (sets status to `Cancelled` + records a reason) |

---

## How it works — key design decisions

- **No double-booking.** Before inserting a booking, the API checks for an existing row matching that `dj_id` + `date`. If one exists, the request is rejected; otherwise the booking is created. The check always runs *before* the insert.
- **History is permanent.** Nothing is ever hard-deleted. DJs and outlets are soft-deleted (`active = 0`), and bookings are soft-cancelled (`status = 'Cancelled'`). This keeps every past booking intact and referenceable.
- **A cancelled date stays blocked.** Because a cancelled booking keeps its row, the availability check still finds it — so re-booking the same DJ on a cancelled date is still rejected. This matches the real venue rule where same-day cancellations don't free the slot.

---

## Running locally

```bash
# 1. clone, then create + activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. create the tables and load sample data (30 DJs, 60 outlets)
python seed.py

# 4. start the server
uvicorn main:app --reload
```

Then open **http://localhost:8000/docs** to explore and try every endpoint interactively.

> The SQLite database (`*.db`) is git-ignored — it's derived data, rebuilt from `database.py` + `seed.py` on first run.

---

## Project structure

```
dj_booking_api/
├── main.py            # FastAPI app + all endpoints
├── database.py        # DB path + schema (CREATE TABLE), runs on import
├── seed.py            # loads sample DJs/outlets from data/seed-data.json
├── data/
│   └── seed-data.json # 30 DJs + 60 outlets
├── requirements.txt
└── ARCHITECTURE.md    # data model + endpoint design notes
```

---

## Possible improvements

- Add a `pytest` suite (availability guard is the prime candidate for tests)
- Enforce foreign keys at the DB level (`PRAGMA foreign_keys = ON`) so bookings can't reference a non-existent DJ or outlet
- Add authentication / authorization (designed but intentionally deferred)
