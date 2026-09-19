import React, { useState, useEffect } from "react";
import { Search, Filter, Monitor, ArrowUpRight, Activity, Shield } from "lucide-react";
import { Card } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { Modal } from "../components/Modal";
import { PostureSkeleton } from "../components/PostureSkeleton";
import { DashboardApi } from "../services/api";
import { WorkstationDetail, WorkstationSummary } from "../types/dashboard";

interface WorkersPageProps {
  initialSelectedDevice?: string | null;
}

export const WorkersPage: React.FC<WorkersPageProps> = ({ initialSelectedDevice }) => {
  const [workstations, setWorkstations] = useState<WorkstationSummary[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [riskFilter, setRiskFilter] = useState<string>("All");
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedWorkerId, setSelectedWorkerId] = useState<string | null>(initialSelectedDevice || null);
  const [workerDetail, setWorkerDetail] = useState<WorkstationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);

  useEffect(() => {
    loadWorkstations();
  }, []);

  useEffect(() => {
    if (initialSelectedDevice) {
      setSelectedWorkerId(initialSelectedDevice);
    }
  }, [initialSelectedDevice]);

  useEffect(() => {
    if (selectedWorkerId) {
      loadWorkerDetail(selectedWorkerId);
    } else {
      setWorkerDetail(null);
    }
  }, [selectedWorkerId]);

  const loadWorkstations = async () => {
    setLoading(true);
    try {
      const data = await DashboardApi.getWorkstations();
      setWorkstations(data);
    } catch (err) {
      console.error("Failed to load workstations roster:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadWorkerDetail = async (deviceId: string) => {
    setDetailLoading(true);
    try {
      const detail = await DashboardApi.getWorkstationDetail(deviceId);
      setWorkerDetail(detail);
    } catch (err) {
      console.error("Failed to load worker detail:", err);
    } finally {
      setDetailLoading(false);
    }
  };

  const filteredWorkstations = workstations.filter((w) => {
    const matchesSearch =
      w.device_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.device_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.dominant_posture.toLowerCase().includes(searchQuery.toLowerCase());

    if (riskFilter === "All") return matchesSearch;
    if (riskFilter === "High Risk") return matchesSearch && (w.average_rula >= 5 || w.high_risk_percentage >= 30);
    if (riskFilter === "Attention") return matchesSearch && w.average_rula >= 3 && w.average_rula < 5;
    if (riskFilter === "Safe") return matchesSearch && w.average_rula < 3;
    return matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-subtle-border">
        <div>
          <h1 className="text-page-title text-content-primary tracking-tight">
            Workstations & Workers Roster
          </h1>
          <p className="mt-1 text-body text-content-secondary">
            Continuous posture assessment telemetry mapped by monitored edge station
          </p>
        </div>

        {/* Search & Filter Controls */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-4 h-4 text-content-muted absolute left-3 top-1/2 transform -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search worker, device, posture..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-4 py-1.5 rounded-md bg-bg-card border border-subtle-border text-body text-content-primary placeholder-content-muted focus:outline-none focus:border-brand-accent transition-colors w-64"
            />
          </div>

          <div className="flex items-center gap-1.5 bg-bg-card p-1 rounded-md border border-subtle-border">
            <Filter className="w-3.5 h-3.5 text-content-muted ml-1" />
            {["All", "Safe", "Attention", "High Risk"].map((filter) => (
              <button
                key={filter}
                onClick={() => setRiskFilter(filter)}
                className={`px-2.5 py-1 rounded text-caption font-medium transition-colors ${
                  riskFilter === filter
                    ? "bg-bg-hover text-content-primary shadow-sm"
                    : "text-content-muted hover:text-content-secondary"
                }`}
              >
                {filter}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Workers Table */}
      <Card noPadding className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse" role="table">
            <thead>
              <tr className="border-b border-subtle-border bg-bg-secondary text-caption text-content-secondary uppercase tracking-wider font-semibold">
                <th className="px-5 py-3">Worker / Station</th>
                <th className="px-5 py-3">Device Node</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Avg RULA</th>
                <th className="px-5 py-3">Avg REBA</th>
                <th className="px-5 py-3">Risk Level</th>
                <th className="px-5 py-3">Break Compliance</th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-subtle-border text-body">
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-5 py-8 text-center text-content-muted animate-pulse">
                    Loading workstation telemetry...
                  </td>
                </tr>
              ) : filteredWorkstations.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-5 py-8 text-center text-content-muted">
                    No workstations match the current query or filter criteria.
                  </td>
                </tr>
              ) : (
                filteredWorkstations.map((w) => {
                  const isHigh = w.average_rula >= 5 || w.high_risk_percentage >= 30;
                  const isModerate = w.average_rula >= 3 && !isHigh;
                  const riskLabel = isHigh ? "High Risk" : isModerate ? "Attention" : "Safe";

                  return (
                    <tr
                      key={w.device_id}
                      className="hover:bg-bg-hover/60 transition-colors cursor-pointer group"
                      onClick={() => setSelectedWorkerId(w.device_id)}
                    >
                      <td className="px-5 py-3.5 font-medium text-content-primary">
                        <div className="flex items-center gap-2">
                          <Monitor className="w-4 h-4 text-brand-secondary" />
                          <span>{w.device_name}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-content-secondary font-mono text-caption">
                        {w.device_id}
                      </td>
                      <td className="px-5 py-3.5">
                        <StatusBadge status={w.health_status || "Online"} size="sm" />
                      </td>
                      <td className="px-5 py-3.5 font-mono font-medium text-content-primary">
                        {w.average_rula.toFixed(1)}
                      </td>
                      <td className="px-5 py-3.5 font-mono text-content-secondary">
                        {w.average_reba.toFixed(1)}
                      </td>
                      <td className="px-5 py-3.5">
                        <StatusBadge status={riskLabel} size="sm" />
                      </td>
                      <td className="px-5 py-3.5 text-content-secondary">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full bg-bg-secondary overflow-hidden">
                            <div
                              style={{ width: `${w.break_compliance_rate}%` }}
                              className="h-full bg-status-safe"
                            />
                          </div>
                          <span className="text-caption font-mono">{w.break_compliance_rate}%</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedWorkerId(w.device_id);
                          }}
                          className="inline-flex items-center gap-1 text-caption text-brand-accent hover:underline font-medium"
                        >
                          <span>Inspect</span>
                          <ArrowUpRight className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Worker Detail Modal */}
      <Modal
        isOpen={!!selectedWorkerId}
        onClose={() => setSelectedWorkerId(null)}
        title={workerDetail ? `${workerDetail.device_name} (${workerDetail.device_id})` : "Workstation Details"}
        subtitle="Detailed ergonomic kinematics and posture breakdown"
        maxWidth="max-w-4xl"
      >
        {detailLoading || !workerDetail ? (
          <div className="py-12 text-center text-content-muted animate-pulse">
            Loading workstation kinematics and fatigue indicators...
          </div>
        ) : (
          <div className="space-y-6">
            {/* Top Stat Summary Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-md bg-bg-secondary border border-subtle-border">
                <span className="text-caption text-content-muted">Average RULA</span>
                <div className="mt-1 text-card-title font-semibold text-content-primary">
                  {workerDetail.metrics.average_rula.toFixed(1)} / 7.0
                </div>
              </div>
              <div className="p-3 rounded-md bg-bg-secondary border border-subtle-border">
                <span className="text-caption text-content-muted">Average REBA</span>
                <div className="mt-1 text-card-title font-semibold text-content-primary">
                  {workerDetail.metrics.average_reba.toFixed(1)} / 12.0
                </div>
              </div>
              <div className="p-3 rounded-md bg-bg-secondary border border-subtle-border">
                <span className="text-caption text-content-muted">Posture Compliance</span>
                <div className="mt-1 text-card-title font-semibold text-status-safe">
                  {Math.round(100 - workerDetail.metrics.high_risk_percentage)}%
                </div>
              </div>
              <div className="p-3 rounded-md bg-bg-secondary border border-subtle-border">
                <span className="text-caption text-content-muted">Screen Session</span>
                <div className="mt-1 text-card-title font-semibold text-content-primary">
                  {workerDetail.fatigue_indicators.screen_time_hours} hrs
                </div>
              </div>
            </div>

            {/* Middle Section: Live Posture Skeleton (NO CAMERA) & Posture Breakdown */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Posture Skeleton Indicator */}
              <div>
                <h4 className="text-card-title text-content-primary font-medium mb-2">
                  Live Posture Kinematic Model
                </h4>
                <PostureSkeleton segments={workerDetail.body_segments} />
              </div>

              {/* Body Segments Breakdown & Fatigue */}
              <div className="space-y-4">
                <div>
                  <h4 className="text-card-title text-content-primary font-medium mb-3">
                    Body Region Risk Breakdown
                  </h4>
                  <div className="space-y-2.5">
                    {Object.entries(workerDetail.body_segments).map(([segment, risk]) => (
                      <div
                        key={segment}
                        className="flex items-center justify-between p-2.5 rounded-md bg-bg-secondary border border-subtle-border"
                      >
                        <span className="capitalize text-body text-content-secondary">
                          {segment}
                        </span>
                        <StatusBadge status={risk} size="sm" />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Fatigue & Activity Indicators */}
                <div className="p-4 rounded-md bg-bg-secondary border border-subtle-border space-y-3">
                  <div className="flex items-center gap-2 pb-2 border-b border-subtle-border">
                    <Activity className="w-4 h-4 text-brand-accent" />
                    <h5 className="text-caption uppercase tracking-wider font-semibold text-content-primary">
                      Fatigue & Movement Health
                    </h5>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-caption">
                    <div>
                      <span className="text-content-muted">Movement Score</span>
                      <div className="text-body font-medium text-content-primary mt-0.5">
                        {workerDetail.fatigue_indicators.movement_frequency_score} / 100
                      </div>
                    </div>
                    <div>
                      <span className="text-content-muted">Break Adherence</span>
                      <div className="text-body font-medium text-status-safe mt-0.5">
                        {workerDetail.fatigue_indicators.break_adherence_pct}%
                      </div>
                    </div>
                    <div>
                      <span className="text-content-muted">Deterioration Trend</span>
                      <div className="text-body font-medium text-content-primary mt-0.5">
                        {workerDetail.fatigue_indicators.posture_deterioration_trend}
                      </div>
                    </div>
                    <div>
                      <span className="text-content-muted">Dominant Defect</span>
                      <div className="text-body font-medium text-status-attention mt-0.5">
                        {workerDetail.metrics.dominant_posture.replace('_', ' ')}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Privacy notice banner inside modal */}
            <div className="p-3 rounded-md bg-bg-secondary/60 border border-subtle-border flex items-center gap-2.5 text-caption text-content-muted">
              <Shield className="w-4 h-4 text-brand-accent flex-shrink-0" />
              <span>
                Privacy Guarantee: Wireframe is computed purely from numerical joint vectors. Central server does not have access to video streams.
              </span>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};
