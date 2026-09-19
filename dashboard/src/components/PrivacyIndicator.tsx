import React from "react";
import { ShieldCheck, Lock, EyeOff } from "lucide-react";

interface PrivacyIndicatorProps {
  compact?: boolean;
}

export const PrivacyIndicator: React.FC<PrivacyIndicatorProps> = ({ compact = false }) => {
  if (compact) {
    return (
      <div
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-pill bg-bg-secondary border border-subtle-border text-caption text-content-secondary hover:text-content-primary transition-colors cursor-help"
        title="Privacy Architecture: Processing occurs 100% on edge nodes. Zero camera frames or facial crops are uploaded or stored centrally."
      >
        <ShieldCheck className="w-3.5 h-3.5 text-brand-accent" />
        <span className="font-medium text-[12px]">Local Edge Processing</span>
      </div>
    );
  }

  return (
    <div className="rounded-card border border-subtle-border bg-bg-card p-4 sm:p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
      <div className="flex items-start gap-3.5">
        <div className="p-2.5 rounded-lg bg-bg-secondary border border-subtle-border text-brand-accent flex-shrink-0">
          <ShieldCheck className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h4 className="text-card-title text-content-primary font-medium">
              Zero-Camera-Storage Enterprise Privacy Model
            </h4>
            <span className="px-2 py-0.5 rounded-pill text-[11px] bg-brand-accent/10 text-brand-accent border border-brand-accent/20 font-medium">
              Enforced by Design
            </span>
          </div>
          <p className="mt-1 text-body text-content-secondary leading-relaxed">
            All computer vision inference and skeletal joint extraction occurs strictly inside the worker’s local device RAM.
            No video streams, camera frames, or facial crops are ever transmitted to or stored on this central server.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3 self-end md:self-auto flex-shrink-0">
        <div className="flex items-center gap-1.5 text-caption text-content-muted">
          <EyeOff className="w-3.5 h-3.5 text-status-safe" />
          <span>No Video Feeds</span>
        </div>
        <div className="flex items-center gap-1.5 text-caption text-content-muted">
          <Lock className="w-3.5 h-3.5 text-brand-primary" />
          <span>Encrypted Metadata</span>
        </div>
      </div>
    </div>
  );
};
