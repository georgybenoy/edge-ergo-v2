# 09. Ergonomics Methodology

EdgeErgo implements automated biomechanical assessment based on two internationally recognized, peer-reviewed ergonomic evaluation standards: **RULA** (Rapid Upper Limb Assessment; McAtamney & Corlett, 1993) and **REBA** (Rapid Entire Body Assessment; Hignett & McAtamney, 2000). This document specifies how these clinical rubrics are adapted for monocular computer vision.

---

## 1. Ergonomic Framework Adaptation

RULA and REBA were historically designed for manual observational audits conducted by industrial ergonomists equipped with clipboards, protractors, and stopwatches. EdgeErgo digitizes this process by extracting 3D spatial vectors from standard webcam frames, computing joint angles via trigonometry, and looking up validated risk scores in real time (PRD §21, §22):

```
+-----------------------------------------------------------------------------+
|                     ERGONOMIC EXTRACTION PIPELINE                           |
|                                                                             |
|  [MediaPipe 3D Landmarks]                                                   |
|             |                                                               |
|             v                                                               |
|  [3D Direction Vectors]  --> v_neck = p_nose - p_shoulder                   |
|             |                v_trunk = p_hip - p_shoulder                   |
|             v                                                               |
|  [Kinematic Angle Math]  --> theta = arccos( (u . v) / (|u| |v|) )          |
|             |                                                               |
|             v                                                               |
|  +-----------------------------------------------------------------------+  |
|  | PURE TABULAR LOOKUP ENGINES (Decoupled from Computer Vision Code)     |  |
|  |                                                                       |  |
|  |   RULA ENGINE (Upper Limbs & Neck)        REBA ENGINE (Whole Body)    |  |
|  |   - Table A: Arm & Wrist Scores           - Group A: Trunk/Neck/Legs  |  |
|  |   - Table B: Neck, Trunk & Leg Scores     - Group B: Upper/Lower Arms |  |
|  |   - Table C: Grand Score (1 to 7)         - Table C: Grand (1 to 15)  |  |
|  +-----------------------------------------------------------------------+  |
|             |                                                               |
|             v                                                               |
|  [Unified 4-Tier Risk Categorization: Low / Medium / High / Very High]      |
+-----------------------------------------------------------------------------+
```

---

## 2. Vision-Derived Anatomical Angles & Modifiers

The Geometry Engine computes five primary anatomical joint groups using spatial landmark positions (PRD §21, §23, §24):

### 2.1 Neck Flexion / Extension ($\theta_{\text{neck}}$)
- **Landmarks**: Nose (0), Mid-Shoulder Reference $\left(\frac{\mathbf{p}_{11} + \mathbf{p}_{12}}{2}\right)$, and Mid-Hip Reference $\left(\frac{\mathbf{p}_{23} + \mathbf{p}_{24}}{2}\right)$.
- **Measurement**: Angle between the cervical spine vector and the vertical trunk axis.
- **RULA Scoring**:
  - $0^\circ \le \theta \le 20^\circ$ Flexion: **Score 1**
  - $\theta > 20^\circ$ Flexion: **Score 2**
  - In Extension ($\theta < 0^\circ$ backward tilt): **Score 4**
  - Lateral Bending / Asymmetric Twist Modifier: **+1** (detected when nose $x$-coordinate deviates from midpoint between shoulders).

### 2.2 Trunk Inclination ($\theta_{\text{trunk}}$)
- **Landmarks**: Mid-Shoulder Reference and Mid-Hip Reference relative to the gravity-aligned vertical axis.
- **RULA Scoring**:
  - Sitting upright, supported at $90^\circ$ to $105^\circ$: **Score 1**
  - $0^\circ \le \theta \le 20^\circ$ Forward Flexion: **Score 2**
  - $20^\circ < \theta \le 60^\circ$ Forward Flexion (Slouching): **Score 3**
  - $\theta > 60^\circ$ Extreme Bending: **Score 4**
  - Trunk Twist / Lateral Tilt Modifier: **+1** (detected when left-right hip-to-shoulder planes cross).

### 2.3 Upper Arm Elevation ($\theta_{\text{upper\_arm}}$)
- **Landmarks**: Shoulder (11 or 12) to Elbow (13 or 14) relative to the trunk vector.
- **RULA Scoring**:
  - $-20^\circ \le \theta \le 20^\circ$ (Neutral vertical hanging): **Score 1**
  - $20^\circ < \theta \le 45^\circ$ (Moderate forward reach): **Score 2**
  - $45^\circ < \theta \le 90^\circ$ (High reaching, elbows elevated): **Score 3**
  - $\theta > 90^\circ$ (Above shoulder height): **Score 4**
  - Shoulder Raised / Abducted Modifier: **+1** (detected when shoulder $y$-coordinate rises toward ear).

### 2.4 Lower Arm Flexion ($\theta_{\text{lower\_arm}}$)
- **Landmarks**: Shoulder, Elbow, and Wrist (15 or 16).
- **RULA Scoring**:
  - $60^\circ \le \theta \le 100^\circ$ (Ergonomic $90^\circ$ desk typing angle): **Score 1**
  - $\theta < 60^\circ$ (Acute forearm flexion) or $\theta > 100^\circ$ (Extended reach): **Score 2**

### 2.5 Wrist Flexion & Deviation ($\theta_{\text{wrist}}$)
- **Landmarks**: Elbow, Wrist, and Index Knuckle (19 or 20).
- **RULA Scoring**:
  - Neutral straight wrist ($\pm 5^\circ$): **Score 1**
  - $0^\circ < |\theta| \le 15^\circ$ Flexion/Extension: **Score 2**
  - $|\theta| > 15^\circ$ Extreme Wrist Bending: **Score 3**
  - Radial / Ulnar Deviation Modifier: **+1** (wrist turned outward relative to forearm).

---

## 3. Non-Vision Factors & Domain Assumptions

Manual RULA and REBA methodologies include environmental and tactile parameters that a standard desk webcam cannot directly observe. EdgeErgo addresses these factors using validated occupational ergonomics assumptions for computer workstation environments (PRD §23, §24):

| Parameter | Clinical Meaning | Monocular Camera Limit | Project Baseline Assumption & Rationale |
| :--- | :--- | :--- | :--- |
| **Load / Force Score** | Physical weight held or lifted by hands. | Cameras cannot measure mass or muscle strain directly. | **Assumed 0 kg / Score = +0**.<br>Computer workstation workers operate keyboards and mice (<0.5 kg). Heavy manual lifting is not part of standard desk work. |
| **Coupling Score** | Quality of hand grip on tools or handles. | Fine finger grip contact cannot be resolved at webcam distances. | **Assumed "Good" / Score = +0**.<br>Mice and keyboard surfaces provide acceptable ergonomic hand contours. |
| **Leg & Foot Support** | Bilateral vs. unilateral foot weight-bearing. | The lower legs and feet are routinely occluded beneath standard office desks. | **Assumed Bilaterally Supported / Score = 1**.<br>Desk workers are seated in chairs with feet resting on the floor or footrest. |
| **Static Muscle Load** | Posture held continuously without relief. | Single-frame observation cannot evaluate temporal duration. | **Dynamic Assessment via Temporal Engine**.<br>If a posture is maintained continuously for $\ge 15$ seconds, the temporal engine dynamically applies the **+1 Static Posture Modifier**. |

---

## 4. Risk Category Mapping Matrix

To provide clarity to both individual desk workers and enterprise health administrators, EdgeErgo maps raw RULA (1–7) and REBA (1–15) scores into a unified 4-tier risk classification (PRD §25):

| Unified Risk Tier | RULA Score Range | REBA Score Range | Ergonomic Assessment Meaning | UI Status Color | System Action |
| :---: | :---: | :---: | :--- | :---: | :--- |
| **LOW RISK** | **1 – 2** | **1 – 3** | Acceptable ergonomic posture. Musculoskeletal strain is minimal. | **Emerald Green** (`#10b981`) | Silent tracking. No worker alert triggered. |
| **MEDIUM RISK** | **3 – 4** | **4 – 7** | Further investigation recommended. Postural deviations present. | **Amber Yellow** (`#f59e0b`) | Monitored. Alert suppressed unless sustained for extended duration. |
| **HIGH RISK** | **5 – 6** | **8 – 10** | Prompt investigation and postural modification required soon. | **Coral Orange** (`#f97316`) | Triggers worker desktop notification if sustained $>20\text{ s}$. |
| **VERY HIGH RISK** | **7** | **11 – 15** | Immediate intervention required. Extreme biomechanical joint angles. | **Crimson Red** (`#ef4444`) | Triggers high-priority visual alert if sustained $>15\text{ s}$. |

---

## 5. Architectural Decoupling: Scoring Logic vs. Computer Vision

A fundamental architectural mandate of EdgeErgo is that **scoring tables and mathematical rules must remain completely separate from computer vision inference modules** (PRD §22, §96):

```
+-----------------------------------------------------------------------------+
|                     STRICT CODEBASE SEPARATION                              |
|                                                                             |
|   VISION MODULES                             ERGONOMICS ENGINE              |
|   (edge_agent/vision/)                       (edge_agent/ergonomics/)       |
|                                                                             |
|   - camera_capture.py                        - rula_tables.py               |
|   - pose_detector.py                         - reba_tables.py               |
|   - face_detector.py                         - evaluator.py                 |
|            |                                        ^                       |
|            | Passes purely numerical dictionary:    |                       |
|            | { "neck_flexion": 24.5,                |                       |
|            |   "trunk_inclination": 12.0, ... }     |                       |
|            +----------------------------------------+                       |
+-----------------------------------------------------------------------------+
```

### Architectural Benefits:
1. **Isolated Unit Testing**: RULA and REBA scoring engines can be tested with 100% test coverage using synthetic fixture tables of joint angles, completely independent of camera hardware or OpenCV builds.
2. **Deterministic Auditability**: Evaluators can verify every row and column of the lookup matrices against published literature without parsing computer vision pipelines.
3. **Pluggable Ergonomic Models**: Future project phases can introduce additional standards (e.g., ROSA for office ergonomics or NIOSH lifting equations) by simply adding a new scoring module.

---

## Related Documents
- [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md) — Pipeline execution of geometry and scoring.
- [06-data-flow-and-privacy.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/06-data-flow-and-privacy.md) — Score transmission boundary.
- [07-data-models.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/07-data-models.md) — Storage of RULA and REBA fields.
- [10-facial-analysis-scope.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/10-facial-analysis-scope.md) — Concurrent facial affect observation.
- [basic-knowledge.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/research/basic-knowledge.md) — Primer on RULA and REBA origins.
