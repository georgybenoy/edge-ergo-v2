import React from "react";
import { Sparkles, ArrowRight } from "lucide-react";
import { Card } from "./Card";

interface InsightCardProps {
  insight: string;
  onAction?: () => void;
}

export const InsightCard: React.FC<InsightCardProps> = ({ insight, onAction }) => {
  return (
    <Card className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-l-4 border-l-brand-primary bg-bg-card">
      <div className="flex items-start gap-3.5">
        <div className="p-2 rounded-md bg-brand-primary/10 text-brand-primary flex-shrink-0 mt-0.5 sm:mt-0">
          <Sparkles className="w-4 h-4" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-caption uppercase tracking-wider text-content-secondary font-semibold">
              Actionable Intelligence
            </span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-bg-secondary text-content-muted border border-subtle-border">
              Automated
            </span>
          </div>
          <p className="mt-1 text-body text-content-primary font-normal leading-snug">
            {insight}
          </p>
        </div>
      </div>

      {onAction && (
        <button
          onClick={onAction}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-bg-secondary hover:bg-bg-hover text-caption text-content-primary border border-subtle-border transition-colors flex-shrink-0 font-medium self-end sm:self-auto"
        >
          <span>View Affected Workers</span>
          <ArrowRight className="w-3.5 h-3.5 text-brand-accent" />
        </button>
      )}
    </Card>
  );
};
