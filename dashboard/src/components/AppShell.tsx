import React from "react";
import { TopNavigation, NavTab } from "./TopNavigation";
import { AlertCircle } from "lucide-react";

interface AppShellProps {
  children: React.ReactNode;
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  alertCount?: number;
  isSystemOnline?: boolean;
  offlineMessage?: string | null;
}

export const AppShell: React.FC<AppShellProps> = ({
  children,
  activeTab,
  onSelectTab,
  alertCount = 0,
  isSystemOnline = true,
  offlineMessage = null,
}) => {
  return (
    <div className="min-h-screen flex flex-col bg-bg-app text-content-primary">
      {/* Offline Alert Banner if Central Server is down (DESIGN doc §40-43) */}
      {!isSystemOnline && (
        <div className="w-full bg-[#FF4D4D]/15 border-b border-[#FF4D4D]/30 py-2.5 px-4 text-center text-caption text-[#FF6B7A] flex items-center justify-center gap-2">
          <AlertCircle className="w-4 h-4 text-status-critical flex-shrink-0" />
          <span>
            {offlineMessage ||
              "Central server unavailable, local monitoring continues. Telemetry will automatically synchronize once reconnection is established."}
          </span>
        </div>
      )}

      {/* Top Navigation */}
      <TopNavigation
        activeTab={activeTab}
        onSelectTab={onSelectTab}
        alertCount={alertCount}
        isSystemOnline={isSystemOnline}
      />

      {/* Main Content Area (Max width 1440px centered) */}
      <main className="flex-grow w-full max-w-content mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-subtle-border bg-bg-app py-4 text-caption text-content-muted">
        <div className="max-w-content mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span>EdgeErgo Enterprise v0.1.0</span>
            <span>•</span>
            <span>Local On-Device Computer Vision</span>
          </div>
          <div>
            Privacy Guarantee: Zero video streaming or facial crops stored centrally.
          </div>
        </div>
      </footer>
    </div>
  );
};
