# Roadmap & Future Work

This document catalogues prospective enhancements, enterprise extensions, and research directions explicitly designated as optional, secondary, or post-v3 milestones in the project specifications (PRD §6, §13, §47, §48, §70, §120).

---

## 1. Post-v3 Roadmap Overview

While the initial EdgeErgo release fulfills all B.Tech project primary goals within a standalone Windows and SQLite architecture, the decoupled codebase is structured to accommodate the following future advancements:

```mermaid
gantt
    title EdgeErgo Post-v3 Strategic Evolution
    dateFormat  YYYY-Q#
    section Enterprise Scaling
    Central PostgreSQL Migration       :active, 2027-Q1, 3m
    Enterprise SSO & Active Directory  :2027-Q2, 3m
    section Edge Capabilities
    Automated Background Self-Updater  :2027-Q1, 2m
    Cross-Platform Agent (macOS/Linux) :2027-Q2, 4m
    section Ergonomic Research
    ROSA Office Ergonomics Rubric      :2027-Q3, 3m
    Dual-Camera Lateral Tracking       :2027-Q4, 4m
```

---

## 2. Strategic Enhancement Areas

### 2.1 Central PostgreSQL Multi-Tenant Migration (PRD §13, §48)
- **Objective**: Scale the Central Server to support enterprise deployments encompassing hundreds or thousands of distributed Edge Nodes across multiple office facilities.
- **Implementation Path**:
  - Transition from embedded SQLite to an enterprise PostgreSQL 16 cluster.
  - Activate connection pooling via SQLAlchemy `QueuePool` and asyncpg driver.
  - Implement tenant isolation, allowing multinational corporations to segment ergonomic data by geographic office branches.

### 2.2 Automated Background Self-Updater (PRD §47, §71)
- **Objective**: Enable seamless, zero-touch Edge Agent updates without requiring manual re-installation by desktop workers.
- **Implementation Path**:
  - The Edge Agent queries a new Central Server endpoint (`GET /api/v1/agent/version`) during startup.
  - If a newer release is published, the agent downloads an update payload in the background, verifies its SHA-256 cryptographic signature, and triggers a clean replacement using a lightweight detached batch runner.

### 2.3 Cross-Platform Edge Agent Support (macOS & Linux) (PRD §70)
- **Objective**: Extend Edge AI monitoring to software engineers and designers operating on macOS (Apple Silicon M-series) and Ubuntu Linux workstations.
- **Implementation Path**:
  - Standardize video capture across Apple AVFoundation (`cv2.CAP_AVFOUNDATION`) and Linux Video4Linux (`cv2.CAP_V4L2`).
  - Package native macOS application bundles (`.dmg` / `.app`) signed with Apple Developer certificates.
  - Distribute Linux packages via standalone AppImage and Flatpak containers.

### 2.4 ROSA (Rapid Office Strain Assessment) Methodology
- **Objective**: Supplement RULA and REBA with an ergonomic assessment standard explicitly formulated for computer workstation equipment (Sonne, Villalta, & Andrews, 2012).
- **Implementation Path**:
  - Introduce an interactive visual calibration screen where workers confirm chair adjustability, monitor height relative to eye level, and mouse positioning.
  - Combine optical webcam measurements with equipment ratings to produce comprehensive ROSA grand scores.

### 2.5 Dual-Camera Lateral Spine Tracking
- **Objective**: Overcome the physical monocular limitation of sagittal spine distortion and desk occlusion.
- **Implementation Path**:
  - Support an optional secondary USB camera positioned at a $90^\circ$ lateral angle to the worker's chair.
  - Fuses front-view (neck, shoulders, wrists) and side-view (lumbar spine curvature, hip-knee angle) skeletal coordinates to produce clinical-grade 3D postural models.

### 2.6 Enterprise Identity & Single Sign-On (SSO)
- **Objective**: Secure administrative dashboard access using corporate identity providers.
- **Implementation Path**:
  - Integrate OAuth2, OpenID Connect (OIDC), and SAML 2.0 authentication into FastAPI.
  - Enforce Role-Based Access Control (RBAC): *Supervisors* view aggregate team trends; *System Admins* manage node deployments; *Individual Workers* view only their private history.

---

## 3. Persistent Ethical Non-Negotiables for Future Versions

Even as EdgeErgo expands in scale and analytical sophistication, the core privacy invariants established in Version 3 remain **permanent and non-negotiable** (PRD §6, §123):
- **Raw video frames, cropped images, and biometric embeddings will NEVER leave the worker's local computer.**
- **The system will NEVER incorporate facial identification or individual surveillance capabilities.**
- **The system will NEVER make clinical medical or psychological diagnoses.**

---

## Related Documents
- [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md) — Core vision and permanent non-goals.
- [03-tech-stack.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/03-tech-stack.md) — Modular database architecture.
- [DEVELOPMENT_PLAN.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/DEVELOPMENT_PLAN.md) — Current phase roadmap.
- [OPEN_QUESTIONS.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/OPEN_QUESTIONS.md) — Immediate open design items.
