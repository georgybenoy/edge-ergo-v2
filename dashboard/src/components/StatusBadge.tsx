import React from "react";

export type StatusType =
  | "Safe"
  | "Attention"
  | "High Risk"
  | "Critical"
  | "Online"
  | "Offline"
  | "Low"
  | "Moderate"
  | "Active"
  | "Resolved";

interface StatusBadgeProps {
  status: StatusType | string;
  label?: string;
  size?: "sm" | "md";
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, size = "md" }) => {
  const norm = status.toLowerCase();

  let colorClasses = "text-content-secondary bg-bg-secondary border-subtle-border";
  let dotColor = "bg-content-muted";

  if (norm.includes("safe") || norm.includes("online") || norm.includes("low") || norm.includes("resolved")) {
    colorClasses = "text-[#39D98A] bg-[#39D98A]/10 border-[#39D98A]/30";
    dotColor = "bg-[#39D98A]";
  } else if (norm.includes("attention") || norm.includes("moderate") || norm.includes("warning")) {
    colorClasses = "text-[#F2C94C] bg-[#F2C94C]/10 border-[#F2C94C]/30";
    dotColor = "bg-[#F2C94C]";
  } else if (norm.includes("high risk") || norm.includes("high")) {
    colorClasses = "text-[#FF6B7A] bg-[#FF6B7A]/10 border-[#FF6B7A]/30";
    dotColor = "bg-[#FF6B7A]";
  } else if (norm.includes("critical") || norm.includes("offline") || norm.includes("very_high")) {
    colorClasses = "text-[#FF4D4D] bg-[#FF4D4D]/10 border-[#FF4D4D]/30";
    dotColor = "bg-[#FF4D4D]";
  }

  const padding = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-caption";
  const displayLabel = label || status;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-pill border font-medium transition-colors ${padding} ${colorClasses}`}
      role="status"
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} aria-hidden="true" />
      <span>{displayLabel}</span>
    </span>
  );
};
