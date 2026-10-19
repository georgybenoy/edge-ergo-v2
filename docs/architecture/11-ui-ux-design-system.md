# 11. UI/UX Design System

The EdgeErgo design system defines the visual language, interface tokens, component behaviors, and ergonomic notification guidelines across both the **Central Web Dashboard** (React) and the native **Worker Desktop Overlay** (PySide6). It is synthesized directly from the official 30-page [EdgeErgo UI/UX Design Document](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/source/EdgeErgo_DESIGN.pdf).

---

## 1. Design Philosophy & Direction

The design direction is defined as a **Premium Dark Enterprise Analytics Dashboard** (DESIGN §1, §2):
- **Professional, Not Medical**: The interface communicates industrial engineering rigor, workplace safety, and statistical precision. It avoids the clinical aesthetic of medical software or the playful gamification of consumer fitness trackers.
- **High Information Density**: Inspired by modern cybersecurity and financial trading terminals, screens present dense, scannable data layouts using rounded analytical cards, subtle grid lines, and high-contrast typography.
- **Minimal Cognitive Friction**: Workers at workstations must not be distracted by jarring flashes, alarmist sounds, or aggressive popups. Alerts are polite, educational, and non-shaming.

---

## 2. Design Tokens & Color Palette

The interface adheres to a carefully calibrated dark color system optimized for low eye fatigue during extended display viewing (DESIGN §3):

```
+-----------------------------------------------------------------------------+
|                            CORE COLOR PALETTE                               |
|                                                                             |
|  SURFACES & BACKGROUNDS                                                     |
|  - App Canvas (Deep Base):         #0B0F19  (rgb(11, 15, 25))               |
|  - Card & Container Surface:       #111827  (rgb(17, 24, 39))               |
|  - Elevated Dropdown / Tooltip:    #1F2937  (rgb(31, 41, 55))               |
|  - Border & Subtle Dividers:       #374151  (rgb(55, 65, 81))               |
|                                                                             |
|  TYPOGRAPHY HIERARCHY                                                       |
|  - Primary Text (Headings / KPIs): #F9FAFB  (rgb(249, 250, 251) - 100%)    |
|  - Secondary Text (Labels / Body): #9CA3AF  (rgb(156, 163, 175) - 70%)     |
|  - Muted Text (Metadata / Timestamps): #6B7280 (rgb(107, 114, 128) - 50%)   |
|                                                                             |
|  SEMANTIC STATUS & ERGONOMIC RISK TOKENS                                    |
|  - Low Risk (Healthy / Nominal):   #10B981  (Emerald Green)                 |
|  - Medium Risk (Attention):        #F59E0B  (Amber Yellow)                  |
|  - High Risk (Warning / Action):   #F97316  (Coral Orange)                  |
|  - Very High Risk (Critical):      #EF4444  (Crimson Red)                   |
|  - Primary Action / Accent:        #3B82F6  (Electric Blue)                 |
+-----------------------------------------------------------------------------+
```

---

## 3. Typography Scale & Layout Grid

### Typography System (DESIGN §4)
- **Primary Typeface**: `Inter`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, sans-serif.
- **Numerical Figures**: Tabular numbers (`font-variant-numeric: tabular-nums`) for all dashboard KPIs, timestamps, and percentages to maintain perfect visual alignment across data rows.
- **Scale**:
  - `Hero KPI Metric`: **32px / Bold (700)** — Used for macro compliance percentages and node counts.
  - `Card Header / Section Title`: **18px / Semi-Bold (600)** — Used for chart card headers.
  - `Standard Body Text`: **14px / Regular (400)** — Used for descriptions and table cell data.
  - `Subtext / Table Headers`: **12px / Medium (500) / Uppercase** — Letter-spaced metadata.
  - `Micro Badge / Status Label`: **11px / Semi-Bold (600)** — Badges and tag indicators.

### Spacing & Elevation (DESIGN §5)
- Standard 8-point base grid: `4px` (xs), `8px` (sm), `12px` (md), `16px` (lg), `24px` (xl), `32px` (2xl).
- **Border Radiuses**:
  - Analytical Cards: `12px`
  - Form Controls & Buttons: `8px`
  - Status Badges & Pills: `9999px` (Full pill radius)
- **Elevation**: Subtle borders (`1px solid #374151`) paired with soft ambient dropshadows (`0 4px 6px -1px rgba(0, 0, 0, 0.4)`), avoiding garish colored glows.

---

## 4. UI Component Library Standards

The dashboard comprises five foundational reusable components (DESIGN §6):

### 4.1 KPI Summary Cards
Compact analytic containers displaying a key organizational metric, a trend percentage indicator, and a miniature sparkline:
- Large 32px metric display.
- Contextual comparison badge (e.g., `+4.2% vs yesterday` in green/red).
- Dark surface background (`#111827`) with thin hairline border.

### 4.2 Status & Risk Badges
Dual-coded visual indicators combining background tint, foreground text, and an explicit icon to guarantee WCAG accessibility:
- `Low Risk`: Green background tint (`rgba(16, 185, 129, 0.15)`), green text, checkmark icon.
- `High Risk`: Orange background tint (`rgba(249, 115, 22, 0.15)`), orange text, triangle warning icon.

### 4.3 Workstation Data Table
Sortable, filterable enterprise data table listing all monitored nodes:
- Columns: Node ID (`NODE-001`), Department, Status (`ONLINE`/`OFFLINE`), Current RULA Score, Predominant Risk, Daily Monitored Time, Last Seen.
- Row-level action buttons: "View Workstation History" and "Download Audit Log".

### 4.4 Ergonomic Distribution Bar
Segmented horizontal progress bar illustrating the percentage of time spent in each risk tier across the selected time period:
```
[ 45% Low Risk (Green) ][ 35% Med (Yellow) ][ 16% High (Orange) ][ 4% V.High (Red) ]
```

---

## 5. Central Dashboard Pages & Layout

The React web application provides six dedicated administrative views (PRD §59; DESIGN §7):

```
+-----------------------------------------------------------------------------+
|                            CENTRAL DASHBOARD SITEMAP                        |
|                                                                             |
|  [Sidebar Navigation]                                                       |
|  ├── 1. Executive Overview     -> Organization macro health, active nodes,  |
|  |                                collective risk breakdown, compliance.   |
|  ├── 2. Workstations Directory -> Tabular list of all nodes, live states,   |
|  |                                filter by department, drill-down.        |
|  ├── 3. Ergonomics Analytics   -> In-depth RULA/REBA distribution, joint    |
|  |                                angle trends, hourly posture heatmaps.    |
|  ├── 4. Expression Trends      -> Macro facial observation percentages,     |
|  |                                eye strain indicators vs time of day.     |
|  ├── 5. Combined Observations  -> Observational correlation matrices        |
|  |                                between awkward postures & strain flags.  |
|  └── 6. Reports & CSV Export   -> Automated PDF generator, date range       |
|                                  selectors, raw CSV export downloads.       |
+-----------------------------------------------------------------------------+
```

---

## 6. Worker Desktop Overlay (PySide6) Specifications

The worker interface is fundamentally distinct from the administrative web dashboard. It runs as a native, hardware-accelerated translucent Qt overlay designed to provide real-time coaching with zero disruption (PRD §30; DESIGN §8):

```
+-----------------------------------------------------------------------------+
|                       WORKER DESKTOP OVERLAY MODES                          |
|                                                                             |
|  MODE A: COMPACT PILL (Always-on-top, Screen Corner)                        |
|  +------------------------------------------------------+                   |
|  | (o) EdgeErgo  |  RULA: 2.1 (Good)  |  Break in: 34m  |                   |
|  +------------------------------------------------------+                   |
|                                                                             |
|  MODE B: EXPANDED COACHING CARD (On Click or Hover)                         |
|  +------------------------------------------------------+                   |
|  |  EdgeErgo Workstation Status                         |                   |
|  |  --------------------------------------------------  |                   |
|  |  Current Posture:    Neutral / Healthy (Score: 2)     |                   |
|  |  Session Duration:   1h 42m                          |                   |
|  |  Continuous Sitting: 26m (Next break recommended in 24m)|                 |
|  |  [ Pause Monitoring (30m) ]   [ Minimize to Tray ]   |                   |
|  +------------------------------------------------------+                   |
|                                                                             |
|  MODE C: TRANSIENT POSTURE TOAST (Appears on Sustained Violation > 20s)     |
|  +------------------------------------------------------+                   |
|  |  (!) Posture Alert                                   |                   |
|  |  Forward neck flexion detected (> 25 deg).           |                   |
|  |  Tip: Elevate your display or pull chin slightly back|                   |
|  +------------------------------------------------------+                   |
+-----------------------------------------------------------------------------+
```

### Overlay Design Rules:
1. **Never Interfere with Clicks**: When in compact mode, the overlay can be configured as click-through, ensuring it never intercepts clicks intended for spreadsheets or code editors.
2. **Auto-Dismissing Toasts**: Posture warning toasts slide into view smoothly from the display edge, remain visible for **8 seconds**, and automatically fade away.
3. **Mute / Do Not Disturb**: Workers can pause monitoring directly from the tray icon or overlay whenever they participate in video conferences or require uninterrupted focus.

---

## 7. State Transitions: Empty, Loading, and Disconnected

Every dashboard widget and edge overlay component accounts for asynchronous lifecycle states (DESIGN §11):
- **Loading State**: Content boxes display subtle pulsing skeleton placeholders matching the target layout dimensions, avoiding layout shifts.
- **Empty State**: When no data exists (e.g., brand-new node installation), containers display a subdued illustration, a friendly explanation ("No telemetry windows recorded yet for this shift"), and an action button ("Trigger Calibration").
- **Disconnected / Offline State**: If the Central Server cannot be reached, the dashboard displays a slim amber status banner at the top of the viewport: *"Central Server Reconnecting — Local Edge Agents operating autonomously in offline queue mode."*

---

## Related Documents
- [03-tech-stack.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/03-tech-stack.md) — Frontend and PySide6 architectural selections.
- [04-edge-agent-workflow.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/04-edge-agent-workflow.md) — Overlay alert triggers and cooldowns.
- [09-ergonomics-methodology.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/09-ergonomics-methodology.md) — 4-tier risk color logic.
- [10-facial-analysis-scope.md](file:///c:/Users/georg/EDGE-ERGO%20V3/docs/architecture/10-facial-analysis-scope.md) — Expression indicators displayed on dashboard.
