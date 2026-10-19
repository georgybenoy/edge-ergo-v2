# EdgeErgo Documentation Index

EdgeErgo is a privacy-preserving, distributed Edge AI system designed to monitor ergonomic posture (via RULA and REBA) and broad facial-expression indicators for computer workstation operators without transmitting or storing raw video.

This documentation suite provides a complete, traceable blueprint of the system's architecture, data models, privacy boundaries, implementation plans, and evaluator references.

---

> [!TIP]
> ### 🌟 Master All-In-One Document
> If you prefer reading the entire project specification in a **single, unified document**, please open:  
> **[docs/EdgeErgo_Complete_Documentation.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/EdgeErgo_Complete_Documentation.md)**  
> *(Contains all 24 core architectural chapters, diagrams, math formulas, data models, API specs, testing KPIs, viva Q&A, and development plans consolidated into one readable master file).*

---

## Documentation Directory

### Architecture & System Design
- [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md): High-level mission, problem statement, vision, primary/secondary goals, non-goals, user personas, and core design principles.
- [02-system-architecture.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/02-system-architecture.md): Two-layer distributed architecture (Edge Layer vs. Central Layer), responsibilities, Mermaid component diagrams, and multi-node topology.
- [03-tech-stack.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/03-tech-stack.md): Layer-by-layer technology choices, justification matrix, lightweight design decisions, and modular database abstraction rationale.
- [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md): Step-by-step edge pipeline from camera capture to local SQLite storage, including scheduling, persistence, cooldowns, and alert priority.
- [05-central-server-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/05-central-server-workflow.md): Central ingestion pipeline, node registration, heartbeat tracking, deduplication, aggregation, and analytics.
- [06-data-flow-and-privacy.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/06-data-flow-and-privacy.md): Privacy boundaries, strict local vs. transmitted data matrix, JSON schema constraints, and zero-leakage audit procedures.
- [07-data-models.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/07-data-models.md): Complete database schemas for Edge SQLite and Central SQLite databases with entity-relationship diagrams.
- [08-offline-and-sync.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/08-offline-and-sync.md): Offline resilience, persistent `sync_queue` lifecycle, exponential backoff, and idempotent deduplication.
- [09-ergonomics-methodology.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/09-ergonomics-methodology.md): RULA and REBA mathematical adaptations for monocular webcam computer vision, joint vectors, and scoring table separation.
- [10-facial-analysis-scope.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/10-facial-analysis-scope.md): Scope of non-biometric facial expression observation, classification categories, confidence filters, and non-medical boundaries.
- [11-ui-ux-design-system.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/11-ui-ux-design-system.md): Enterprise dark-mode design tokens, typography, spacing, component standards, and non-intrusive worker overlay specifications.
- [12-repository-structure.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/12-repository-structure.md): Full repository layout with directory purposes and file-level descriptions.

### API & Contracts
- [api-reference.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/api/api-reference.md): Detailed REST API specification for node registration, heartbeats, telemetry ingestion, CSV exports, and dashboard queries.
- [telemetry-schema.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/api/telemetry-schema.md): Exact JSON contract defining window-level telemetry summaries transmitted from edge nodes to the central server.

### Deployment & Configuration
- [deployment-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/deployment/deployment-overview.md): Packaging and runtime guide covering PyInstaller standalone edge builds, FastAPI server deployment, and initial node discovery.
- [configuration-reference.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/deployment/configuration-reference.md): Exhaustive guide to all agent and server settings, intervals, thresholds, and benchmark-dependent defaults.

### Research, Testing & Viva Defense
- [basic-knowledge.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/research/basic-knowledge.md): Foundational technical explainers covering edge computing, vector kinematics, ergonomic scoring, and distributed queues.
- [glossary.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/research/glossary.md): Alphabetical reference of domain acronyms and architectural terms.
- [limitations-and-risks.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/research/limitations-and-risks.md): Analysis of computer vision constraints (lighting, occlusion, angles, single-person assumption) and mitigation strategies.
- [testing-strategy.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/research/testing-strategy.md): Test verification matrix spanning unit, integration, synthetic benchmark, and privacy audit suites aligned with project KPIs.
- [viva-qa.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/research/viva-qa.md): Curated defense questions and concise, grounded answers for academic evaluators.

### Project Governance & Planning
- [DEVELOPMENT_PLAN.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/DEVELOPMENT_PLAN.md): 20-phase sequential development plan detailing scope, deliverables, and dependencies.
- [OPEN_QUESTIONS.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/OPEN_QUESTIONS.md): Explicit list of unresolved design choices, benchmark dependencies, and future hardware validations.
- [ROADMAP_AND_FUTURE_WORK.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/ROADMAP_AND_FUTURE_WORK.md): Planned post-v3 enhancements including database scaling, cross-platform agents, and automated updates.

---

## Recommended Reading Paths

### Track A: Academic Evaluator / Viva Examiner (30 Minutes)
*Goal: Understand project novelty, technical validity, ergonomics rigor, and privacy guarantees.*
1. [EdgeErgo_Complete_Documentation.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/EdgeErgo_Complete_Documentation.md) — All-in-one consolidated read.
2. [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md) — Mission, problem statement, and non-goals.
3. [02-system-architecture.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/02-system-architecture.md) — Two-layer distributed edge-cloudless design.
4. [06-data-flow-and-privacy.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/06-data-flow-and-privacy.md) — Zero raw video transmission guarantee.
5. [09-ergonomics-methodology.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/09-ergonomics-methodology.md) — RULA/REBA adaptation for vision.
6. [10-facial-analysis-scope.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/10-facial-analysis-scope.md) — Ethical, non-medical facial classification.
7. [viva-qa.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/research/viva-qa.md) — Viva defense responses.

### Track B: Software Engineer / Implementer (Full Technical Deep-Dive)
*Goal: Build, run, debug, and extend the Edge Agent and Central Server.*
1. [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md) — System scope and non-negotiables.
2. [03-tech-stack.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/03-tech-stack.md) — Libraries, dependencies, and constraints.
3. [12-repository-structure.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/12-repository-structure.md) — Code organization.
4. [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md) — Edge processing loop.
5. [05-central-server-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/05-central-server-workflow.md) — Backend ingestion loop.
6. [07-data-models.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/07-data-models.md) & [telemetry-schema.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/api/telemetry-schema.md) — Data schemas and contracts.
7. [08-offline-and-sync.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/08-offline-and-sync.md) — Queue management and sync resilience.
8. [DEVELOPMENT_PLAN.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/DEVELOPMENT_PLAN.md) — Implementation phases.

---

## Non-Negotiable Architectural Rules

Every implementation detail and documentation file in this repository strictly adheres to five core axioms:
1. **Zero Video Egress**: Raw video frames, cropped images, face meshes, and facial embeddings **never** leave worker workstation memory. Only aggregated numerical summaries are persisted or transmitted (PRD §1, §6, §63).
2. **Offline-First Independence**: The Edge Agent executes complete computer vision, scoring, and alerting cycles without requiring a network connection or central server presence (PRD §4, §39).
3. **No Biometric Identification or Psychological Diagnoses**: The system does not identify persons, perform facial recognition, or make psychological or medical assertions (e.g., "depressed", "stressed", "injured"). Facial states represent statistical observation classes only (PRD §6, §27, §28).
4. **Correlation Without Causation**: Joint ergonomic and facial telemetry are presented strictly as "observed patterns", never clinical causation (PRD §6, §29).
5. **Separation of Presentation**: React/Vite is used solely on the Central Server web dashboard. Worker PCs run a native, low-overhead PySide6 desktop overlay (PRD §12, §14, §30).

---

## Related Documents
- [EdgeErgo_Complete_Documentation.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/EdgeErgo_Complete_Documentation.md)
- [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md)
- [02-system-architecture.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/02-system-architecture.md)
- [DEVELOPMENT_PLAN.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/DEVELOPMENT_PLAN.md)
