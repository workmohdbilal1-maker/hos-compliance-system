# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-09

### Added

- **HOS Engine** -- Pure Python FMCSA HOS compliance engine implementing 10 rules from 49 CFR Part 395:
  - 14-Hour Driving Window (395.3(a)(2))
  - 11-Hour Driving Limit (395.3(a)(3))
  - 30-Minute Rest Break (395.3(a)(3)(ii))
  - 60/70-Hour On-Duty Cycle Limit (395.3(b))
  - 34-Hour Restart (395.3(c))
  - Sleeper Berth Provision (395.1(g))
  - Adverse Driving Conditions Exception (395.1(b)(1))
  - CDL Short-Haul Exception (395.1(e)(1))
  - Non-CDL Short-Haul Exception (395.1(e)(2))
  - 16-Hour Short-Haul Exception (395.1(o))
- **Trip Planning** -- Route-based trip planning via OpenRouteService API with automatic HOS-compliant duty log generation including required breaks, rest periods, and fuel stops.
- **RODS PDF Generation** -- Record of Duty Status PDF generation by overlaying driver data onto the official RODs_Ex.pdf template using ReportLab and PyPDF2.
- **Django REST API** -- Full CRUD API with JWT authentication for trips, duty logs, HOS status, and route planning.
- **React Frontend** -- Interactive map visualization (Leaflet), 24-hour duty status timeline, trip planning form, and one-click PDF download.
- **Test Suite** -- 46 unit tests covering all FMCSA rules plus 10 canonical compliance verification scenarios.
- **Documentation** -- Architecture diagram, FMCSA rule mapping, API reference, development and production deployment guides.
- **Docker Support** -- Docker Compose configuration for full-stack local development (PostgreSQL, Django, Vite).
- **CI/CD** -- GitHub Actions pipeline running backend tests and frontend build on push/PR.
- **Seed Data** -- Management command to create demo driver with sample trips and historical duty logs.
