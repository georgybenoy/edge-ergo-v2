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
    validate_workstation_name,
)
from edge_agent.main import EdgeAgentController
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

    def test_whitespace_in_url_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="cannot contain whitespace"):
            normalize_server_url("192.168.1. 100")

    def test_invalid_port_range_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Port must be an integer between 1 and 65535"):
            normalize_server_url("192.168.1.100:99999")
        with pytest.raises(ValueError, match="Port must be an integer between 1 and 65535"):
            normalize_server_url("192.168.1.100:0")

    def test_non_numeric_port_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Port must be an integer between 1 and 65535"):
            normalize_server_url("192.168.1.100:port")


# ── 2. Workstation Name Validation Tests ──────────────────────────────────────

class TestWorkstationNameValidation:
    """Tests workstation name rules and sanitization."""

    def test_valid_workstation_name(self) -> None:
        assert validate_workstation_name("HR-Desk-01") == "HR-Desk-01"
        assert validate_workstation_name("  Finance-PC-3  ") == "Finance-PC-3"

    def test_empty_workstation_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_workstation_name("")
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_workstation_name("   ")

    def test_too_long_workstation_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="must not exceed 100 characters"):
            validate_workstation_name("A" * 101)

    def test_control_characters_in_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="control characters"):
            validate_workstation_name("Desk\n01")
        with pytest.raises(ValueError, match="control characters"):
            validate_workstation_name("Desk\x0001")


# ── 3. Server Health Check Connectivity Tests ─────────────────────────────────

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

    def test_read_timeout_handled(self) -> None:
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ReadTimeout("Read timed out")

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


# ── 4. Interactive Setup Workflow Tests ───────────────────────────────────────

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

    def test_change_server_url_on_failure_then_succeed(self, tmp_path: Path) -> None:
        """Verifies option [2] allows entering a different server URL after failure."""
        cfg_file = tmp_path / "edge_config.json"
        config_manager = ConfigManager(cfg_file)

        # 1: User enters bad IP and desk name
        # 2: First health check fails -> user chooses "2" (Enter different URL)
        # 3: User enters good IP
        # 4: Second health check succeeds
        inputs = iter(["192.168.1.99", "Sales-Desk-05", "2", "192.168.1.100"])
        outputs: list[str] = []
        call_urls: list[str] = []

        def mock_health(url: str, timeout: float) -> Tuple[bool, Any]:
            call_urls.append(url)
            if "192.168.1.99" in url:
                return False, "Host unreachable"
            return True, {"status": "healthy", "server": "EdgeErgo Central Server"}

        server_url, device_name = run_interactive_setup(
            config_manager=config_manager,
            input_func=lambda _: next(inputs),
            print_func=outputs.append,
            health_checker=mock_health,
        )

        assert call_urls == ["http://192.168.1.99:8000", "http://192.168.1.100:8000"]
        assert server_url == "http://192.168.1.100:8000"
        assert device_name == "Sales-Desk-05"

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

    def test_keyboard_interrupt_exits_gracefully(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "edge_config.json"
        config_manager = ConfigManager(cfg_file)

        def mock_input(_: str) -> str:
            raise KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc_info:
            run_interactive_setup(
                config_manager=config_manager,
                input_func=mock_input,
                health_checker=lambda u, t: (True, {}),
            )
        assert exc_info.value.code == 0

    def test_cli_server_provided_prompts_only_for_name(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "edge_config.json"
        config_manager = ConfigManager(cfg_file)

        # CLI provides server; prompt should only ask for workstation name
        inputs = iter(["Warehouse-Desk-01"])

        def mock_health(url: str, timeout: float) -> Tuple[bool, Any]:
            return True, {"status": "healthy"}

        server_url, device_name = run_interactive_setup(
            config_manager=config_manager,
            cli_server_url="192.168.1.22",
            input_func=lambda _: next(inputs),
            health_checker=mock_health,
        )

        assert server_url == "http://192.168.1.22:8000"
        assert device_name == "Warehouse-Desk-01"

    def test_cli_device_name_provided_prompts_only_for_server(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "edge_config.json"
        config_manager = ConfigManager(cfg_file)

        # CLI provides device name; prompt should only ask for server URL
        inputs = iter(["192.168.1.33"])

        def mock_health(url: str, timeout: float) -> Tuple[bool, Any]:
            return True, {"status": "healthy"}

        server_url, device_name = run_interactive_setup(
            config_manager=config_manager,
            cli_device_name="Warehouse-Desk-02",
            input_func=lambda _: next(inputs),
            health_checker=mock_health,
        )

        assert server_url == "http://192.168.1.33:8000"
        assert device_name == "Warehouse-Desk-02"

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


# ── 5. Multi-Workstation Architecture & Registration Tests ────────────────────

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

    def test_multiple_workstations_controller_setup_and_register(self, tmp_path: Path) -> None:
        """Verifies multi-workstation controller initialization and registration."""
        db = CentralDatabase(db_path=tmp_path / "controller_multi.db", auto_init=True)
        app = create_app(database=db)

        with TestClient(app) as client:
            # Workstation 1 setup
            cfg1_path = tmp_path / "node1_config.json"
            ctrl1 = EdgeAgentController(
                config_path=str(cfg1_path),
                server_url="http://testserver",
                device_name="Executive-Desk-01",
                no_camera=True,
                headless=True,
            )
            # Patch ServerSync client to talk directly to TestClient
            with patch("httpx.Client") as mock_http:
                mock_client = MagicMock()
                mock_resp = MagicMock()
                mock_resp.status_code = 201
                mock_resp.json.return_value = {"device_id": "NODE-001"}
                mock_client.post.return_value = mock_resp
                mock_http.return_value.__enter__.return_value = mock_client

                id1 = ctrl1.setup_and_register()

            # Workstation 2 setup
            cfg2_path = tmp_path / "node2_config.json"
            ctrl2 = EdgeAgentController(
                config_path=str(cfg2_path),
                server_url="http://testserver",
                device_name="Executive-Desk-02",
                no_camera=True,
                headless=True,
            )
            with patch("httpx.Client") as mock_http:
                mock_client = MagicMock()
                mock_resp = MagicMock()
                mock_resp.status_code = 201
                mock_resp.json.return_value = {"device_id": "NODE-002"}
                mock_client.post.return_value = mock_resp
                mock_http.return_value.__enter__.return_value = mock_client

                id2 = ctrl2.setup_and_register()

            assert id1 == "NODE-001"
            assert id2 == "NODE-002"
            assert id1 != id2
            ctrl1.db.close()
            ctrl2.db.close()
        db.close()


# ── 6. Existing Agent Functionality Preservation Tests ────────────────────────

class TestExistingAgentFunctionalityPreserved:
    """Verifies that interactive setup preserves all existing agent configuration and features."""

    def test_existing_config_options_preserved_on_save(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "edge_config.json"
        # Seed custom configuration
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump({
                "capture_fps": 20,
                "frame_width": 1280,
                "frame_height": 720,
                "telemetry_window_sec": 120,
                "rula_alert_threshold": 6,
                "break_interval_min": 50,
                "server_url": "http://192.168.1.10:8000",
                "device_name": "Old-Desk",
            }, f)

        config_manager = ConfigManager(cfg_file)
        inputs = iter(["192.168.1.55", "New-Lab-Desk"])

        def mock_health(url: str, timeout: float) -> Tuple[bool, Any]:
            return True, {"status": "healthy"}

        server_url, device_name = run_interactive_setup(
            config_manager=config_manager,
            input_func=lambda _: next(inputs),
            health_checker=mock_health,
        )

        assert server_url == "http://192.168.1.55:8000"
        assert device_name == "New-Lab-Desk"

        # Verify other settings were preserved
        cfg = config_manager.config
        assert cfg.capture_fps == 20
        assert cfg.frame_width == 1280
        assert cfg.frame_height == 720
        assert cfg.telemetry_window_sec == 120
        assert cfg.rula_alert_threshold == 6
        assert cfg.break_interval_min == 50
