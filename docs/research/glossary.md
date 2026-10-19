# Glossary of Terms & Acronyms

This glossary provides concise, authoritative definitions of the technical, ergonomic, and distributed systems terminology used throughout EdgeErgo documentation and codebase.

---

### A
- **Anonymized Summary**: A compact JSON data structure containing aggregated statistical scores (e.g., average RULA, risk percentages) computed over a monitoring window. Contains zero video frames, cropped images, or personal identifying information (PRD §49).
- **ASGI (Asynchronous Server Gateway Interface)**: The Python standard for asynchronous web servers and applications (e.g., Uvicorn and FastAPI), enabling high-concurrency event loops (TECH §2).

### B
- **BlazePose**: Google’s lightweight convolutional neural network pipeline (underlying MediaPipe Pose) capable of inferring 33 3D skeletal landmarks from a single 2D camera frame in real time on commodity CPUs (PRD §19).

### C
- **Central Layer**: The on-premise server environment responsible for node registration, heartbeat monitoring, telemetry ingestion, multi-workstation aggregation, reporting, and dashboard hosting (PRD §11).
- **Central Server**: The centralized backend service executing FastAPI, SQLite, and background analytics routines on the organizational network (PRD §11; TECH §2).
- **Cooldown**: A throttling duration (default: 120 seconds) enforcing a mandatory silence window after an alert, preventing notification fatigue when a worker remains in a suboptimal posture (PRD §36).

### D
- **Duty Cycle**: A scheduled monitoring cadence alternating between brief active camera sampling bursts (e.g., 30 seconds) and idle sleep intervals (e.g., 4.5 minutes), minimizing system resource consumption (PRD §15, §17.3).

### E
- **EAR (Eye Aspect Ratio)**: A scalar geometric ratio measuring the vertical opening of the palpebral fissure relative to horizontal eye width, used to identify physical squinting and prolonged eye closure (PRD §27).
- **Edge Agent**: The autonomous Python background client installed on a worker computer, orchestrating camera acquisition, computer vision, kinematics, scoring, desktop overlay alerts, and local persistence (PRD §10).
- **Edge Computing**: A distributed computing paradigm where data processing and machine learning inference are performed directly on local endpoint devices (at the "edge" of the network) rather than streaming raw data to cloud servers (PRD §1, §8).
- **Edge Node**: A specific worker computer running the Edge Agent, uniquely identified in network transactions by an assigned machine identifier (e.g., `NODE-001`) (PRD §10, §42).

### F
- **Face Mesh**: A high-density geometric landmark pipeline (MediaPipe Face) tracking facial fiducial points in volatile memory to calculate aspect ratios without extracting identity vectors (PRD §27).
- **Frame Skipping**: The computational optimization of processing only 1 out of every $n$ camera frames (e.g., step = 3 $\implies$ 10 FPS effective from a 30 FPS webcam) to conserve CPU cycles (PRD §17.2).

### I
- **Idempotency**: An API property guaranteeing that identical requests dispatched multiple times produce the exact same outcome as a single request. Enforced via `window_hash` unique constraints (PRD §87).

### M
- **MAR (Mouth Aspect Ratio)**: A scalar ratio measuring vertical lip aperture relative to horizontal lip width, identifying active speaking during calls or yawning (PRD §27).
- **MediaPipe**: Google's open-source cross-platform machine learning framework delivering CPU-optimized computer vision pipelines (BlazePose, Face Mesh) (PRD §12.1; TECH §1).
- **Monocular Computer Vision**: Estimating 3D spatial properties from a single 2D RGB camera sensor, without requiring stereoscopic lenses or infrared depth projectors (PRD §18).
- **MSD / WMSD (Work-Related Musculoskeletal Disorder)**: Injuries or pain affecting muscles, tendons, nerves, and spinal discs caused by prolonged static postures, repetitive movements, and ergonomic strain at workstations (PRD §3).

### N
- **Neck Flexion / Extension**: Anatomical sagittal bending of the cervical spine. Flexion represents downward/forward tilting beyond $20^\circ$; extension represents backward tilting (PRD §21, §23).

### O
- **Offline-First**: A software architecture designed to execute all primary functions locally without an active network connection, buffering outgoing data into a persistent queue until connectivity is restored (PRD §39).

### P
- **Persistence (Temporal Persistence)**: The operational requirement that an adverse ergonomic condition must be sustained continuously for a minimum threshold (e.g., 20 seconds) before triggering an alert, filtering out momentary movements (PRD §26).
- **PyInstaller**: A build tool that freezes Python programs into standalone native executables (`.exe`) bundling the interpreter, libraries, and binary assets (PRD §71; TECH §5).
- **PySide6**: The official Python binding for the Qt 6 GUI toolkit, used by EdgeErgo to render hardware-accelerated, transparent desktop overlay widgets on worker screens (PRD §12.1; TECH §1).

### R
- **REBA (Rapid Entire Body Assessment)**: An internationally validated ergonomic postural rubric (Hignett & McAtamney, 2000) yielding a whole-body Grand Score from 1 to 15 (PRD §24).
- **RULA (Rapid Upper Limb Assessment)**: An ergonomic evaluation rubric (McAtamney & Corlett, 1993) focusing on the neck, trunk, and upper limbs, yielding a Grand Score from 1 to 7 (PRD §23).

### S
- **Sync Queue**: A transactional SQLite table (`sync_queue`) on the Edge Node storing unsent telemetry payloads with retry counters and timestamps, ensuring zero data loss during network partitions (PRD §38, §40).

### T
- **Telemetry Window**: A discrete temporal accounting window (typically 5 minutes) aggregating duty cycle samples into an anonymized summary record (PRD §49).
- **Trunk Inclination**: The forward, lateral, or twisting angle of the thoracic/lumbar spine relative to the vertical plumb line (PRD §21, §23).

### U
- **Uvicorn**: A lightning-fast ASGI web server implementation used to run FastAPI applications (TECH §2).

### W
- **WAL (Write-Ahead Logging)**: A SQLite journaling mode where changes are appended to a separate log file, enabling concurrent reads while writes are being committed (PRD §86).
- **Window Hash**: A SHA-256 fingerprint generated across canonical telemetry fields, serving as a global primary key for deduplication on the Central Server (PRD §87).

---

## Related Documents
- [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md) — System concepts.
- [03-tech-stack.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/03-tech-stack.md) — Frameworks defined in this glossary.
- [09-ergonomics-methodology.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/09-ergonomics-methodology.md) — Ergonomic standards.
- [basic-knowledge.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/research/basic-knowledge.md) — Technical deep-dives.
