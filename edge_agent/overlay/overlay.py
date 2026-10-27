"""
Worker Feedback Desktop Overlay (PySide6).

A lightweight, non-blocking, frameless floating widget that stays near the screen edge.
Provides:
  1. Persistent status indicator (PRD §31):
     - Monitoring state ('EdgeErgo ● Monitoring' / 'Idle')
     - Posture risk level badge ('LOW RISK', 'MODERATE', 'HIGH RISK')
     - Last analysis time & next scheduled analysis time
     - Server sync status indicator
  2. Transient notification cards (PRD §30, §32, §33, §34):
     - Displays prioritized alert cards with specific actionable recommendations
     - Auto-dismisses after configured duration
     - Includes general wellness disclaimers on non-medical nudges

Non-intrusive design:
  - Frameless, translucent background
  - Always on top, Tool window (does not steal focus or clutter taskbar)
  - Dismissible with a single click
"""

from __future__ import annotations

import logging
from pathlib import Path
import sys
from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.png"
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from edge_agent.feedback.alert_engine import AlertEngine, AlertPriority, NotificationItem

logger = logging.getLogger(__name__)


# ── Color Palette & Stylesheet Tokens ─────────────────────────────────────────

BG_COLOR = "rgba(20, 24, 33, 0.94)"
CARD_BG_COLOR = "rgba(30, 36, 50, 0.96)"
BORDER_COLOR = "rgba(255, 255, 255, 0.12)"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"

COLOR_LOW = "#10B981"       # Emerald green
COLOR_MODERATE = "#F59E0B"  # Amber
COLOR_HIGH = "#EF4444"      # Red
COLOR_BLUE = "#3B82F6"      # Info blue


# ── Overlay Widget ────────────────────────────────────────────────────────────

class WorkerOverlayWidget(QWidget):
    """PySide6 floating overlay for ergonomic status and transient notifications."""

    status_signal = Signal(dict)

    def __init__(
        self,
        alert_engine: Optional[AlertEngine] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.alert_engine = alert_engine

        # Window configuration: frameless, always-on-top, tool window, no focus steal
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Internal state
        self._current_notification: Optional[NotificationItem] = None
        self._is_collapsed = False
        self._drag_pos = QPoint()

        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        self.status_signal.connect(self._apply_status_update)

        self._build_ui()
        self._setup_timers()

    # ── UI Construction ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(6)

        # Container Frame
        self.container = QFrame(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet(f"""
            QFrame#container {{
                background-color: {BG_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 12px;
            }}
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(12, 10, 12, 10)
        container_layout.setSpacing(8)

        # 1. Status Bar (Persistent)
        self.status_bar = QWidget(self.container)
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)

        if LOGO_PATH.exists():
            self.lbl_logo = QLabel(self.status_bar)
            pix = QPixmap(str(LOGO_PATH)).scaled(
                16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_logo.setPixmap(pix)
            status_layout.addWidget(self.lbl_logo)

        # Monitoring status indicator
        self.lbl_monitoring = QLabel("EdgeErgo ● Monitoring", self.status_bar)
        self.lbl_monitoring.setStyleSheet(f"color: {COLOR_LOW}; font-weight: bold; font-size: 11px;")

        # Risk badge
        self.lbl_risk = QLabel("LOW RISK", self.status_bar)
        self.lbl_risk.setStyleSheet(f"""
            background-color: rgba(16, 185, 129, 0.15);
            color: {COLOR_LOW};
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 10px;
        """)

        # Timing label
        self.lbl_timing = QLabel("Last: --", self.status_bar)
        self.lbl_timing.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")

        # Live Scores (RULA / REBA)
        self.lbl_scores = QLabel("RULA: -- | REBA: --", self.status_bar)
        self.lbl_scores.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; font-weight: 500;")

        # Sync indicator
        self.lbl_sync = QLabel("Synced ●", self.status_bar)
        self.lbl_sync.setStyleSheet(f"color: {COLOR_BLUE}; font-size: 10px;")

        # Collapse / dismiss toggle
        self.btn_toggle = QPushButton("−", self.status_bar)
        self.btn_toggle.setFixedSize(18, 18)
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.1);
                color: {TEXT_SECONDARY};
                border: none;
                border-radius: 9px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.2);
                color: #FFFFFF;
            }}
        """)
        self.btn_toggle.clicked.connect(self.toggle_collapse)

        status_layout.addWidget(self.lbl_monitoring)
        status_layout.addWidget(self.lbl_risk)
        status_layout.addWidget(self.lbl_scores)
        status_layout.addStretch()
        status_layout.addWidget(self.lbl_timing)
        status_layout.addWidget(self.lbl_sync)
        status_layout.addWidget(self.btn_toggle)

        container_layout.addWidget(self.status_bar)

        # 2. Notification Card (Transient — initially hidden)
        self.card_frame = QFrame(self.container)
        self.card_frame.setObjectName("card")
        self.card_frame.setStyleSheet(f"""
            QFrame#card {{
                background-color: {CARD_BG_COLOR};
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 8px;
            }}
        """)
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(4)

        card_header = QHBoxLayout()
        card_header.setSpacing(6)

        self.lbl_card_title = QLabel("⚠️ Posture Warning", self.card_frame)
        self.lbl_card_title.setStyleSheet(f"color: {COLOR_HIGH}; font-weight: bold; font-size: 11px;")

        self.btn_close_card = QPushButton("✕", self.card_frame)
        self.btn_close_card.setFixedSize(16, 16)
        self.btn_close_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_card.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_MUTED};
                border: none;
                font-size: 10px;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
            }}
        """)
        self.btn_close_card.clicked.connect(self.dismiss_notification)

        card_header.addWidget(self.lbl_card_title)
        card_header.addStretch()
        card_header.addWidget(self.btn_close_card)

        self.lbl_headline = QLabel("Maintain a more neutral neck position", self.card_frame)
        self.lbl_headline.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 600; font-size: 11px;")
        self.lbl_headline.setWordWrap(True)

        self.lbl_action = QLabel("Raise your monitor so top line is at eye level.", self.card_frame)
        self.lbl_action.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px;")
        self.lbl_action.setWordWrap(True)

        self.lbl_disclaimer = QLabel("", self.card_frame)
        self.lbl_disclaimer.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; font-style: italic;")
        self.lbl_disclaimer.setVisible(False)

        card_layout.addLayout(card_header)
        card_layout.addWidget(self.lbl_headline)
        card_layout.addWidget(self.lbl_action)
        card_layout.addWidget(self.lbl_disclaimer)

        container_layout.addWidget(self.card_frame)
        self.card_frame.setVisible(False)

        self.main_layout.addWidget(self.container)

        # Position at bottom-right corner of screen by default
        self._position_on_screen()

    def _position_on_screen(self) -> None:
        """Position the overlay near the bottom-right corner of the primary screen."""
        screen = QApplication.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            # 360px wide, place 24px from right, 48px from bottom
            x = geom.width() - 380
            y = geom.height() - 150
            self.setGeometry(x, y, 360, 100)

    def _setup_timers(self) -> None:
        """Setup periodic poll timer for alert engine and auto-dismiss."""
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(500)  # check every 500ms
        self.poll_timer.timeout.connect(self._on_poll_tick)
        self.poll_timer.start()

    # ── Status Updates (PRD §31) ──────────────────────────────────────

    def update_status(
        self,
        *,
        is_monitoring: bool = True,
        risk_level: str = "LOW",
        rula: float = 1.0,
        reba: float = 1.0,
        dominant_posture: str = "NEUTRAL",
        last_time_str: str = "--",
        next_time_str: str = "--",
        sync_status: str = "Synced ●",
    ) -> None:
        """Thread-safe status update via Qt Signal."""
        self.status_signal.emit({
            "is_monitoring": is_monitoring,
            "risk_level": risk_level,
            "rula": rula,
            "reba": reba,
            "dominant_posture": dominant_posture,
            "last_time_str": last_time_str,
            "next_time_str": next_time_str,
            "sync_status": sync_status,
        })

    def _apply_status_update(self, data: dict) -> None:
        """Executed on Qt main thread via Signal slot."""
        is_monitoring = data.get("is_monitoring", True)
        risk_level = data.get("risk_level", "LOW")
        rula = float(data.get("rula", 1.0))
        reba = float(data.get("reba", 1.0))
        last_time_str = data.get("last_time_str", "--")
        sync_status = data.get("sync_status", "Synced ●")

        if is_monitoring:
            self.lbl_monitoring.setText("EdgeErgo ● Monitoring")
            self.lbl_monitoring.setStyleSheet(f"color: {COLOR_LOW}; font-weight: bold; font-size: 11px;")
        else:
            self.lbl_monitoring.setText("EdgeErgo ○ Idle")
            self.lbl_monitoring.setStyleSheet(f"color: {TEXT_MUTED}; font-weight: bold; font-size: 11px;")

        # Update risk badge
        risk_clean = str(risk_level).upper()
        if risk_clean in ("VERY_HIGH", "HIGH"):
            color = COLOR_HIGH
            bg = "rgba(239, 68, 68, 0.18)"
        elif risk_clean == "MODERATE":
            color = COLOR_MODERATE
            bg = "rgba(245, 158, 11, 0.18)"
        else:
            color = COLOR_LOW
            bg = "rgba(16, 185, 129, 0.18)"

        self.lbl_risk.setText(risk_clean)
        self.lbl_risk.setStyleSheet(f"""
            background-color: {bg};
            color: {color};
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 10px;
        """)

        # Live terminal parity scores
        self.lbl_scores.setText(f"RULA: {rula:.1f} | REBA: {reba:.1f}")

        # Update timing and sync status
        next_time_str = data.get("next_time_str", "--")
        self.lbl_timing.setText(f"Last: {last_time_str} | Next: {next_time_str}")
        self.lbl_sync.setText(sync_status)
        if "Syncing" in sync_status:
            self.lbl_sync.setStyleSheet(f"color: {COLOR_MODERATE}; font-size: 10px;")
        else:
            self.lbl_sync.setStyleSheet(f"color: {COLOR_BLUE}; font-size: 10px;")

        self.update()

    # ── Notification Presentation (PRD §30, §35) ──────────────────────

    def show_notification(self, item: NotificationItem) -> None:
        """Display a transient notification card."""
        self._current_notification = item

        # Border and title color by priority
        if item.priority == AlertPriority.HIGH_RISK_POSTURE:
            accent = COLOR_HIGH
            border_css = f"border: 1px solid rgba(239, 68, 68, 0.5);"
        elif item.priority == AlertPriority.POSTURE_WARNING:
            accent = COLOR_MODERATE
            border_css = f"border: 1px solid rgba(245, 158, 11, 0.5);"
        else:
            accent = COLOR_BLUE
            border_css = f"border: 1px solid rgba(59, 130, 246, 0.5);"

        self.card_frame.setStyleSheet(f"""
            QFrame#card {{
                background-color: {CARD_BG_COLOR};
                {border_css}
                border-radius: 8px;
            }}
        """)

        self.lbl_card_title.setText(item.title)
        self.lbl_card_title.setStyleSheet(f"color: {accent}; font-weight: bold; font-size: 11px;")

        self.lbl_headline.setText(item.headline)
        self.lbl_action.setText(item.action_tip)

        if item.disclaimer:
            self.lbl_disclaimer.setText(item.disclaimer)
            self.lbl_disclaimer.setVisible(True)
        else:
            self.lbl_disclaimer.setVisible(False)

        self.card_frame.setVisible(True)
        self.adjustSize()

    def hide_notification(self) -> None:
        """Hide the transient notification card."""
        self._current_notification = None
        self.card_frame.setVisible(False)
        self.adjustSize()

    def dismiss_notification(self) -> None:
        """Worker manually dismissed notification."""
        if self.alert_engine is not None:
            self.alert_engine.dismiss_current()
        self.hide_notification()

    def toggle_collapse(self) -> None:
        """Collapse or expand the status bar to a compact pill."""
        self._is_collapsed = not self._is_collapsed
        if self._is_collapsed:
            self.lbl_scores.setVisible(False)
            self.lbl_timing.setVisible(False)
            self.lbl_sync.setVisible(False)
            self.card_frame.setVisible(False)
            self.btn_toggle.setText("+")
        else:
            self.lbl_scores.setVisible(True)
            self.lbl_timing.setVisible(True)
            self.lbl_sync.setVisible(True)
            if self._current_notification is not None:
                self.card_frame.setVisible(True)
            self.btn_toggle.setText("−")
        self.adjustSize()

    # ── Internal Polling Tick ─────────────────────────────────────────

    def _on_poll_tick(self) -> None:
        """Poll the alert engine for auto-dismiss and newly queued alerts."""
        if self.alert_engine is None:
            return

        import time
        now = time.monotonic()
        active = self.alert_engine.poll(now)

        if active is not None and active != self._current_notification:
            self.show_notification(active)
        elif active is None and self.card_frame.isVisible():
            self.hide_notification()

    # ── Drag Window Support ───────────────────────────────────────────

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: Any) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
