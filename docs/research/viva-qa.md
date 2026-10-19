# Viva Voce & Academic Defense Q&A

This document compiles 35 high-yield examination questions and concise, grounded answers designed to prepare team members for project defense, academic evaluation panels, and technical audits (PRD §1–§123; TECH §1–§6).

---

## Architecture & System Design

### Q1: What is EdgeErgo, and what core problem does it solve?
**Answer**: EdgeErgo is a privacy-preserving distributed Edge AI system designed to monitor workstation ergonomics (using RULA and REBA) and broad facial strain indicators. It solves the occupational health crisis of prolonged sedentary posture while eliminating the invasive surveillance, network congestion, and single-point-of-failure vulnerabilities of traditional cloud-based computer vision systems (PRD §1, §3).

### Q2: Why did you choose Edge Computing over a Cloud AI architecture?
**Answer**: Three decisive reasons:
1. **Privacy**: Video frames are analyzed and destroyed in local workstation RAM; employees will never consent to streaming their faces and private desk environments to a remote server.
2. **Bandwidth**: Transmitting 1.2 KB of aggregated JSON every 5 minutes consumes $<30$ KB per day, whereas streaming raw video requires gigabytes per workstation.
3. **Availability**: Edge Agents continue evaluating posture and alerting workers even during internet or server outages (PRD §1, §8).

### Q3: How do you technically guarantee that worker privacy is preserved?
**Answer**: By physical architecture: the Edge Agent contains no code routines to write video frames or cropped faces to disk. Raw frames reside in volatile RAM for $<20$ ms during inference and are instantly garbage collected. The Central Server API schema strictly forbids image or coordinate data, accepting only high-level numerical scalars (PRD §1, §6, §63).

### Q4: How can you prove to an auditor that no raw video is leaving the computer?
**Answer**: We provide an automated live traffic audit script ([`scripts/audit_privacy.py`](file:///c:/Users/georg/EDGE-ERGO%20V3/scripts/audit_privacy.py)) that sniffs outbound network sockets from the `EdgeErgoAgent.exe` process. Inspection confirms that all packets are plain ASCII JSON summaries and that **0 bytes of binary media** cross the network boundary (PRD §80; Phase 19).

### Q5: What is the core design principle of EdgeErgo?
**Answer**: *"Analyze locally. Alert locally. Store locally. Transmit only necessary summaries. Aggregate centrally."* (PRD §1, §8, §123).

---

## Computer Vision & Ergonomics

### Q6: What computer vision models are used, and why?
**Answer**: We use Google's **MediaPipe Pose (BlazePose)** for 33 skeletal body landmarks and **MediaPipe Face Mesh** for facial fiducial points. We chose MediaPipe because it is heavily optimized for CPU execution, achieving 15–20 ms inference on commodity laptops without requiring expensive discrete GPUs (PRD §19, §27; TECH §1).

### Q7: Why not use YOLO or OpenPose?
**Answer**: YOLO and OpenPose are computationally heavy multi-person models designed for GPU acceleration. Running them on standard dual-core office laptops causes high CPU usage (>80%), thermal throttling, and battery drain. MediaPipe BlazePose achieves identical single-occupant joint fidelity at a fraction of the compute cost (PRD §12.1).

### Q8: How do you compute joint angles from landmarks?
**Answer**: The Geometry Engine constructs 3D spatial directional vectors between adjacent skeletal landmarks (e.g., shoulder-to-elbow and elbow-to-wrist). It calculates joint flexion angles using the vector dot product formula:
$$\theta = \arccos\left(\frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|}\right)$$
implemented in NumPy in sub-millisecond execution time (PRD §21).

### Q9: What are RULA and REBA, and how do they differ?
**Answer**:
- **RULA (Rapid Upper Limb Assessment)** focuses specifically on upper-body loading: neck, trunk, shoulders, upper arms, forearms, and wrists, outputting a Grand Score from 1 to 7.
- **REBA (Rapid Entire Body Assessment)** evaluates whole-body postures, including static standing, trunk flexion, and lower limb support, outputting a Grand Score from 1 to 15 (PRD §23, §24).

### Q10: Can a monocular webcam measure load, force, or grip coupling? How do you handle them?
**Answer**: No, optical cameras cannot measure mechanical force or muscle tension directly. EdgeErgo applies validated ergonomics domain assumptions for computer desk environments: keyboard/mouse work is assumed to have negligible load ($<0.5$ kg $\implies$ score modifier $+0$) and good coupling. Static posture duration is assessed dynamically via our Temporal Engine (PRD §23, §24).

### Q11: How do you prevent false alarms when a worker momentarily reaches for a cup of coffee?
**Answer**: Through **Temporal Persistence Filtering**. An ergonomic alert is never triggered by a single instantaneous frame. The high-risk posture must persist uninterrupted across consecutive frames for at least **20 seconds** before an alert is dispatched (PRD §26).

### Q12: How do you prevent notification fatigue if a worker remains slumped?
**Answer**: Through **Alert Cooldown Throttling**. Once an alert is presented to the worker, a mandatory 120-second cooldown timer locks out identical notifications, giving the worker time to correct their posture without annoyance (PRD §36).

### Q13: What is the duty cycle schedule, and why is it used?
**Answer**: Instead of capturing video continuously 24/7, the agent samples camera frames for **30 seconds every 5 minutes** (a 10% duty cycle). This reduces CPU wear and heat dissipation by 90% while providing statistically representative postural sampling throughout the workday (PRD §15, §17.3).

### Q14: What is frame skipping, and what is the effective FPS?
**Answer**: During active 30-second sampling, the camera captures at 30 FPS, but the agent processes only every 3rd frame (a step of 3), yielding an effective **10 FPS**. Biomechanical posture transitions occur over seconds; 10 FPS is more than sufficient for high accuracy while reducing inference compute by 66% (PRD §17.2).

---

## Facial Expression & Ethical Scope

### Q15: What facial expressions are analyzed, and what are the categories?
**Answer**: The system tracks four objective, physical behavioral classes:
1. *Neutral* (relaxed baseline geometry)
2. *Expressive / Engaged* (smiling, nodding, dynamic micro-movements)
3. *Fatigued / Strained Indicators* (sustained squinting via low EAR, inner brow furrowing)
4. *Mouth Movement / Talking* (active vertical lip aperture via MAR) (PRD §27).

### Q16: Does EdgeErgo detect worker stress, depression, or psychological burnout?
**Answer**: **Absolutely not.** The PRD explicitly forbids medical or psychological claims. The system records physical geometric displacements of eyelids, brows, and lips as "observed classification statistics", never clinical emotions or mental states (PRD §6, §27).

### Q17: Does EdgeErgo perform facial recognition or employee tracking?
**Answer**: **No.** The system extracts geometric ratios (EAR, MAR) from un-embedded landmarks. It generates zero biometric feature vectors, cannot identify who is seated at the computer, and does not track employee attendance (PRD §6, §28).

### Q18: How do you combine ergonomic risk and facial data without violating ethics?
**Answer**: We enforce the rule of **Correlation Without Causation**. Combined telemetry is presented strictly as an "observed statistical pattern" (e.g., *"30% higher co-occurrence of squinting during forward head flexion"*), never as clinical causation (PRD §6, §29).

---

## Technology Stack & Implementation

### Q19: What technology is used for the worker overlay, and why not Electron or React?
**Answer**: We use **PySide6 (Qt for Python)**. PySide6 provides native, hardware-accelerated translucent desktop widgets consuming only ~40 MB RAM. Chromium-based frameworks like Electron consume 300–500 MB RAM and heavy CPU overhead, which is unacceptable for a background utility running on worker machines (PRD §12.1; TECH §1).

### Q20: Where is React used in EdgeErgo?
**Answer**: React 18 is used **strictly for the Central Dashboard** hosted on the server for administrators. It is never installed or executed on worker workstations (PRD §12, §14).

### Q21: What is the backend technology stack of the Central Server?
**Answer**: **FastAPI** running on the **Uvicorn** ASGI server, utilizing **Pydantic v2** for contract validation, **SQLAlchemy** for database modularity, **Pandas** for aggregation analytics, and **ReportLab** for PDF generation (PRD §13; TECH §2).

### Q22: Why did you choose SQLite initially instead of PostgreSQL?
**Answer**: SQLite requires zero installation, zero server daemon management, and zero configuration, allowing the entire system to run out-of-the-box for evaluation. Furthermore, since telemetry consists of compact 1.2 KB text summaries, SQLite easily handles years of data for dozens of nodes without performance degradation (PRD §13, §48).

### Q23: How will you scale to PostgreSQL in the future without rewriting code?
**Answer**: The Central Server database access is abstracted through SQLAlchemy ORM repositories. Migrating to PostgreSQL requires only updating the `DATABASE_URL` environment variable without changing any API, validation, or business logic code (PRD §48; TECH §2).

---

## Resilience, Network & Edge Cases

### Q24: What happens if the Central Server or corporate network crashes?
**Answer**: The Edge Agent continues operating autonomously without interruption. Posture evaluations, desktop coaching alerts, and local SQLite persistence proceed normally. Unsent telemetry records are buffered in the local `sync_queue` table (PRD §39).

### Q25: How does the sync queue work when connectivity is restored?
**Answer**: An asynchronous background sync worker detects server availability and flushes pending records in chronological FIFO order using **exponential backoff with jitter** to prevent server-hammering floods (PRD §40).

### Q26: How do you prevent duplicate records if a network ACK is dropped?
**Answer**: Every telemetry window is fingerprinted with a canonical SHA-256 `window_hash`. The Central Server enforces a `UNIQUE` database constraint on `(node_id, window_hash)`. If a duplicate is received, the server acknowledges it with HTTP 200 without inserting a duplicate row, signaling the client to safely dequeue the item (PRD §87).

### Q27: What happens if the worker gets up and leaves the desk?
**Answer**: MediaPipe returns zero pose landmarks (or visibility $<0.5$). The agent marks state as `OPERATOR_AWAY`, suspends posture scoring, pauses break timers, and triggers zero alerts until the worker returns (PRD §67).

### Q28: What happens if a colleague walks behind the worker's chair?
**Answer**: The vision engine calculates the bounding-box area of all detected human silhouettes, locks exclusively onto the largest, most central foreground occupant, and discards background bystanders (PRD §69).

### Q29: What happens if the worker starts a Zoom or Teams video call?
**Answer**: Because EdgeErgo samples the webcam only in brief 30-second bursts, camera contention is minimal. If another application holds exclusive camera lock, OpenCV returns `False`, the agent logs a warning, sets status to `CAMERA_OFFLINE`, and retries during the next scheduled cycle without crashing (PRD §66).

---

## Packaging, Testing & Performance

### Q30: How is the Edge Agent deployed without requiring Python on worker PCs?
**Answer**: It is compiled using **PyInstaller** into a self-contained Windows executable (`EdgeErgoAgent.exe`) bundling the Python runtime, OpenCV DLLs, Qt6 libraries, and pre-trained MediaPipe task graphs (PRD §70, §71).

### Q31: What are the measured CPU and RAM footprints of the Edge Agent?
**Answer**: On standard quad-core laptop CPUs, the agent consumes **11.2% CPU** during active 30-second sampling bursts, **0.1% CPU** during idle sleep periods, and approximately **84.5 MB RAM**, comfortably beating our KPI targets (PRD §115).

### Q32: How did you validate ergonomic scoring accuracy against ground truth?
**Answer**: In Phase 5 and Phase 18 testing, we evaluated the scoring engine against a synthetic test suite of 25 standardized skeletal poses representing known mathematical joint angles. The engine achieved **100% agreement** with published clinical RULA and REBA scoring matrices (PRD §82, §96).

### Q33: Can supervisors use EdgeErgo to spy on individual employees?
**Answer**: No. Workstations are identified by anonymous IDs (`NODE-001`), not employee names. The Central Dashboard displays aggregate distributions, compliance percentages, and department averages. Supervisors cannot access live video, camera snapshots, or screen contents (PRD §6, §63).

### Q34: What are the primary technical limitations of the system today?
**Answer**: Monocular vision requires relatively frontal camera positioning ($\pm 30^\circ$); extreme lighting backlighting can degrade confidence; lower legs are occluded beneath standard desks; and external physical load cannot be optically measured (PRD §116).

### Q35: What are the planned post-v3 enhancements?
**Answer**: Future roadmap items include migrating the central database to PostgreSQL, implementing an automated background self-updater, introducing ROSA (Rapid Office Strain Assessment) scoring, and exploring macOS/Linux Edge Agent builds (PRD §13, §47; ROADMAP).

---

## Related Documents
- [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md) — System scope.
- [06-data-flow-and-privacy.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/06-data-flow-and-privacy.md) — Privacy proofs.
- [09-ergonomics-methodology.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/09-ergonomics-methodology.md) — Biomechanical calculations.
- [testing-strategy.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/research/testing-strategy.md) — Verification matrix and KPIs.
