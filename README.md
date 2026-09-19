# EdgeErgo

**Privacy-preserving distributed Edge AI for ergonomic and facial-expression monitoring
at computer workstations.**

EdgeErgo runs independent Edge Agents on each worker's PC to capture camera frames,
perform real-time pose estimation (RULA/REBA) and broad facial-expression classification
entirely on-device using MediaPipe, and deliver instant posture feedback through a
desktop overlay. Raw video, camera frames, face crops, and facial-landmark images
**never leave the worker's machine**. Only small, anonymized JSON telemetry summaries
are transmitted to a Central Server, which aggregates data across workstations and
powers an admin dashboard with trend analytics, CSV exports, and periodic reports.

---

## Repository Layout

```
EdgeErgo/
├── edge_agent/          # Python Edge Agent (runs on every worker PC)
│   ├── main.py          #   entry point — orchestrates the analysis loop
│   ├── camera/          #   OpenCV frame capture
│   ├── vision/          #   MediaPipe pose & face engines, preprocessing
│   ├── geometry/        #   pure angle/vector math (no ergo dependency)
│   ├── ergonomics/      #   RULA & REBA scoring tables + orchestrator
│   ├── expression/      #   broad facial-expression classifier
│   ├── temporal/        #   windowed telemetry aggregation
│   ├── feedback/        #   alert engine, recommendations, break scheduler
│   ├── overlay/         #   PySide6 desktop overlay widget
│   ├── storage/         #   local SQLite database
│   ├── sync/            #   server sync client (offline-resilient)
│   ├── config/          #   configuration manager
│   └── health/          #   heartbeat client
├── central_server/      # FastAPI Central Server
│   ├── main.py          #   app factory + static-file serving
│   ├── api/             #   REST routers (edge, dashboard, reports)
│   ├── aggregation/     #   telemetry rollup engine
│   ├── analytics/       #   trend & comparative analytics
│   ├── database/        #   central SQLite (Postgres-swappable)
│   ├── reports/         #   report generator (daily/weekly/monthly)
│   └── validation/      #   Pydantic request/response models
├── dashboard/           # React + Vite + TypeScript + Tailwind CSS
├── installer/           # PyInstaller packaging for the Edge Agent
├── tests/               # pytest — edge/, server/, integration/
├── docs/                # architecture, deployment, API, research
├── requirements.txt     # Python dependencies
└── README.md
```

## Quick Start — Development Environment

### Prerequisites

- **Python 3.11+** (3.12 recommended)
- **Node.js 18+** (for the dashboard, scaffolded in Phase 14)
- **Git**
- A webcam (for Edge Agent testing)

### 1. Clone and create a virtual environment

```bash
git clone <repo-url> EdgeErgo
cd EdgeErgo

python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Run tests

```bash
pytest
```

### 4. (Later) Dashboard

The React dashboard is scaffolded in Phase 14. Until then, see
`dashboard/package.json` for planned dependencies.

---

## Privacy Guarantees

| Data type | Stored locally? | Transmitted? |
|---|---|---|
| Raw camera frames | **Never** (in-memory only) | **Never** |
| Face crops / landmark images | **Never** | **Never** |
| RULA/REBA scores | ✅ local SQLite | ✅ as anonymized JSON |
| Expression categories | ✅ local SQLite | ✅ as anonymized JSON |
| Telemetry window summaries | ✅ local SQLite | ✅ JSON to Central Server |

## License

This project is developed as a solo final-year B.Tech Computer Science project.
