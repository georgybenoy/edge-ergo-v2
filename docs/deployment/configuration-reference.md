# Configuration Reference

This document provides an exhaustive reference of all configurable runtime settings in EdgeErgo. Configuration parameters control duty-cycle scheduling, camera acquisition, ergonomic persistence thresholds, break reminders, alert cooldowns, and network endpoints (PRD §16, §74).

---

## 1. Edge Agent Configuration (`edge_config.json`)

The Edge Agent reads its runtime parameters from a local JSON configuration file located alongside the executable (`edge_config.json`). If this file is missing on launch, the agent generates a template populated with standard defaults.

```json
{
  "node_id": "NODE-001",
  "department": "Engineering",
  "server_url": "http://192.168.1.100:8000",
  "camera": {
    "camera_index": 0,
    "target_width": 320,
    "target_height": 240,
    "frame_skip_step": 3
  },
  "schedule": {
    "monitoring_start_time": "09:00",
    "monitoring_end_time": "18:00",
    "monitoring_interval_minutes": 5,
    "analysis_duration_seconds": 30,
    "continuous_mode": false
  },
  "ergonomics": {
    "posture_warning_persistence_seconds": 20,
    "alert_cooldown_seconds": 120,
    "break_reminder_interval_minutes": 60,
    "hydration_reminder_interval_minutes": 90
  },
  "overlay": {
    "mode": "compact",
    "position": "bottom_right",
    "click_through": true,
    "toast_duration_seconds": 8
  },
  "logging": {
    "level": "INFO",
    "log_to_file": true
  }
}
```

---

## 2. Exhaustive Setting Catalog

### 2.1 Identity & Network Settings

| Parameter | Type | Default Value | PRD Reference | Description |
| :--- | :---: | :---: | :---: | :--- |
| `node_id` | String | `"NODE-001"` | PRD §42, §63 | Unique workstation identifier. Must adhere to regex `^[A-Z0-9_-]{3,32}$`. Must never be populated with an employee's personal name. |
| `department` | String | `"General"` | PRD §51, §60 | Organizational grouping tag used by the Central Server to aggregate department-level ergonomic statistics. |
| `server_url` | String | `"http://localhost:8000"` | PRD §41, §43 | Base HTTP endpoint of the Central Server API. |

---

### 2.2 Camera & Vision Settings

| Parameter | Type | Default Value | PRD Reference | Description |
| :--- | :---: | :---: | :---: | :--- |
| `camera_index` | Integer | `0` | PRD §18, §44 | Operating system device index passed to OpenCV `cv2.VideoCapture()`. `0` is standard for integrated laptop webcams. |
| `target_width` | Integer | `320` | PRD §17.1 | Downsampled horizontal pixel resolution for computer vision inference. |
| `target_height` | Integer | `240` | PRD §17.1 | Downsampled vertical pixel resolution. 320×240 cuts inference latency by ~65% vs. native HD. |
| `frame_skip_step` | Integer | `3` | PRD §17.2 | Frame sampling step. At `3`, the agent processes 1 out of every 3 camera frames (yielding 10 FPS effective from a 30 FPS sensor). |

---

### 2.3 Monitoring Schedule Settings

| Parameter | Type | Default Value | PRD Reference | Description |
| :--- | :---: | :---: | :---: | :--- |
| `monitoring_start_time` | String | `"09:00"` | PRD §15 | Daily scheduled start time (24-hour format). Camera sampling is suppressed before this hour. |
| `monitoring_end_time` | String | `"18:00"` | PRD §15 | Daily scheduled conclusion time. The agent sleeps outside of active work hours. |
| `monitoring_interval_minutes` | Integer | `5` | PRD §15, §16 | Repetition interval of the monitoring duty cycle (valid range: 2–15 minutes). |
| `analysis_duration_seconds` | Integer | `30` | PRD §15, §16 | Active camera sampling burst duration per cycle (valid range: 15–60 seconds). |
| `continuous_mode` | Boolean | `false` | PRD §15, §16 | If `true`, overrides duty cycling to run uninterrupted inference at 10 FPS. Intended for calibration or research trials. |

---

### 2.4 Ergonomics & Alert Settings

> [!NOTE]
> Where indicated below as **"TBD via benchmarking"**, the initial value reflects the empirical starting recommendation from the PRD, subject to formal Phase 20 ergonomic calibration trials.

| Parameter | Type | Default Value | PRD Reference | Description |
| :--- | :---: | :---: | :---: | :--- |
| `posture_warning_persistence_seconds` | Integer | **20** *(TBD via benchmarking)* | PRD §26 | Number of continuous seconds a high-risk posture (RULA $\ge 5$) must persist before triggering an alert. Range: 10–60s. |
| `alert_cooldown_seconds` | Integer | **120** *(TBD via benchmarking)* | PRD §36 | Lockout duration after an alert during which identical posture warnings are suppressed. Range: 60–300s. |
| `break_reminder_interval_minutes` | Integer | **60** | PRD §33 | Continuous seated working time threshold after which the agent suggests a micro-movement or stretching break. |
| `hydration_reminder_interval_minutes`| Integer | **90** | PRD §34 | Timer interval prompting a gentle hydration suggestion. |

---

### 2.5 Desktop Overlay Settings

| Parameter | Type | Default Value | PRD Reference | Description |
| :--- | :---: | :---: | :---: | :--- |
| `mode` | String | `"compact"` | PRD §30; DESIGN §8 | Initial presentation state. Options:<br>• `compact`: Small floating status pill.<br>• `expanded`: Detailed coaching card with live metrics.<br>• `toast_only`: Invisible except when active alerts trigger.<br>• `hidden`: Completely suppressed (tray-only mode). |
| `position` | String | `"bottom_right"` | DESIGN §8 | Anchor corner on primary display. Options: `bottom_right`, `top_right`, `bottom_left`, `top_left`. |
| `click_through` | Boolean | `true` | DESIGN §8 | When `true`, mouse clicks pass through the translucent overlay into underlying windows when in compact mode. |
| `toast_duration_seconds` | Integer | `8` | DESIGN §8 | Duration in seconds that a transient warning toast remains visible before auto-dismissing. |

---

## 3. Central Server Environment Variables

The Central Server is configured via environment variables or a `.env` file located in the root directory:

| Environment Variable | Default Value | Description |
| :--- | :---: | :--- |
| `SERVER_HOST` | `0.0.0.0` | Network interface to bind Uvicorn server. |
| `SERVER_PORT` | `8000` | Port for REST API and web dashboard. |
| `DATABASE_URL` | `sqlite:///./edgeergo_central.db` | SQLAlchemy database connection URI. Can be updated to `postgresql://...` for future enterprise scaling. |
| `LOG_LEVEL` | `info` | Server logging verbosity (`debug`, `info`, `warning`, `error`). |
| `STALE_NODE_THRESHOLD_SECONDS` | `120` | Seconds without heartbeat before a node is marked `STALE`. |
| `OFFLINE_NODE_THRESHOLD_SECONDS`| `300` | Seconds without heartbeat before a node is marked `OFFLINE`. |

---

## Related Documents
- [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md) — Operational logic governed by these parameters.
- [08-offline-and-sync.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/08-offline-and-sync.md) — Queue backoff parameters.
- [deployment-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/deployment/deployment-overview.md) — Executable startup using configuration files.
- [OPEN_QUESTIONS.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/OPEN_QUESTIONS.md) — Settings marked for empirical benchmarking.
