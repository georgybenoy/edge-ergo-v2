# Foundational Concepts & Technical Primer

This document serves as an accessible technical explainer for students, evaluators, and engineers reviewing EdgeErgo. It demystifies the core theoretical and software engineering concepts underpinning the project: edge computing, computer vision kinematics, ergonomic clinical frameworks, distributed queues, and modern application packaging.

---

## 1. Edge Computing vs. Cloud Computing

The defining architectural decision of EdgeErgo is processing video at the **Edge** (the worker's workstation) rather than in the **Cloud**:

```
CLOUD COMPUTING ARCHITECTURE (Traditional / Invasive)
[ Camera ] === Raw Video Stream (MB/s) ===> [ Corporate WAN / Cloud Server ]
- Severe privacy violation (employee video crosses the wire).
- Heavy bandwidth consumption (100 cameras = 200+ Mbps).
- High cloud GPU hosting costs.
- System fails completely if internet connection drops.

EDGE COMPUTING ARCHITECTURE (EdgeErgo / Privacy-Preserving)
[ Camera ] ---> [ Local CPU RAM ] ---> [ Instant Destruction ]
                       |
                       +---> [ 1.2 KB Anonymized JSON Summary ] ===> [ Local LAN Server ]
- 100% privacy guarantee (raw video never leaves volatile RAM).
- Negligible bandwidth (< 30 KB per node per day).
- Zero cloud GPU infrastructure costs.
- Continuous autonomous operation during internet/server outages.
```

---

## 2. Distributed Systems Fundamentals

EdgeErgo is a **distributed system** composed of multiple independent computational nodes communicating over a network:
- **Autonomous Node**: An Edge Node functions as an independent state machine. It does not wait for server permission to evaluate posture or trigger desktop alerts.
- **Eventual Consistency**: When an Edge Node is disconnected from the network, its local database diverges from the Central Server. Upon reconnection, the node drains its sync queue, bringing the central database into eventual consistency with all historical events.
- **Partition Tolerance**: Under the CAP Theorem (Consistency, Availability, Partition Tolerance), EdgeErgo prioritizes **Availability** and **Partition Tolerance** at the edge: workers continue receiving posture coaching regardless of network health.

---

## 3. Pose Estimation & MediaPipe Landmarks

Human pose estimation involves predicting spatial anatomical landmark coordinates from 2D pixel grids:
- **MediaPipe Pose (BlazePose)**: A specialized, lightweight two-stage convolutional pipeline designed by Google for real-time mobile and CPU inference.
  1. *Detector*: Locates the person/torso region of interest (ROI) within the downsampled frame.
  2. *Landmark Tracker*: Predicts **33 3D skeletal keypoints** $(x, y, z)$ within the bounding box, where $x, y$ are normalized screen coordinates $[0.0, 1.0]$ and $z$ represents estimated depth relative to the mid-hip point.
- **Why BlazePose for Edge AI?** Unlike heavy multi-person models (e.g., OpenPose or HRNet) requiring discrete NVIDIA GPUs, MediaPipe executes in **15–25 ms on standard dual-core laptop CPUs**.

```
                0 (Nose)
             1 /  \ 4
            2      5
            3      6
          7 (Ear)  8 (Ear)
              9   10
      11 (L.Shoulder) ----- 12 (R.Shoulder)
             |                     |
             | 13 (L.Elbow)        | 14 (R.Elbow)
             |                     |
             | 15 (L.Wrist)        | 16 (R.Wrist)
             |                     |
      23 (L.Hip) ---------- 24 (R.Hip)
```

---

## 4. Biomechanical Joint Angle Mathematics

To evaluate ergonomic criteria, the Geometry Engine calculates joint angles from 3D landmark points using linear algebra (PRD §21):

### Vector Construction
Given landmark points $\mathbf{A}$, $\mathbf{B}$, and $\mathbf{C}$ (e.g., Shoulder $\mathbf{A}$, Elbow $\mathbf{B}$, Wrist $\mathbf{C}$):
$$\mathbf{u} = \mathbf{A} - \mathbf{B} = \langle x_A - x_B,\, y_A - y_B,\, z_A - z_B \rangle$$
$$\mathbf{v} = \mathbf{C} - \mathbf{B} = \langle x_C - x_B,\, y_C - y_B,\, z_C - z_B \rangle$$

### The Vector Dot Product & Angle Extraction
The Euclidean dot product relates the two vectors to the cosine of the included angle $\theta$:
$$\mathbf{u} \cdot \mathbf{v} = \|\mathbf{u}\| \|\mathbf{v}\| \cos\theta$$
$$\theta = \arccos\left(\frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|}\right) = \arccos\left(\frac{u_x v_x + u_y v_y + u_z v_z}{\sqrt{u_x^2 + u_y^2 + u_z^2}\sqrt{v_x^2 + v_y^2 + v_z^2}}\right)$$

Converting radians to degrees:
$$\theta_{\text{deg}} = \theta \times \frac{180^\circ}{\pi}$$

---

## 5. Ergonomic Assessment Standards: RULA & REBA

### 5.1 RULA (Rapid Upper Limb Assessment)
- **Origin**: Developed in 1993 by McAtamney and Corlett at the University of Nottingham.
- **Focus**: Evaluates biomechanical loading on the upper body—specifically the neck, trunk, shoulders, upper arms, forearms, and wrists.
- **Scoring Architecture**:
  - *Table A*: Combines upper arm, lower arm, and wrist posture scores + muscle use/load modifiers.
  - *Table B*: Combines neck, trunk, and leg posture scores + muscle use/load modifiers.
  - *Table C*: Cross-references Table A and Table B subtotals into a final **Grand Score (1 to 7)**.
  - A score of **1–2** is acceptable; **3–4** warrants investigation; **5–6** requires change soon; **7** requires immediate modification.

### 5.2 REBA (Rapid Entire Body Assessment)
- **Origin**: Developed in 2000 by Hignett and McAtamney for healthcare and dynamic workplaces.
- **Focus**: Evaluates whole-body postures, including static standing, trunk flexion, leg support, and coupling quality.
- **Scoring Architecture**: Yields a **Grand Score (1 to 15)** grouped into five clinical action levels.

---

## 6. Facial Landmarks & Observable Expression Geometry

EdgeErgo utilizes MediaPipe Face Mesh to track dense facial geometry without extracting identity vectors:
- **Eye Aspect Ratio (EAR)**: Computes vertical eyelid aperture relative to horizontal eye width. When a worker squints or experiences dry eye strain during prolonged screen focus, EAR drops significantly below the nominal resting baseline ($0.30 \to < 0.20$).
- **Mouth Aspect Ratio (MAR)**: Tracks vertical lip separation, distinguishing speech aperture dynamics during video calls from resting focus.
- **Scientific Limitation**: Facial geometry indicates **physical strain symptoms** (eye squinting, brow furrowing), not emotions. EdgeErgo reports observable physical movements, strictly refusing to speculate on psychological states.

---

## 7. REST APIs & Asynchronous FastAPI

- **REST (Representational State Transfer)**: A stateless, resource-oriented networking model utilizing standard HTTP methods (`GET` for reading data, `POST` for submitting records).
- **FastAPI**: A high-performance Python web framework built on the **ASGI** (Asynchronous Server Gateway Interface) standard. Using Python's `async` and `await` event loop, a single FastAPI server process handles thousands of concurrent edge node connections without thread-locking bottlenecks.
- **Pydantic Validation**: Automatically parses, validates, and sanitizes incoming JSON text against typed Python data classes at the server boundary.

---

## 8. Embedded Database: SQLite & WAL Mode

- **Serverless Embedded Engine**: Unlike client-server databases (MySQL, PostgreSQL) that require a standalone background daemon process, SQLite is compiled directly into the application runtime.
- **Zero Administration**: The database is a single cross-platform file on disk (`edgeergo_local.db`).
- **WAL (Write-Ahead Logging)**: Standard SQLite locks the entire database file during writes. Enabling WAL mode (`PRAGMA journal_mode = WAL`) allows multiple concurrent readers while a background writer commits data, eliminating database lock contention.

---

## 9. Reliable Sync Queues & Exponential Backoff

- **Store-and-Forward Queue**: Telemetry windows are committed to SQLite *before* attempting network transmission. If the network drops, the data is safe on disk.
- **Exponential Backoff**: When network failures occur, retrying immediately and continuously exhausts CPU and floods the network. Exponential backoff progressively doubles the wait time between retry attempts ($5\text{s} \to 10\text{s} \to 20\text{s} \to \dots \to 300\text{s}$), paired with randomized jitter to prevent synchronized reconnect floods.

---

## 10. Standalone Packaging: PyInstaller

- **The Distribution Problem**: Distributing raw Python scripts requires client machines to have a compatible Python interpreter, pip, Visual C++ runtimes, and dozens of third-party libraries installed.
- **The PyInstaller Solution**: PyInstaller analyzes Python import graphs, collects all referenced bytecode files, bundles shared C++ DLLs (OpenCV, Qt6), packages data assets (MediaPipe models), and attaches a lightweight native C bootloader. The result is a single executable (`EdgeErgoAgent.exe`) that executes instantly on clean Windows workstations.

---

## Related Documents
- [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md) — System scope and vision.
- [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md) — Implementation of these concepts in the Edge Agent.
- [09-ergonomics-methodology.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/09-ergonomics-methodology.md) — Complete RULA and REBA tables.
- [viva-qa.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/research/viva-qa.md) — Viva examination oral defense questions.
