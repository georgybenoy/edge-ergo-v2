import React, { useState, useEffect } from "react";
import { AppShell } from "./components/AppShell";
import { NavTab } from "./components/TopNavigation";
import { DashboardPage } from "./pages/DashboardPage";
import { WorkersPage } from "./pages/WorkersPage";
import { DevicesPage } from "./pages/DevicesPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { AlertsPage } from "./pages/AlertsPage";
import { DashboardApi } from "./services/api";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavTab>("Dashboard");
  const [selectedWorkerId, setSelectedWorkerId] = useState<string | null>(null);
  const [alertCount, setAlertCount] = useState<number>(0);
  const [isSystemOnline, setIsSystemOnline] = useState<boolean>(true);
  const [offlineMessage, setOfflineMessage] = useState<string | null>(null);

  // Periodic health & alert checks
  useEffect(() => {
    const checkSystemHealth = async () => {
      try {
        const summary = await DashboardApi.getSummary();
        setIsSystemOnline(true);
        setOfflineMessage(null);
        setAlertCount(summary.kpis.active_alerts || 0);
      } catch (err: any) {
        setIsSystemOnline(false);
        setOfflineMessage(
          err?.message ||
            "Central server unavailable, local monitoring continues. Telemetry will sync when connection restores."
        );
      }
    };

    checkSystemHealth();
    const interval = setInterval(checkSystemHealth, 30000); // 30s poll
    return () => clearInterval(interval);
  }, []);

  const handleDrilldownWorker = (deviceId: string) => {
    setSelectedWorkerId(deviceId);
    setActiveTab("Workers");
  };

  return (
    <AppShell
      activeTab={activeTab}
      onSelectTab={(tab) => {
        if (tab !== "Workers") setSelectedWorkerId(null);
        setActiveTab(tab);
      }}
      alertCount={alertCount}
      isSystemOnline={isSystemOnline}
      offlineMessage={offlineMessage}
    >
      {activeTab === "Dashboard" && (
        <DashboardPage onNavigateToWorkers={() => setActiveTab("Workers")} />
      )}
      {activeTab === "Workers" && (
        <WorkersPage initialSelectedDevice={selectedWorkerId} />
      )}
      {activeTab === "Devices" && <DevicesPage />}
      {activeTab === "Analytics" && <AnalyticsPage />}
      {activeTab === "Reports" && <ReportsPage />}
      {activeTab === "Alerts" && (
        <AlertsPage onViewWorker={handleDrilldownWorker} />
      )}
    </AppShell>
  );
};

export default App;
