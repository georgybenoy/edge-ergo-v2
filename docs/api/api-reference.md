# REST API Reference

The EdgeErgo Central Server exposes a versioned RESTful HTTP API under the `/api/v1` prefix. This interface serves two distinct client types: autonomous **Edge Agents** transmitting telemetry over the LAN, and the administrative **React Web Dashboard** querying aggregated metrics and reports (PRD §41, §88).

---

## 1. Global API Conventions

- **Base URL**: `http://<server-ip>:8000/api/v1`
- **Content Type**: `application/json` (except file export endpoints returning `text/csv` or `application/pdf`).
- **Date & Time Format**: ISO 8601 UTC strings (`YYYY-MM-DDTHH:MM:SSZ`).
- **Standard HTTP Status Codes**:
  - `200 OK`: Request succeeded.
  - `201 Created`: Resource successfully registered or created.
  - `400 Bad Request`: Malformed request syntax or unparseable query params.
  - `404 Not Found`: Target entity (`node_id`, `report_id`) does not exist.
  - `422 Unprocessable Entity`: JSON payload failed Pydantic contract validation.
  - `500 Internal Server Error`: Unhandled server-side exception.

---

## 2. Edge Agent Endpoints

### 2.1 Register Edge Node
- **Route**: `POST /api/v1/nodes/register`
- **Purpose**: Registers a new workstation or updates hardware metadata upon agent startup (PRD §42).

#### Request Headers
```http
Content-Type: application/json
```

#### Request Payload
```json
{
  "node_id": "NODE-001",
  "hostname": "ENG-DESK-104",
  "ip_address": "192.168.1.104",
  "os_version": "Windows 11 Pro 23H2",
  "agent_version": "3.0.0",
  "department": "Engineering"
}
```

#### Response (`200 OK`)
```json
{
  "status": "registered",
  "node_id": "NODE-001",
  "server_time": "2026-10-14T09:00:00Z",
  "message": "Node successfully enrolled in central registry."
}
```

#### Validation Rules & Errors
- `node_id`: Required string matching pattern `^[A-Z0-9_-]{3,32}$`.
- Returns `422 Unprocessable Entity` if `node_id` is missing or contains invalid characters.

---

### 2.2 Submit Node Heartbeat
- **Route**: `POST /api/v1/nodes/heartbeat`
- **Purpose**: Periodic liveness check dispatched every 60 seconds (PRD §46).

#### Request Payload
```json
{
  "node_id": "NODE-001",
  "agent_version": "3.0.0",
  "monitoring_state": "ACTIVE",
  "camera_status": "OK",
  "queue_depth": 0
}
```

#### Response (`200 OK`)
```json
{
  "status": "acknowledged",
  "node_id": "NODE-001",
  "server_time": "2026-10-14T09:01:00Z"
}
```

#### Error Cases
- `404 Not Found`: If `node_id` has never been registered, the server prompts the node to re-invoke registration.

---

### 2.3 Ingest Telemetry Window Summary
- **Route**: `POST /api/v1/telemetry`
- **Purpose**: Ingests an anonymized 5-minute sampling window summary (PRD §48, §49).

#### Request Payload
```json
{
  "node_id": "NODE-001",
  "window_hash": "a4b89c3f91e704d98342152865e94b29f76a521e8f237b12d590e8c14a9386bc",
  "window_start": "2026-10-14T09:00:00Z",
  "window_end": "2026-10-14T09:05:00Z",
  "window_duration_seconds": 300,
  "sample_count": 300,
  "presence_ratio": 0.94,
  "ergonomics": {
    "rula_grand_score_avg": 3.82,
    "rula_grand_score_max": 6.0,
    "reba_grand_score_avg": 4.15,
    "reba_grand_score_max": 7.0,
    "risk_distribution_pct": {
      "low_risk": 42.5,
      "medium_risk": 38.0,
      "high_risk": 16.5,
      "very_high_risk": 3.0
    },
    "predominant_risk_factor": "forward_head_flexion"
  },
  "facial_expressions": {
    "neutral_pct": 71.0,
    "expressive_pct": 14.5,
    "fatigue_strained_pct": 11.0,
    "mouth_movement_pct": 3.5
  },
  "events": {
    "posture_warning_count": 2,
    "break_reminder_count": 0,
    "hydration_reminder_count": 0,
    "breaks_taken_count": 0
  },
  "agent_metadata": {
    "version": "3.0.0",
    "monitoring_interval_min": 5,
    "sampling_duration_sec": 30
  }
}
```

#### Response (`200 OK` - New Record Ingested)
```json
{
  "status": "success",
  "record_id": 4021,
  "node_id": "NODE-001",
  "window_hash": "a4b89c3f91e704d98342152865e94b29f76a521e8f237b12d590e8c14a9386bc"
}
```

#### Response (`200 OK` - Duplicate Acknowledged)
```json
{
  "status": "duplicate_ignored",
  "node_id": "NODE-001",
  "window_hash": "a4b89c3f91e704d98342152865e94b29f76a521e8f237b12d590e8c14a9386bc",
  "message": "Window summary already ingested. Client may safely purge from queue."
}
```

#### Validation Constraints
- `rula_grand_score_avg`: Must satisfy $1.0 \le x \le 7.0$.
- `reba_grand_score_avg`: Must satisfy $1.0 \le x \le 15.0$.
- Risk distribution percentages: Sum must be $\le 100.01\%$.
- Facial expression percentages: Sum must be $\le 100.01\%$.
- Any presence of prohibited fields (e.g., `image`, `frame`, `video`, `embedding`, `landmarks`) results in immediate `422` rejection.

---

## 3. Administrative Dashboard Endpoints

### 3.1 Get Executive Overview
- **Route**: `GET /api/v1/dashboard/overview`
- **Purpose**: Delivers macro-level organizational KPIs for the main dashboard view (PRD §59).

#### Response (`200 OK`)
```json
{
  "summary_date": "2026-10-14",
  "total_registered_nodes": 24,
  "active_nodes_online": 18,
  "total_monitored_hours": 128.5,
  "collective_compliance_pct": 82.4,
  "collective_risk_distribution": {
    "low_risk": 48.2,
    "medium_risk": 32.1,
    "high_risk": 16.4,
    "very_high_risk": 3.3
  },
  "predominant_organizational_risk": "forward_head_flexion",
  "active_alerts_count": 5
}
```

---

### 3.2 List Workstations
- **Route**: `GET /api/v1/dashboard/workstations`
- **Query Parameters**:
  - `department` (optional string): Filter by department name.
  - `status` (optional string): Filter by `ONLINE`, `STALE`, or `OFFLINE`.
- **Purpose**: Populates the workstation directory table (PRD §60).

#### Response (`200 OK`)
```json
{
  "count": 2,
  "workstations": [
    {
      "node_id": "NODE-001",
      "department": "Engineering",
      "status": "ONLINE",
      "current_rula_score": 3.2,
      "current_risk_tier": "MEDIUM",
      "predominant_risk": "forward_head_flexion",
      "today_monitored_minutes": 240,
      "break_compliance_pct": 75.0,
      "last_heartbeat": "2026-10-14T09:01:00Z"
    },
    {
      "node_id": "NODE-002",
      "department": "Customer Support",
      "status": "ONLINE",
      "current_rula_score": 2.1,
      "current_risk_tier": "LOW",
      "predominant_risk": "none",
      "today_monitored_minutes": 210,
      "break_compliance_pct": 100.0,
      "last_heartbeat": "2026-10-14T09:01:15Z"
    }
  ]
}
```

---

### 3.3 Get Workstation Detail
- **Route**: `GET /api/v1/dashboard/workstations/{node_id}`
- **Purpose**: Chronological telemetry history and risk profile for a specific workstation.

#### Response (`200 OK`)
```json
{
  "node_id": "NODE-001",
  "department": "Engineering",
  "hardware": {
    "hostname": "ENG-DESK-104",
    "os_version": "Windows 11 Pro 23H2",
    "agent_version": "3.0.0"
  },
  "today_summary": {
    "rula_avg": 3.45,
    "reba_avg": 3.80,
    "posture_warnings": 6,
    "breaks_taken": 4
  },
  "recent_windows": [
    {
      "window_start": "2026-10-14T08:55:00Z",
      "rula_avg": 3.82,
      "reba_avg": 4.15,
      "predominant_risk": "forward_head_flexion"
    }
  ]
}
```

---

### 3.4 Get Collective Ergonomic Analytics
- **Route**: `GET /api/v1/dashboard/analytics/ergonomics`
- **Query Parameters**:
  - `start_date` (ISO date): Filter start (e.g., `2026-10-01`).
  - `end_date` (ISO date): Filter end (e.g., `2026-10-14`).
- **Purpose**: Feeds the Ergonomics Analytics deep-dive page with hourly risk heatmaps and posture breakdown bars (PRD §52, §55).

---

### 3.5 Get Expression Statistics
- **Route**: `GET /api/v1/dashboard/analytics/expressions`
- **Purpose**: Delivers aggregated macro facial observation proportions over time (PRD §53).

---

### 3.6 Get Combined Pattern Observations
- **Route**: `GET /api/v1/dashboard/analytics/combined`
- **Purpose**: Generates observational correlation matrices between high-risk postures and facial strain indicators (PRD §54).

---

## 4. Reporting & Export Endpoints

### 4.1 Export Telemetry to CSV
- **Route**: `GET /api/v1/export/csv`
- **Query Parameters**:
  - `type` (string, required): `summaries` or `daily_rollups`.
  - `node_id` (optional string): Filter to a specific node.
  - `start_date` / `end_date` (optional strings): Date range.
- **Response**: `text/csv` stream with `Content-Disposition: attachment; filename="edgeergo_telemetry_2026-10-14.csv"`.

---

### 4.2 Generate Executive Report
- **Route**: `POST /api/v1/reports/generate`
- **Purpose**: Triggers synthesis of a publication-quality PDF executive briefing (PRD §58).

#### Request Payload
```json
{
  "report_type": "EXECUTIVE_SUMMARY",
  "start_date": "2026-10-07",
  "end_date": "2026-10-14",
  "include_departments": ["Engineering", "Customer Support"]
}
```

#### Response (`201 Created`)
```json
{
  "report_id": 84,
  "status": "ready",
  "download_url": "/api/v1/reports/84/download",
  "file_size_bytes": 348120,
  "generated_at": "2026-10-14T09:05:30Z"
}
```

---

### 4.3 Download Generated Report
- **Route**: `GET /api/v1/reports/{report_id}/download`
- **Response**: Binary stream with `Content-Type: application/pdf`.

---

## Related Documents
- [05-central-server-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/05-central-server-workflow.md) — Server-side ingestion pipeline.
- [06-data-flow-and-privacy.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/06-data-flow-and-privacy.md) — Privacy boundaries and data protection.
- [07-data-models.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/07-data-models.md) — Database schemas storing API objects.
- [telemetry-schema.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/api/telemetry-schema.md) — Exhaustive field-by-field telemetry contract.
