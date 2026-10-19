# Limitations & Risk Analysis

This document examines the known physical and technical limitations of monocular computer vision in office environments, alongside the project's formal operational risk matrix and mitigations (PRD §6, §66–§69, §116).

---

## 1. Known Technical & Environmental Limitations

Automated visual ergonomic assessment using standard commodity webcams operates under real-world constraints that must be accounted for during deployment and academic evaluation:

### 1.1 Camera Placement & Perspective Distortion
- **The Challenge**: Laptop webcams view the operator from below, whereas monitors mounted high view from above. Off-axis angles distort perceived 2D sagittal neck flexion.
- **System Constraint**: EdgeErgo requires the camera to be positioned relatively frontal (within $\pm 30^\circ$ azimuth of the worker's face and torso) for reliable landmark estimation.
- **Mitigation**: An interactive camera preview wizard during first-run setup guides the worker to position their display and chair so their head and shoulders fit comfortably within the target framing box.

### 1.2 Environmental Lighting & Backlighting
- **The Challenge**: Harsh direct sunlight behind the worker (backlighting) silhouettes the face, while dim office lighting degrades optical contrast, introducing landmark jitter.
- **System Constraint**: MediaPipe landmark confidence drops in sub-optimal illumination.
- **Mitigation**: The preprocessor calculates average frame luminance. If confidence falls below **0.60**, samples are tagged `LOW_CONFIDENCE` and excluded from scoring rather than producing false postural alarms (PRD §68).

### 1.3 Physical Occlusion by Office Desks & Apparel
- **The Challenge**: Standard office desks completely obstruct the lower legs, knees, and feet from monocular webcam view. Loose winter sweaters or bulky clothing can obscure exact elbow and shoulder joint pivots.
- **System Constraint**: The system cannot directly observe foot-ground contact or precise forearm rotation while typing.
- **Mitigation**: EdgeErgo applies standard validated ergonomic assumptions: computer workers are modeled as seated with bilateral foot support (REBA leg score = 1). Upper arm and neck vectors rely on skeletal points less susceptible to clothing occlusion (nose, ear, and acromion shoulder points).

### 1.4 Single-Person Workstation Constraint
- **The Challenge**: Colleagues frequently walk past in open-plan offices, or stand behind a worker's desk to converse.
- **System Constraint**: The system is calibrated for a single primary workstation occupant.
- **Mitigation**: When multiple humans are detected in the frame, the vision engine calculates the pixel bounding-box area of each detected subject, locks exclusively onto the largest, most centrally positioned foreground occupant, and discards background bystanders (PRD §69).

### 1.5 Inability to Sense Mechanical Load & Grip Force
- **The Challenge**: Monocular webcams cannot detect muscle activation, grip tension, or the physical weight of handled objects.
- **System Constraint**: RULA and REBA load/force modifiers cannot be computed directly from pixels.
- **Mitigation**: Computer workstation tasks involve lightweight peripherals (<0.5 kg). The system assumes a baseline load modifier of $+0$ kg, focusing on joint geometry and static holding duration (PRD §23, §24).

---

## 2. Expanded Risk & Mitigation Matrix

The table below synthesizes the project's risk analysis, severity ratings, and architectural safeguards (PRD §116):

| Risk Description | Severity | Likelihood | Architectural Mitigation Strategy |
| :--- | :---: | :---: | :--- |
| **Alert Fatigue / Worker Annoyance**<br>Frequent, unwarranted desktop alerts cause workers to disable or uninstall the agent. | **HIGH** | Medium | **Persistence & Cooldown Filtering**:<br>Alerts require $\ge 20$ seconds of uninterrupted high risk to trigger, followed by a mandatory 120-second cooldown lockout. Non-intrusive, auto-dismissing visual toasts are used instead of jarring audio alarms (PRD §26, §36). |
| **Worker Surveillance Concerns**<br>Employees suspect the software secretly streams camera footage to management. | **CRITICAL** | High | **Verifiable Zero-Leakage Architecture**:<br>Frames are destroyed in volatile memory within 30 ms. Transmitted payloads contain only compact JSON summaries. An open-source packet inspection script ([`scripts/audit_privacy.py`](file:///c:/Users/georg/EDGE-ERGO%20V3/scripts/audit_privacy.py)) allows anyone to verify that zero image bytes leave the machine (PRD §1, §6, §80). |
| **System Resource Saturation**<br>Agent overheats laptop CPUs, spins fans, or exhausts battery life. | **HIGH** | Medium | **Duty Cycling & Frame Skipping**:<br>Camera runs for only 30 seconds every 5 minutes (a 10% duty cycle). During sampling, the agent processes 1 in 3 frames at downscaled 320×240 resolution. CPU utilization remains $\le 15\%$ on dual-core chips (PRD §15, §17.1, §17.2). |
| **Corporate Network Disconnections**<br>Server reboots, VPN drops, or network switches fail, preventing telemetry uploads. | **MEDIUM** | High | **Offline-First SQLite Sync Queue**:<br>Telemetry is committed to local SQLite before network transmission. Unsent summaries queue with exponential backoff retries, ensuring zero data loss during prolonged network outages (PRD §39, §40). |
| **Data Duplication & Double-Counting**<br>Network retries cause the server to receive duplicate telemetry windows, skewing stats. | **MEDIUM** | Medium | **SHA-256 Window Hash Deduplication**:<br>Every window payload carries a cryptographic hash. The Central Server enforces a `UNIQUE` index, gracefully acknowledging duplicates without double-writing (PRD §87). |
| **Camera Hardware Contention**<br>Agent blocks the webcam when the worker joins a Microsoft Teams or Zoom meeting. | **HIGH** | Medium | **Smart Sharing & Graceful Backoff**:<br>The agent captures video in short 30-second bursts. If another video application requests the camera, the agent releases the device handle, marks status as `CAMERA_OFFLINE`, and retries during the next scheduled cycle (PRD §66). |

---

## Related Documents
- [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md) — Non-goals and ethical boundaries.
- [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md) — Failure handling implementations.
- [06-data-flow-and-privacy.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/06-data-flow-and-privacy.md) — Privacy boundary verification.
- [09-ergonomics-methodology.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/09-ergonomics-methodology.md) — Non-vision ergonomic assumptions.
