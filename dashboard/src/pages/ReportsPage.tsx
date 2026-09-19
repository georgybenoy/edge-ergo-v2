import React, { useState, useEffect } from "react";
import { FileText, Download, FileSpreadsheet, Check, Calendar, ShieldCheck, AlertCircle } from "lucide-react";
import { Card } from "../components/Card";
import { KPICard } from "../components/KPICard";
import { DashboardApi } from "../services/api";

export const ReportsPage: React.FC = () => {
  const [downloadingCsv, setDownloadingCsv] = useState(false);
  const [downloadMessage, setDownloadMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reportData, setReportData] = useState<any>(null);

  useEffect(() => {
    const loadReportSummary = async () => {
      try {
        const data = await DashboardApi.getPeriodicReport("weekly");
        setReportData(data);
      } catch (err: any) {
        console.warn("Could not load initial weekly report summary:", err);
      }
    };
    loadReportSummary();
  }, []);

  const handleExportCsv = async () => {
    setDownloadingCsv(true);
    setErrorMessage(null);
    try {
      await DashboardApi.downloadCsv();
      setDownloadMessage("Aggregated telemetry CSV export downloaded successfully.");
      setTimeout(() => setDownloadMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to download CSV export.");
      setTimeout(() => setErrorMessage(null), 5000);
    } finally {
      setDownloadingCsv(false);
    }
  };

  const handleGeneratePdf = () => {
    try {
      DashboardApi.openReportHtml("weekly");
      setDownloadMessage("Opened executive briefing formatted for Print-to-PDF.");
      setTimeout(() => setDownloadMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to open printable report.");
    }
  };

  const handleAuditCertificate = () => {
    try {
      DashboardApi.openReportHtml("monthly");
      setDownloadMessage("Opened compliance audit certificate.");
      setTimeout(() => setDownloadMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to open audit certificate.");
    }
  };

  const summary = reportData?.summary;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-subtle-border">
        <div>
          <h1 className="text-page-title text-content-primary tracking-tight">
            Compliance Reports & Data Exports
          </h1>
          <p className="mt-1 text-body text-content-secondary">
            Enterprise health & safety documentation, exportable audits, and executive summaries
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleExportCsv}
            disabled={downloadingCsv}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-md bg-bg-card hover:bg-bg-hover text-caption text-content-primary border border-subtle-border transition-colors font-medium shadow-sm cursor-pointer disabled:opacity-50"
          >
            <FileSpreadsheet className="w-4 h-4 text-status-safe" />
            <span>{downloadingCsv ? "Exporting CSV..." : "Export CSV"}</span>
          </button>

          <button
            onClick={handleGeneratePdf}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-md bg-brand-primary text-bg-app hover:opacity-90 text-caption font-semibold transition-opacity shadow-sm cursor-pointer"
          >
            <FileText className="w-4 h-4" />
            <span>Generate PDF</span>
          </button>
        </div>
      </div>

      {downloadMessage && (
        <div className="p-3 rounded-md bg-status-safe/10 border border-status-safe/30 text-caption text-status-safe flex items-center gap-2">
          <Check className="w-4 h-4" />
          <span>{downloadMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-3 rounded-md bg-status-critical/10 border border-status-critical/30 text-caption text-status-critical flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Summary KPI Cards from real weekly report */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Total Telemetry Windows"
          value={summary?.total_windows ?? 0}
          subtext="analyzed on edge"
        />
        <KPICard
          label="Workers Analyzed"
          value={summary?.workers_analyzed ?? 0}
          delta={summary?.workers_analyzed ? `${summary.workers_analyzed} active` : undefined}
          subtext="in current period"
        />
        <KPICard
          label="OSHA Ergo Compliance"
          value={`${summary?.posture_compliance_pct ?? 100}%`}
          delta={summary?.posture_compliance_pct ? (summary.posture_compliance_pct >= 80 ? "Optimal" : "Attention") : "Optimal"}
          subtext="workplace audit grade"
        />
        <KPICard
          label="Break Adherence"
          value={`${summary?.break_adherence_pct ?? 0}%`}
          subtext="movement prompts acknowledged"
        />
      </div>

      {/* Available Pre-Formatted Report Templates */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center gap-2 text-content-primary font-medium text-card-title mb-1">
              <Calendar className="w-4 h-4 text-brand-secondary" />
              <span>Weekly Executive Briefing</span>
            </div>
            <p className="text-body text-content-secondary leading-relaxed">
              High-level overview of ergonomic risk factors, break adherence percentages, and department trends across the past 7 days.
            </p>
          </div>
          <button
            onClick={handleGeneratePdf}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md bg-bg-secondary hover:bg-bg-hover text-caption text-content-primary border border-subtle-border transition-colors font-medium cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Open Executive Briefing</span>
          </button>
        </Card>

        <Card className="flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center gap-2 text-content-primary font-medium text-card-title mb-1">
              <FileSpreadsheet className="w-4 h-4 text-status-safe" />
              <span>OSHA RULA / REBA Raw Telemetry</span>
            </div>
            <p className="text-body text-content-secondary leading-relaxed">
              Granular per-session telemetry windows containing joint angle averages, RULA/REBA classification scores, and alert flags.
            </p>
          </div>
          <button
            onClick={handleExportCsv}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md bg-bg-secondary hover:bg-bg-hover text-caption text-content-primary border border-subtle-border transition-colors font-medium cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download CSV Data</span>
          </button>
        </Card>

        <Card className="flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center gap-2 text-content-primary font-medium text-card-title mb-1">
              <ShieldCheck className="w-4 h-4 text-brand-accent" />
              <span>Privacy & Security Compliance Audit</span>
            </div>
            <p className="text-body text-content-secondary leading-relaxed">
              Cryptographic verification certificate verifying zero camera frames, video feeds, or facial crops were written to disk or transferred.
            </p>
          </div>
          <button
            onClick={handleAuditCertificate}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md bg-bg-secondary hover:bg-bg-hover text-caption text-content-primary border border-subtle-border transition-colors font-medium cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download Audit Certificate</span>
          </button>
        </Card>
      </div>
    </div>
  );
};
