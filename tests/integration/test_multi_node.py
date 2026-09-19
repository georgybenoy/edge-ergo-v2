"""
Multi-Node Integration Test Suite (Phase 12, PRD §103, §46).

Simulates concurrent execution of at least 4 independent Edge Agent nodes
(NODE-001, NODE-002, NODE-003, NODE-004) communicating with a single Central Server.

Verifies:
  1. Concurrent registration: 4 distinct nodes register and receive unique NODE-xxx IDs.
  2. Data isolation: No cross-node contamination in sessions, assessments, or telemetry.
  3. Independent heartbeat health tracking: (e.g. NODE-001..003 ONLINE, NODE-004 OFFLINE).
  4. Fault tolerance: Network failure on one node does not degrade other active nodes.
  5. Backlog catchup: A disconnected node buffers offline and recovers cleanly when reconnected.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from typing import Any, Dict, List
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from central_server.database.database import CentralDatabase
from central_server.main import create_app
from edge_agent.config.config_manager import ConfigManager
from edge_agent.health.heartbeat import HeartbeatClient
from edge_agent.storage.local_db import LocalDatabase
from edge_agent.sync.server_sync import ServerSync


# ── Fixtures & Mock HTTP Bridge ───────────────────────────────────────────────

class SimulatedNetworkBridge:
    """Bridges Edge Agent httpx requests directly to the FastAPI TestClient.

    Supports per-node network failure simulation (simulating dropped packets or offline nodes).
    """

    def __init__(self, test_client: TestClient) -> None:
        self.test_client = test_client
        self.blocked_nodes: set[str] = set()

    def block_node(self, node_id: str) -> None:
        self.blocked_nodes.add(node_id)

    def unblock_node(self, node_id: str) -> None:
        self.blocked_nodes.discard(node_id)

    def is_blocked(self, url: str, json_body: Dict[str, Any]) -> bool:
        # Check if request is associated with a blocked node
        for node in self.blocked_nodes:
            if node in url:
                return True
            if json_body and json_body.get("device_id") in self.blocked_nodes:
                return True
        return False

    def make_client_context(self):
        bridge = self

        class MockHttpClientContext:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def get(self, url, **kwargs):
                path = url.replace("http://central-server:8000", "")
                params = kwargs.get("params", {})
                device_id = params.get("device_id", "")
                if device_id in bridge.blocked_nodes:
                    import httpx
                    raise httpx.RequestError(f"Simulated network drop for {device_id}")
                return bridge.test_client.get(path, **kwargs)

            def post(self, url, **kwargs):
                path = url.replace("http://central-server:8000", "")
                body = kwargs.get("json", {})
                if bridge.is_blocked(url, body):
                    import httpx
                    raise httpx.RequestError(f"Simulated network drop for {body.get('device_id')}")
                return bridge.test_client.post(path, **kwargs)

        return MockHttpClientContext


class SimulatedEdgeNode:
    """Encapsulates a complete simulated Edge Agent workstation node."""

    def __init__(
        self,
        node_index: int,
        work_dir: Path,
        server_url: str = "http://central-server:8000",
    ) -> None:
        self.node_index = node_index
        self.node_dir = work_dir / f"agent_node_{node_index}"
        self.node_dir.mkdir(parents=True, exist_ok=True)

        self.db = LocalDatabase(self.node_dir / "agent.db")
        self.config_mgr = ConfigManager(self.node_dir / "config.json", auto_load=False)
        self.config_mgr.config.server_url = server_url
        self.config_mgr.config.device_name = f"Floor-1-Workstation-{node_index:02d}"

        self.sync = ServerSync(config_manager=self.config_mgr, local_db=self.db)
        self.heartbeat: HeartbeatClient | None = None
        self.assigned_device_id: str = ""

    def register(self) -> str:
        with patch("edge_agent.sync.server_sync.list_available_cameras", return_value=[0]):
            ok, dev_id = self.sync.register_node(device_name=self.config_mgr.config.device_name)
        if ok:
            self.assigned_device_id = dev_id
            self.heartbeat = HeartbeatClient(
                server_url=self.config_mgr.config.server_url,
                device_id=dev_id,
                software_version="0.1.0",
                status_provider=lambda: "active",
            )
        return dev_id

    def send_heartbeat(self) -> bool:
        if self.heartbeat:
            return self.heartbeat.send_heartbeat()
        return False

    def record_and_queue_session(
        self,
        session_id: str,
        rula: int,
        reba: int,
        risk_level: str,
        dominant_posture: str,
        start_time: str,
        end_time: str,
    ) -> str:
        self.db.record_session(session_id, self.assigned_device_id, start_time, end_time, 300.0)
        self.db.record_assessment(
            f"assess_{session_id}",
            session_id,
            end_time,
            rula,
            reba,
            risk_level,
            dominant_posture,
            "Neutral",
        )
        return self.db.enqueue_sync(record_id=session_id)

    def close(self) -> None:
        self.db.close()


# ── Integration Tests ─────────────────────────────────────────────────────────

class TestMultiNodeIntegration:

    def test_concurrent_registration_of_4_nodes(self, tmp_path: Path) -> None:
        """PRD §103: Spin up 4 Edge Nodes and register them concurrently."""
        central_db = CentralDatabase(tmp_path / "central.db")
        app = create_app(database=central_db)
        test_client = TestClient(app)
        bridge = SimulatedNetworkBridge(test_client)

        nodes = [SimulatedEdgeNode(i, tmp_path) for i in range(1, 5)]

        with patch("httpx.Client", side_effect=bridge.make_client_context()):
            # Register concurrently using a thread pool
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(node.register) for node in nodes]
                registered_ids = [f.result() for f in futures]

        # Verify all 4 nodes received unique sequential IDs
        assert len(set(registered_ids)) == 4
        expected_ids = {"NODE-001", "NODE-002", "NODE-003", "NODE-004"}
        assert set(registered_ids) == expected_ids

        # Verify central server registry
        server_devices = central_db.list_devices()
        assert len(server_devices) == 4
        server_ids = {d["device_id"] for d in server_devices}
        assert server_ids == expected_ids

        for n in nodes:
            n.close()
        central_db.close()

    def test_multi_node_data_isolation(self, tmp_path: Path) -> None:
        """PRD §103: Confirm server strictly keeps 4 nodes' telemetry data isolated."""
        central_db = CentralDatabase(tmp_path / "central_iso.db")
        app = create_app(database=central_db)
        test_client = TestClient(app)
        bridge = SimulatedNetworkBridge(test_client)

        nodes = [SimulatedEdgeNode(i, tmp_path) for i in range(1, 5)]

        with patch("httpx.Client", side_effect=bridge.make_client_context()):
            # 1. Register all nodes
            for n in nodes:
                n.register()

            # 2. Each node records distinct posture conditions
            # Node 1: High Neck Flexion
            nodes[0].record_and_queue_session(
                session_id="S-NODE1-001",
                rula=6, reba=6, risk_level="HIGH",
                dominant_posture="NECK_FLEXION",
                start_time="2026-09-19T09:00:00Z", end_time="2026-09-19T09:05:00Z",
            )
            # Node 2: Low Risk Neutral
            nodes[1].record_and_queue_session(
                session_id="S-NODE2-001",
                rula=2, reba=2, risk_level="LOW",
                dominant_posture="NEUTRAL",
                start_time="2026-09-19T09:00:00Z", end_time="2026-09-19T09:05:00Z",
            )
            # Node 3: Trunk Flexion
            nodes[2].record_and_queue_session(
                session_id="S-NODE3-001",
                rula=5, reba=4, risk_level="HIGH",
                dominant_posture="TRUNK_FLEXION",
                start_time="2026-09-19T09:00:00Z", end_time="2026-09-19T09:05:00Z",
            )
            # Node 4: Awkward Wrist
            nodes[3].record_and_queue_session(
                session_id="S-NODE4-001",
                rula=4, reba=3, risk_level="MODERATE",
                dominant_posture="AWKWARD_WRIST",
                start_time="2026-09-19T09:00:00Z", end_time="2026-09-19T09:05:00Z",
            )

            # 3. Concurrently upload telemetry from all nodes
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(n.sync.sync_pending_telemetry) for n in nodes]
                synced_counts = [f.result() for f in futures]

            assert all(c == 1 for c in synced_counts)

            # 4. Verify data isolation on Central Server
            w1 = central_db.list_telemetry_windows(device_id="NODE-001")
            assert len(w1) == 1
            assert w1[0]["session_id"] == "S-NODE1-001"
            assert w1[0]["dominant_posture"] == "NECK_FLEXION"
            assert w1[0]["average_rula"] == 6.0

            w2 = central_db.list_telemetry_windows(device_id="NODE-002")
            assert len(w2) == 1
            assert w2[0]["session_id"] == "S-NODE2-001"
            assert w2[0]["dominant_posture"] == "NEUTRAL"
            assert w2[0]["average_rula"] == 2.0

            w3 = central_db.list_telemetry_windows(device_id="NODE-003")
            assert len(w3) == 1
            assert w3[0]["session_id"] == "S-NODE3-001"
            assert w3[0]["dominant_posture"] == "TRUNK_FLEXION"

            w4 = central_db.list_telemetry_windows(device_id="NODE-004")
            assert len(w4) == 1
            assert w4[0]["session_id"] == "S-NODE4-001"
            assert w4[0]["dominant_posture"] == "AWKWARD_WRIST"

            # Total windows across server
            all_windows = central_db.list_telemetry_windows()
            assert len(all_windows) == 4

        for n in nodes:
            n.close()
        central_db.close()

    def test_independent_heartbeat_online_offline_status(self, tmp_path: Path) -> None:
        """PRD §46: Verify NODE-001..003 are ONLINE while NODE-004 is OFFLINE."""
        central_db = CentralDatabase(tmp_path / "central_hb.db")
        app = create_app(database=central_db)
        test_client = TestClient(app)
        bridge = SimulatedNetworkBridge(test_client)

        nodes = [SimulatedEdgeNode(i, tmp_path) for i in range(1, 5)]

        with patch("httpx.Client", side_effect=bridge.make_client_context()):
            for n in nodes:
                n.register()

            # Send heartbeats for NODE-001, NODE-002, NODE-003 now
            now_time = datetime.now(timezone.utc)
            for n in nodes[:3]:
                n.send_heartbeat()

            # Set NODE-004's last_seen to 10 minutes ago (simulating stopped heartbeat)
            stale_time = (now_time - timedelta(minutes=10)).isoformat()
            central_db.update_heartbeat("NODE-004", "0.1.0", "idle", stale_time)

            # Evaluate health status with standard 120-second timeout (PRD §46)
            health = {d["device_id"]: d["health_status"] for d in central_db.list_devices_with_health(timeout_sec=120.0, reference_time=now_time)}

            assert health["NODE-001"] == "ONLINE"
            assert health["NODE-002"] == "ONLINE"
            assert health["NODE-003"] == "ONLINE"
            assert health["NODE-004"] == "OFFLINE"

        for n in nodes:
            n.close()
        central_db.close()

    def test_fault_tolerance_single_node_failure_and_recovery(self, tmp_path: Path) -> None:
        """PRD §39, §103: One node failing network does not degrade others, and recovers backlog cleanly."""
        central_db = CentralDatabase(tmp_path / "central_fault.db")
        app = create_app(database=central_db)
        test_client = TestClient(app)
        bridge = SimulatedNetworkBridge(test_client)

        nodes = [SimulatedEdgeNode(i, tmp_path) for i in range(1, 5)]

        with patch("httpx.Client", side_effect=bridge.make_client_context()):
            for n in nodes:
                n.register()

            # 1. Simulate network disconnect ONLY for NODE-004
            bridge.block_node("NODE-004")

            # 2. All 4 nodes attempt to send heartbeats and telemetry
            for i, n in enumerate(nodes):
                n.record_and_queue_session(
                    session_id=f"S-FAULT-{n.assigned_device_id}",
                    rula=4, reba=4, risk_level="MODERATE",
                    dominant_posture="NEUTRAL",
                    start_time="2026-09-19T10:00:00Z", end_time="2026-09-19T10:05:00Z",
                )

            # Nodes 1, 2, 3 must succeed without degradation
            for n in nodes[:3]:
                hb_ok = n.send_heartbeat()
                assert hb_ok is True
                synced = n.sync.sync_pending_telemetry()
                assert synced == 1

            # Node 4 must fail network call gracefully without throwing
            hb_node4 = nodes[3].send_heartbeat()
            assert hb_node4 is False
            synced_node4 = nodes[3].sync.sync_pending_telemetry()
            assert synced_node4 == 0

            # Verify Node 4 has buffered the unsynced record locally
            summary_4 = nodes[3].db.get_sync_status_summary()
            assert summary_4["PENDING"] == 1

            # 3. Restore network for NODE-004 and trigger catchup sync
            bridge.unblock_node("NODE-004")
            # Clear backoff last_attempt for immediate retry in test
            pending = nodes[3].db.get_pending_sync_records()
            nodes[3].db.update_sync_status(pending[0]["sync_id"], "PENDING", retry_increment=False, last_attempt="2020-01-01T00:00:00Z")

            # Catchup
            recovered_synced = nodes[3].sync.sync_pending_telemetry()
            assert recovered_synced == 1

            # Verify all 4 nodes now have their telemetry stored centrally
            central_all = central_db.list_telemetry_windows()
            assert len(central_all) == 4

        for n in nodes:
            n.close()
        central_db.close()
