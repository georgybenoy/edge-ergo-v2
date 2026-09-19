import React, { useState } from "react";
import { TrendPoint } from "../types/dashboard";

interface PostureRiskTimelineProps {
  data: TrendPoint[];
  height?: number;
}

type MetricMode = "RULA" | "REBA" | "Posture%" | "Fatigue";

export const PostureRiskTimeline: React.FC<PostureRiskTimelineProps> = ({
  data,
  height = 240,
}) => {
  const [activeMetric, setActiveMetric] = useState<MetricMode>("RULA");
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // If no trend data yet, produce default baseline hours
  const displayData = data.length > 0 ? data : [
    { time_bucket: "09:00", window_count: 2, average_rula: 2.5, average_reba: 3.0, dominant_risk_level: "LOW" as const, dominant_posture: "NEUTRAL" },
    { time_bucket: "11:00", window_count: 2, average_rula: 3.2, average_reba: 3.4, dominant_risk_level: "MODERATE" as const, dominant_posture: "FORWARD_HEAD" },
    { time_bucket: "13:00", window_count: 2, average_rula: 4.8, average_reba: 5.1, dominant_risk_level: "MODERATE" as const, dominant_posture: "FORWARD_HEAD" },
    { time_bucket: "15:00", window_count: 2, average_rula: 5.6, average_reba: 6.0, dominant_risk_level: "HIGH" as const, dominant_posture: "TRUNK_FLEXION" },
    { time_bucket: "17:00", window_count: 2, average_rula: 4.0, average_reba: 4.2, dominant_risk_level: "MODERATE" as const, dominant_posture: "NEUTRAL" },
  ];

  const getMetricValue = (item: TrendPoint): number => {
    switch (activeMetric) {
      case "RULA":
        return item.average_rula;
      case "REBA":
        return item.average_reba;
      case "Posture%":
        // Inverse risk -> compliance
        return Math.max(0, 100 - (item.average_rula / 7) * 100);
      case "Fatigue":
        // Fatigue indicator proxy based on RULA and progression
        return Math.min(100, Math.round((item.average_rula / 7) * 85));
    }
  };

  const getMetricMax = (): number => {
    switch (activeMetric) {
      case "RULA":
        return 7;
      case "REBA":
        return 12;
      case "Posture%":
      case "Fatigue":
        return 100;
    }
  };

  const maxVal = getMetricMax();
  const width = 640;
  const paddingX = 40;
  const paddingY = 30;
  const chartW = width - paddingX * 2;
  const chartH = height - paddingY * 2;

  // Calculate coordinates
  const points = displayData.map((d, i) => {
    const x = paddingX + (i / (displayData.length - 1 || 1)) * chartW;
    const val = getMetricValue(d);
    const y = paddingY + chartH - (val / maxVal) * chartH;
    return { x, y, val, data: d };
  });

  const pathD = points.reduce((acc, pt, i, arr) => {
    if (i === 0) return `M ${pt.x} ${pt.y}`;
    // Smooth bezier curve between points
    const prev = arr[i - 1];
    const cp1x = prev.x + (pt.x - prev.x) / 2;
    const cp1y = prev.y;
    const cp2x = prev.x + (pt.x - prev.x) / 2;
    const cp2y = pt.y;
    return `${acc} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${pt.x} ${pt.y}`;
  }, "");

  // Area under path
  const areaD = points.length > 0
    ? `${pathD} L ${points[points.length - 1].x} ${paddingY + chartH} L ${points[0].x} ${paddingY + chartH} Z`
    : "";

  let strokeColor = "#66C7FF"; // Brand Accent
  let fillColor = "url(#accentGradient)";
  if (activeMetric === "RULA") {
    strokeColor = "#FF6B7A";
    fillColor = "url(#riskGradient)";
  } else if (activeMetric === "REBA") {
    strokeColor = "#A878FF";
    fillColor = "url(#brandSecondaryGradient)";
  }

  return (
    <div className="w-full flex flex-col space-y-4">
      {/* Metric Selector Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1 bg-bg-secondary p-1 rounded-md border border-subtle-border">
          {(["RULA", "REBA", "Posture%", "Fatigue"] as MetricMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setActiveMetric(m)}
              className={`px-3 py-1 rounded text-caption font-medium transition-all ${
                activeMetric === m
                  ? "bg-bg-hover text-content-primary shadow-sm"
                  : "text-content-muted hover:text-content-secondary"
              }`}
            >
              {m}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-caption text-content-muted">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: strokeColor }} />
          <span>Active Metric: <strong className="text-content-primary font-medium">{activeMetric}</strong></span>
        </div>
      </div>

      {/* SVG Chart */}
      <div className="relative w-full overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto overflow-visible select-none"
        >
          <defs>
            <linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#FF6B7A" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#FF6B7A" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="accentGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#66C7FF" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#66C7FF" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="brandSecondaryGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#A878FF" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#A878FF" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Minimal Grid Lines */}
          {[0.25, 0.5, 0.75, 1.0].map((frac, idx) => {
            const y = paddingY + chartH - frac * chartH;
            const labelVal = Math.round(frac * maxVal);
            return (
              <g key={idx}>
                <line
                  x1={paddingX}
                  y1={y}
                  x2={width - paddingX}
                  y2={y}
                  stroke="#282828"
                  strokeDasharray="4 4"
                  strokeWidth="1"
                />
                <text
                  x={paddingX - 10}
                  y={y + 4}
                  fill="#707070"
                  fontSize="10"
                  textAnchor="end"
                  fontFamily="Inter, sans-serif"
                >
                  {labelVal}
                </text>
              </g>
            );
          })}

          {/* Area Fill */}
          <path d={areaD} fill={fillColor} />

          {/* Trend Line */}
          <path
            d={pathD}
            fill="none"
            stroke={strokeColor}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Interactive Points and Hover Zones */}
          {points.map((pt, i) => {
            const isHovered = hoveredIndex === i;
            const timeLabel = pt.data.time_bucket.includes("T")
              ? pt.data.time_bucket.split("T")[1].substring(0, 5)
              : pt.data.time_bucket.substring(0, 5);

            return (
              <g
                key={i}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredIndex(i)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                {/* Invisible wide hover target */}
                <rect
                  x={pt.x - 20}
                  y={paddingY}
                  width="40"
                  height={chartH}
                  fill="transparent"
                />

                {/* Vertical hover guide line */}
                {isHovered && (
                  <line
                    x1={pt.x}
                    y1={paddingY}
                    x2={pt.x}
                    y2={paddingY + chartH}
                    stroke="#444444"
                    strokeDasharray="2 2"
                    strokeWidth="1"
                  />
                )}

                {/* Point dot */}
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={isHovered ? 6 : 4}
                  fill="#1D1D1D"
                  stroke={strokeColor}
                  strokeWidth="2.5"
                  className="transition-all duration-150"
                />

                {/* X Axis Time Labels */}
                <text
                  x={pt.x}
                  y={height - 8}
                  fill={isHovered ? "#F5F5F5" : "#707070"}
                  fontSize="10"
                  textAnchor="middle"
                  fontFamily="Inter, sans-serif"
                >
                  {timeLabel}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Rounded Tooltip Overlay */}
        {hoveredIndex !== null && points[hoveredIndex] && (
          <div
            className="absolute pointer-events-none transform -translate-x-1/2 -translate-y-full px-3 py-2 rounded-md bg-bg-card border border-subtle-border shadow-xl text-caption z-10 whitespace-nowrap"
            style={{
              left: `${(points[hoveredIndex].x / width) * 100}%`,
              top: `${(points[hoveredIndex].y / height) * 100 - 8}%`,
            }}
          >
            <div className="flex items-center gap-2 font-medium text-content-primary">
              <span>{activeMetric}:</span>
              <strong style={{ color: strokeColor }}>
                {points[hoveredIndex].val.toFixed(1)}
              </strong>
            </div>
            <div className="text-[10px] text-content-muted mt-0.5">
              Risk: {points[hoveredIndex].data.dominant_risk_level} • {points[hoveredIndex].data.dominant_posture}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
