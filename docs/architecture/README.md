# Architecture Documentation

This directory contains the system architecture, component specifications, workflows, data models, and design standards for EdgeErgo.

---

## Documents in this Directory

- [01-project-overview.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/01-project-overview.md): High-level overview, problem statement, vision, goals, non-goals, and core design principles.
- [02-system-architecture.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/02-system-architecture.md): Two-layer distributed architecture, component diagrams, and multi-node topology.
- [03-tech-stack.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/03-tech-stack.md): Technology stack justification across Edge, Central, Dashboard, and Packaging layers.
- [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md): Complete Edge Agent pipeline from camera capture to local SQLite storage.
- [05-central-server-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/05-central-server-workflow.md): Central Server ingestion, validation, deduplication, and aggregation pipelines.
- [06-data-flow-and-privacy.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/06-data-flow-and-privacy.md): Strict privacy boundaries, local vs. transmitted matrix, and zero-leakage audit.
- [07-data-models.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/07-data-models.md): Entity-relationship diagrams and table schemas for Edge and Central SQLite databases.
- [08-offline-and-sync.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/08-offline-and-sync.md): Offline autonomy, sync queue state machine, and exponential backoff retry.
- [09-ergonomics-methodology.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/09-ergonomics-methodology.md): RULA and REBA kinematic adaptation for monocular computer vision.
- [10-facial-analysis-scope.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/10-facial-analysis-scope.md): Non-biometric facial expression observation categories and ethical boundaries.
- [11-ui-ux-design-system.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/11-ui-ux-design-system.md): Enterprise dark design tokens, typography, component standards, and overlay specifications.
- [12-repository-structure.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/12-repository-structure.md): Full repository manifest detailing the purpose of every directory and key file.

---

## Related Documents
- [Master Documentation Index](../README.md)
- [Development Plan](../DEVELOPMENT_PLAN.md)
