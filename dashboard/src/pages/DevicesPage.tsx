import React, { useState, useEffect } from "react";
import { Laptop, CheckCircle2, RefreshCw } from "lucide-react";
import { Card } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { KPICard } from "../components/KPICard";
import { DashboardApi } from "../services/api";
import { DeviceItem } from "../types/dashboard";

export const DevicesPage: React.FC = () => {
  const [devices, setDevices] = useState<DeviceItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadDevices = async () => {
    setLoading(true);
    try {
      const data = await DashboardApi.getDevices();
      setDevices(data);
    } catch (err) {
      console.error("Failed to load devices inventory:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDevices();
  }, []);

  const totalRegistered = devices.length;
  const onlineCount = devices.filter((d) => d.health_status === "ONLINE").length;
  const offlineCount = devices.filter((d) => d.health_status === "OFFLINE").length;
  const warningCount = 0; // Configured thresholds

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-subtle-border">
        <div>
          <h1 className="text-page-title text-content-primary tracking-tight">
            Device Management & Connectivity
          </h1>
          <p className="mt-1 text-body text-content-secondary">
            Distributed edge nodes running local computer vision and periodic synchronization
          </p>
        </div>

        <button
          onClick={loadDevices}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-bg-card hover:bg-bg-hover text-caption text-content-primary border border-subtle-border transition-colors font-medium self-start md:self-auto"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh Fleet</span>
        </button>
      </div>

      {/* Device Count Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Total Registered"
          value={totalRegistered}
          subtext="edge fleet"
        />
        <KPICard
          label="Online & Active"
          value={onlineCount}
          delta={`${totalRegistered > 0 ? Math.round((onlineCount / totalRegistered) * 100) : 0}%`}
          subtext="heartbeat < 120s"
        />
        <KPICard
          label="Warning State"
          value={warningCount}
          subtext="delayed sync"
        />
        <KPICard
          label="Offline Nodes"
          value={offlineCount}
          subtext="reconnecting"
          isNegativeDeltaGood={true}
        />
      </div>

      {/* Devices Inventory Table */}
      <Card noPadding className="overflow-hidden">
        <div className="p-4 border-b border-subtle-border flex items-center justify-between">
          <h3 className="text-card-title text-content-primary font-medium">
            Edge Fleet Inventory
          </h3>
          <span className="text-caption text-content-muted font-mono">
            {devices.length} registered nodes
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse" role="table">
            <thead>
              <tr className="border-b border-subtle-border bg-bg-secondary text-caption text-content-secondary uppercase tracking-wider font-semibold">
                <th className="px-5 py-3">Device Node</th>
                <th className="px-5 py-3">Workstation / Location</th>
                <th className="px-5 py-3">Health Status</th>
                <th className="px-5 py-3">Last Heartbeat</th>
                <th className="px-5 py-3">Agent Version</th>
                <th className="px-5 py-3">Local Camera</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-subtle-border text-body">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-content-muted animate-pulse">
                    Loading device fleet records...
                  </td>
                </tr>
              ) : devices.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-content-muted">
                    No edge devices have registered yet. Once edge agents start, they will appear here.
                  </td>
                </tr>
              ) : (
                devices.map((d) => (
                  <tr key={d.device_id} className="hover:bg-bg-hover/60 transition-colors">
                    <td className="px-5 py-3.5 font-medium text-content-primary font-mono text-caption">
                      <div className="flex items-center gap-2">
                        <Laptop className="w-4 h-4 text-brand-secondary" />
                        <span>{d.device_id}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-content-primary font-medium">
                      {d.device_name}
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={d.health_status} size="sm" />
                    </td>
                    <td className="px-5 py-3.5 text-content-secondary text-caption">
                      {d.last_seen ? new Date(d.last_seen).toLocaleString() : "Never"}
                    </td>
                    <td className="px-5 py-3.5 text-content-secondary font-mono text-caption">
                      v{d.software_version || "0.1.0"}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="inline-flex items-center gap-1 text-caption text-status-safe">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Connected</span>
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};
