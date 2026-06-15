# HOS Compliance System

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django 4.2](https://img.shields.io/badge/Django-4.2-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)


A full-stack **Hours of Service (HOS)** compliance system for truck drivers, implementing the complete FMCSA 49 CFR Part 395 ruleset. The system combines route-based trip planning, automated HOS-compliant duty log generation, and RODS (Record of Duty Status) PDF output overlaid on the official DOT template.

---

## Table of Contents

- [Features](#features)
- [FMCSA Rules Implemented](#fmcsa-rules-implemented)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Docker Setup](#docker-setup)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [RODS PDF Generation](#rods-pdf-generation)
- [Running Tests](#running-tests)
- [Sample API Usage](#sample-api-usage)

---

## Features

- **FMCSA HOS Rules Engine** -- Pure Python implementation of all major HOS regulations with no Django dependencies; uses only standard library and dataclasses.
- **Trip Planning** -- Route-based trip planning via the OpenRouteService API. Automatically generates HOS-compliant duty logs with required breaks, rest periods, and fuel stops.
- **RODS PDF Generation** -- Produces Record of Duty Status PDFs by overlaying driver data onto the official `RODs_Ex.pdf` template using ReportLab and PyPDF2.
- **React Frontend** -- Interactive map visualization (Leaflet), 24-hour duty status timeline, trip planning form, and one-click PDF download.
- **JWT Authentication** -- Token-based auth via SimpleJWT with access and refresh tokens.
- **Demo Mode** -- Ships with `AllowAny` permissions and a `seed_data` management command that creates a demo driver with sample trips for quick evaluation.

---

## FMCSA Rules Implemented

The HOS engine (`backend/apps/hos/engine.py`) implements the following regulations from the **Interstate Truck Driver's Guide to HOS (April 2022)**:

| Rule | CFR Reference | Description |
|------|---------------|-------------|
| **14-Hour Driving Window** | 395.3(a)(2) | Drivers may not drive after 14 consecutive hours on duty following 10+ hours off duty |
| **11-Hour Driving Limit** | 395.3(a)(3) | Maximum 11 hours of driving within the 14-hour window |
| **30-Minute Break** | 395.3(a)(3)(ii) | Required 30-minute break after 8 cumulative hours of driving |
| **60/70-Hour Cycle Limit** | 395.3(b) | 60 hours in 7 days or 70 hours in 8 consecutive days |
| **34-Hour Restart** | 395.3(c) | Resets the 60/70-hour cycle after 34 consecutive hours off duty |
| **Sleeper Berth Provision** | 395.1(g) | Split sleeper berth combinations (7/3 or 8/2 splits) |
| **Adverse Driving Exception** | 395.1(b)(1) | Extends driving window by up to 2 hours for adverse conditions |
| **CDL Short-Haul Exception** | 395.1(e)(1) | 150 air-mile radius exemption for CDL drivers |
| **Non-CDL Short-Haul Exception** | 395.1(e)(2) | 150 air-mile radius exemption for non-CDL drivers |
| **16-Hour Short-Haul Exception** | 395.1(o) | One-time 16-hour window extension for short-haul drivers |

---

## Tech Stack

### Backend
- **Django 4.2** with Django REST Framework
- **SimpleJWT** for authentication
- **PostgreSQL** (production) / **SQLite** (development)
- **ReportLab** + **PyPDF2** for PDF generation
- **OpenRouteService API** for route calculations

### Frontend
- **React 18** with **TypeScript 5.5**
- **Vite 5** build tool
- **Tailwind CSS** with **shadcn/ui** components
- **Leaflet** / **React Leaflet** for map visualization
- **TanStack React Query** for server state management
- **Axios** for HTTP requests

### Infrastructure
- **Docker Compose** (PostgreSQL 15, backend, frontend)
- **GitHub Actions** CI pipeline

---

## Project Structure

```
.
├── backend/
│   ├── apps/
│   │   ├── accounts/        # User/driver models, JWT auth endpoints
│   │   ├── hos/             # HOS rules engine, compliance status
│   │   │   ├── engine.py    # Pure Python FMCSA rules engine
│   │   │   └── tests/       # 46 test cases covering all rules
│   │   ├── pdf_gen/         # RODS PDF generation service
│   │   └── trips/           # Trip planning, duty log generation
│   ├── config/              # Django settings, root URL config
│   ├── requirements.txt
│   └── manage.py
├── frontend/
│   └── src/
│       ├── api/             # API client layer
│       ├── components/      # Reusable UI components
│       ├── hooks/           # Custom React hooks
│       ├── pages/           # Page-level components
│       ├── types/           # TypeScript type definitions
│       └── lib/             # Utilities
├── RODs_Ex.pdf              # Official RODS template for PDF overlay
├── eld_template_mapping.json # Coordinate mapping for PDF field positions
├── docker-compose.yml       # PostgreSQL + backend + frontend services
└── .github/workflows/ci.yml # CI pipeline
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- An [OpenRouteService API key](https://openrouteservice.org/) (free tier available)

### Backend

```bash
cd backend
python -m venv ../venv
source ../venv/bin/activate    # On Windows: ..\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data     # Creates demo driver + sample trips
python manage.py runserver
```

The API will be available at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173`.

---

## Docker Setup

Run the entire stack with Docker Compose:

```bash
# Optional: set your ORS API key
export ORS_API_KEY=your_key_here

docker compose up --build
```

This starts:
- **PostgreSQL 15** on port `5432`
- **Django backend** on port `8000`
- **Vite dev server** on port `5173`

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | Auto-generated in dev |
| `DEBUG` | Enable debug mode | `True` |
| `DATABASE_URL` | PostgreSQL connection string | Falls back to SQLite |
| `ORS_API_KEY` | OpenRouteService API key | -- |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend URLs | `http://localhost:5173` |
| `VITE_API_URL` | Backend API base URL (frontend) | `http://localhost:8000` |

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register/` | Create a new driver account |
| `POST` | `/api/auth/login/` | JWT login (returns access + refresh tokens) |
| `POST` | `/api/auth/token/refresh/` | Refresh an expired access token |

### Trips

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/trips/` | List the authenticated driver's trips |
| `POST` | `/api/trips/` | Create a trip (triggers ORS routing + HOS engine) |
| `GET` | `/api/trips/{id}/` | Trip details with stops, duty logs, daily summaries |
| `GET` | `/api/trips/{id}/logs/` | Duty status logs for a specific trip |
| `GET` | `/api/trips/{id}/pdf/` | Download the RODS PDF for a trip |

### HOS

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/hos/status/` | Current HOS compliance status and remaining hours |
| `POST` | `/api/validate/hos/` | Validate arbitrary HOS entries against rules |
| `GET` | `/api/hos/logs/` | List all duty status logs |

### Maps

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/maps/route/` | Route proxy (accepts `coordinates` query param) |

---

## RODS PDF Generation

The system generates official-looking Record of Duty Status documents by overlaying data onto the `RODs_Ex.pdf` template:

1. **Template** -- The `RODs_Ex.pdf` file is the blank RODS form used as the base layer.
2. **Coordinate Mapping** -- `eld_template_mapping.json` defines the exact pixel coordinates for every field on the PDF (driver name, date, carrier, 24-hour grid lines, total hours, etc.).
3. **Overlay Generation** -- `RODSPDFGenerator` (in `backend/apps/pdf_gen/generator.py`) uses **ReportLab** to draw text and duty status grid lines onto a transparent canvas at the mapped coordinates.
4. **Merge** -- **PyPDF2** merges the overlay canvas with the original template page, producing a final PDF that visually matches the official DOT form with the driver's data filled in.

Duty status lines on the 24-hour grid are color-coded:
- **Dark gray** -- Off Duty
- **Dark blue** -- Sleeper Berth
- **Dark green** -- Driving
- **Dark orange** -- On Duty (Not Driving)

---

## Running Tests

The HOS engine has 46 test cases covering all implemented FMCSA rules:

```bash
cd backend
python -m pytest apps/hos/tests/test_engine.py -v
```

To run the full test suite:

```bash
cd backend
python -m pytest
```

Tests are also executed automatically on push and pull request via GitHub Actions.

---

## Sample API Usage

### Create a Trip

```bash
curl -X POST http://localhost:8000/api/trips/ \
  -H "Content-Type: application/json" \
  -d '{
    "current_location": {"lat": 40.7128, "lng": -74.0060, "name": "New York, NY"},
    "pickup_location": {"lat": 39.9526, "lng": -75.1652, "name": "Philadelphia, PA"},
    "dropoff_location": {"lat": 33.7490, "lng": -84.3880, "name": "Atlanta, GA"},
    "cycle_hours_used": 0,
    "options": {"adverse_driving": false}
  }'
```

The response includes the planned route, all generated duty status logs, required rest/break stops, and daily summaries. In demo mode, unauthenticated requests are automatically assigned to the `demo_driver` user.

### Download RODS PDF

```bash
curl -o rods.pdf http://localhost:8000/api/trips/1/pdf/
```

---

## License

This project was built as a technical assessment for Spotter AI.
