# Open Questions & Design Ambiguities

This document records architectural, empirical, and configuration parameters that the source specifications ([EdgeErgo_PRD_V3.pdf](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/source/EdgeErgo_PRD_V3.pdf), [EdgeErgo_V3_TECH.pdf](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/source/EdgeErgo_V3_TECH.pdf), and [EdgeErgo_DESIGN.pdf](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/source/EdgeErgo_DESIGN.pdf)) leave undecided, mark for empirical benchmarking, or present minor divergence.

---

## 1. Summary of Open Items

| Item ID | Category | Topic / Parameter | PRD / Source Reference | Interim Project Assumption |
| :---: | :--- | :--- | :---: | :--- |
| **OQ-1** | Parameter Tuning | Posture Persistence Threshold (`posture_warning_persistence_seconds`) | PRD §26 | **Default: 20 seconds** (empirical validation in Phase 20). |
| **OQ-2** | Parameter Tuning | Alert Cooldown Duration (`alert_cooldown_seconds`) | PRD §36 | **Default: 120 seconds** (empirical validation in Phase 20). |
| **OQ-3** | Database Architecture| PostgreSQL Enterprise Cutover Threshold | PRD §13, §48 | **SQLite for $\le 50$ nodes**; recommend PostgreSQL for $>50$ concurrent nodes. |
| **OQ-4** | OS Platform Scope | macOS & Linux Edge Agent Support | PRD §70, §71 | **Windows 10/11 only** for final-year defense; Unix deferred to future roadmap. |
| **OQ-5** | Security Architecture | Node Authentication & Pre-Shared Secret Tokens | PRD §42, §62 | Unauthenticated HTTP on trusted LAN for prototype; API token header planned for enterprise. |
| **OQ-6** | Desktop UX | Click-Through Toggle vs. Interactivity in PySide6 | DESIGN §8 | Click-through enabled in compact mode; repositioning managed via System Tray settings dialog. |

---

## 2. Detailed Technical Analysis

### OQ-1: Posture Persistence Threshold Calibration
- **The Issue**: PRD §26 states that a posture warning should only be triggered if high ergonomic risk persists across consecutive frames, noting the duration is *"TBD via benchmarking"* with a recommended range of 10 to 60 seconds.
- **Trade-Off**: A low threshold (e.g., 10s) catches bad posture quickly but risks false alarms when a worker pauses to read or reaches for a phone. A high threshold (e.g., 45s) reduces false alarms but allows prolonged slouching before alerting.
- **Interim Resolution**: Initial software builds use **20 seconds** as the default baseline. Phase 20 includes user study trials to calibrate the final empirical value.

### OQ-2: Alert Cooldown Duration Calibration
- **The Issue**: PRD §36 requires an alert cooldown period to prevent annoying workers, noting the duration is *"TBD via benchmarking"* with a recommended range of 60 to 300 seconds.
- **Trade-Off**: A 60-second cooldown may still feel repetitive if a worker is engaged in an intense coding or typing task; a 300-second (5-minute) cooldown may allow a worker to slip back into harmful slumping without guidance.
- **Interim Resolution**: Default baseline is set to **120 seconds (2 minutes)**, configurable via `edge_config.json`.

### OQ-3: PostgreSQL Migration Trigger Threshold
- **The Issue**: PRD §13 and §48 state that SQLite is used initially with a modular database repository layer to allow a future transition to PostgreSQL. However, the exact operational ceiling where SQLite should be retired is not explicitly defined.
- **Interim Resolution**: SQLite comfortably supports concurrent ingestion for up to **50 active Edge Nodes** generating ~4,800 window records daily (~4.8 MB/day) using Write-Ahead Logging (WAL). When scaling beyond 50 nodes or across multi-site subnets, switching the `DATABASE_URL` to PostgreSQL is recommended to support native connection pooling.

### OQ-4: Operating System Compatibility Scope
- **The Issue**: PRD §70 and §71 specify standalone PyInstaller compilation for Windows 10/11 (`EdgeErgoAgent.exe`), but some office environments utilize macOS or Ubuntu desktop machines.
- **Interim Resolution**: For the final-year B.Tech project presentation and defense, the Edge Agent is formally verified on **Windows 10 and 11 (64-bit)**. Cross-platform builds (macOS `.app` and Linux AppImage) are cataloged under future roadmap items.

### OQ-5: API Authentication on the Corporate LAN
- **The Issue**: PRD §42 describes node registration (`POST /api/v1/nodes/register`) and telemetry submission using open JSON requests across the local network. While practical for an isolated academic laboratory or intranet, enterprise production requires protection against rogue rogue node spoofing.
- **Interim Resolution**: For the project presentation, nodes register using their assigned `node_id` without authentication headers. A pre-shared authorization token (`X-EdgeErgo-Key`) is designed as a modular middleware extension for production deployment.

### OQ-6: PySide6 Overlay Click-Through Interaction Model
- **The Issue**: Setting `Qt.WindowTransparentForInput` on the PySide6 overlay ensures that mouse clicks pass through the translucent status pill into underlying software (code editors, spreadsheets). However, this prevents the user from clicking the pill to drag or reposition it.
- **Interim Resolution**: In compact pill mode, the overlay is click-through by default. Workers can reposition the overlay or toggle between display corners (`bottom_right`, `top_right`) via the **EdgeErgo System Tray Context Menu**.

---

## Related Documents
- [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md) — Persistence and cooldown mechanics.
- [07-data-models.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/07-data-models.md) — Database design and modularity.
- [configuration-reference.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/deployment/configuration-reference.md) — Configurable settings catalog.
- [ROADMAP_AND_FUTURE_WORK.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/ROADMAP_AND_FUTURE_WORK.md) — Planned post-v3 enhancements.
