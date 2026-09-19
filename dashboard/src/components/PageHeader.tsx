import React from "react";

export type DashboardSubTab =
  | "Overview"
  | "Posture"
  | "Risk"
  | "Fatigue"
  | "Expression"
  | "Activity";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  tabs?: DashboardSubTab[];
  activeSubTab?: DashboardSubTab;
  onSelectSubTab?: (tab: DashboardSubTab) => void;
  filterOption?: string;
  onFilterChange?: (opt: string) => void;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  tabs,
  activeSubTab,
  onSelectSubTab,
  filterOption = "All Workers",
  onFilterChange,
}) => {
  return (
    <div className="w-full pb-4 border-b border-subtle-border space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-page-title text-content-primary tracking-tight">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-1 text-body text-content-secondary">
              {subtitle}
            </p>
          )}
        </div>

        {/* Filter Controls (All Workers / Today / Live) */}
        <div className="flex items-center gap-2">
          {["All Workers", "Today", "Live"].map((opt) => {
            const isSelected = filterOption === opt;
            return (
              <button
                key={opt}
                onClick={() => onFilterChange?.(opt)}
                className={`px-3 py-1.5 rounded-md text-caption font-medium border transition-colors ${
                  isSelected
                    ? "bg-bg-hover text-content-primary border-subtle-border shadow-sm"
                    : "bg-bg-card text-content-secondary border-subtle-border hover:bg-bg-secondary hover:text-content-primary"
                }`}
              >
                {opt === "Live" && (
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-status-safe mr-1.5 animate-pulse" />
                )}
                {opt}
              </button>
            );
          })}
        </div>
      </div>

      {/* Sub-tabs with subtle underline */}
      {tabs && tabs.length > 0 && (
        <div className="flex items-center gap-6 overflow-x-auto pt-1" role="tablist">
          {tabs.map((tab) => {
            const isActive = activeSubTab === tab;
            return (
              <button
                key={tab}
                role="tab"
                aria-selected={isActive}
                onClick={() => onSelectSubTab?.(tab)}
                className={`pb-2 text-body transition-colors relative whitespace-nowrap ${
                  isActive
                    ? "text-content-primary font-medium"
                    : "text-content-muted hover:text-content-secondary"
                }`}
              >
                {tab}
                {isActive && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-brand-primary rounded-pill" />
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
