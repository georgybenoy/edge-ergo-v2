import React from "react";
import { Info, TrendingUp } from "lucide-react";

interface RiskForecastChartProps {
  currentRiskPct: number;
}

export const RiskForecastChart: React.FC<RiskForecastChartProps> = ({
  currentRiskPct,
}) => {
  // Model projections: 1h, 2h, 3h, 4h without breaks vs with scheduled breaks
  const hours = ["+1 hr", "+2 hrs", "+3 hrs", "+4 hrs"];
  const baseline = Math.max(15, currentRiskPct);

  const withoutBreaks = [
    Math.min(95, Math.round(baseline * 1.2)),
    Math.min(98, Math.round(baseline * 1.45)),
    Math.min(100, Math.round(baseline * 1.7)),
    Math.min(100, Math.round(baseline * 1.95)),
  ];

  const withBreaks = [
    Math.max(10, Math.round(baseline * 0.95)),
    Math.max(10, Math.round(baseline * 0.85)),
    Math.max(8, Math.round(baseline * 0.75)),
    Math.max(8, Math.round(baseline * 0.7)),
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-brand-primary" />
          <span className="text-card-title text-content-primary font-medium">
            Ergonomic Risk Forecast
          </span>
        </div>
        <div className="flex items-center gap-1 text-[11px] text-content-muted bg-bg-secondary px-2 py-0.5 rounded-pill border border-subtle-border">
          <Info className="w-3 h-3 text-brand-accent" />
          <span>Statistical Model Estimate</span>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2 text-center pt-2">
        {hours.map((h, i) => (
          <div
            key={i}
            className="p-2.5 rounded-md bg-bg-secondary border border-subtle-border flex flex-col items-center justify-between min-h-[90px]"
          >
            <span className="text-caption text-content-muted font-medium">{h}</span>

            <div className="flex flex-col items-center gap-0.5 my-1">
              <span className="text-card-title text-status-highRisk font-semibold">
                {withoutBreaks[i]}%
              </span>
              <span className="text-[10px] text-content-muted">no breaks</span>
            </div>

            <div className="flex items-center gap-1 text-[11px] text-status-safe">
              <span>{withBreaks[i]}%</span>
              <span className="text-[9px] text-content-muted">opt.</span>
            </div>
          </div>
        ))}
      </div>

      <p className="text-caption text-content-muted text-center italic">
        Forecast reflects cumulative musculoskeletal strain projection based on sustained posture fatigue curves.
      </p>
    </div>
  );
};
