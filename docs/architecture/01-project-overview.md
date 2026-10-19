# 01. Project Overview

EdgeErgo is a privacy-preserving, distributed Edge AI system designed for ergonomic and broad facial-expression monitoring at computer workstations. By shifting all computer vision processing to local worker machines, EdgeErgo prevents invasive surveillance while providing real-time postural feedback and high-level organizational analytics.

---

## 1. Executive Summary

Modern desk workers routinely spend eight or more hours daily in front of computer displays. Prolonged, uncorrected awkward postures (forward neck flexion, spinal slumping, asymmetric shoulder elevation) significantly increase the incidence of Work-Related Musculoskeletal Disorders (WMSDs). Concurrently, cognitive fatigue and eye strain manifest through observable facial tension, squinting, and reduced movement (PRD §1, §3).

Traditional automated ergonomic assessment systems rely on centralized cloud computer vision: raw video feeds from webcams are streamed across corporate networks to cloud servers running heavy deep learning models. This centralized model creates critical vulnerabilities:
1. **Severe Privacy Infringement**: Employees reject continuous streaming of their private desk environments and faces.
2. **Network Saturation**: Streaming high-resolution video streams from hundreds of workstations exhausts local bandwidth.
3. **Single Point of Failure**: When cloud connectivity drops, all monitoring and posture alerts cease immediately.

EdgeErgo resolves this dilemma by implementing a **distributed Edge AI architecture**. Each worker computer acts as an independent **Edge Node** equipped with a lightweight **Edge Agent**. The Edge Agent processes monocular webcam frames locally in volatile memory, computes standard ergonomic risk scores (RULA and REBA) and broad facial affect classes, alerts the worker through a lightweight desktop overlay, and transmits only compact, anonymized numerical summaries to an on-premise **Central Server** (PRD §1, §8).

```
+-----------------------------------------------------------------------------------+
|                                INDIVIDUAL LEVEL (EDGE)                            |
|                                                                                   |
|  [Camera] ---> [Local Edge AI] ---> [Ergonomic & Face] ---> [Worker Overlay]     |
|                                            |                                      |
+--------------------------------------------|--------------------------------------+
                                             | Anonymized Window Summaries
                                             v
+-----------------------------------------------------------------------------------+
|                               COLLECTIVE LEVEL (CENTRAL)                          |
|                                                                                   |
|  [Central Server] ---> [Aggregation Engine] ---> [Dashboard / CSV / Reports]     |
+-----------------------------------------------------------------------------------+
```

---

## 2. The Core Design Principle

Every architectural decision in EdgeErgo is governed by one guiding maxim (PRD §1, §8, §123):

> **"Analyze locally. Alert locally. Store locally. Transmit only necessary summaries. Aggregate centrally."**

- **Analyze Locally**: Video frames are processed inside worker machine RAM via OpenCV and MediaPipe. Frames are discarded immediately after landmark extraction.
- **Alert Locally**: Posture corrections and break notifications are generated natively on the worker PC using a non-intrusive desktop overlay.
- **Store Locally**: Granular frame-level metrics and windowed session records are stored in a local SQLite database on the worker machine.
- **Transmit Only Summaries**: Only aggregated telemetry windows (e.g., 5-minute anonymized JSON records) are transmitted to the Central Server.
- **Aggregate Centrally**: The Central Server computes team-level risk distributions, department compliance averages, and temporal heatmaps without ever possessing the ability to reconstruct raw footage.

---

## 3. Problem Statement

Office and remote computer workers suffer from chronic postural degradation due to static seating postures, suboptimal desk and display heights, and prolonged cognitive focus without restorative breaks (PRD §3). 

Existing workplace solutions suffer from major operational deficiencies:
- **Manual Ergonomic Audits**: Professional on-site ergonomic evaluations using paper-based RULA (Rapid Upper Limb Assessment) or REBA (Rapid Entire Body Assessment) are infrequent, expensive, subjective, and capture only a single static instant in time.
- **Wearable Sensors**: Inertial measurement units (IMUs) or posture harnesses require constant battery charging, manual calibration, and physical discomfort, leading to high employee abandonment rates.
- **Cloud-Based Vision Surveillance**: Cloud streaming cameras represent unacceptable surveillance overreach, exposing employees to privacy leaks and violating strict workplace data protection regulations.

EdgeErgo bridges this gap by delivering objective, continuous, automated ergonomic assessments using standard, commodity webcams without ever exposing workers to surveillance risks.

---

## 4. Product Vision

To establish a non-invasive, privacy-preserving standard for digital workplace health where workers receive autonomous, real-time posture coaching and organizations gain actionable ergonomic intelligence without compromising individual privacy (PRD §2, §120).

---

## 5. Goals

### 5.1 Primary Goals (PRD §4.1)
1. **Local Edge Processing**: Execute all computer vision models locally on commodity worker CPUs without requiring dedicated GPUs or cloud computation.
2. **Body Landmark Detection**: Track 33 standard human body landmarks using lightweight pose estimation (MediaPipe Pose).
3. **Biomechanical Angle Calculation**: Compute joint flexion/extension angles for the neck, trunk, upper arms, lower arms, and wrists using vector dot-product geometry.
4. **Ergonomic Assessment**: Calculate standardized ergonomic risk indices conforming to validated RULA and REBA scoring methodologies.
5. **Facial-Expression Classification**: Classify broad, non-medical facial expression states locally using facial landmarks.
6. **Configurable Scheduling**: Support duty-cycle monitoring schedules (e.g., sample for 30 seconds every 5 minutes) to conserve system resources.
7. **Temporal Persistence Filtering**: Differentiate momentary shifts from sustained slouching, triggering alerts only when poor posture persists beyond a defined duration threshold.
8. **Real-Time Worker Feedback**: Display immediate, non-intrusive posture corrections, break reminders, and hydration notifications via a native desktop overlay.
9. **Break and Movement Reminders**: Encourage regular micro-breaks and postural adjustments based on continuous sitting duration.
10. **Local SQLite Persistence**: Maintain historical telemetry and event logs locally on each workstation.
11. **Offline Independence**: Ensure Edge Agents operate autonomously without disruption when network connectivity or the Central Server is unavailable.
12. **Resilient Synchronization**: Automatically queue and transmit unsent summaries once central server connectivity is restored.
13. **Strict Data Minimization**: Transmit only compact, anonymized JSON summaries containing numerical scores and duration percentages.
14. **Multi-Node Aggregation**: Aggregate telemetry across multiple independent worker nodes (`NODE-001`, `NODE-002`, ...).
15. **Collective Risk Analytics**: Generate organizational ergonomic risk profiles, postural breakdown trends, and department compliance metrics.
16. **Collective Expression Statistics**: Provide macro-level facial engagement and fatigue-indicator proportions.
17. **Observed Pattern Analysis**: Analyze observational correlations between high ergonomic risk postures and expressive states without inferring causality.
18. **Centralized Management Dashboard**: Provide an interactive web dashboard for ergonomic supervisors and system administrators.
19. **Standardized Data Export**: Support raw aggregate data export in CSV format for third-party auditing and longitudinal research.
20. **Comprehensive Reporting**: Automatically generate structured HTML/PDF ergonomic summary reports.
21. **Low Resource Footprint**: Constrain agent CPU utilization to ≤15–20% on standard dual-core/quad-core office laptops.
22. **Cross-Hardware Deployability**: Provide a turnkey installer capable of running out-of-the-box on standard Windows workstations.

### 5.2 Secondary Goals (PRD §5)
- Provide a zero-configuration installation flow using bundled standalone executables.
- Minimize user friction: the Edge Agent runs unobtrusively in the background without requiring daily manual initiation or calibration.

---

## 6. Non-Goals (Explicit Boundaries)

To ensure ethical integrity, legal compliance, and technical feasibility, EdgeErgo explicitly excludes the following capabilities (PRD §6):

| Non-Goal | Architectural Rationale |
| :--- | :--- |
| **No Medical Diagnostics** | EdgeErgo does not diagnose carpal tunnel syndrome, cervical spondylosis, spinal disc herniation, or any clinical disorder. It is an educational and preventative awareness tool. |
| **No Injury Confirmation** | The system does not confirm, predict, or evaluate individual physical injuries. |
| **No Psychological Assertions** | The system **never** reports clinical psychological states such as "depressed", "stressed", "anxious", or "burnt out". Expression telemetry is strictly limited to observable physical facial movements. |
| **No Facial Recognition** | The system does not detect identity, match faces against a database, or verify worker attendance. |
| **No Raw Video Storage/Streaming** | Central servers, cloud endpoints, and network logs **never** receive raw frames, cropped faces, or biometric embeddings. |
| **No Continuous Video Recording** | Video frames are ephemeral; they reside in local RAM for milliseconds during inference and are instantly overwritten. |
| **No Ergonomist Replacement** | The software serves as a screening and tracking aid, not a certified clinical ergonomic practitioner. |
| **No Multi-Person Assessment** | The camera pipeline targets a single workstation operator positioned within the primary foreground. Background bystanders are filtered out. |
| **No Workforce Surveillance** | The platform does not track keystrokes, monitor active applications, take desktop screenshots, or measure worker productivity. |
| **No Cloud Dependency** | Core processing and alerting do not require cloud services, third-party APIs, or external SaaS infrastructure. |

---

## 7. Target Users & Personas

EdgeErgo serves two primary user categories with distinct permissions and interfaces (PRD §7.1, §7.2):

### 7.1 Worker / Individual Desk Operator
- **Context**: Office workers, software engineers, customer support agents, and remote employees working at computer monitors for extended shifts.
- **Needs**: Instant, non-intrusive feedback when falling into harmful posture habits; guidance on when to rest; complete assurance that their employer cannot view their webcam or spy on their home office.
- **Interface**: Lightweight native desktop overlay (PySide6) positioned in a screen corner, providing color-coded status badges, gentle toast notifications, and private daily summary stats.

### 7.2 Ergonomics Officer / HR Administrator / Supervisor
- **Context**: Occupational health and safety (OH&S) managers, facility ergonomics teams, and department leads responsible for workplace wellbeing.
- **Needs**: Macro-level visibility into departmental posture risk, effectiveness of ergonomic chair/desk investments, identification of high-risk work shifts, and exportable compliance reports.
- **Interface**: Central Web Analytics Dashboard (FastAPI + React) displaying anonymized workstation cards, collective risk distributions, compliance metrics, and automated PDF/CSV export tools.

---

## Related Documents
- [02-system-architecture.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/02-system-architecture.md) — Two-layer distributed design.
- [03-tech-stack.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/03-tech-stack.md) — Technology selections and trade-offs.
- [06-data-flow-and-privacy.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/06-data-flow-and-privacy.md) — Privacy boundary specification.
- [10-facial-analysis-scope.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/10-facial-analysis-scope.md) — Ethical boundaries of facial classification.
