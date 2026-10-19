# Deployment Overview

This document specifies the deployment architecture, build procedures, runtime requirements, and first-run pairing workflows for both the **Edge Agent** and the **Central Server** (PRD §70–§73; TECH §5).

---

## 1. Deployment Topology Summary

EdgeErgo is distributed as two independent deployable packages:
1. **Edge Agent Deployment**: A standalone Windows executable (`EdgeErgoAgent.exe`) compiled via PyInstaller, requiring zero pre-installed Python runtime, zero administrative privileges, and zero cloud accounts.
2. **Central Server & Dashboard Deployment**: A unified FastAPI application that serves both the high-concurrency REST API and the pre-compiled React administrative dashboard SPA from a single network port (default: `8000`).

```
+=============================================================================+
|                          DEPLOYMENT ARCHITECTURE                            |
|                                                                             |
|   WORKER WORKSTATIONS (Win 10/11)               ON-PREMISE SERVER           |
|                                                                             |
|   +-----------------------------+               +-----------------------+   |
|   | EdgeErgoAgent.exe           |               | Central Server Host   |   |
|   | - Bundled Python 3.10       |               | - Python 3.10 + ASGI  |   |
|   | - OpenCV & MediaPipe Models |               | - FastAPI Backend     |   |
|   | - PySide6 Desktop Overlay   | -- HTTP LAN-> | - React Dashboard SPA |   |
|   | - Local SQLite DB           |   Port 8000   | - Central SQLite DB   |   |
|   +-----------------------------+               +-----------------------+   |
+=============================================================================+
```

---

## 2. Edge Agent Packaging (PyInstaller)

Worker computers in corporate and educational environments typically lack Python interpreters, developer tools, or C++ build environments. The Edge Agent is therefore packaged into a turnkey standalone Windows distribution (PRD §70, §71):

### 2.1 The Packaging Pipeline ([`installer/EdgeErgoAgent.spec`](file:///c:/Users/georg/EDGE-ERGO%20V3/installer/EdgeErgoAgent.spec))
The PyInstaller specification bundles:
- The Python 3.10 standard library and runtime.
- OpenCV dynamic link libraries (`opencv_world*.dll`).
- PySide6 Qt platform plugins and Qt6Core/Qt6Gui/Qt6Widgets libraries.
- Pre-trained MediaPipe binary task graphs (`pose_landmarker_lite.task` and `face_landmarker.task`).
- Pure Python kinematics and scoring rules.

### 2.2 Building the Edge Executable
To generate the standalone executable from the project root:
```bash
# Activate build virtual environment
venv\Scripts\activate

# Execute packaging builder
python installer/build_agent.py
```
The output is written to `installer/dist/EdgeErgoAgent/`:
- `EdgeErgoAgent.exe`: Main binary launcher.
- `models/`: Bundled MediaPipe task assets.
- `edge_config.json`: Default configuration template.

---

## 3. Central Server & Dashboard Deployment

The Central Server is packaged to run as a consolidated service on a Windows or Linux server on the organization's local network (PRD §72, §73):

### 3.1 Building the React Dashboard SPA
The administrative frontend is compiled into production-optimized static assets:
```bash
cd dashboard
npm install
npm run build
```
This generates the optimized bundle in `dashboard/dist/` (HTML, minified JavaScript, CSS, and SVG assets).

### 3.2 Unified Serving via FastAPI
FastAPI mounts the compiled React distribution directly at the root or `/dashboard` prefix, eliminating the need for a separate Nginx web server for small-to-medium deployments:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="EdgeErgo Central Server")

# Mount API Routers
app.include_router(edge_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")

# Mount Dashboard SPA
app.mount("/dashboard", StaticFiles(directory="dashboard/dist", html=True), name="dashboard")
```

### 3.3 Running the Production Server
The backend is launched using Uvicorn across the local network interface:
```bash
# Windows launch script
installer\start_server.bat

# Manual CLI invocation
uvicorn central_server.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 4. First-Run Discovery & Workstation Pairing

When an Edge Node is launched for the first time on a new workstation, it executes an interactive enrollment and calibration flow (PRD §43):

```mermaid
sequenceDiagram
    autonumber
    participant Worker as Worker User
    participant Agent as EdgeErgoAgent.exe
    participant Central as Central Server (Port 8000)

    Worker->>Agent: Launch EdgeErgoAgent.exe
    Agent->>Agent: Inspect edge_config.json (node_id or server_url missing)
    Agent->>Worker: Display Setup & Pairing Wizard
    
    Worker->>Agent: Enter Server URL (e.g., http://192.168.1.100:8000)
    Worker->>Agent: Enter Assigned Node ID (e.g., NODE-001) or Select Auto-ID
    Worker->>Agent: Select Camera Index (e.g., Camera 0: Integrated Webcam)
    
    Agent->>Agent: Test Camera Stream & Validate Landmark Tracking
    Agent->>Central: Dispatches POST /api/v1/nodes/register
    
    alt Connection Succeeded
        Central-->>Agent: HTTP 200 OK {"status": "registered"}
        Agent->>Agent: Commit configuration to edge_config.json
        Agent->>Agent: Initialize edgeergo_local.db schemas
        Agent->>Worker: Display "Setup Complete! Monitoring in background."
        Agent->>Agent: Minimize to System Tray
    else Connection Failed (Offline Deployment)
        Central--xAgent: Network Unreachable
        Agent->>Agent: Cache configuration locally; flag registration PENDING
        Agent->>Worker: Display "Offline mode enabled. Data will sync when connected."
        Agent->>Agent: Start monitoring autonomously
    end
```

---

## 5. System Requirements & Hardware Compatibility

### Edge Node (Worker PC) Requirements:
- **Operating System**: Windows 10 (64-bit) or Windows 11.
- **CPU**: Intel Core i3 (6th Gen+) / AMD Ryzen 3 or equivalent (dual-core 2.0 GHz+).
- **RAM**: Minimum 4 GB available system RAM (Edge Agent consumes $\le 120$ MB).
- **Camera**: Standard USB 2.0 or integrated laptop webcam (720p or 1080p, 30 FPS).
- **Network**: 10/100 Mbps Ethernet or 802.11n Wi-Fi (only required for syncing summaries).
- **Disk Space**: $\le 150$ MB for binary installation and local database buffer.

### Central Server Requirements:
- **Operating System**: Windows 10/11, Windows Server, or Ubuntu Linux 20.04/22.04 LTS.
- **CPU**: 4 CPU Cores (e.g., Intel Core i5 / AMD Ryzen 5).
- **RAM**: 8 GB RAM (FastAPI and SQLite run comfortably in $<250$ MB).
- **Storage**: 10 GB free disk space (sufficient for years of JSON window summaries).

---

## Related Documents
- [03-tech-stack.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/03-tech-stack.md) — Technology rationale.
- [08-offline-and-sync.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/08-offline-and-sync.md) — Offline operation resilience.
- [12-repository-structure.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/12-repository-structure.md) — Packaging files and specs.
- [configuration-reference.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/deployment/configuration-reference.md) — Exhaustive settings catalog.
