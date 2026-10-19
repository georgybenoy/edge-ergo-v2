# 10. Facial Analysis Scope & Boundaries

EdgeErgo incorporates lightweight facial monitoring solely to track observable physical indicators associated with computer screen fatigue and communicative engagement. This document delineates the strict technical, ethical, and clinical boundaries governing facial analysis, ensuring full compliance with privacy-preserving principles.

---

## 1. Technical Scope: Four Observable Categories

Rather than attempting to decipher complex emotional or psychological spectra, EdgeErgo restricts facial classification to four mutually exclusive, physically observable behavioral states (PRD §27):

```
+-----------------------------------------------------------------------------+
|                     FOUR OBSERVABLE FACIAL CATEGORIES                       |
|                                                                             |
|  [ 1. NEUTRAL ]                                                             |
|  - Baseline relaxed facial geometry                                         |
|  - Standard palpebral aperture (EAR in nominal range 0.25 - 0.35)           |
|  - Absence of pronounced brow furrowing or active jaw movement             |
|                                                                             |
|  [ 2. EXPRESSIVE / ENGAGED ]                                                |
|  - Dynamic micro-movements, smiling, nodding, active visual engagement     |
|  - Minor bilateral zygomatic elevation (cheek raise)                        |
|                                                                             |
|  [ 3. FATIGUED / STRAINED INDICATORS ]                                      |
|  - Sustained squinting (EAR < 0.20 for > 5 consecutive seconds)             |
|  - Prolonged eye closure (micro-sleeps or severe eye dryness)               |
|  - Pronounced corrugator supercilii contraction (inner brow furrowing)      |
|                                                                             |
|  [ 4. MOUTH MOVEMENT / TALKING ]                                            |
|  - Repeated vertical aperture fluctuations (MAR > 0.40)                     |
|  - Indicates active telephone/video conference speaking or yawning          |
+-----------------------------------------------------------------------------+
```

---

## 2. Geometric Feature Extraction & Confidence Filtering

Facial state classification is driven purely by geometric ratios calculated across MediaPipe Face Mesh landmark coordinates in volatile memory (PRD §27, §68):

### 2.1 Eye Aspect Ratio (EAR)
Measures the vertical opening of the eyelids relative to horizontal eye width:
$$\text{EAR} = \frac{\|\mathbf{p}_2 - \mathbf{p}_6\| + \|\mathbf{p}_3 - \mathbf{p}_5\|}{2 \|\mathbf{p}_1 - \mathbf{p}_4\|}$$
- **Nominal Open Eye**: $\text{EAR} \approx 0.28 - 0.35$
- **Squint / Heavy Eye Strain**: $\text{EAR} < 0.20$
- **Eye Closure**: $\text{EAR} < 0.15$

### 2.2 Mouth Aspect Ratio (MAR)
Measures vertical lip separation to identify talking or yawning:
$$\text{MAR} = \frac{\|\mathbf{p}_{\text{lip\_top}} - \mathbf{p}_{\text{lip\_bottom}}\|}{\|\mathbf{p}_{\text{lip\_left}} - \mathbf{p}_{\text{lip\_right}}\|}$$
- **Nominal Closed / Resting Mouth**: $\text{MAR} < 0.25$
- **Active Talking / Movement**: $\text{MAR} \ge 0.40$

### 2.3 Confidence Thresholding & Lighting Filters (PRD §68)
- If overall facial detection confidence drops below **0.60** (due to extreme head turns, deep shadows, backlighting, or hand-over-face occlusion), the frame is tagged `LOW_CONFIDENCE`.
- `LOW_CONFIDENCE` samples are immediately discarded and excluded from temporal expression ratios, preventing noisy optical artifacts from corrupting summary statistics.

---

## 3. Explicit Boundaries: What Is Claimed vs. What Is Not

To prevent misunderstanding or misrepresentation during academic evaluation, the table below establishes explicit claims versus non-claims (PRD §6, §27):

| Aspect | What EdgeErgo Formally Claims | What EdgeErgo Strictly Rejects & DOES NOT Claim |
| :--- | :--- | :--- |
| **Scientific Claim** | **"Observed Physical Classification Statistics"**.<br>The system records objective geometric displacements of eyelids, brows, and lips over time. | ❌ **No Psychological or Emotional Claims**.<br>The system **never** claims a worker is "sad", "angry", "stressed", "anxious", "depressed", or "unhappy". |
| **Fatigue Metrics** | **"Observable Physical Strain Indicators"**.<br>The system detects physical squinting and prolonged eye closure (corroborating potential screen glare or dry eye). | ❌ **No Medical / Neurological Diagnosis**.<br>The system does not diagnose clinical chronic fatigue, burnout syndrome, or sleep apnea. |
| **Identity & Biometrics** | **"Zero Biometric Tracking"**.<br>Facial points are used purely to compute scalar aspect ratios; no face templates or embeddings are generated. | ❌ **No Facial Recognition**.<br>The system cannot identify who is sitting at the computer; it cannot verify identity or distinguish between different people. |
| **Workplace Output** | **"Workstation Health Monitoring"**.<br>Tracks physical ergonomics to promote healthier posture habits. | ❌ **No Productivity or Surveillance Scoring**.<br>Expression metrics are never used to compute employee "engagement scores" or "attentiveness ratings". |

---

## 4. Combined Ergonomic & Facial Analysis: Correlation Without Causation

EdgeErgo generates combined temporal analyses examining the intersection of high ergonomic risk postures and facial strain indicators. However, the system enforces a strict scientific principle regarding these findings (PRD §6, §29):

> [!WARNING]
> **Observed Pattern vs. Clinical Causation Rule:**  
> All reports, dashboard charts, and exported summaries must describe combined ergonomic and expressive findings strictly as **"observed patterns"** or **"statistical co-occurrences"**, and **never as causal relationships**.

### Acceptable Scientific Wording:
- ✅ *"During 5-minute sampling windows characterized by High Risk RULA scores ($\ge 5$), an observed $28\%$ increase in facial strain indicators (prolonged squinting and brow tension) was recorded across monitored workstations."*
- ✅ *"Workstations exhibiting frequent forward head flexion co-occurred with lower expressive engagement ratios."*

### Strictly Prohibited Wording:
- ❌ *"Poor posture caused worker stress."*
- ❌ *"The employee experienced depression and anxiety while working."*
- ❌ *"Forward neck tilt proved that the worker was mentally fatigued."*

---

## 5. Privacy Safeguards Governing Facial Processing

Facial image data is subject to the most stringent privacy restrictions in the EdgeErgo architecture (PRD §28, §63):
1. **Zero Disk Storage**: Neither full camera frames nor cropped facial images are ever written to the workstation's hard drive or SSD.
2. **Immediate Memory Garbage Collection**: As soon as `EAR`, `MAR`, and brow furrow scalars are derived, all landmark coordinate buffers and pixel matrices are explicitly dereferenced in RAM.
3. **Pure Aggregate Wire Transmission**: The Central Server receives only high-level percentage floats (e.g., `neutral_pct: 71.0`, `fatigue_strained_pct: 11.0`). It is mathematically impossible to reconstruct the appearance, facial geometry, or likeness of the worker from these aggregated scalars.

---

## Related Documents
- [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md) — Non-goals and privacy constraints.
- [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md) — Edge pipeline landmark extraction.
- [06-data-flow-and-privacy.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/06-data-flow-and-privacy.md) — Detailed data boundary matrix.
- [09-ergonomics-methodology.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/09-ergonomics-methodology.md) — RULA and REBA kinematic methodology.
- [telemetry-schema.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/api/telemetry-schema.md) — Exact JSON fields for facial percentages.
