# 12. Repository Structure

This document provides a comprehensive structural guide to the EdgeErgo codebase, documenting the role and responsibility of every directory, module, and configuration file in accordance with the project layout standard (PRD §91).

---

## 1. High-Level Architectural Layout

The repository is organized into five decoupled operational subsystems: the autonomous **Edge Agent**, the asynchronous **Central Server**, the administrative **React Dashboard**, the standalone **PyInstaller Packaging Suite**, and the automated **Verification & Testing Framework**.

```
EDGE-ERGO V3/
├── edge_agent/           # Autonomous Python Edge Client application
├── central_server/       # FastAPI asynchronous ingestion & analytics backend
├── dashboard/            # Administrative Analytics React SPA (Vite + Tailwind)
├── installer/            # PyInstaller build recipes and distribution launchers
├── scripts/              # Automated privacy audit and presentation seeding utilities
├── tests/                # Comprehensive unit, integration, and benchmark test suites
└── docs/                 # Formal architecture, API, deployment, and research docs
```

---

## 2. Directory & File Manifest

### 2.1 Edge Agent (`edge_agent/`)
The client-side background application deployed to worker workstations (PRD §10, §91):

```
edge_agent/
├── __init__.py                # Package initialization
├── main.py                    # Edge Agent entry point and lifecycle orchestrator
├── camera/
│   ├── __init__.py
│   └── camera.py              # OpenCV video capture, device enumeration, and retry loop
├── config/
│   ├── __init__.py
│   └── config_manager.py      # Local JSON configuration parser and schema defaults
├── ergonomics/
│   ├── __init__.py
│   ├── rula.py                # Pure RULA tabular scoring and Grand Score lookup
│   ├── reba.py                # Pure REBA tabular scoring and Grand Score lookup
│   └── scoring.py             # Ergonomic score aggregator and risk tier mapper
├── expression/
│   ├── __init__.py
│   └── classifier.py          # Geometric ratio classifier (EAR, MAR, Brow Furrow)
├── feedback/
│   ├── __init__.py
│   ├── alert_engine.py        # Posture warning evaluator and priority arbitrator
│   ├── recommendations.py    # Non-intrusive postural coaching tip generator
│   └── scheduler.py           # Duty cycle and sampling duration timer
├── geometry/
│   ├── __init__.py
│   └── angle_calculator.py    # NumPy 3D spatial vector dot-product angle math
├── health/
│   ├── __init__.py
│   └── heartbeat.py           # Periodic liveness telemetry dispatcher
├── models/
│   ├── face_landmarker.task   # MediaPipe optimized Face Mesh binary model graph
│   └── pose_landmarker_lite.task # MediaPipe BlazePose Lite model graph
├── overlay/
│   ├── __init__.py
│   └── overlay.py             # Hardware-accelerated PySide6 translucent desktop UI
├── storage/
│   ├── __init__.py
│   └── local_db.py            # Local SQLite schema management and transaction handler
├── sync/
│   ├── __init__.py
│   └── server_sync.py         # Asynchronous HTTP sync queue processor and backoff worker
├── temporal/
│   ├── __init__.py
│   └── analyzer.py            # Temporal posture persistence accumulator and cooldown filter
└── vision/
    ├── __init__.py
    ├── preprocessing.py       # Frame resizing (320x240) and color conversions
    ├── pose_engine.py         # MediaPipe Pose landmark inference pipeline
    └── face_engine.py         # MediaPipe Face landmark inference pipeline
```

---

### 2.2 Central Server (`central_server/`)
The centralized ingestion backend and analytical clearinghouse (PRD §11, §91):

```
central_server/
├── __init__.py                # Package initialization
├── main.py                    # FastAPI application setup, middleware, and route mounting
├── aggregation/
│   ├── __init__.py
│   └── aggregator.py          # Daily workstation rollups and collective trend synthesizer
├── analytics/
│   ├── __init__.py
│   └── analytics.py           # Statistical percentile calculations and risk distribution engine
├── api/
│   ├── __init__.py
│   ├── edge.py                # Node registration, heartbeat, and telemetry endpoints
│   ├── dashboard.py           # Administrative analytics and device management endpoints
│   └── reports.py             # Report generation triggers and file download routes
├── database/
│   ├── __init__.py
│   └── database.py            # SQLAlchemy database engine, session factory, and central models
├── reports/
│   ├── __init__.py
│   └── report_generator.py    # ReportLab PDF synthesis and CSV tabular flat-file exporter
└── validation/
    ├── __init__.py
    └── validators.py          # Pydantic v2 schemas and JSON contract boundary checks
```

---

### 2.3 Administrative Dashboard (`dashboard/`)
The modern dark-mode analytics single-page application (PRD §13, §61; DESIGN §1):

```
dashboard/
├── index.html                 # HTML5 SPA host shell
├── package.json               # Node.js dependencies (React 18, Lucide, Tailwind, Vite)
├── vite.config.ts             # Vite bundler configuration and proxy rules
├── tailwind.config.js         # Design token palette and enterprise dark-theme utility rules
├── src/
│   ├── main.tsx               # React application DOM mount
│   ├── App.tsx                # SPA router and global layout controller
│   ├── index.css              # Base CSS layer, typography tokens, and custom scrollbars
│   ├── charts/
│   │   ├── PostureBreakdownBar.tsx  # Segmented horizontal risk distribution bar
│   │   ├── PostureRiskTimeline.tsx  # Chronological line chart of day-long RULA/REBA scores
│   │   ├── RiskDonutChart.tsx       # Circular proportional breakdown of risk tiers
│   │   └── RiskForecastChart.tsx    # Predictive trend projection widget
│   ├── components/
│   │   ├── AppShell.tsx             # Responsive dark-theme sidebar and header navigation
│   │   ├── KPICard.tsx              # Large metric card with comparison badge and subtext
│   │   ├── Card.tsx                 # Standard rounded dark surface container
│   │   ├── AlertCard.tsx            # Prioritized notification card with status badge
│   │   ├── InsightCard.tsx          # Analytical finding summary container
│   │   ├── Modal.tsx                # Accessible backdrop dialog overlay
│   │   └── PageHeader.tsx           # Standard title, breadcrumb, and action button bar
│   ├── pages/
│   │   ├── DashboardPage.tsx        # Executive summary view with macro organizational KPIs
│   │   ├── WorkersPage.tsx          # Workstation directory table with sorting and filters
│   │   ├── AnalyticsPage.tsx        # Deep-dive ergonomic and expression breakdown views
│   │   ├── AlertsPage.tsx           # Central audit log of high-risk posture events
│   │   ├── DevicesPage.tsx          # Hardware status, versions, and heartbeat liveness view
│   │   └── ReportsPage.tsx          # Report generator, date range selectors, and CSV exports
│   ├── services/
│   │   └── api.ts                   # Axios/Fetch client wrapper for Central Server REST routes
│   └── types/
│       └── dashboard.ts             # TypeScript interfaces mirroring server API payloads
```

---

### 2.4 Installer & Packaging (`installer/`)
Packaging tooling for standalone deployment (PRD §70–§73):

```
installer/
├── EdgeErgoAgent.spec         # PyInstaller build specification with bundled MediaPipe models
├── build_agent.py             # Automated build script invoking PyInstaller
├── start_agent.bat            # Windows launcher script for local Edge Agent execution
└── start_server.bat           # Windows launcher script for Central Server and Dashboard
```

---

### 2.5 Verification & Audit Scripts (`scripts/`)
Automated audit and testing tools:

```
scripts/
├── audit_privacy.py           # Sniffs network traffic to verify zero raw image/video transmission
├── seed_presentation_data.py  # Generates realistic synthetic multi-workstation test datasets
└── test_clean_environment.ps1 # Validates deployment on pristine Windows machines without Python
```

---

### 2.6 Test Suite (`tests/`)
Comprehensive multi-tier verification matrix (PRD §83–§85):

```
tests/
├── edge/                      # Edge Agent unit and benchmark tests
│   ├── test_camera.py         # Validates camera access and graceful failure handling
│   ├── test_geometry.py       # Validates 3D vector angle calculation against known coordinates
│   ├── test_ergonomics.py     # Validates RULA and REBA tables against benchmark postures
│   ├── test_face_engine.py    # Validates landmark extraction and EAR/MAR ratio calculations
│   ├── test_expression.py    # Validates 4-tier expression classification logic
│   └── benchmark.py           # Measures CPU inference latency and memory consumption
├── server/                    # Central Server unit and API tests
│   ├── test_edge_api.py       # Validates node registration, heartbeats, and telemetry ingestion
│   ├── test_dashboard_api.py  # Validates dashboard aggregation and query routes
│   ├── test_analytics.py      # Validates mathematical rollups and percentile aggregations
│   └── test_reports.py        # Validates CSV generation and PDF synthesis
├── integration/               # Distributed integration test suites
│   ├── test_multi_node.py     # Simulates 10 concurrent nodes transmitting to one server
│   └── test_failure_privacy.py # Validates offline queuing and zero-leakage network boundaries
└── benchmarks/
    └── test_analytics_perf.py # Benchmarks SQLite query throughput under 100,000 window records
```

---

### 2.7 Documentation Suite (`docs/`)
Structured project documentation:

```
docs/
├── README.md                  # Master documentation index and reading paths
├── DEVELOPMENT_PLAN.md        # 20-phase sequential development plan and deliverables
├── OPEN_QUESTIONS.md          # Open technical questions and benchmark dependencies
├── ROADMAP_AND_FUTURE_WORK.md # Future roadmap enhancements and scaling milestones
├── architecture/              # 12 detailed architectural specification documents
├── api/                       # REST API contracts and telemetry schema definitions
├── deployment/                # Packaging, installation, and configuration guides
├── research/                  # Evaluator primers, glossary, testing strategy, and viva Q&A
└── source/                    # Authoritative PRD, TECH, and DESIGN source PDFs
```

---

## Related Documents
- [02-system-architecture.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/02-system-architecture.md) — Two-layer distributed design.
- [03-tech-stack.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/03-tech-stack.md) — Technology stack selections.
- [DEVELOPMENT_PLAN.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/DEVELOPMENT_PLAN.md) — Phase-by-phase development roadmap.
