import React from "react";
import { RiskDistribution } from "../types/dashboard";

interface RiskDonutChartProps {
  distribution?: RiskDistribution;
}

export const RiskDonutChart: React.FC<RiskDonutChartProps> = ({ distribution }) => {
  const low = distribution?.LOW || 0;
  const mod = distribution?.MODERATE || 0;
  const high = distribution?.HIGH || 0;
  const crit = distribution?.VERY_HIGH || 0;
  const total = low + mod + high + crit || 1;

  const lowPct = Math.round((low / total) * 100);
  const modPct = Math.round((mod / total) * 100);
  const highPct = Math.round((high / total) * 100);
  const critPct = Math.round((crit / total) * 100);

  // SVG Donut calculations
  const size = 160;
  const strokeWidth = 22;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  // Segment strokeDasharray and offset calculations
  const segments = [
    { label: "Low Risk", count: low, pct: lowPct, color: "#39D98A", value: low },
    { label: "Moderate", count: mod, pct: modPct, color: "#F2C94C", value: mod },
    { label: "High Risk", count: high, pct: highPct, color: "#FF6B7A", value: high },
    { label: "Critical", count: crit, pct: critPct, color: "#FF4D4D", value: crit },
  ];

  let accumulatedPercent = 0;

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
      {/* Donut SVG */}
      <div className="relative w-[160px] h-[160px] flex-shrink-0 flex items-center justify-center">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="transform -rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="#222222"
            strokeWidth={strokeWidth}
            fill="transparent"
          />
          {segments.map((seg, idx) => {
            const segFraction = total > 0 ? seg.value / total : 0;
            const strokeDasharray = `${segFraction * circumference} ${circumference}`;
            const strokeDashoffset = -accumulatedPercent * circumference;
            accumulatedPercent += segFraction;

            if (seg.value === 0) return null;

            return (
              <circle
                key={idx}
                cx={size / 2}
                cy={size / 2}
                r={radius}
                stroke={seg.color}
                strokeWidth={strokeWidth}
                strokeDasharray={strokeDasharray}
                strokeDashoffset={strokeDashoffset}
                fill="transparent"
                strokeLinecap="round"
                className="transition-all duration-500 ease-out"
              />
            );
          })}
        </svg>

        {/* Center Total Count */}
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className="text-display text-content-primary font-medium tracking-tight">
            {total}
          </span>
          <span className="text-caption uppercase tracking-wider text-content-muted">
            Windows
          </span>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-col gap-2.5 w-full">
        {segments.map((s, idx) => (
          <div key={idx} className="flex items-center justify-between text-body">
            <div className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                style={{ backgroundColor: s.color }}
              />
              <span className="text-content-secondary">{s.label}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-content-primary font-medium">{s.count}</span>
              <span className="text-caption text-content-muted w-9 text-right font-mono">
                {s.pct}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
