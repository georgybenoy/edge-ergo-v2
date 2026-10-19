# 06. Data Flow & Privacy

Privacy is the foundational design constraint of EdgeErgo. The system is engineered to guarantee that raw video streams, cropped facial images, biometric embeddings, and personal worker identities never leave the worker's computer.

---

## 1. Strict Data Localization Matrix

The table below defines the strict physical boundaries of every data type generated within EdgeErgo, establishing where each artifact is allowed to exist and where it is strictly prohibited (PRD §1, §6, §28, §63, §117):

| Data Category | Ephemeral In-Memory (Edge RAM) | Local Disk (Edge SQLite) | Network In-Transit (Wire / HTTP) | Central Storage (Central SQLite) | Central Dashboard (Admin Browser) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Raw Webcam Video Frames** | ✅ (Milliseconds during inference) | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** |
| **Cropped Facial Images** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** |
| **Facial Recognition Embeddings** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** |
| **33 Skeletal Landmark Coordinates $(x,y,z)$** | ✅ (Transitory during geometry calculation) | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** |
| **Biometric Facial Fiducial Points** | ✅ (Transitory during EAR/MAR calculation) | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** |
| **Worker Names, Logins, Email Addresses** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** |
| **Screen Capture / Active App Titles / Keystrokes** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** | ❌ **PROHIBITED** |
| **Anonymous Node Identifier (`NODE-XXX`)** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Session Timestamps (Start / End)** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **RULA / REBA Grand Scores (1–7 / 1–15)** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Joint Flexion Angles (Degrees)** | ✅ | ✅ | ❌ **Omitted from Wire** | ❌ **Omitted** | ❌ **Omitted** |
| **Posture Risk Tier Durations (% Time in Risk)** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Observable Expression Proportions (% Neutral, etc.)** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Posture Violation Counts & Break Events** | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 2. Privacy Architecture & Perimeter Encasement

The system enforces data minimization through five concentric physical security perimeters (PRD §62, §63, §117):

```
+========================================================================================+
|                                    WORKER COMPUTER                                     |
|                                                                                        |
|  [ CAMERA HARDWARE ]                                                                   |
|          | (Raw Optical Stream)                                                        |
|          v                                                                             |
|  +----------------------------------------------------------------------------------+  |
|  | VOLATILE MEMORY ENCLAVE (RAM ONLY)                                               |  |
|  |                                                                                  |  |
|  |  [Frame Buffer] -> [MediaPipe Models] -> [Skeletal / Facial Landmarks]            |  |
|  |                                                        |                         |  |
|  |                                                        v                         |  |
|  |                     [Kinematic Angles] -> [RULA / REBA Scores]                    |  |
|  |                                                        |                         |  |
|  |  +-----------------------------------------------------+                         |  |
|  |  | ZERO-RETENTION DESTRUCTION:                                                   |  |
|  |  | Frames, crops, and landmarks are dereferenced and garbage collected           |  |
|  |  | immediately after score computation. ZERO BYTES WRITTEN TO LOCAL DISK.        |  |
|  |  +-------------------------------------------------------------------------------+  |
|  +-----------------------------------------+----------------------------------------+  |
|                                            | Numerical Metrics Only                    |
|                                            v                                           |
|  +----------------------------------------------------------------------------------+  |
|  | LOCAL PERSISTENCE BOUNDARY (Edge SQLite)                                         |  |
|  | - Anonymous Node ID (NODE-001)                                                   |  |
|  | - Window Timestamp Summaries                                                     |  |
|  | - RULA/REBA Scores & Risk Durations                                              |  |
|  | - NO FRAMES, NO FACES, NO IDENTIFIERS                                            |  |
|  +-----------------------------------------+----------------------------------------+  |
+============================================|===========================================+
                                             | Anonymized JSON Summary Only
                                             | (NO VIDEO / NO IMAGES / NO BIOMETRICS)
                                             v
+========================================================================================+
|                                   NETWORK BOUNDARY                                     |
|                                                                                        |
|  HTTP POST /api/v1/telemetry                                                           |
|  Wire Payload: Pure ASCII / JSON String (< 1,500 bytes per 5-minute window)            |
|  Auditable: Content is human-readable; zero binary media payload.                      |
+============================================+===========================================+
                                             |
                                             v
+========================================================================================+
|                                 CENTRAL SERVER BOUNDARY                                |
|                                                                                        |
|  - Ingestion schema validation strictly rejects binary or nested image properties.     |
|  - Stores aggregate risk metrics. Impossible to reconstruct worker likeness.           |
+========================================================================================+
```

---

## 3. Exact Telemetry JSON Contract

The data sent over the corporate network is strictly limited to structured, anonymized numerical summaries. Below is an authentic representation of a single 5-minute telemetry payload (PRD §49):

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

### Observations on Payload Anatomy:
1. **Zero High-Dimensional Vectors**: No MediaPipe 33-point coordinates or 468-point face mesh arrays are present.
2. **Normalized Aggregates**: Expression states are reported purely as temporal percentages summing to $100\%$.
3. **Absence of Identity**: The payload identifies the machine (`NODE-001`), not the human operator.

---

## 4. What Is Explicitly Never Sent

To eliminate any ambiguity during institutional reviews and employee consultations, the following data items are strictly barred from transmission or storage (PRD §6, §63):

- ❌ **Webcam Frames & Video Files**: Not even downscaled thumbnails, grayscale versions, or temporary snapshots.
- ❌ **Facial Crops & Avatars**: No cropped rectangles of the user's face or eye regions.
- ❌ **Biometric Embeddings**: No vector representations from FaceNet, DeepFace, InsightFace, or any facial identification library.
- ❌ **Biometric Coordinates**: No raw landmark coordinate tables $(x, y, z)$.
- ❌ **Employee Personal Identifiers**: No employee names, corporate emails, payroll numbers, or domain user accounts.
- ❌ **Surveillance Metadata**: No keystroke logging, active window titles, application usage statistics, or screen captures.
- ❌ **Psychological Diagnoses**: No fields labeled "stress_level", "depression_index", "burnout_score", or "mood".

---

## 5. Privacy Verification & Audit Methodology

EdgeErgo does not ask users to trust its privacy claims on faith; it provides reproducible automated audit tools to prove zero data leakage (PRD §80, §110; Phase 19):

### 5.1 Automated Network Traffic Audit ([`scripts/audit_privacy.py`](file:///c:/Users/georg/EDGE-ERGO%20V3/scripts/audit_privacy.py))
During Phase 19 testing and live deployment, an independent packet inspection script captures and analyzes every outbound network packet emitted by the Edge Agent process:

```
========================================================================
             EDGEERGO LIVE NETWORK TRAFFIC PRIVACY AUDIT
========================================================================
Process Monitored: EdgeErgoAgent.exe (PID: 14820)
Target Host:       http://192.168.1.100:8000
Duration:          01:00:00 (1 Hour Active Monitoring)
------------------------------------------------------------------------
Endpoint                      | Bytes Sent | Media Payload  | Status
------------------------------------------------------------------------
/api/v1/nodes/heartbeat       | 74 B       | NONE (0 bytes) | PASSED
/api/v1/nodes/heartbeat       | 74 B       | NONE (0 bytes) | PASSED
/api/v1/telemetry             | 1,284 B    | NONE (0 bytes) | PASSED
/api/v1/telemetry             | 1,310 B    | NONE (0 bytes) | PASSED
------------------------------------------------------------------------
Summary:
- Total HTTP Requests:        62
- Total Wire Data Outbound:   27.4 KB
- Binary Image / Video Data:  0 BYTES (0.00%)
- Media Headers Detected:     NONE
- Privacy Audit Result:       100% COMPLIANT (ZERO RAW DATA LEAKAGE)
========================================================================
```

### 5.2 Local Storage Audit
An automated test inspects the local edge database (`edgeergo_local.db`) and file system:
- Verifies that no SQLite tables contain `BLOB` columns.
- Scans temporary directories (`%TEMP%`, AppData) to guarantee that no `.jpg`, `.png`, `.mp4`, or raw frame dumps are generated during runtime.

---

## Related Documents
- [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md) — Non-goals and ethical principles.
- [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md) — Volatile memory frame handling.
- [07-data-models.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/07-data-models.md) — Local and central database schemas.
- [10-facial-analysis-scope.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/10-facial-analysis-scope.md) — Expression monitoring boundaries.
- [telemetry-schema.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/api/telemetry-schema.md) — Formal field-level data contract.
