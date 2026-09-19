import React from "react";

interface PostureBreakdownBarProps {
  compliancePct: number;
  goodPct?: number;
  moderatePct?: number;
  highRiskPct?: number;
}

export const PostureBreakdownBar: React.FC<PostureBreakdownBarProps> = ({
  compliancePct,
  goodPct,
  moderatePct,
  highRiskPct,
}) => {
  // If breakdown percentages aren't individually provided, derive from compliance
  const good = goodPct ?? Math.min(100, Math.max(0, Math.round(compliancePct * 0.85)));
  const moderate = moderatePct ?? Math.max(0, Math.round((100 - compliancePct) * 0.6));
  const high = highRiskPct ?? Math.max(0, 100 - good - moderate);

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <span className="text-body text-content-secondary font-medium">
          Posture Compliance Score
        </span>
        <span className="text-section text-status-safe font-semibold">
          {compliancePct}%
        </span>
      </div>

      {/* Stacked Progress Bar */}
      <div className="w-full h-3 rounded-pill bg-bg-secondary overflow-hidden flex border border-subtle-border">
        <div
          style={{ width: `${good}%` }}
          className="h-full bg-status-safe transition-all duration-500"
          title={`Safe / Optimal Posture: ${good}%`}
        />
        <div
          style={{ width: `${moderate}%` }}
          className="h-full bg-status-attention transition-all duration-500"
          title={`Moderate / Attention: ${moderate}%`}
        />
        <div
          style={{ width: `${high}%` }}
          className="h-full bg-status-highRisk transition-all duration-500"
          title={`High Risk: ${high}%`}
        />
      </div>

      {/* Legend */}
      <div className="flex items-center justify-between text-caption pt-1">
        <div className="flex items-center gap-1.5 text-content-secondary">
          <span className="w-2 h-2 rounded-full bg-status-safe" />
          <span>Optimal ({good}%)</span>
        </div>
        <div className="flex items-center gap-1.5 text-content-secondary">
          <span className="w-2 h-2 rounded-full bg-status-attention" />
          <span>Attention ({moderate}%)</span>
        </div>
        <div className="flex items-center gap-1.5 text-content-secondary">
          <span className="w-2 h-2 rounded-full bg-status-highRisk" />
          <span>High Risk ({high}%)</span>
        </div>
      </div>
    </div>
  );
};
