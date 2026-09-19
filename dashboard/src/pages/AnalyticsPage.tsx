import React, { useState, useEffect } from "react";
import { TrendingUp, BarChart2, Activity } from "lucide-react";
import { Card } from "../components/Card";
import { PostureRiskTimeline } from "../charts/PostureRiskTimeline";
import { RiskDonutChart } from "../charts/RiskDonutChart";
import { DashboardApi } from "../services/api";
import { CorrelationsResponse, DashboardSummaryResponse, TrendPoint } from "../types/dashboard";

export const AnalyticsPage: React.FC = () => {
  const [correlations, setCorrelations] = useState<CorrelationsResponse | null>(null);
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
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
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const patterns = correlations?.observed_patterns || [];
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

      {/* Observed Non-Causal Multi-Factor Correlations (PRD §54) */}
      <Card>
        <div className="flex items-center justify-between pb-3 border-b border-subtle-border mb-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-brand-primary" />
            <div>
              <h3 className="text-section text-content-primary font-medium">
                Observed Multi-Factor Correlations
              </h3>
              <p className="text-caption text-content-secondary mt-0.5">
                Statistically correlated co-occurrences. Strictly non-causal observation.
              </p>
            </div>
          </div>

          <span className="px-2.5 py-1 rounded-pill text-caption bg-brand-accent/10 text-brand-accent border border-brand-accent/20 font-medium">
            PRD §54 Non-Causal Standard
          </span>
        </div>

        <div className="space-y-3">
          {loading ? (
            <div className="py-6 text-center text-content-muted animate-pulse">
              Computing statistical patterns...
            </div>
          ) : patterns.length === 0 ? (
            <div className="py-6 text-center text-content-muted">
              Insufficient telemetry windows to derive statistically significant multi-factor correlations yet.
            </div>
          ) : (
            patterns.map((p) => (
              <div
                key={p.pattern_id}
                className="p-4 rounded-md bg-bg-secondary border border-subtle-border flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] text-content-muted uppercase">
                      {p.pattern_id}
                    </span>
                  </div>
                  <p className="text-body text-content-primary leading-relaxed">
                    {p.observed_pattern}
                  </p>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0 self-end md:self-auto">
                  <span className="text-caption text-content-muted bg-bg-card px-2 py-1 rounded border border-subtle-border font-mono">
                    Quantified Observation
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      {/* RULA / REBA and Break Compliance Analysis */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <div className="flex items-center gap-2 pb-3 border-b border-subtle-border mb-4">
            <BarChart2 className="w-4 h-4 text-brand-secondary" />
            <h3 className="text-card-title text-content-primary font-medium">
              Ergonomic Scoring Methodology
            </h3>
          </div>
          <div className="space-y-3 text-body text-content-secondary leading-relaxed">
            <p>
              • <strong className="text-content-primary">RULA (Rapid Upper Limb Assessment):</strong> Targets neck, trunk, shoulders, upper arm, lower arm, and wrist postures. Scores scale 1–7. Scores &ge; 5 indicate elevated risk requiring investigation.
            </p>
            <p>
              • <strong className="text-content-primary">REBA (Rapid Entire Body Assessment):</strong> Evaluates whole-body postures including lower extremity support. Scores scale 1–12.
            </p>
            <p>
              All lookups and scoring matrices run strictly in-memory on the edge node from localized geometric joint angles.
            </p>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-2 pb-3 border-b border-subtle-border mb-4">
            <Activity className="w-4 h-4 text-status-safe" />
            <h3 className="text-card-title text-content-primary font-medium">
              Movement & Break Compliance
            </h3>
          </div>
          <div className="space-y-4">
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
    </div>
  );
};
