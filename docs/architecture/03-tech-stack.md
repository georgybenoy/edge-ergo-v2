# 03. Technology Stack

EdgeErgo is built upon a lightweight, modular technology stack specifically selected to maximize edge processing performance, minimize workstation resource consumption, eliminate cloud infrastructure dependencies, and ensure frictionless deployment.

---

## 1. Stack Summary

> **One-Line Stack Summary:**  
> **Python 3.10 + OpenCV + MediaPipe + PySide6 + SQLite on the Edge Node; FastAPI + Uvicorn + SQLite + React/Vite on the Central Server.**

---

## 2. Technology Selection Matrix by Layer

### 2.1 Edge Agent (Worker PC)
The Edge Agent runs directly on standard office hardware. Its dependencies are chosen to guarantee smooth execution without requiring dedicated GPUs (PRD §12.1; TECH §1).

| Technology | Role / Purpose | Architectural Justification |
| :--- | :--- | :--- |
| **Python 3.10** | Core Edge Runtime | Standardized, robust ecosystem for computer vision and numerical computing; rapid development speed; extensive packaging support. |
| **OpenCV (4.11)** | Frame Acquisition & Preprocessing | Industry-standard hardware camera interface. Highly optimized C++ backend provides low-overhead frame capture, direct color conversions (BGR to RGB), and downscaling (to 320×240) in under 2 ms. |
| **MediaPipe Pose (0.10)** | 33-Landmark Skeletal Tracking | Google's lightweight ML pipeline utilizing BlazePose. Runs smoothly on consumer laptop CPUs (15–30 ms inference), accurately estimating 3D coordinates for neck, shoulders, elbows, wrists, hips, and knees without GPU acceleration. |
| **MediaPipe Face Mesh (0.10)** | Facial Landmark Detection | Tracks dense facial fiducial markers with negligible computational overhead. Enables geometric extraction of Eye Aspect Ratio (EAR), mouth movement, and facial tilt without requiring heavy deep neural nets. |
| **NumPy (1.26)** | Vector Kinematics & Geometry | Vectorized 3D Euclidean geometry and linear algebra. Computes spatial joint angles using vector dot products ($\cos\theta = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|\|\mathbf{v}\|}$) in sub-millisecond execution times. |
| **Python Ergonomics Engine** | RULA & REBA Scoring Tables | Pure deterministic Python lookup algorithms implementing standard ergonomic scoring tables. Decoupled completely from computer vision code to facilitate independent unit testing and calibration. |
| **PySide6 (Qt 6.8)** | Native Worker Desktop Overlay | Official Python bindings for Qt. Provides hardware-accelerated, transparent, click-through, always-on-top desktop widgets. Consumes ~40 MB RAM—far superior to heavy Chromium/Electron web wrappers on worker endpoints. |
| **SQLite (3.x embedded)** | Local Storage & Sync Queue | Zero-configuration, serverless, single-file ACID transactional database. Provides rock-solid local storage for session metrics and persists the offline sync queue across system reboots. |

### 2.2 Central Server (Backend)
The Central Server aggregates telemetry, validates data contracts, manages node records, and delivers analytical data (PRD §13; TECH §2).

| Technology | Role / Purpose | Architectural Justification |
| :--- | :--- | :--- |
| **Python 3.10** | Core Server Runtime | Consistent runtime across edge and central codebases, enabling shared data models and validation schemas. |
| **FastAPI (0.111)** | High-Performance REST API | Modern, asynchronous ASGI framework based on Starlette. Delivers microsecond routing performance, auto-generates interactive OpenAPI/Swagger documentation, and natively integrates with Pydantic for validation. |
| **Uvicorn (0.30)** | ASGI Web Server | Lightning-fast, event-driven asynchronous server implementation based on `uvloop` and `httptools`. Handles concurrent edge node ingestion streams effortlessly. |
| **Pydantic v2 (2.13)** | Data Contract Validation | Enforces strict, type-safe validation on incoming telemetry payloads. Rejects corrupted, malformed, or out-of-spec JSON packets at the network perimeter. |
| **SQLite / SQLAlchemy (2.0)** | Central Data Persistence | Embedded relational database engine. Offers zero-configuration deployment for laboratory and small/medium enterprise setups. Managed via SQLAlchemy ORM to ensure seamless database modularity. |
| **Pandas (2.3)** | Analytics & Aggregation Engine | Efficient multi-node data manipulation. Generates daily workstation rollups, statistical percentiles, temporal heatmaps, and organizational risk distributions. |
| **ReportLab (3.x/4.x)** | PDF Report Generation | Enterprise programmatic PDF generation library. Synthesizes structured, publication-quality executive ergonomic compliance reports. |

### 2.3 Administrative Dashboard (Frontend)
The Central Dashboard provides occupational health officers and system administrators with a visual overview of workplace ergonomic health (PRD §13, §61; DESIGN §1).

> [!IMPORTANT]
> **Strict Separation of UI Technologies:** React is used **exclusively** for the Central Dashboard served to administrative web browsers. It is **never** installed or executed on worker edge workstations (PRD §12, §14).

| Technology | Role / Purpose | Architectural Justification |
| :--- | :--- | :--- |
| **React 18** | Web Dashboard SPA | Component-driven, declarative frontend library for dynamic UI updates, modular analytical widgets, and reactive state management. |
| **Vite** | Frontend Build Tool | Ultra-fast native ES-module development server and optimized Rollup bundler producing compact production assets. |
| **Tailwind CSS / CSS Tokens** | UI Styling System | High-performance utility styling adhering strictly to the enterprise dark analytics theme specified in the EdgeErgo Design System. |
| **Lucide React / Chart.js** | Icons & Data Visualization | Lightweight, clean icon set combined with responsive, hardware-accelerated canvas charts for ergonomic distribution graphs and temporal trends. |

### 2.4 Communication & Networking
Connecting Edge Nodes to the Central Server across the organizational LAN (PRD §41, §64; TECH §4).

| Technology | Role / Purpose | Architectural Justification |
| :--- | :--- | :--- |
| **HTTP / REST** | Network Protocol | Standard, stateless, firewall-friendly request-response protocol. Operates seamlessly across corporate switches without requiring specialized network configurations or open WebSocket tunnels. |
| **JSON** | Serialization Standard | Universal, human-readable, compact text format. Ensures total transparency during privacy audits and zero binary payload obfuscation. |
| **Requests / Urllib3** | Edge HTTP Client | Robust synchronous HTTP client library on the Edge Agent. Features configurable timeouts, connection pooling, and structured error handling for network outages. |

### 2.5 Deployment & Packaging
Packaging the system for frictionless distribution across varied environments (PRD §70–§73; TECH §5).

| Technology | Role / Purpose | Architectural Justification |
| :--- | :--- | :--- |
| **PyInstaller (6.x)** | Standalone Edge Executable | Packages the Python interpreter, OpenCV binaries, MediaPipe inference graphs, PySide6 Qt libraries, and Edge Agent code into a standalone Windows binary (`EdgeErgoAgent.exe`). Eliminates user Python installation dependencies. |
| **Windows Inno Setup / Batch** | Windows Installer / Launcher | Turnkey installer script providing automated desktop shortcuts, initial directory provisioning, and optional startup registration. |
| **FastAPI Static Mount** | Single-Server Production Host | FastAPI serves the compiled React production bundle directly (`/dashboard`), enabling the entire central server and dashboard to run as a single process on port 8000. |

---

## 3. Database Architecture & Scalability Strategy

EdgeErgo adopts a phased database strategy designed to balance immediate ease of deployment with long-term enterprise scalability (PRD §13, §48; TECH §2):

```
+-----------------------------------------------------------------------------+
|                           DATABASE ARCHITECTURE                             |
|                                                                             |
|      +-------------------------+            +-------------------------+     |
|      |    Edge Node Storage    |            |   Central Server Storage|     |
|      |     (Local SQLite)      |            |     (Modular Engine)    |     |
|      +------------+------------+            +------------+------------+     |
|                   |                                      |                  |
|                   v                                      v                  |
|      [edgeergo_local.db]                    [SQLAlchemy Repository Layer]   |
|      - Single-file                          - Decoupled abstraction         |
|      - Embedded engine                      - Connection-agnostic           |
|      - Zero network latency                                |                |
|      - Instant offline buffer                +-------------+-------------+  |
|                                              |                           |  |
|                                              v                           v  |
|                                    [Initial Prototype]          [Future Enterprise]
|                                    SQLite Database              PostgreSQL Engine   |
|                                    (edgeergo_central.db)        (Multi-tenant pool) |
+-----------------------------------------------------------------------------+
```

### Why SQLite First?
1. **Zero Configuration**: Eliminates the requirement to install, configure, secure, and maintain a dedicated database daemon (such as MySQL or PostgreSQL) for academic evaluation and initial workplace trials.
2. **Deterministic Reliability**: SQLite is self-contained, serverless, and transactional. If the central machine reboots, database recovery is instant without lockfile corruption.
3. **Sufficient Capacity**: Telemetry records are compact JSON summaries (~1 KB per 5-minute window). A 50-node enterprise generates ~4,800 records daily (~4.8 MB/day, or ~1.7 GB/year), which is well within SQLite's proven multi-gigabyte efficiency envelope.

### Modular DB Layer for Future PostgreSQL Migration
To prevent vendor lock-in, the Central Server repository layer utilizes SQLAlchemy 2.0 ORM models and standard repository patterns. Queries avoid SQLite-specific dialect extensions (PRD §48). Migrating to PostgreSQL for large enterprise deployments (>100 nodes) requires only modifying the database connection URI in the environment configuration (`DATABASE_URL=postgresql://user:pass@localhost:5432/edgeergo`), with zero alterations to core business logic.

---

## Related Documents
- [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md) — High-level goals and constraints.
- [02-system-architecture.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/02-system-architecture.md) — Two-layer architectural design.
- [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md) — Detailed edge pipeline implementation.
- [07-data-models.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/07-data-models.md) — Edge and Central SQLite schemas.
- [deployment-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/deployment/deployment-overview.md) — Standalone compilation and hosting.
