import React from "react";
import { Bell, User, ShieldCheck } from "lucide-react";

export type NavTab = "Dashboard" | "Workers" | "Devices" | "Analytics" | "Reports" | "Alerts";

interface TopNavigationProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  alertCount?: number;
  isSystemOnline?: boolean;
}

export const TopNavigation: React.FC<TopNavigationProps> = ({
  activeTab,
  onSelectTab,
  alertCount = 0,
  isSystemOnline = true,
}) => {
  const navItems: NavTab[] = [
    "Dashboard",
    "Workers",
    "Devices",
    "Analytics",
    "Reports",
    "Alerts",
  ];

  return (
    <header className="sticky top-0 z-50 w-full bg-bg-app border-b border-subtle-border">
      <div className="max-w-content mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
        {/* Left: Brand Logo & Nav items */}
        <div className="flex items-center gap-6 lg:gap-8">
          <div
            onClick={() => onSelectTab("Dashboard")}
            className="flex items-center gap-2 cursor-pointer select-none group"
          >
            <img
              src="/logo.png"
              alt="EdgeErgo Logo"
              className="w-8 h-8 rounded-lg object-contain shadow-sm group-hover:scale-105 transition-transform"
            />
            <span className="font-semibold text-[15px] tracking-tight text-content-primary group-hover:text-white transition-colors">
              EDGE<span className="text-brand-primary">ERGO</span>
            </span>
          </div>

          {/* Nav Items */}
          <nav className="flex items-center gap-1 sm:gap-2" aria-label="Main Navigation">
            {navItems.map((item) => {
              const isActive = activeTab === item;
              return (
                <button
                  key={item}
                  onClick={() => onSelectTab(item)}
                  className={`px-3 py-1.5 rounded-md text-nav transition-colors relative ${
                    isActive
                      ? "bg-bg-hover text-content-primary font-medium shadow-sm"
                      : "text-content-secondary hover:text-content-primary hover:bg-bg-card/60"
                  }`}
                  aria-current={isActive ? "page" : undefined}
                >
                  {item}
                  {item === "Alerts" && alertCount > 0 && (
                    <span className="ml-1.5 px-1.5 py-0.2 rounded-pill bg-status-highRisk/20 text-status-highRisk border border-status-highRisk/30 text-[10px] font-semibold">
                      {alertCount}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Right: Privacy Indicator, System Status, Notifications, Account */}
        <div className="flex items-center gap-4">
          {/* Privacy Guarantee Pill */}
          <div className="hidden md:flex items-center gap-1.5 text-caption text-content-muted hover:text-content-secondary transition-colors" title="Raw video is processed 100% on device. No camera feeds uploaded.">
            <ShieldCheck className="w-3.5 h-3.5 text-brand-accent" />
            <span>Edge AI Privacy</span>
          </div>

          {/* System Online Status */}
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-pill bg-bg-secondary border border-subtle-border">
            <span
              className={`w-2 h-2 rounded-full ${
                isSystemOnline ? "bg-status-safe animate-pulse" : "bg-status-critical"
              }`}
            />
            <span className="text-caption font-medium text-content-secondary">
              {isSystemOnline ? "System Online" : "Server Disconnected"}
            </span>
          </div>

          {/* Notification Bell */}
          <button
            onClick={() => onSelectTab("Alerts")}
            className="relative p-1.5 rounded-md hover:bg-bg-hover text-content-secondary hover:text-content-primary transition-colors"
            aria-label="View Alerts"
          >
            <Bell className="w-4 h-4" />
            {alertCount > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-status-highRisk" />
            )}
          </button>

          {/* User Account */}
          <div className="flex items-center gap-2 pl-2 border-l border-subtle-border">
            <div className="w-7 h-7 rounded-full bg-bg-secondary border border-subtle-border flex items-center justify-center text-content-secondary">
              <User className="w-4 h-4" />
            </div>
            <span className="hidden sm:inline text-caption text-content-secondary font-medium">
              Admin
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
