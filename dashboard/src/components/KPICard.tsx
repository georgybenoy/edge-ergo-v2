import React from "react";
import { Card } from "./Card";

interface KPICardProps {
  label: string;
  value: string | number;
  delta?: string;
  subtext?: string;
  isNegativeDeltaGood?: boolean;
}

export const KPICard: React.FC<KPICardProps> = ({
  label,
  value,
  delta,
  subtext,
  isNegativeDeltaGood = false,
}) => {
  let deltaColor = "text-content-secondary";
  if (delta) {
    const isNegative = delta.startsWith("-");
    const isPositive = delta.startsWith("+");
    if (isNegativeDeltaGood) {
      deltaColor = isNegative ? "text-status-safe" : "text-status-highRisk";
    } else {
      deltaColor = isPositive ? "text-status-safe" : isNegative ? "text-status-highRisk" : "text-content-secondary";
    }
  }

  return (
    <Card className="flex flex-col justify-between h-full min-h-[115px]">
      <div className="flex items-center justify-between gap-2">
        <span className="text-body text-content-secondary font-medium tracking-wide">
          {label}
        </span>
        {delta && (
          <span
            className={`text-caption px-2 py-0.5 rounded-pill bg-bg-secondary border border-subtle-border font-medium ${deltaColor}`}
          >
            {delta}
          </span>
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-display text-content-primary font-medium tracking-tight">
          {value}
        </span>
        {subtext && (
          <span className="text-caption text-content-muted">
            {subtext}
          </span>
        )}
      </div>
    </Card>
  );
};
