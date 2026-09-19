# EdgeErgo — Installation & Deployment Guide

> **Phase 16 Deployment & Packaging** (PRD §11, §12.1, §13, §42, §43, §107, TECH doc §5)

This document provides complete, step-by-step instructions for deploying both components of the **EdgeErgo** platform:
1. **Central Server + Enterprise Dashboard**: The central aggregation server, REST API, SQLite database, and compiled React analytics frontend.
2. **Edge Agent (EdgeErgoAgent.exe)**: The standalone worker workstation client bundled with OpenCV, MediaPipe task models, and the PySide6 awareness overlay.

---

## 1. System Architecture Overview

```
 ┌─────────────────────────────────────────────────────────────┐
 │                Central Management Server                    │
 │                                                             │
 │  ┌─────────────────────────┐   ┌─────────────────────────┐  │
 │  │      FastAPI App        │   │  Production React SPA   │  │
 │  │   (REST API + Sync)     │   │     (dashboard/dist)    │  │
 │  └────────────┬────────────┘   └────────────┬────────────┘  │
 │               │                             │               │
 │               └──────────────┬──────────────┘               │
 │                              │                              │
 │                  SQLite: central_server.db                  │
 └──────────────────────────────┼──────────────────────────────┘
                                ▲
                 HTTP/REST Sync │ Heartbeat (JSON Telemetry Only)
                                │ (Zero raw images/video leave edge)
 ┌──────────────────────────────┴──────────────────────────────┐
 │             Worker Workstation (Edge Node)                  │
 │                                                             │
 │  ┌───────────────────────────────────────────────────────┐  │
 │  │                 EdgeErgoAgent.exe                     │  │
 │  │                                                       │  │
 │  │  • MediaPipe Pose & Face Task Models (Bundled)        │  │
 │  │  • Local OpenCV Video Ingestion (In-Memory Only)      │  │
 │  │  • RULA / REBA Ergonomic Scoring Engine               │  │
 │  │  • PySide6 Worker Awareness Overlay                   │  │
 │  │  • Local SQLite Storage (edgeergo_local.db)           │  │
 │  └───────────────────────────────────────────────────────┘  │
 └─────────────────────────────────────────────────────────────┘
```

---

## 2. Central Server Deployment

The Central Server runs FastAPI on Python 3.10+, coordinates worker nodes, stores aggregated telemetry in SQLite, and serves the production React analytics dashboard.

### Prerequisites (Server Host)
- **OS**: Windows 10/11, Windows Server, macOS, or Linux (Ubuntu 20.04+)
- **Python**: Version 3.10, 3.11, or 3.12 installed with `pip`
- **Node.js**: Version 18+ and `npm` (required only if building dashboard from source)
- **Port**: Port `8000` (or custom configurable port) open for inbound workstation traffic

### Step 1: Clone Repository & Set Up Virtual Environment

```bash
# Clone the repository
git clone https://github.com/organization/edge-ergo.git
cd edge-ergo

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install server dependencies
pip install -r requirements.txt
```

### Step 2: Build the Production Dashboard

The frontend is a modern React + TypeScript + Vite + Tailwind CSS dashboard located in `dashboard/`.

```bash
cd dashboard
npm install
npm run build
cd ..
```

This compiles the static bundle into `dashboard/dist/` (`index.html`, assets, and scripts). The Central Server's FastAPI app automatically detects this folder and mounts it at the web root (`/`).

### Step 3: Launch Central Server

Run the unified server startup command:

```bash
# Direct uvicorn command:
uvicorn central_server.main:app --host 0.0.0.0 --port 8000

# Or on Windows using the launcher script:
installer\start_server.bat
```

### Verifying Central Server Operation
- **Web Dashboard**: Navigate to `http://localhost:8000` in any modern web browser. You should see the EdgeErgo Enterprise Dashboard.
- **Interactive API Docs**: Navigate to `http://localhost:8000/docs` to inspect OpenAPI documentation for `/api/v1/edge/*` and `/api/v1/dashboard/*`.
- **Database**: The server will automatically initialize `central_server.db` in the workspace root.

---

## 3. Edge Agent Deployment (`EdgeErgoAgent.exe`)

The Edge Agent is packaged as a standalone single-file Windows executable (`EdgeErgoAgent.exe`) using PyInstaller.

> [!IMPORTANT]
> Workers do **NOT** need Python, OpenCV, MediaPipe, or Node.js installed on their machines. All vision runtime libraries and pre-trained neural network models are self-contained inside `EdgeErgoAgent.exe`.

### System Requirements (Worker Workstation)
- **OS**: Windows 10 (64-bit) or Windows 11
- **Hardware**: Any modern multi-core CPU (Intel Core i3/i5/i7 8th gen+ or AMD Ryzen)
- **Memory**: 4 GB RAM minimum (8 GB recommended)
- **Camera**: Standard integrated laptop webcam or USB external webcam
- **Network**: Local Area Network (LAN) or VPN connectivity to the Central Server

---

### Step 1: Building the Standalone Executable (Admin / Build Machine)

If building `EdgeErgoAgent.exe` from source on a build machine:

1. Ensure the MediaPipe task models are present in `edge_agent/models/`:
   - `edge_agent/models/pose_landmarker_lite.task` (MediaPipe 33-landmark pose model)
   - `edge_agent/models/face_landmarker.task` (MediaPipe 478-landmark face model)
2. Run the automated build script:
   ```bash
   python installer/build_agent.py
   ```
3. Upon completion, the standalone executable is generated at:
   ```
   installer/dist/EdgeErgoAgent.exe
   ```

---

### Step 2: Distributing and Installing on Worker Machines

1. Copy `EdgeErgoAgent.exe` (or the `installer/` folder) to the worker's computer (e.g. `C:\Program Files\EdgeErgo\` or `C:\Users\<user>\EdgeErgo\`).
2. Optionally copy `installer/start_agent.bat` for convenient first-time configuration.

---

### Step 3: First-Time Launch and Server Configuration

When launching the Edge Agent for the first time, it needs the Central Server's URL so it can register itself and begin syncing.

#### Option A: Interactive Batch Launcher (Recommended for Workers)
Double-click `start_agent.bat`. If no configuration exists, it will prompt:
```
First-time launch detected!
Enter Central Server URL [default: http://localhost:8000]: http://192.168.1.50:8000
Enter Workstation / Desk Name [default: Workstation-01]: Desk-4B-Marketing
```
The agent registers itself with the Central Server (`POST /api/v1/edge/register`), receives a persistent anonymous node ID (e.g. `NODE-001`), saves settings to `edge_config.json`, and starts monitoring.

#### Option B: Command-Line Flags
Run directly via Command Prompt or PowerShell:
```cmd
EdgeErgoAgent.exe --server http://192.168.1.50:8000 --device-name "Desk-4B-Marketing"
```

#### Option C: Pre-Provisioned Configuration File
Admins can deploy a pre-configured `edge_config.json` alongside `EdgeErgoAgent.exe`:
```json
{
  "device_id": "",
  "device_name": "Accounting-Desk-12",
  "server_url": "http://192.168.1.50:8000",
  "capture_fps": 15,
  "camera_index": 0,
  "monitoring_start_time": "09:00",
  "monitoring_end_time": "17:00"
}
```
On first launch, `EdgeErgoAgent.exe` reads `edge_config.json`, registers with the server, updates `device_id`, and initiates background telemetry syncing.

---

## 4. Operational Modes & Command-Line Reference

`EdgeErgoAgent.exe` supports several runtime flags for different deployment scenarios:

| Flag | Type | Description |
| :--- | :--- | :--- |
| `--server <URL>` | String | Central Server address (e.g. `http://10.0.0.15:8000`). |
| `--device-name <NAME>` | String | Human-readable label for workstation (e.g. `Lab-Desk-3`). |
| `--config <PATH>` | String | Explicit path to configuration JSON file (default: `edge_config.json`). |
| `--headless` | Flag | Runs the agent without the PySide6 worker GUI overlay (daemon mode). |
| `--no-camera` | Flag | Test mode using synthetic frames (useful for CI/VM environments without physical webcams). |
| `--fps <FLOAT>` | Float | Target video capture frame rate (default: `15.0`). |

### Examples

**Standard Employee Workstation (Camera + Desktop Awareness Overlay):**
```cmd
EdgeErgoAgent.exe --server http://central-ergo.internal:8000
```

**Background Daemon / Headless Mode:**
```cmd
EdgeErgoAgent.exe --server http://central-ergo.internal:8000 --headless
```

**Hardware Testing Without Camera:**
```cmd
EdgeErgoAgent.exe --server http://localhost:8000 --no-camera
```

---

## 5. Offline Operation & Privacy Guarantee

### Privacy Invariant (PRD §28, TECH doc §5)
- **Zero Raw Video Transmission**: Camera frames are processed strictly in local RAM and immediately discarded. No video streams, photographs, or facial crops are ever written to disk or transmitted across the network.
- **Anonymized Telemetry**: Only computed mathematical indices (RULA score, REBA score, posture category, coarse expression category) are saved in local SQLite (`edgeergo_local.db`) and synced to Central Server.

### Offline Resiliency (PRD §39, §40)
- If network connection to the Central Server is interrupted, the Edge Agent continues local monitoring, local posture evaluation, and worker overlay nudges without interruption.
- Telemetry windows are queued in local SQLite (`sync_queue` table).
- When network connectivity is restored, the agent automatically flushes the queue using exponential backoff retry logic.

---

## 6. Troubleshooting

### Issue: "Failed to open physical camera"
- **Cause**: Another application (Teams, Zoom, browser) may be holding an exclusive lock on the camera, or Windows Privacy settings may block camera access.
- **Remedy**:
  1. Close other video conferencing tools.
  2. In Windows, go to **Settings > Privacy & Security > Camera** and ensure **"Let desktop apps access your camera"** is enabled.
  3. The agent will automatically fall back to synthetic frames if no camera is available.

### Issue: "Could not reach Central Server"
- **Cause**: Server is offline, URL is mistyped, or firewall blocks port 8000.
- **Remedy**:
  1. Verify the server is running by opening `http://<server-ip>:8000/docs` in the worker machine's browser.
  2. Check firewall rules on the server host: allow TCP port 8000 inbound.
  3. The Edge Agent operates safely in offline mode (`NODE-LOCAL`) until the connection is restored.

### Issue: MediaPipe Model Asset Error in Custom PyInstaller Builds
- **Cause**: MediaPipe `.task` files were not copied to the bundle directory.
- **Remedy**: Always use `installer/build_agent.py` or compile with the provided `installer/EdgeErgoAgent.spec`, which explicitly bundles both `pose_landmarker_lite.task` and `face_landmarker.task`.
