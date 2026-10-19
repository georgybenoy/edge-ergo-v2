# Telemetry Schema Specification

This document provides a field-by-field reference for the **Telemetry Window JSON Contract**. This payload represents the primary data transmission unit in EdgeErgo, dispatched by the Edge Agent to the Central Server at the conclusion of each monitoring window (PRD §49, §89).

---

## 1. Schema Overview & Design Principles

The telemetry schema enforces strict data minimization:
1. **Scalar Aggregations Only**: No multi-dimensional arrays, frame matrices, or landmark lists are permitted.
2. **Deterministic Cryptographic Hashing**: Every window generates a canonical SHA-256 fingerprint (`window_hash`) enabling server-side idempotent deduplication.
3. **Closed Field Boundary**: The Central Server Pydantic validator rejects unknown or unexpected attributes, preventing unintended data leaks.

---

## 2. Field-by-Field Dictionary

### 2.1 Root Level Properties

| Field Name | Type | Range / Format | Nullable | Description & Constraints |
| :--- | :---: | :---: | :---: | :--- |
| `node_id` | String | `^[A-Z0-9_-]{3,32}$` | No | Anonymous workstation identifier assigned to the Edge Node (e.g., `NODE-001`). Must not contain employee personal names. |
| `window_hash` | String | 64 Hex characters | No | SHA-256 hash computed across canonical window keys. Used for idempotent deduplication. |
| `window_start` | String | ISO 8601 UTC | No | Exact start timestamp of the 5-minute sampling window (e.g., `2026-10-14T09:00:00Z`). |
| `window_end` | String | ISO 8601 UTC | No | Exact conclusion timestamp of the sampling window (e.g., `2026-10-14T09:05:00Z`). |
| `window_duration_seconds` | Integer | $60 \le x \le 3600$ | No | Total elapsed wall-clock duration of the window in seconds (standard default: `300`). |
| `sample_count` | Integer | $x \ge 0$ | No | Total number of video frames processed by the vision engine during the duty cycle. |
| `presence_ratio` | Float | $0.0 \le x \le 1.0$ | No | Proportion of duty cycle samples where an operator was detected in front of the camera. |
| `ergonomics` | Object | JSON Object | No | Nested object containing biomechanical risk scores and risk tier distributions. |
| `facial_expressions` | Object | JSON Object | No | Nested object containing temporal percentage allocations of observable facial states. |
| `events` | Object | JSON Object | No | Nested object tallying desktop notifications and break compliance interactions. |
| `agent_metadata` | Object | JSON Object | No | Software release version and active duty cycle configuration. |

---

### 2.2 The `ergonomics` Object

| Field Name | Type | Range / Format | Nullable | Description & Constraints |
| :--- | :---: | :---: | :---: | :--- |
| `rula_grand_score_avg` | Float | $1.0 \le x \le 7.0$ | No | Mean RULA Grand Score evaluated across all present frames within the sampling duration. |
| `rula_grand_score_max` | Float | $1.0 \le x \le 7.0$ | No | Peak RULA Grand Score reached during the sampling window. |
| `reba_grand_score_avg` | Float | $1.0 \le x \le 15.0$ | No | Mean REBA Grand Score across all present frames. |
| `reba_grand_score_max` | Float | $1.0 \le x \le 15.0$ | No | Peak REBA Grand Score reached during the window. |
| `risk_distribution_pct` | Object | JSON Object | No | Temporal percentage breakdown of time spent in each of the four unified risk tiers. |
| `predominant_risk_factor` | String | Enum string | No | Leading postural deviation identified during the window. Allowed values:<br>• `none`<br>• `forward_head_flexion`<br>• `trunk_slumping`<br>• `shoulder_elevation`<br>• `excessive_wrist_extension` |

#### `risk_distribution_pct` Sub-Properties:
- `low_risk` (Float, $0.0 \le x \le 100.0$): Percentage of time at RULA 1–2 / REBA 1–3.
- `medium_risk` (Float, $0.0 \le x \le 100.0$): Percentage of time at RULA 3–4 / REBA 4–7.
- `high_risk` (Float, $0.0 \le x \le 100.0$): Percentage of time at RULA 5–6 / REBA 8–10.
- `very_high_risk` (Float, $0.0 \le x \le 100.0$): Percentage of time at RULA 7 / REBA 11–15.
- **Sum Constraint**: `low_risk + medium_risk + high_risk + very_high_risk` must equal $100.0\% \pm 0.1\%$.

---

### 2.3 The `facial_expressions` Object

| Field Name | Type | Range / Format | Nullable | Description & Constraints |
| :--- | :---: | :---: | :---: | :--- |
| `neutral_pct` | Float | $0.0 \le x \le 100.0$ | No | Percentage of time the operator displayed nominal, relaxed facial baseline geometry. |
| `expressive_pct` | Float | $0.0 \le x \le 100.0$ | No | Percentage of time displaying micro-movements, smiling, nodding, or visual engagement. |
| `fatigue_strained_pct` | Float | $0.0 \le x \le 100.0$ | No | Percentage of time exhibiting physical strain markers (sustained squinting, brow furrowing, prolonged eye closure). |
| `mouth_movement_pct` | Float | $0.0 \le x \le 100.0$ | No | Percentage of time displaying active speaking or yawning aperture dynamics. |
| **Sum Constraint** | | | | `neutral_pct + expressive_pct + fatigue_strained_pct + mouth_movement_pct` must equal $100.0\% \pm 0.1\%$. |

---

### 2.4 The `events` Object

| Field Name | Type | Range / Format | Nullable | Description & Constraints |
| :--- | :---: | :---: | :---: | :--- |
| `posture_warning_count` | Integer | $x \ge 0$ | No | Count of posture correction toasts displayed to the worker during this window. |
| `break_reminder_count` | Integer | $x \ge 0$ | No | Count of movement-break notifications displayed. |
| `hydration_reminder_count`| Integer | $x \ge 0$ | No | Count of hydration reminder dialogs displayed. |
| `breaks_taken_count` | Integer | $x \ge 0$ | No | Count of confirmed breaks or walkaways recorded during this window. |

---

### 2.5 The `agent_metadata` Object

| Field Name | Type | Range / Format | Nullable | Description & Constraints |
| :--- | :---: | :---: | :---: | :--- |
| `version` | String | SemVer (e.g. `3.0.0`) | No | Edge Agent software version string. |
| `monitoring_interval_min` | Integer | $1 \le x \le 60$ | No | Repetition cycle interval in minutes (default: `5`). |
| `sampling_duration_sec` | Integer | $5 \le x \le 300$ | No | Active camera sampling burst duration in seconds (default: `30`). |

---

## 3. Strict Boundary Validation Rules

The Central Server enforces strict schema validation using Pydantic v2 (PRD §89):

```python
class TelemetryPayload(BaseModel):
    node_id: str = Field(..., pattern=r"^[A-Z0-9_-]{3,32}$")
    window_hash: str = Field(..., min_length=64, max_length=64)
    window_start: datetime
    window_end: datetime
    window_duration_seconds: int = Field(gt=0, le=3600)
    sample_count: int = Field(ge=0)
    presence_ratio: float = Field(ge=0.0, le=1.0)
    ergonomics: ErgonomicsSummary
    facial_expressions: FacialSummary
    events: EventCounts
    agent_metadata: MetadataSummary

    model_config = ConfigDict(extra="forbid")  # Strictly rejects unknown fields!
```

> [!CAUTION]
> **Zero Tolerance for Unexpected Fields:** Setting `extra="forbid"` ensures that if any client erroneously attempts to submit binary blobs, base64-encoded image crops, or un-summarized coordinate arrays, the request is rejected with `HTTP 422 Unprocessable Entity` and flagged in server security logs.

---

## Related Documents
- [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md) — Local window synthesis.
- [05-central-server-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/05-central-server-workflow.md) — Server-side ingestion validation.
- [06-data-flow-and-privacy.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/06-data-flow-and-privacy.md) — Privacy boundary specification.
- [07-data-models.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/07-data-models.md) — SQLite storage tables.
- [api-reference.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/api/api-reference.md) — REST API reference for ingestion.
