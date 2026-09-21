# Heathrow Taxi Rank System (MVP)

A Python MVP that models Heathrow Airport's central "feeder park" taxi
queueing system: estimated wait times, terminal-call notifications, and the
**Local** / **Fares Fare** return exemptions.

FastAPI backend + a small server-rendered web UI (four role-based pages) so
the whole flow can be driven from a browser without any extra tooling.

## How it models the real system

- **Feeder park** — a single central FIFO queue. Drivers join it from the
  app and see their live queue position and an estimated wait time, derived
  from how fast taxis have actually been called forward recently (a moving
  average over the last 30 minutes, falling back to a sane default until
  there's enough history).
- **Dispatch** — when a terminal needs a taxi, a rank agent calls the next
  one forward. The driver at the front of the queue is popped off, assigned
  that terminal, and sent an in-app notification telling them where to go.
- **Fares** — when a passenger reaches the rank, the rank agent enters their
  destination. The system classifies it as:
  - **Standard** — anything else. The driver must rejoin the back of the
    feeder park after dropping off.
  - **Local** — a nearby destination within London (~1h return trip).
  - **Fares Fare** — a destination outside London within a reasonable
    distance (~1h15 return trip).
  Classification is matched against a small destination lookup table
  (`app/data/destinations.py`); a rank agent can always override the
  classification and round-trip estimate for a destination that isn't in
  the table.
- **Return exemption** — Local and Fares Fare drivers don't have to rejoin
  the central queue. Once they mark the fare complete, they get a return
  deadline (minimum **60 min** for Local, **90 min** for Fares Fare — the
  spec's floors — extended by the destination's own round-trip estimate and
  by simulated live traffic conditions, never shortened below the floor).
  Before that deadline, the driver can pick **any terminal that currently
  has room**, skipping the central queue entirely.
- **Terminal capacity** — each terminal holds at most **15 taxis** at once
  (configurable per terminal by an admin). A returning driver can only pick
  a terminal that isn't already full. Picking a terminal doesn't reserve a
  spot for the whole drive back, though: the driver gives an expected
  arrival time, and they're only actually added to that terminal's rank —
  counted against its capacity and visible to its rank agent — once they're
  within **5 minutes** of arriving (or immediately, if they're already
  close). If the terminal fills up in the meantime, the driver is added
  automatically as soon as a slot frees up.
- **Geofencing** — a returning driver's check-in location can optionally be
  checked against an airport-radius geofence, purely to confirm they're
  back in the vicinity. It never disqualifies a driver or penalizes the
  route they took (diversions for traffic, fuel, etc. are always fine) — a
  late return is recorded, not blocked.
- **Feeder park information screens** — show badge numbers of drivers due to
  be called within the next 5 minutes, plus the full queue.
- **Admin** — add/remove taxis, rank agents, and terminals, and set the
  (simulated) live traffic level.

## Architecture

```
app/
  models.py            domain entities & enums (dataclasses)
  store.py              single in-memory Store (thread-safe) - see note below
  clock.py               controllable clock (real time in prod, simulated in load tests)
  config.py              tunable constants (floors, multipliers, geofence, etc.)
  data/destinations.py    static destination -> classification/round-trip lookup
  services/                business logic, framework-free
    queue_service.py         feeder park join/position/ETA
    throughput.py             call-rate estimation from dispatch history
    dispatch_service.py       "call next taxi" for a terminal
    fare_service.py            classification + exemption/return lifecycle
    geofence.py                 haversine distance / airport radius check
    admin_service.py            taxi / rank agent / terminal CRUD
    notifications.py            in-app driver notifications
  schemas.py             Pydantic request/response models
  serializers.py           dataclass -> response schema conversion
  routers/                 FastAPI routers (driver / rank-agent / admin / screens / pages)
  templates/, static/       server-rendered UI (Jinja2 + vanilla JS polling)
  simulation/               24h/10,000-driver load simulation (see below)
tests/                    pytest unit + API integration tests + simulation smoke tests
scripts/
  seed_demo_data.py         populates a running server with sample data
  simulate.py                 CLI for the load simulation
```

**Storage**: state lives in an in-memory `Store` (guarded by a lock) rather
than a database, to keep the MVP dependency-free and easy to run anywhere.
State resets when the process restarts. All access goes through the
service layer, so swapping in a real database later is a matter of
reimplementing `app/store.py`'s internals, not rewriting the app.

**Auth**: none — this is an MVP focused on the queueing/dispatch domain
logic. A production version would put real authentication and
role-based access control in front of the driver/rank-agent/admin routers.

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python run.py
# or: uvicorn app.main:app --reload
```

Then open:
- http://127.0.0.1:8000/ — overview / links to every page
- http://127.0.0.1:8000/driver — driver app (enter a badge number)
- http://127.0.0.1:8000/rank-agent — rank agent console
- http://127.0.0.1:8000/admin — admin console
- http://127.0.0.1:8000/screen — feeder park information screen
- http://127.0.0.1:8000/docs — interactive API docs (Swagger UI)

Four Heathrow terminals (T2–T5) are seeded automatically on startup. To
populate some sample taxis/agents/queue so the UI isn't empty:

```bash
python scripts/seed_demo_data.py   # requires the server to already be running
```

### Try the full flow

1. **Admin** → add a taxi (e.g. badge `T-001`) and a rank agent assigned to
   a terminal (e.g. `RA-1` at `T5`).
2. **Driver app** → log in as `T-001`, click "Join feeder park" — see the
   queue position and estimated wait.
3. **Rank agent console** → log in as `RA-1` at `T5`, click "Call next taxi"
   — the driver gets a notification.
4. Still in the rank agent console, click "Take fare" for that taxi and
   enter a destination:
   - `Manchester` → Standard fare.
   - `Kensington` → Local.
   - `Windsor` → Fares Fare.
5. **Driver app** → click "Fare complete". Standard fares rejoin the feeder
   park automatically; Local/Fares Fare fares show a live countdown and a
   terminal picker (full terminals are greyed out) plus an "expected minutes
   until arrival" field. Pick a terminal with `0` minutes to be added
   straight away, or a larger number to see it show as a pending "heading to
   Terminal X" return that gets added automatically once you're within 5
   minutes of arriving.
6. **Feeder park screen** → watch badge numbers appear as they get close to
   being called.
7. **Admin** → the terminals table shows live occupancy (`x/15`) and flags
   full terminals.

## Tests

```bash
pytest
```

60 tests cover queue position/ETA estimation, destination classification,
the exemption return-deadline math (floors + traffic multiplier), the
geofence distance check, terminal capacity, admin CRUD, full API-level
flows for standard, local, and fares-fare fares, and fast smoke tests for
the load simulation below.

## Load simulation: a full day, up to 10,000 drivers

`scripts/simulate.py` runs a 24-hour (midnight-to-midnight), up-to-10,000
driver simulation straight through the app's real service layer - the same
`admin_service` / `queue_service` / `dispatch_service` / `fare_service`
functions the HTTP API calls - so it's a genuine load test of the actual
queueing, dispatch, classification, terminal-capacity and exemption-return
logic, not a separate model of it. `app/clock.py` lets it drive that logic
against a simulated clock instead of real time, so a full day runs in a few
seconds.

It models:
- **Flight-driven demand**: ~55 flights/hour between 05:00-23:00 (with a
  realistic morning/evening bank layered on top, averaging to that rate)
  and a low overnight baseline, each sending a handful of taxi-seeking
  passengers to a terminal a little after landing.
- **Driver shift patterns**: a 3-mode mixture of shift start times (dawn /
  day / evening) roughly tracking the demand peaks, with randomised shift
  lengths - not all 10,000 drivers are working at once.
- **Return-trip timing**: drawn from the same destination table
  (`app/data/destinations.py`) the app itself classifies fares against.
- **The "does the driver return?" decision**: after a Local/Fares Fare
  exemption, drivers have a baseline chance of just not coming back, which
  is biased significantly higher for central-London destinations (more
  competing street hails there) and higher still near the end of a shift.

```bash
python scripts/simulate.py                                  # 10,000 drivers, default seed
python scripts/simulate.py --drivers 2000 --seed 7           # smaller/faster run
python scripts/simulate.py --csv out/timeseries.csv          # also write a 15-min snapshot CSV
python scripts/simulate.py --progress 60                     # print progress hourly
```

It prints a summary (fares by classification, exemption return/no-return
breakdown and reasons, terminal-full rejections, final taxi states) and,
with `--csv`, a time series of feeder-park length, active drivers, and
per-terminal occupancy you can chart. Every parameter (flight rate, fare
mix, shift patterns, the not-return bias) is a documented, overridable
assumption in `app/simulation/config.py` - the point is exercising the
app's real logic under realistic-shaped load, not a precise digital twin
of Heathrow.

A small/fast version of this (a few hundred simulated drivers) runs as
part of `pytest` (`tests/test_simulation.py`) checking invariants like
"every driver is accounted for", "terminal occupancy never exceeds
capacity", and "central-London destinations decline to return more often".

## Known MVP limitations / next steps

- In-memory storage only (no persistence across restarts) — swap `Store`
  for a real database-backed repository for production use.
- No authentication/authorization on any role's endpoints.
- Destination classification uses a small static lookup table rather than a
  real mapping/distance API; rank agents can override it manually.
- "Live traffic conditions" is an admin-settable simulated value rather than
  a real traffic feed integration.
- Push notifications are in-app/polled rather than real mobile push
  (APNs/FCM) — the notification model is in place to plug that in later.
