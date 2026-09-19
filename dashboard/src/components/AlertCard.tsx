import React from "react";
import { AlertTriangle, Clock, ArrowUpRight } from "lucide-react";
import { AlertItem } from "../types/dashboard";
import { StatusBadge } from "./StatusBadge";
import { Card } from "./Card";

interface AlertCardProps {
  alert: AlertItem;
  onViewWorker?: (deviceId: string) => void;
}

export const AlertCard: React.FC<AlertCardProps> = ({ alert, onViewWorker }) => {
  return (
    <Card className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 hover:border-content-muted/40 transition-colors">
      <div className="flex items-start gap-3.5 flex-grow">
        <div className="p-2 rounded-md bg-bg-secondary border border-subtle-border flex-shrink-0 text-status-attention mt-0.5">
          <AlertTriangle className="w-4 h-4 text-status-attention" />
        </div>

        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={alert.severity} size="sm" />
            <span className="text-body font-medium text-content-primary">
              {alert.device_name}
            </span>
            <span className="text-caption text-content-muted">
              ({alert.device_id})
            </span>
          </div>

          <p className="text-body text-content-secondary leading-snug">
            {alert.description}
          </p>

          <div className="flex flex-wrap items-center gap-4 text-caption text-content-muted pt-1">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Duration: {alert.duration_sec}s
            </span>
            <span>RULA Score: <strong className="text-content-primary">{alert.rula_score}</strong></span>
            <span>Triggered: {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 self-end md:self-auto flex-shrink-0">
        <button
          onClick={() => onViewWorker?.(alert.device_id)}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-bg-secondary hover:bg-bg-hover text-caption text-brand-accent border border-subtle-border transition-colors font-medium"
        >
          <span>View Worker</span>
          <ArrowUpRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </Card>
  );
};
