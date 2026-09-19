import React, { useState, useEffect } from "react";
import { Filter, CheckCircle2 } from "lucide-react";
import { AlertCard } from "../components/AlertCard";
import { DashboardApi } from "../services/api";
import { AlertItem, SeverityLevel } from "../types/dashboard";

interface AlertsPageProps {
  onViewWorker: (deviceId: string) => void;
}

export const AlertsPage: React.FC<AlertsPageProps> = ({ onViewWorker }) => {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [activeSeverity, setActiveSeverity] = useState<SeverityLevel>("All");
  const [loading, setLoading] = useState<boolean>(true);

  const loadAlerts = async (severity: SeverityLevel) => {
    setLoading(true);
    try {
      const data = await DashboardApi.getAlerts(severity === "All" ? undefined : severity);
      setAlerts(data);
    } catch (err) {
      console.error("Failed to load alerts:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAlerts(activeSeverity);
  }, [activeSeverity]);

  const severities: SeverityLevel[] = ["All", "Attention", "High Risk", "Critical", "Resolved"];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-subtle-border">
        <div>
          <h1 className="text-page-title text-content-primary tracking-tight">
            Ergonomic & System Alerts
          </h1>
          <p className="mt-1 text-body text-content-secondary">
            Sustained posture threshold violations and edge agent health incidents
          </p>
        </div>

        {/* Severity Filter Tabs */}
        <div className="flex items-center gap-1.5 bg-bg-card p-1 rounded-md border border-subtle-border">
          <Filter className="w-3.5 h-3.5 text-content-muted ml-1" />
          {severities.map((sev) => (
            <button
              key={sev}
              onClick={() => setActiveSeverity(sev)}
              className={`px-3 py-1 rounded text-caption font-medium transition-colors ${
                activeSeverity === sev
                  ? "bg-bg-hover text-content-primary shadow-sm"
                  : "text-content-muted hover:text-content-secondary"
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Alerts List */}
      <div className="space-y-3">
        {loading ? (
          <div className="py-12 text-center text-content-muted animate-pulse">
            Loading active and historical alerts...
          </div>
        ) : alerts.length === 0 ? (
          <div className="p-8 rounded-card bg-bg-card border border-subtle-border text-center space-y-2">
            <CheckCircle2 className="w-8 h-8 text-status-safe mx-auto" />
            <h3 className="text-card-title font-medium text-content-primary">
              No Active Alerts in this Category
            </h3>
            <p className="text-body text-content-secondary max-w-md mx-auto">
              All monitored workstations are currently operating within safe posture persistence thresholds.
            </p>
          </div>
        ) : (
          alerts.map((alert) => (
            <AlertCard
              key={alert.alert_id}
              alert={alert}
              onViewWorker={onViewWorker}
            />
          ))
        )}
      </div>
    </div>
  );
};
