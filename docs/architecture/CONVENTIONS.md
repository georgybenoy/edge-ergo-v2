# EdgeErgo — Development Conventions

This document defines the coding standards, module boundaries, and
privacy rules that ALL contributors (and future-you) must follow.

---

## 1. Naming Conventions

### Python (Edge Agent + Central Server)

| Element | Style | Example |
|---|---|---|
| Modules / files | `snake_case` | `angle_calculator.py` |
| Classes | `PascalCase` | `PoseEngine`, `RulaCalculator` |
| Functions / methods | `snake_case` | `compute_neck_angle()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RULA_SCORE = 7` |
| Private members | `_leading_underscore` | `_raw_landmarks` |
| Type aliases | `PascalCase` | `LandmarkDict` |

### TypeScript / React (Dashboard — Phase 14+)

| Element | Style | Example |
|---|---|---|
| Components | `PascalCase` | `WorkstationCard.tsx` |
| Hooks | `camelCase`, `use` prefix | `useTrends()` |
| Utilities / services | `camelCase` | `apiClient.ts` |
| Types / interfaces | `PascalCase` | `TelemetryWindow` |
| Constants | `UPPER_SNAKE_CASE` | `API_BASE_URL` |

### General

- File and directory names are always `snake_case` (Python) or
  `PascalCase` (React components).
- No abbreviations in public APIs — `calculate_angle`, not `calc_ang`.
- Boolean variables/params start with `is_`, `has_`, `should_`.

---

## 2. Module Boundaries (Enforced)

```
vision/          →  geometry/         →  ergonomics/
(landmarks)         (angles)              (RULA/REBA scores)
```

### Dependency rules

| Module | May import from | Must NOT import from |
|---|---|---|
| `geometry/` | `numpy` only | `vision/`, `ergonomics/`, `expression/`, any I/O |
| `ergonomics/` | `geometry/`, `numpy` | `vision/`, `camera/`, `overlay/` |
| `expression/` | `numpy` | `vision/` (receives landmarks, not frames) |
| `vision/` | `mediapipe`, `opencv`, `numpy` | `ergonomics/`, `expression/` |
| `feedback/` | `ergonomics/`, `expression/`, `config/` | `vision/`, `camera/` |
| `overlay/` | `PySide6`, `feedback/` | `vision/`, `camera/`, `storage/` |
| `sync/` | `storage/`, `config/`, `httpx` | `vision/`, `camera/` |

> **Key invariant:** `geometry/` is a pure math library.  It computes
> angles from 3D coordinates and has ZERO knowledge of ergonomic scoring
> tables, MediaPipe, or any I/O.

### RULA/REBA scoring tables

All RULA and REBA lookup tables, score mappings, and risk-level
classifications **must** live in `ergonomics/rula.py` and
`ergonomics/reba.py` respectively — never in `geometry/` or `vision/`.

---

## 3. Logging Rules

### What to log

- Computed scores (RULA, REBA, expression category)
- System events (session start/stop, sync success/failure, config changes)
- Performance metrics (FPS, processing latency)
- Errors and warnings with stack traces

### What to NEVER log (privacy-critical)

> [!CAUTION]
> Violations of these rules are treated as security bugs.

- ❌ Raw camera frames or any pixel data
- ❌ Face crops, face embeddings, or facial landmark coordinates
- ❌ Facial landmark images or visualisations
- ❌ Any data that could identify a specific individual
- ❌ File paths to temporarily cached images (there should be none)

### Format

```python
import logging
logger = logging.getLogger(__name__)

# Good
logger.info("RULA score computed: %d (risk: %s)", score, risk_level)

# Bad — NEVER do this
logger.debug("Frame data: %s", frame.tobytes())  # ❌ PROHIBITED
```

---

## 4. Error Handling

- All vision/ML errors are caught and logged — they must never crash the
  overlay or the analysis loop.
- Network errors in `sync/` use exponential backoff with jitter.
- Database errors are retried once, then logged as warnings.

---

## 5. Testing Conventions

- Test files mirror the source tree: `tests/edge/test_angle_calculator.py`
  tests `edge_agent/geometry/angle_calculator.py`.
- Use `pytest` fixtures for reusable landmark data.
- Vision tests use pre-recorded landmark dicts, **never** real camera
  frames or face images.

---

## 6. Expression Classification — Non-Goals

The expression classifier outputs one of four broad categories:

| Category | Meaning |
|---|---|
| `NEUTRAL` | Resting / baseline facial state |
| `POSITIVE` | Smiling, engaged |
| `NEGATIVE` | Frowning, discomfort indicators |
| `REDUCED` | Minimal facial movement / fatigue indicators |

> [!IMPORTANT]
> **Never** use clinical or diagnostic terms in code, logs, UI, or
> transmitted data.  Prohibited terms include (but are not limited to):
> *stressed, depressed, anxious, angry, sad, disgusted, fearful,
> pain, suffering, distressed*.

---

## 7. Database Rationale

EdgeErgo uses Python's built-in `sqlite3` module (stdlib) instead of
SQLAlchemy.  Reasons:

1. **Minimal dependencies** — no ORM install on every Edge Agent.
2. **Explicit SQL** — the schema is simple enough that raw SQL is
   clearer and easier to audit.
3. **Postgres migration path** — all SQL is written in
   Postgres-compatible syntax.  Swapping to `asyncpg` later is a
   one-file change in `database/database.py`.

---

## 8. Git Workflow

- Commit messages: `[component] Brief description` — e.g.,
  `[geometry] Add neck flexion angle calculation`
- One logical change per commit.
- Never commit `*.db`, `*.jpg`, `*.png`, `*.mp4`, or `venv/`.
