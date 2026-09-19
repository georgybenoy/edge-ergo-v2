# EdgeErgo Posture & Well-Being Intelligence Platform

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB.svg?logo=react&logoColor=black)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10.14-FF6F00.svg?logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![PySide6](https://img.shields.io/badge/GUI-PySide6%20Qt-41CD52.svg?logo=qt&logoColor=white)](https://pypi.org/project/PySide6/)
[![Tests](https://img.shields.io/badge/Tests-248%20Passed%20(100%25)-brightgreen.svg?logo=pytest&logoColor=white)](#testing--verification)
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Zero--Media%20Wire%20Audit-success.svg?logo=shield&logoColor=white)](#privacy-guarantees--wire-audit-evidence)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Privacy-Preserving Distributed Edge AI for Real-Time Ergonomic Evaluation & Enterprise Well-Being Intelligence**

[Key Features](#key-features) •
[Architecture](#system-architecture) •
[Quickstart](#quickstart-guide) •
[Hardware Benchmarks](#hardware-benchmarks--sizing) •
[Privacy Audit](#privacy-guarantees--wire-audit-evidence) •
[Documentation](#documentation-directory)

</div>

---

## Overview

**EdgeErgo** is an enterprise-grade, edge-first ergonomics and worker health monitoring system designed to mitigate musculoskeletal disorders (MSD) and workplace fatigue. 

Operating under an uncompromising **Zero-Media Privacy Policy**, EdgeErgo executes computer vision pose estimation, facial blendshape tracking, 3D anatomical vector math, and clinical ergonomic assessments (RULA and REBA) **entirely on the worker's workstation**. 

**Raw video, camera frames, facial crops, and biometric landmarks never touch a disk and never traverse the network.** Only lightweight, anonymized statistical summaries (605 bytes JSON) are synced to an enterprise Central Server, powering a high-performance Executive Analytics Dashboard.

```
┌─────────────────────────────────────────────────────────────┐
│                      WORKSTATION (EDGE)                     │
│  [Camera] ──> [MediaPipe Vision] ──> [3D Geometry & RULA]   │
│                      │                         │            │
│             (RAM-only / 0 Disk)         [Desktop HUD]       │
│                      │                         │            │
│                      ▼                         ▼            │
│               [Local SQLite] ─────────> [Sync Worker]       │
└─────────────────────────────────────────────────────────────┘
                                                 │
                                     Anonymized Telemetry JSON
                                         (605 Bytes / No Media)
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    CENTRAL ENTERPRISE SERVER                │
│   [FastAPI REST API] ──> [SQLite Repository] ──> [Analytics]│
│                                                 │           │
│                                                 ▼           │
│                             [React 18 Executive Dashboard]  │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Features

- **🔒 100% Edge-First Privacy Guarantee**:
  MediaPipe Pose Landmarker Lite and Face Landmarker process frames strictly in-memory. Zero pixel data, zero face embeddings, and zero landmark coordinates are ever stored or transmitted. Verified via packet-level wire captures.
- **📐 Clinical Ergonomic Scoring (RULA & REBA)**:
  Direct implementation of published ergonomic standards. Computes 3D joint angle vectors (neck flexion/extension, trunk lean, shoulder elevation, elbow flexion, wrist deviation) and evaluates official Tables A, B, and C Grand Scores in real time.
- **😊 Non-Invasive Well-Being Expression Classification**:
  Tracks 52 facial blendshapes to categorize aggregate worker affect into 4 high-level states (*Neutral*, *Positive*, *Negative*, *Reduced*) without facial recognition or identity extraction.
- **🖥️ Ambient Desktop Awareness Overlay**:
  Transparent, non-intrusive PySide6 desktop HUD displaying real-time ergonomic risk category (Safe, Attention, High Risk) and micro-break prompts without disrupting employee workflows.
- **⏱️ Temporal Posture Persistence**:
  Eliminates false alarms from momentary posture adjustments. Alerts trigger only when high-risk postures persist continuously ($\ge 20$ seconds), governed by an intelligent 120-second cooldown engine.
- **🌐 Central Analytics Engine & REST Server**:
  FastAPI server providing multi-node fleet management, workstation summaries, hourly posture progressions, break compliance rollups, and CSV data exports.
- **📊 Executive Dark-Mode Dashboard**:
  State-of-the-art React + Vite + TypeScript dashboard built with custom enterprise design tokens (#000000 app canvas, #1D1D1D surfaces, Inter typography, and Recharts data visualizations).
- **📦 Zero-Dependency Packaging**:
  Packaged into a standalone single-file binary (`EdgeErgoAgent.exe`) via PyInstaller, running on bare office PCs with zero pre-installed Python, IDE, or drivers.

---

## System Architecture

```
EDGE-ERGO V3/
├── edge_agent/                     # Workstation Edge Client
│   ├── camera/                     # OpenCV video ingestion (DirectShow / MSMF / V4L2)
│   ├── vision/                     # MediaPipe Pose & Face Landmarker neural pipelines
│   ├── geometry/                   # Pure NumPy 3D joint angle vector math
│   ├── ergonomics/                 # Official RULA & REBA lookup tables & Grand Score engines
│   ├── expression/                 # 52-blendshape facial affect classifier
│   ├── temporal/                   # Posture persistence & session telemetry rollup
│   ├── feedback/                   # Posture recommendations & alert priority queues
│   ├── overlay/                    # PySide6 translucent desktop awareness widget
│   ├── storage/                    # Local SQLite engine (WAL mode, offline buffering)
│   ├── sync/                       # Offline-resilient sync client with exponential backoff
│   ├── health/                     # Autonomous background heartbeat daemon
│   └── config/                     # Edge Agent configuration manager
│
├── central_server/                 # Enterprise Central Server
│   ├── api/                        # REST routes (/edge, /dashboard, /reports, /export)
│   ├── aggregation/                # Multi-node telemetry rollup & mathematical aggregates
│   ├── analytics/                  # Batch workstation comparison & time-series trend engine
│   ├── database/                   # Modularity-abstracted SQLite repository layer
│   ├── reports/                    # Daily, weekly, monthly report generator & PDF builder
│   └── validation/                 # Pydantic v2 strict payload schemas & validators
│
├── dashboard/                      # Executive Web Dashboard
│   ├── src/
│   │   ├── api/                    # Type-safe API client & React query hooks
│   │   ├── components/             # StatCards, RiskBadges, Navbar, Sidebar, Modals
│   │   ├── screens/                # Overview, Workstations, Trends, Reports, Settings
│   │   └── types/                  # TypeScript interface contracts
│   └── tailwind.config.js          # Enterprise Dark SaaS design tokens
│
├── installer/                      # PyInstaller build specs & bundling assets
├── scripts/                        # Operational audit & deployment utilities
│   ├── audit_privacy.py            # Live packet-level wire inspection auditor
│   └── test_clean_environment.ps1  # Automated clean-machine sandbox tester
├── tests/                          # 248 Automated Tests (100% Pass Rate)
│   ├── edge/                       # Vision, geometry, scoring, camera, overlay tests
│   ├── server/                     # API routes, database repository, reports tests
│   ├── integration/                # Multi-node concurrency & failure/privacy suites
│   └── benchmarks/                 # Database scalability & 5,000-window query tests
└── docs/                           # Architecture, benchmark, and DoD reports
```

---

## Hardware Benchmarks & Sizing

The Edge Agent was rigorously benchmarked across 4 hardware profiles on an Intel Core i5-12450HX host using automated `psutil` instrumentation ([`docs/architecture/hardware-benchmark-report.md`](docs/architecture/hardware-benchmark-report.md)):

| Hardware Tier | CPU Core Allocation | Input Resolution | Pose FPS | Face FPS | End-to-End Latency | Sustained Throughput | Process CPU % | Memory (RSS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **High-End Workstation** | 12 Threads (Full) | 1080p (1920x1080) | 43.0 FPS | 138.5 FPS | 30.3 ms | 32.9 FPS | 143.8% | 473.8 MB |
| **Modern Office Desktop** | 12 Threads (Full) | 720p (1280x720) | 45.3 FPS | 171.5 FPS | 27.8 ms | 35.9 FPS | 147.3% | 465.3 MB |
| **Standard Office Laptop** | 4 Threads (2 Cores) | **480p (640x480)** | **59.7 FPS** | **370.9 FPS** | **19.4 ms** | **51.3 FPS** | **111.8%** | **460.3 MB** |
| **Entry-Level Thin Client** | **1 Single Core** | **480p (640x480)** | **60.4 FPS** | **335.6 FPS** | **21.5 ms** | **46.5 FPS** | **84.9%** | **460.5 MB** |
| **Physical Webcam (Live)** | 4 Threads (2 Cores) | 480p (DirectShow) | 37.4 FPS | 251.6 FPS | 79.6 ms | **12.6 FPS (reg.)** | **36.3%** | **239.2 MB** |

### Stability & Zero-Leak Verification
- **Continuous Execution**: 600 consecutive steady-state processing cycles.
- **Memory Drift**: Bounded growth ($< 0.90\text{ MB}$ net variation over hundreds of cycles).
- **Leak Verdict**: `passed_leak_check = True` (Zero memory leaks detected).

### Recommended Hardware Specifications

- **Minimum Spec (Thin Clients / POS / Legacy Desktops)**:
  Dual-Core x86_64 / ARM64 @ 1.8 GHz (AVX2/NEON supported), 4 GB RAM, 640x480 webcam, 300 MB disk.
- **Recommended Production Spec (Standard Corporate PCs)**:
  Quad-Core x86_64 @ 2.4 GHz+ (Intel Core i5 10th Gen+ / AMD Ryzen 5), 8–16 GB RAM, 720p HD webcam, 500 MB SSD.

---

## Privacy Guarantees & Wire Audit Evidence

EdgeErgo complies with the strictest enterprise data privacy regulations (GDPR, HIPAA, and internal enterprise worker monitoring standards):

| Data Class | Processed In-Memory? | Stored on Local Disk? | Transmitted Over Network? |
| :--- | :---: | :---: | :---: |
| **Raw Camera Frames** | ✅ (Overwritten each frame) | ❌ **NEVER** | ❌ **NEVER** |
| **Facial Crops & Images** | ❌ **NEVER** | ❌ **NEVER** | ❌ **NEVER** |
| **Biometric Landmark Coordinates** | ✅ (Transitory in RAM) | ❌ **NEVER** | ❌ **NEVER** |
| **RULA / REBA Grand Scores** | ✅ | ✅ (Local SQLite) | ✅ (Anonymized JSON) |
| **Facial Affect Percentages** | ✅ | ✅ (Local SQLite) | ✅ (Anonymized JSON) |

### Live Network Traffic Audit ([`scripts/audit_privacy.py`](scripts/audit_privacy.py))

```text
------------------------------------------------------------------------
                  TRAFFIC INSPECTION LOG
------------------------------------------------------------------------
Endpoint                         | Bytes    | Media Content  | Status
------------------------------------------------------------------------
/api/v1/edge/heartbeat           | 74       | NONE (0 bytes) | PASSED
/api/v1/edge/assessment          | 605      | NONE (0 bytes) | PASSED
------------------------------------------------------------------------
>>> AUDIT RESULT: PASSED (100% Zero-Media Privacy Enforcement)
    No pixels, frames, video streams, or facial geometry on the wire.
```

#### Actual Transmitted Wire Payload (`POST /api/v1/edge/assessment`):
```json
{
  "window_id": "SESS-AUDIT-1789824058_2026-09-19T13:20:58.620842+00:00",
  "device_id": "NODE-001",
  "session_id": "SESS-AUDIT-1789824058",
  "window_start": "2026-09-19T13:20:58.620842+00:00",
  "window_end": "2026-09-19T13:20:59.072119+00:00",
  "ergonomics": {
    "average_rula": 1.0,
    "maximum_rula": 1,
    "average_reba": 1.0,
    "maximum_reba": 1,
    "high_risk_percentage": 0.0,
    "dominant_posture": "NEUTRAL"
  },
  "facial_expression": {
    "neutral_percentage": 100,
    "positive_percentage": 0,
    "negative_percentage": 0,
    "reduced_expression_percentage": 0
  },
  "breaks": {
    "breaks_recommended": 0,
    "breaks_acknowledged": 0
  }
}
```

---

## Quickstart Guide

### Option 1: Standalone Windows Executable (Production)

To deploy on worker machines without installing Python or dependencies:
1. Download or locate `dist/EdgeErgoAgent.exe` (142.9 MB self-contained bundle).
2. Launch the agent:
   ```cmd
   EdgeErgoAgent.exe --server-url http://central-server-ip:8000
   ```
3. The desktop overlay will appear in the screen corner, automatically initializing camera capture, registering with the server, and beginning posture monitoring.

---

### Option 2: Developer Environment Setup

#### Prerequisites
- **Python 3.10+** (Python 3.10.11 recommended)
- **Node.js 18+** & **npm** (for Central Dashboard)
- USB or integrated webcam

#### 1. Clone & Initialize Environment
```bash
git clone https://github.com/your-org/edge-ergo.git
cd edge-ergo

# Create virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Start Central Server
```bash
uvicorn central_server.main:app --host 0.0.0.0 --port 8000 --reload
```
* Central Server API Docs: `http://localhost:8000/docs`
* OpenAPI JSON Spec: `http://localhost:8000/openapi.json`

#### 3. Start Edge Agent
In a separate terminal (with virtual environment active):
```bash
python -m edge_agent.main --server-url http://localhost:8000
```
* To run in headless mode (no camera / synthetic testing):
  ```bash
  python -m edge_agent.main --headless --no-camera
  ```

#### 4. Launch React Executive Dashboard
In a separate terminal:
```bash
cd dashboard
npm install
npm run dev
```
* Access Dashboard UI: `http://localhost:5173`

---

## Testing & Verification

EdgeErgo includes comprehensive unit, integration, failure, and scalability benchmark suites:

```bash
# Run the complete test suite (248 tests)
pytest -q

# Run Failure & Privacy integration tests (29 tests)
pytest tests/integration/test_failure_privacy.py -v

# Run Multi-Node concurrency tests (simulating NODE-001..NODE-004)
pytest tests/integration/test_multi_node.py -v

# Run 5,000-window database scalability benchmark
pytest tests/benchmarks/test_analytics_perf.py -v

# Execute real-time network traffic privacy audit
python scripts/audit_privacy.py

# Run automated multi-hardware benchmark
python tests/edge/benchmark.py --profile all --frames 100 --stability
```

### Full Regression Output
```text
........................................................................ [ 28%]
........................................................................ [ 57%]
........................................................................ [ 85%]
....................................                                     [100%]
======================= 248 passed, 4 skipped in 28.43s =======================
```

---

## Configuration Reference (`edge_config.json`)

The Edge Agent can be customized via local JSON configuration or remote server overrides:

```json
{
  "device_id": "NODE-001",
  "device_name": "Workstation-Office-4A",
  "server_url": "http://localhost:8000",
  "camera_index": 0,
  "capture_fps": 10,
  "frame_width": 640,
  "frame_height": 480,
  "analysis_interval_sec": 1.0,
  "telemetry_window_sec": 300,
  "persistence_threshold_sec": 20.0,
  "alert_cooldown_sec": 120.0,
  "heartbeat_interval_sec": 60,
  "sync_interval_sec": 30,
  "backoff_base_sec": 2.0,
  "backoff_max_sec": 300.0,
  "rula_alert_threshold": 5,
  "reba_alert_threshold": 5,
  "break_interval_min": 45
}
```

---

## Documentation Directory

| Document | Purpose & Scope |
| :--- | :--- |
| [`docs/architecture/final-success-criteria-checklist.md`](docs/architecture/final-success-criteria-checklist.md) | **Formal Sign-Off**: 100% audit of all 38 PRD §112–114 & §122 requirements |
| [`docs/architecture/failure-privacy-report.md`](docs/architecture/failure-privacy-report.md) | **Fault & Privacy Report**: 8 failure modes, network outage tests, wire captures |
| [`docs/architecture/hardware-benchmark-report.md`](docs/architecture/hardware-benchmark-report.md) | **Hardware Sizing**: Latency waterfalls, multi-tier CPU profiling, memory drift |
| [`docs/architecture/multi-node-test-report.md`](docs/architecture/multi-node-test-report.md) | **Multi-Node Concurrency**: Multi-node isolation, health status, and sync recovery |
| [`docs/deployment/clean-computer-test-report.md`](docs/deployment/clean-computer-test-report.md) | **Clean-Room Test**: Verification on pristine Windows environment without Python |
| [`docs/deployment/INSTALL.md`](docs/deployment/INSTALL.md) | **Installation Guide**: Complete enterprise deployment procedures for Edge & Server |
| [`docs/architecture/CONVENTIONS.md`](docs/architecture/CONVENTIONS.md) | **Engineering Standards**: Architectural layer boundaries and privacy logging rules |

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
