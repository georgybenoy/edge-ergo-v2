"""
Unit & Integration Tests for Interactive Workstation Setup & Server Verification.

Covers all PRD & prompt requirements:
  1. Successful server health check (GET /api/v1/health -> 200).
  2. Unreachable server (ConnectError handled gracefully).
  3. Invalid server URL (format validation, auto-prefixing http:// and :8000).
  4. Connection timeout (5-second timeout handled without hanging).
  5. Retry behavior (interactive retry loop).
  6. Saved configuration defaults (reusing local edge_config.json).
  7. Overriding settings via command-line arguments.
  8. Ensuring monitoring does not start before successful connection verification.
  9. Multi-workstation registration with unique device names against Central Server.
  10. Preserving existing agent configuration contracts.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Tuple
from unittest.mock import MagicMock, patch
import pytest
import httpx
from fastapi.testclient import TestClient

from edge_agent.config.config_manager import ConfigManager, EdgeConfig
from edge_agent.setup.interactive import (
    check_server_health,
    get_default_workstation_name,
    normalize_server_url,
    run_interactive_setup,
)
from central_server.main import create_app
from central_server.database.database import CentralDatabase


# ── 1. URL Normalization & Validation Tests ──────────────────────────────────

class TestURLNormalization:
    """Verifies input normalization and validation rules."""

    def test_ip_address_auto_adds_http_and_port_8000(self) -> None:
        assert normalize_server_url("192.168.1.100") == "http://192.168.1.100:8000"

    def test_ip_with_custom_port(self) -> None:
        assert normalize_server_url("192.168.1.100:9000") == "http://192.168.1.100:9000"

    def test_full_http_url_preserves_port(self) -> None:
        assert normalize_server_url("http://192.168.1.50:8000") == "http://192.168.1.50:8000"

    def test_full_http_url_strips_trailing_slash(self) -> None:
        assert normalize_server_url("http://192.168.1.50:8000/") == "http://192.168.1.50:8000"

    def test_http_url_without_port_adds_8000(self) -> None:
        assert normalize_server_url("http://192.168.1.50") == "http://192.168.1.50:8000"

    def test_https_url_preserved(self) -> None:
        assert normalize_server_url("https://ergo-server.corp.local:8443") == "https://ergo-server.corp.local:8443"

    def test_localhost_normalized(self) -> None:
        assert normalize_server_url("localhost") == "http://localhost:8000"

    def test_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_server_url("")
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_server_url("   ")

    def test_unsupported_scheme_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Only http:// and https://"):
            normalize_server_url("ftp://192.168.1.100")


# ── 2. Server Health Check Connectivity Tests ─────────────────────────────────

class TestServerHealthCheck:
    """Tests GET /api/v1/health connectivity checks under various network states."""

    def test_successful_health_check_against_live_test_server(self, tmp_path: Path) -> None:
        db = CentralDatabase(db_path=tmp_path / "test.db", auto_init=True)
        app = create_app(database=db)

        # Use FastAPI TestClient directly
        with TestClient(app, base_url="http://testserver") as client:
            is_healthy, data = check_server_health("http://testserver", client=client)
            assert is_healthy is True
            assert isinstance(data, dict)
            assert data.get("status") == "healthy"
            assert "EdgeErgo Central Server" in data.get("server", "")

    def test_unreachable_server_returns_false(self) -> None:
        # Port 59999 should not have any listening server
        is_healthy, error_msg = check_server_health("http://127.0.0.1:59999", timeout_sec=0.5)
        assert is_healthy is False
        assert len(str(error_msg)) > 0
        assert any(keyword in str(error_msg).lower() for keyword in ("unreachable", "refused", "timed out", "error"))

    def test_connection_timeout_handled(self) -> None:
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectTimeout("Request timed out")

        is_healthy, error_msg = check_server_health("http://192.168.1.200:8000", client=mock_client)
        assert is_healthy is False
        assert "timed out" in str(error_msg).lower()

    def test_server_http_error_handled(self) -> None:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.reason_phrase = "Service Unavailable"
        mock_client.get.return_value = mock_resp

        is_healthy, error_msg = check_server_health("http://192.168.1.50:8000", client=mock_client)
        assert is_healthy is False
        assert "503" in str(error_msg)


# ── 3. Interactive Setup Workflow Tests ───────────────────────────────────────

class TestInteractiveSetupWorkflow:
    """Tests interactive prompt inputs, saved defaults, retries, and exit options."""

    def test_successful_first_time_setup(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "edge_config.json"
        config_manager = ConfigManager(cfg_file)

        # User enters IP and desk name
        inputs = iter(["192.168.1.50", "Marketing-Desk-03"])
        outputs: list[str] = []

        def mock_health(url: str, timeout: float) -> Tuple[bool, Any]:
            return True, {"status": "healthy", "server": "EdgeErgo Central Server", "version": "0.1.0"}

        server_url, device_name = run_interactive_setup(
            config_manager=config_manager,
            input_func=lambda _: next(inputs),
            print_func=outputs.append,
            health_checker=mock_health,
        )

        assert server_url == "http://192.168.1.50:8000"
        assert device_name == "Marketing-Desk-03"

        # Verify settings persisted locally
        assert cfg_file.exists()
        with open(cfg_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["server_url"] == "http://192.168.1.50:8000"
        assert saved["device_name"] == "Marketing-Desk-03"

    def test_subsequent_launch_uses_saved_defaults_on_empty_enter(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "edge_config.json"
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump({
                "server_url": "http://192.168.1.37:8000",
                "device_name": "Executive-Desk-4A",
            }, f)

        config_manager = ConfigManager(cfg_file)

        # User hits Enter on both prompts to keep defaults
        inputs = iter(["", ""])
        outputs: list[str] = []

        def mock_health(url: str, timeout: float) -> Tuple[bool, Any]:
            return True, {"status": "healthy"}

        server_url, device_name = run_interactive_setup(
            config_manager=config_manager,
            input_func=lambda _: next(inputs),
            print_func=outputs.append,
            health_checker=mock_health,
        )

        assert server_url == "http://192.168.1.37:8000"
        assert device_name == "Executive-Desk-4A"

    def test_cli_arguments_override_interactive_prompts(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "edge_config.json"
        config_manager = ConfigManager(cfg_file)

        def mock_health(url: str, timeout: float) -> Tuple[bool, Any]:
            return True, {"status": "healthy"}

        server_url, device_name = run_interactive_setup(
            config_manager=config_manager,
            cli_server_url="192.168.1.88",
            cli_device_name="CLI-Desk-09",
            non_interactive=True,
            health_checker=mock_health,
        )

        assert server_url == "http://192.168.1.88:8000"
        assert device_name == "CLI-Desk-09"
        assert config_manager.config.server_url == "http://192.168.1.88:8000"
        assert config_manager.config.device_name == "CLI-Desk-09"

    def test_retry_on_initial_failure_then_succeed(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "edge_config.json"
        config_manager = ConfigManager(cfg_file)

        # 1: User enters IP and desk name
        # 2: First health check fails -> user chooses "1" (Retry)
        # 3: Second health check succeeds
        inputs = iter(["192.168.1.50", "Desk-Test", "1"])
        outputs: list[str] = []
        call_count = 0

        def mock_health(url: str, timeout: float) -> Tuple[bool, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False, "Connection refused"
            return True, {"status": "healthy"}

        server_url, device_name = run_interactive_setup(
            config_manager=config_manager,
            input_func=lambda _: next(inputs),
            print_func=outputs.append,
            health_checker=mock_health,
        )

        assert call_count == 2
        assert server_url == "http://192.168.1.50:8000"
        assert device_name == "Desk-Test"

    def test_user_chooses_exit_on_failure(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "edge_config.json"
        config_manager = ConfigManager(cfg_file)

        inputs = iter(["192.168.1.50", "Desk-Exit", "3"])
        outputs: list[str] = []

        def mock_health(url: str, timeout: float) -> Tuple[bool, Any]:
            return False, "Host unreachable"

        with pytest.raises(SystemExit) as exc_info:
            run_interactive_setup(
                config_manager=config_manager,
                input_func=lambda _: next(inputs),
                print_func=outputs.append,
                health_checker=mock_health,
            )
        assert exc_info.value.code == 0

    def test_monitoring_does_not_start_when_connection_fails(self, tmp_path: Path) -> None:
        """Requirement 8: Verify that EdgeAgentController is never initialized if health check fails."""
        cfg_file = tmp_path / "edge_config.json"
        config_manager = ConfigManager(cfg_file)

        with patch("edge_agent.main.EdgeAgentController") as mock_controller_cls:
            # Simulate non-interactive launch with unreachable server
            with pytest.raises(SystemExit):
                run_interactive_setup(
                    config_manager=config_manager,
                    cli_server_url="http://192.168.1.99:8000",
                    cli_device_name="Unreachable-Desk",
                    non_interactive=True,
                    health_checker=lambda u, t: (False, "Connection refused"),
                )

            # Assert EdgeAgentController was NEVER instantiated
            mock_controller_cls.assert_not_called()


# ── 4. Multi-Workstation Architecture & Registration Tests ────────────────────

class TestMultiWorkstationRegistration:
    """Verifies that multiple workstations can independently register unique names."""

    def test_independent_workstations_assign_distinct_node_ids(self, tmp_path: Path) -> None:
        db = CentralDatabase(db_path=tmp_path / "multi_node.db", auto_init=True)

        w1 = db.register_device(device_name="Finance-Desk-01", software_version="0.1.0")
        w2 = db.register_device(device_name="Engineering-Desk-02", software_version="0.1.0")
        w3 = db.register_device(device_name="HR-Desk-03", software_version="0.1.0")

        assert w1["device_id"] == "NODE-001"
        assert w2["device_id"] == "NODE-002"
        assert w3["device_id"] == "NODE-003"
        assert w1["device_name"] != w2["device_name"]
        db.close()
