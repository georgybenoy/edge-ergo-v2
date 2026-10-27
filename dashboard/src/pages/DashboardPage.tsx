import React, { useState, useEffect } from "react";
import { PageHeader } from "../components/PageHeader";
import { KPICard } from "../components/KPICard";
import { Card } from "../components/Card";
import { InsightCard } from "../components/InsightCard";
import { PostureRiskTimeline } from "../charts/PostureRiskTimeline";
import { PostureBreakdownBar } from "../charts/PostureBreakdownBar";
import { RiskDonutChart } from "../charts/RiskDonutChart";
import { RiskForecastChart } from "../charts/RiskForecastChart";
import { DashboardApi } from "../services/api";
import { DashboardSummaryResponse, TrendPoint } from "../types/dashboard";
import { RefreshCw, Smile, Frown, Meh, Activity } from "lucide-react";

interface DashboardPageProps {
  onNavigateToWorkers: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigateToWorkers }) => {
  const [filterOption, setFilterOption] = useState<string>("All Workers");
  const [summaryData, setSummaryData] = useState<DashboardSummaryResponse | null>(null);
  const [trendsData, setTrendsData] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async (silent: boolean = false) => {
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const [sum, tr] = await Promise.all([
        DashboardApi.getSummary(),
        DashboardApi.getTrends("hourly"),
      ]);
      setSummaryData(sum);
      setTrendsData(tr);
    } catch (err: any) {
      if (!silent) {
        setError(err.message || "Failed to load dashboard telemetry.");
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    loadData();
    // Live telemetry auto-polling every 4 seconds to mirror edge stream
    const pollTimer = setInterval(() => {
      loadData(true);
    }, 4000);
    return () => clearInterval(pollTimer);
  }, []);

  const kpis = summaryData?.kpis;
  const metrics = summaryData?.metrics;
  const expr = metrics?.expression_distribution;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="Ergonomic Analytics"
        subtitle="Real-time workplace posture intelligence"
        filterOption={filterOption}
        onFilterChange={setFilterOption}
      />

      {error && (
        <div className="p-3 rounded-md bg-status-critical/10 text-caption text-status-critical border border-status-critical/30">
          {error}
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 rounded-card bg-bg-card/60 border border-subtle-border" />
          ))}
        </div>
      )}

      {/* KPI Cards Row */}
      {!loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-4">
          <KPICard
            label="Workers Monitored"
            value={kpis?.workers_monitored ?? 0}
            delta={kpis?.workers_monitored_delta}
            subtext="active nodes"
          />
          <KPICard
            label="At-Risk Workers"
            value={kpis?.at_risk_workers ?? 0}
            delta={kpis?.at_risk_workers_delta}
            subtext="RULA >= 5.0"
            isNegativeDeltaGood={true}
          />
          <KPICard
            label="Posture Compliance"
            value={`${kpis?.posture_compliance_pct ?? 100}%`}
            delta={kpis?.posture_compliance_delta}
            subtext="within safe ergonomic limits"
          />
          <KPICard
            label="Active Alerts"
            value={kpis?.active_alerts ?? 0}
            delta={kpis?.active_alerts_delta}
            subtext="requiring attention"
            isNegativeDeltaGood={true}
          />
        </div>
      )}

      {/* Main Analytics Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Posture Risk Timeline */}
        <Card className="lg:col-span-2 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-subtle-border mb-4">
              <div>
                <h3 className="text-section text-content-primary font-medium">
                  Posture Risk Timeline
                </h3>
                <p className="text-caption text-content-secondary mt-0.5">
                  Continuous chronological ergonomic progression across monitored sessions
                </p>
              </div>
              <button
                onClick={() => loadData(false)}
                className="p-1.5 rounded-md hover:bg-bg-hover text-content-muted hover:text-content-primary transition-colors"
                title="Refresh Telemetry"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>

            <PostureRiskTimeline data={trendsData} height={260} />
          </div>

          <div className="mt-4 pt-3 border-t border-subtle-border flex items-center justify-between text-caption text-content-muted">
            <span>Dominant Workstation Strain: <strong className="text-content-primary font-medium">{metrics?.dominant_posture?.replace('_', ' ') || "None"}</strong></span>
            <span>Break Compliance: <strong className="text-status-safe font-medium">{metrics?.break_compliance_rate ?? 0}%</strong></span>
          </div>
        </Card>

        {/* Right 1 Col: Risk Distribution Donut & Posture Overview */}
        <div className="space-y-6">
          <Card>
            <h3 className="text-card-title text-content-primary font-medium pb-2 border-b border-subtle-border mb-4">
              Risk Analysis Distribution
            </h3>
            <RiskDonutChart distribution={metrics?.risk_distribution} />
          </Card>

          <Card>
            <h3 className="text-card-title text-content-primary font-medium pb-2 border-b border-subtle-border mb-4">
              Posture Overview
            </h3>
            <PostureBreakdownBar
              compliancePct={kpis?.posture_compliance_pct ?? 92}
            />
          </Card>
        </div>
      </div>

      {/* Secondary Row: Risk Forecast & Expression Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk Forecast (clearly labeled as estimate) */}
        <Card>
          <RiskForecastChart currentRiskPct={metrics?.high_risk_percentage ?? 25} />
        </Card>

        {/* Expression Analytics (strictly non-causal pattern observation) */}
        <Card className="flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2 border-b border-subtle-border mb-4">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-brand-secondary" />
                <h3 className="text-card-title text-content-primary font-medium">
                  Observed Expression Patterns
                </h3>
              </div>
              <span className="text-[11px] px-2 py-0.5 rounded-pill bg-bg-secondary text-content-muted border border-subtle-border">
                Non-Causal Statistical Observation
              </span>
            </div>

            <p className="text-caption text-content-secondary mb-4">
              Aggregated facial feature pattern ratios derived locally on edge nodes. Data represents computer vision landmark measurements, never emotional diagnostics.
            </p>

            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 rounded-md bg-bg-secondary border border-subtle-border flex flex-col items-center">
                <Smile className="w-5 h-5 text-status-safe mb-1" />
                <span className="text-card-title font-semibold text-content-primary">
                  {expr?.neutral_percentage ?? 75}%
                </span>
                <span className="text-caption text-content-muted mt-0.5">Neutral Baseline</span>
              </div>

              <div className="p-3 rounded-md bg-bg-secondary border border-subtle-border flex flex-col items-center">
                <Meh className="w-5 h-5 text-status-attention mb-1" />
                <span className="text-card-title font-semibold text-content-primary">
                  {expr?.reduced_expression_percentage ?? 15}%
                </span>
                <span className="text-caption text-content-muted mt-0.5">Fatigue-Related</span>
              </div>

              <div className="p-3 rounded-md bg-bg-secondary border border-subtle-border flex flex-col items-center">
                <Frown className="w-5 h-5 text-brand-primary mb-1" />
                <span className="text-card-title font-semibold text-content-primary">
                  {((expr?.positive_percentage ?? 5) + (expr?.negative_percentage ?? 5))}%
                </span>
                <span className="text-caption text-content-muted mt-0.5">Other Cues</span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-subtle-border text-caption text-content-muted italic">
            Notice: No facial embeddings, images, or identifiable biometric crops are stored or transmitted.
          </div>
        </Card>
      </div>

      {/* Actionable Insight Card */}
      {summaryData?.insight && (
        <InsightCard
          insight={summaryData.insight}
          onAction={onNavigateToWorkers}
        />
      )}
    </div>
  );
};
