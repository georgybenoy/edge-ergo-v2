import React, { useState, useEffect } from "react";
import { Activity } from "lucide-react";
import { Card } from "../components/Card";
import { PostureRiskTimeline } from "../charts/PostureRiskTimeline";
import { RiskDonutChart } from "../charts/RiskDonutChart";
import { DashboardApi } from "../services/api";
import { CorrelationsResponse, DashboardSummaryResponse, TrendPoint } from "../types/dashboard";

export const AnalyticsPage: React.FC = () => {
  const [correlations, setCorrelations] = useState<CorrelationsResponse | null>(null);
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [trends, setTrends] = useState<TrendPoint[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [corr, sum, tr] = await Promise.all([
          DashboardApi.getCorrelations(),
          DashboardApi.getSummary(),
          DashboardApi.getTrends("hourly"),
        ]);
        setCorrelations(corr);
        setSummary(sum);
        setTrends(tr);
      } catch (err) {
        console.error("Failed to load analytics:", err);
      }
    };
    fetchData();
  }, []);

  const metrics = summary?.metrics;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-subtle-border">
        <div>
          <h1 className="text-page-title text-content-primary tracking-tight">
            Collective Ergonomic Analytics
          </h1>
          <p className="mt-1 text-body text-content-secondary">
            Cross-station correlation insights, temporal posture degradation, and non-causal expression dynamics
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-caption text-content-muted bg-bg-card px-3 py-1.5 rounded-md border border-subtle-border">
            Total Analyzed Windows: <strong className="text-content-primary">{correlations?.total_analyzed_windows || 0}</strong>
          </span>
        </div>
      </div>

      {/* Main Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <div className="pb-3 border-b border-subtle-border mb-4">
            <h3 className="text-section text-content-primary font-medium">
              Temporal Ergonomic Progression
            </h3>
            <p className="text-caption text-content-secondary mt-0.5">
              Hourly aggregate scores indicating diurnal posture changes
            </p>
          </div>
          <PostureRiskTimeline data={trends} height={260} />
        </Card>

        <Card>
          <div className="pb-3 border-b border-subtle-border mb-4">
            <h3 className="text-card-title text-content-primary font-medium">
              Overall Risk Segmentation
            </h3>
            <p className="text-caption text-content-secondary mt-0.5">
              Categorized posture assessment distribution
            </p>
          </div>
          <RiskDonutChart distribution={metrics?.risk_distribution} />
        </Card>
      </div>

      {/* Movement & Break Compliance */}
      <Card>
        <div className="flex items-center gap-2 pb-3 border-b border-subtle-border mb-4">
          <Activity className="w-4 h-4 text-status-safe" />
          <h3 className="text-card-title text-content-primary font-medium">
            Movement & Break Compliance
          </h3>
        </div>
        <div className="space-y-4 max-w-xl">
          <div className="flex items-center justify-between text-body">
            <span className="text-content-secondary">Total Scheduled Movement Prompts:</span>
            <span className="font-medium text-content-primary font-mono">
              {metrics?.total_breaks_recommended || 0}
            </span>
          </div>
          <div className="flex items-center justify-between text-body">
            <span className="text-content-secondary">Acknowledged by Workers:</span>
            <span className="font-medium text-content-primary font-mono">
              {metrics?.total_breaks_acknowledged || 0}
            </span>
          </div>
          <div className="flex items-center justify-between text-body">
            <span className="text-content-secondary">Fleet Break Adherence Rate:</span>
            <span className="font-medium text-status-safe font-mono">
              {metrics?.break_compliance_rate || 0}%
            </span>
          </div>

          <div className="w-full h-2 rounded-full bg-bg-secondary overflow-hidden">
            <div
              style={{ width: `${metrics?.break_compliance_rate || 0}%` }}
              className="h-full bg-status-safe"
            />
          </div>
        </div>
      </Card>
    </div>
  );
};
