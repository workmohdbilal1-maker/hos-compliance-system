What Are the Hours of Service (HOS) Regulations?
Who Must Comply with the Hours of Service Regulations?.
Interstate/Intrastate Commerce
Personal Use of a CMV, Personal Conveyance and Yard Moves in a CMV.
What Is On-Duty Time?.
On-Duty Time in a CMV.
What Is Off-Duty Time?
What Are the Hours of Service Limits?
14-Hour Driving Window.
11-Hour Driving Limit.
Sleeper Berth Provision
30-Minute Rest Break
60/70-Hour On-Duty Limit
70-hour/8-day rule: Calculating the rolling 8-day total
34-Hour Restart
What Is the Adverse Driving Conditions Exception?
What Is the CDL Short-Haul Exception?.
What Is the Non-CDL Short-Haul Exception?
What Is the 16-Hour Short-Haul Exception?.
What Is a "Driver's Daily Log" and Electronic Logging Device (ELD)?
What Must the Record of Duty Status Include?.


You are building a complete production-ready system that ingests driver trip inputs, computes Hours-of-Service (HOS) compliant schedules, renders route maps, auto-fills the provided RODs_Ex.pdf ELD/daily log template using **ReportLab**, and exposes a clean REST API plus a polished React frontend. Treat this as a high-stakes, regulatory product: accuracy, traceability, test coverage, and reproducibility matter.

Below are the **explicit, non-negotiable instructions** and deliverables. Read them carefully and execute in order. You **must** start by parsing and understanding the two PDF documents provided in the project root:

* `fmcsa-hos-395-drivers-guide-to-hos-2022-04-28-0-1-.pdf` — **read this fully**, extract the rules, edge cases, definitions, exceptions, and sample scenarios. Your HOS engine must implement those rules faithfully (see rules list below).
* `RODs_Ex.pdf` — **open and inspect this template**. You will overlay generated values onto this template using ReportLab (see ReportLab section). Do not generate a new free-form PDF that ignores the template: the output must visually match the template with data drawn into the correct locations.

---

0. REQUIRED TOOLING — MCP SERVERS (MANDATORY)

You must actively use the following MCP servers whenever relevant:

1) pdf-reader MCP

Use for:

Parsing FMCSA HOS guide PDF

Reading RODs_Ex.pdf template

Extracting:

rules

field positions

layout structure

tables

definitions

You must NOT guess FMCSA rules.
All rule logic must trace back to parsed PDF content.

2) ai-filesystem MCP

Use for:

Reading project files

Writing code files

Creating folder structure

Updating configs

Saving generated artifacts (PDFs, JSON, docs)

Never hallucinate file contents.
Always read/write through filesystem MCP.

3) ripgrep MCP

Use for:

Searching inside repo

Finding:

TODOs

rule references

template usage

config values

Always search before modifying code.

1. FIRST ACTION — MANDATORY ANALYSIS PHASE

Before writing any code, you must:

Step 1 — Parse FMCSA HOS PDF via pdf-reader MCP

Extract and produce:

A. Structured Rule Map

Include:

- Rule name
- Exact FMCSA definition
- Conditions
- Exceptions
- Edge cases
- Required log fields
- Mathematical constraints
- Source page reference

B. Implementation Mapping

For each rule, define:
```
rule → Python function → unit test → API exposure
```

No coding allowed until this mapping is complete.

Step 2 — Inspect RODs_Ex.pdf Template via pdf-reader MCP

You must:

- Detect page count
- Detect grid structure
- Detect header field
- Estimate coordinates
- Identify duty status chart region

Then generate:
```
eld_template_mapping.json
```

Stored via ai-filesystem MCP.


# 1 — High-level Deliverables (final artifacts)

1. Django backend (DRF) with full models, serializers, services, endpoints, and tests.
2. Complete, well-documented HOS engine implementing FMCSA rules and exceptions.
3. React + TypeScript frontend (Tailwind + recommended UI libs) with Map integration, trip planner, dashboard, log visualizer, and PDF download.
4. ReportLab code that writes driver logs onto `RODs_Ex.pdf` template and returns a downloadable PDF.
5. CI/CD pipeline (GitHub Actions) to run tests and deploy:

   * Backend: containerized, deployed to Render / Railway / AWS ECS (documented).
   * Frontend: deployed to Vercel.
6. README, architecture diagram, API docs (OpenAPI / Swagger), unit & integration tests, and demonstration (hosted URL).
7. Acceptance test suite with several FMCSA sample scenarios asserting algorithm correctness.

---

# 2 — Requirements: FMCSA HOS Rules (must be implemented)

You must read the FMCSA doc and implement each as rules with tests. At minimum implement:

* Definitions and who must comply (Interstate vs Intrastate).
* Personal conveyance, yard move, and how they affect logs.
* What is On-Duty Time (in CMV & not in CMV) and Off-Duty time.
* **14-hour duty window**: start when driver comes on duty after 10 consecutive off-duty hours; driver may drive up to 11 hours within the 14-hour window.
* **11-hour driving limit**: no more than 11 hours driving after 10 consecutive off-duty hours (subject to sleeper berth split rules).
* **Sleeper Berth Provision**: allow split sleeper berth (e.g., 8/2) — implement both continuous and split rules per FMCSA guidance.
* **30-minute rest break**: must take a 30-minute break before 8 cumulative hours of driving (can be split per allowances in doc).
* **60/70-hour on-duty limits**: enforce rolling 7/8-day limits as defined by the doc (the user stated 70/8-day; implement rolling 70h in 8-day cycle and 60h if applicable).
* **Calculating rolling 8-day total**: include method to compute rolling totals given historical logs.
* **34-hour restart**: implement restart rules and constraints (document required conditions from FMCSA).
* **Adverse driving conditions exception**.
* **CDL Short-Haul, Non-CDL Short-Haul, 16-Hour Short-Haul exceptions** — where applicable implement toggles and logic.
* **Driver’s Daily Log & ELD required fields**: ensure logs include all required fields (date, start/end times, mileage, shipping document numbers, carrier info, duty status changes with timestamps, total hours by duty status, etc.)

For each rule, produce unit tests and at least three scenario tests (one normal, one edge case, one failure/exempted case).

---

# 3 — Backend: Models, Services & API Contracts

Design the backend with clear separation: models → services (HOS engine, route planner, PDF generator) → API (DRF viewsets).

## Required models (minimum)

* `Driver` (id, name, CDL info flag, carrier, timezone, default cycle type, credentials)
* `Trip` (id, driver, created_at, origin (geo), pickup (geo), dropoff (geo), state enum, cycle_hours_used, options: short_haul_exemption booleans)
* `TripSegment` (trip, leg_index, start_point, end_point, miles, duration_hours, reason (drive/fuel/pickup/drop))
* `TripDayLog` or `RecordOfDuty` (trip, day_index, date, duty_events: JSON list with timestamp, duty_status, location, odometer, remarks)
* `ELDTemplateMapping` (template_field_name, x, y, page_number, font_size, alignment) — a config mapping between template and fill coordinates so the PDF generator is configurable.
* `Carrier` (name, DOT, address, contact)
* `HistoricalLog` (driver, date, day_log) — used to compute rolling cycles.

Use `PointField` (GeoDjango) if possible, otherwise store lat/lon floats + optional geometry later.

## Services to implement

* `route_planner` — integrate Mapbox Directions or OpenRouteService. Return distance (mi), duration (hrs), polyline.
* `hos_engine` — core HOS algorithm (see section 4).
* `eld_pdf_generator` — uses `RODs_Ex.pdf` + `ELDTemplateMapping` to render final PDF using ReportLab with a safe overlay approach (instructions below).
* `validator` — validates inputs, verifies driver/vehicle details, and ensures policy compliance.
* `audit_logger` — immutable event log for decisions (which rules triggered, timestamps, inputs) saved to DB for traceability and appeals.

## DRF Endpoints (API contract examples)

* `POST /api/trips/` — create trip. Body:

```json
{
  "driver_id": 12,
  "current_location": {"lat": 40.7128, "lng": -74.0060},
  "pickup_location": {"lat": 39.9526, "lng": -75.1652},
  "dropoff_location": {"lat": 33.748995, "lng": -84.387982},
  "cycle_hours_used": 28.5,
  "options": {
    "short_haul_exemption": false,
    "adverse_driving": false,
    "sleeper_berth_split": {"first": 8, "second": 2}
  }
}
```

Successful response returns trip object and computed summary (distance, days, hours, next required breaks).

* `GET /api/trips/{id}/` — trip summary with day logs and route polyline.
* `GET /api/trips/{id}/logs/` — raw `TripDayLog` records JSON.
* `GET /api/trips/{id}/pdf/` — returns generated RODs PDF (Content-Disposition: attachment; filename=trip_{id}_rods.pdf).
* `POST /api/drivers/` — create driver.
* `GET /api/drivers/{id}/history?days=8` — returns historical logs used to compute rolling 8-day total.
* `POST /api/validate/hos/` — submit arbitrary logs+history to validate compliance (useful for tests).
* `GET /api/maps/route/?origin=lat,lng&destination=lat,lng` — return polyline, distance, duration.

## Security & Auth

* JWT (simple) or session auth. Implement role-based access: `driver`, `admin`, `inspector`.
* Rate limiting on route and PDF endpoints; input validation & schema enforcement.

---

# 4 — HOS Algorithm: Detailed Design (pseudocode + implementation guidance)

This is the heart of the system. Implement robust, thoroughly tested service `hos_engine` that consumes:

* `start_datetime` (tz aware, driver local)
* `starting_cycle_hours_used` (float)
* `historical_logs` (list of last 8 days of logs, with duty status timelines)
* `route_profile` (total_miles, per_leg distances)
* `options` (adverse_condition, exemptions, sleeper_split, short_haul)

### Core algorithm outline (pseudocode)

```
function plan_trip(start_dt, historical_logs, total_miles, options):
    speed = choose_avg_speed(options, route_profile)  # default 55 mph
    miles_remaining = total_miles
    day = 0
    logs = []
    cycle_hours = compute_rolling_cycle_hours(historical_logs)  # last 7/8 days
    while miles_remaining > 0:
        day += 1
        duty_window_start = start_dt + elapsed_time
        duty_window_end = duty_window_start + 14 hours
        available_drive_hours_in_window = min(11, remaining_hours_until_cycle_limit(cycle_hours))
        # allocate driving for this day
        drive_hours = min(available_drive_hours_in_window, miles_remaining / speed)
        # break rules:
        if cumulative_drive_since_last_break + drive_hours > 8:
            insert_break_at = 8 - cumulative_drive_since_last_break
            add 30-minute break into timeline
        # sleeper berth option: compute allowable split if selected
        # fuel stop every 1000 miles: insert fuel stop events when crossing thresholds
        # include 1 hour pickup + 1 hour dropoff at appropriate legs
        # advance miles_remaining and elapsed_time
        # compute on_duty/off_duty totals
        # update cycle_hours
        logs.append(day_record)
    return {total_days, logs, alerts_if_violation}
```

### Important implementation details

* Use timezone-aware datetimes; drivers operate in local timezones.
* Implement **rolling cycle computation** by summing `on_duty` hours from historical logs in the previous 7/8 day window, as defined by FMCSA; include the option to compute both 60h/7d and 70h/8d variants.
* Provide `explain()` metadata with each planned day: which rule limited driving (e.g., 11-hour cap, 14-hour window, cycle reached), and exact times of duty switching.
* For sleeper berth, support both continuous (10-hr off) and split (e.g., 8+2) logic per FMCSA: ensure split times add to required off duty total and are at least the minimal split durations.
* Implement adverse driving extension (allowed additional driving time up to limit) per FMCSA rules — encode time-based extension rules and require driver flag `adverse_driving` with reasoning.
* Add `what_if` simulation mode: change avg_speed, add stops, toggle exceptions.

### Outputs (for API & UI)

* Time series of events per trip: ordered list of timestamped events `{timestamp, duty_status, lat,lng, odometer, reason, explanation}`.
* Per-day totals: driving_hours, on_duty_hours, off_duty_hours, fuel_stop boolean, pickup/drop flag.
* Alerts array: explicit text for any computed violations, near-violations, or rules triggered.

---

# 5 — ReportLab PDF generation (must use `RODs_Ex.pdf` template)

You **must** generate the final RODS PDF by overlaying text/lines on the provided `RODs_Ex.pdf` template using ReportLab. Follow this procedure exactly:

1. **Inspect the template**: programmatically open `RODs_Ex.pdf` to determine number of pages and approximate target fields. Create a JSON mapping file `eld_template_mapping.json` with entries:

```json
{
  "page_count": 2,
  "fields": {
    "driver_name": {"page": 0, "x": 60, "y": 720, "font": "Helvetica", "size": 10, "align": "left"},
    "date": {"page": 0, "x": 420, "y": 720, "font": "Helvetica", "size": 10, "align": "right"},
    "daily_grid": {"page": 1, "x": 40, "y": 600}
    // ...
  }
}
```

2. **Tooling**: Use `PyPDF2` (or `pypdf`) to read the template, and create a ReportLab `canvas` for each page to draw overlay text/graphics at specified coordinates. Merge overlay with template to produce a final PDF.
3. **Font & styling**: use legible fonts (`Helvetica`/`Times-Roman`) and sizes matching template. Support bold and small caps where needed.
4. **Duty status line drawing**: implement drawing routines to render the timeline graph (ELD style): vertical grid for hours (0–24), and a polyline representing duty-state across each hour (Off/On/Sleeper/Driving). Map each event timestamp to an X coordinate on the daily grid and draw colored/filled segments. (Colors can be generic; production palette acceptable.)
5. **Verification**: provide an automated PDF visual test that asserts text is present and key coordinates contain non-blank pixels (basic raster check). Additionally, include a human-review helper that creates an HTML preview overlay with field rectangles for tweaking coordinates.
6. **Configurable mapping**: publish a small admin endpoint `POST /api/templates/mapping/` that accepts the JSON mapping and stores it; the system must be able to re-render PDFs after mapping tweaks without code changes.
7. **Edge cases**: if daily logs span multiple template pages, generate multiple pages accordingly (replicate header fields).

**Important**: the generated PDF must visually match `RODs_Ex.pdf` (same header/footer and grid) — not a freeform replacement.

---

# 6 — React UI Layout & UX Requirements

Build a professional, responsive React + TypeScript application. Use Tailwind for styling; shadcn/ui or Chakra/Material optional. Use Mapbox GL JS or OpenLayers + OpenRouteService if you prefer an open option.

## Pages & Components

* **Login / Driver Select** (basic auth)
* **Trip Planner** — form to enter current/pickup/dropoff, cycle used, options (short haul, adverse conditions). Validate addresses.
* **Route Preview** — show map with polyline, segment markers (fuel, pickup, drop), distance & ETA. Button: “Plan Trip”.
* **Trip Timeline / Dashboard** — per-day cards summarizing driving/on-duty/off-duty, visual ELD timeline chart, alerts, remaining cycle hours, next required break.
* **ELD PDF Viewer / Download** — preview and download generated RODs PDF.
* **Admin** — template mapping editor (visual overlay), driver management, historical logs viewer.

## UI Behaviors

* Timeline visualization: horizontal stacked bars for duty categories per day with hover to show exact timestamps.
* Audit/explain pane: for each day show why an action was taken (rule that capped driving).
* Mobile-friendly for drivers: large buttons, minimal typing, geolocation auto-fill.
* Accessibility: keyboard accessible forms, alt tags, color contrast.

## State & Data Flow

* Use React Query for API calls; Zustand (or Redux) for global state (auth, selected trip).
* Persist last trip locally for offline use and re-synchronization.

---

# 7 — Tests, Validation & Acceptance Criteria

## Tests

* Unit tests for every HOS rule function (pytest).
* Integration tests for endpoints (DRF test client).
* PDF generation tests (file exists, >0 bytes, and basic raster assertions).
* End-to-end tests (Playwright or Cypress) for core user flows (plan → preview → download PDF).

## Acceptance Criteria (minimum)

1. HOS engine passes a provided canonical set of FMCSA scenarios (include at least 10 test scenarios with known expected outcomes).
2. The generated PDF visually overlays data into `RODs_Ex.pdf` template; core fields (driver, dates, daily grid) display expected values in spot checks.
3. Trip API returns day logs and an alerts array; sample client can render timeline and map correctly.
4. Hosted demo (backend + frontend) is reachable and stable, and CI runs tests on PRs.
5. Documentation: README with setup, env vars, migration & deploy commands, API docs, sample cURLs.

---

# 8 — Production Deployment Steps (concise, reproducible)

## Infrastructure (recommended)

* Backend: Docker container; deploy to Render / Railway / Heroku (container); managed PostgreSQL.
* Frontend: Vercel (connect GitHub).
* Optional: Sentry for error monitoring; Cloudflare in front of frontend for static caching.
* CI: GitHub Actions to run tests and build Docker image then push to registry and deploy.

## Example step-by-step

1. Create `.env` templates:

```
SECRET_KEY=...
DATABASE_URL=postgres://user:pass@host:5432/db
MAPBOX_TOKEN=...
SENTRY_DSN=...
DJANGO_SETTINGS_MODULE=project.settings.production
```

2. Dockerfile for Django: use python:3.11, install requirements, collectstatic, run migrations, run Gunicorn.
3. docker-compose.yml for local dev: Django, Postgres, Redis (for Celery), and a simple adminer.
4. GitHub Actions:

   * `on: push/pull_request`
   * Steps: checkout, setup python, install deps, run tests, build Docker image, push to registry (if using).
   * Deploy step: call provider API (Render/GHActions) to trigger deployment or use provider specific actions.
5. Frontend: commit, configure Vercel project to build `npm run build`, set env vars in Vercel.
6. Database migrations: `python manage.py migrate` — include a startup healthcheck to retry DB connectivity.
7. Secrets & Keys: use secret manager (Render secrets / GitHub secrets / AWS Parameter Store).
8. Logging & Monitoring: attach Sentry DSN and logs to a centralized log (Papertrail/LogDNA); expose Prometheus metrics endpoint if using k8s.

---

# 9 — Security, Privacy & Compliance

* Keep PII minimal and encrypted in transit (HTTPS) and at rest for sensitive fields.
* Implement audit trail for every plan generation and PDF generation (who, when, inputs).
* Rate limit map/directions endpoints to prevent abuse of map API keys.
* Allow drivers to request data deletion (implement GDPR-style erasure endpoint).
* Ensure PDF output does not leak credentials or keys.

---

# 10 — Developer Workflow & Deliverable Format

* Use a monorepo with `/backend` and `/frontend`.
* Use conventional commits, semantic versioning, and a CHANGELOG.md.
* OpenAPI/Swagger for backend endpoints: publish `openapi.json`.
* Include `seed_data` script to create sample drivers, trips and historical logs for tests.
* Create a `dev.md` and `prod.md` with exact commands for running locally and deploying.

---

# 11 — Acceptance & Handover checklist for the AI Agent (what to produce in the final PR)

* Fully working code in `/backend` and `/frontend`.
* `docs/` with architecture diagram, API docs, deployment instructions, and FMCSA rule mapping document (which sections map to which implemented rule).
* `tests/` with coverage report: target >=80% for backend critical modules (HOS engine).
* Live demo URL(s) and sample driver credentials.
* One example generated PDF (trip_123_rods.pdf) produced from `RODs_Ex.pdf`.
* `eld_template_mapping.json` and admin tool to tweak coordinates.
* README that explains how `RODs_Ex.pdf` fields map to generator coordinates.
* A `verify_hos_compliance.py` script that runs the 10 canonical scenarios and outputs a compliance report; attach expected vs actual.

---

# 12 — Strong opinions & final constraints (follow these)

* Implement the HOS engine in pure Python (no black-box services). Unit tests must prove logic.
* Use ReportLab + PyPDF2 merging approach — do not attempt to edit PDF form fields only (not reliable across templates); instead use canvas overlays merged with template.
* Prefer Mapbox Directions API for consistent routing; allow a fallback to OpenRouteService with configuration toggles.
* Do not hardcode coordinates for the template: require a mapping JSON and provide a small UI to tune coordinates visually.
* Make the system deterministic: given identical inputs and historical logs, results must be identical (no random seeds).
