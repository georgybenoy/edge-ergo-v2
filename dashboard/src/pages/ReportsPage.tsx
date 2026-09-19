import React, { useState } from "react";
import { FileText, Download, FileSpreadsheet, Check, Calendar, ShieldCheck } from "lucide-react";
import { Card } from "../components/Card";
import { KPICard } from "../components/KPICard";

export const ReportsPage: React.FC = () => {
  const [downloadingCsv, setDownloadingCsv] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [downloadMessage, setDownloadMessage] = useState<string | null>(null);

  const handleExportCsv = () => {
    setDownloadingCsv(true);
    // Simulate generation or call endpoint
    setTimeout(() => {
      // Create and download CSV locally for the user
      const headers = "Device_ID,Session_ID,Window_Start,RULA_Avg,REBA_Avg,Risk_Level,Dominant_Posture\n";
      const sample = "NODE-001,S-001,2026-09-19T09:00:00Z,5.2,6.1,HIGH,FORWARD_HEAD\nNODE-002,S-002,2026-09-19T09:00:00Z,2.1,2.4,LOW,NEUTRAL\n";
      const blob = new Blob([headers + sample], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `edgeergo_ergonomic_report_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setDownloadingCsv(false);
      setDownloadMessage("CSV report generated and downloaded successfully.");
      setTimeout(() => setDownloadMessage(null), 4000);
    }, 600);
  };

  const handleExportPdf = () => {
    setDownloadingPdf(true);
    setTimeout(() => {
      setDownloadingPdf(false);
      setDownloadMessage("PDF executive report compilation scheduled (Phase 15 endpoint).");
      setTimeout(() => setDownloadMessage(null), 4000);
    }, 800);
  };

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
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-md bg-bg-card hover:bg-bg-hover text-caption text-content-primary border border-subtle-border transition-colors font-medium shadow-sm"
          >
            <FileSpreadsheet className="w-4 h-4 text-status-safe" />
            <span>{downloadingCsv ? "Generating..." : "Export CSV"}</span>
          </button>

          <button
            onClick={handleExportPdf}
            disabled={downloadingPdf}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-md bg-brand-primary text-bg-app hover:opacity-90 text-caption font-semibold transition-opacity shadow-sm"
          >
            <FileText className="w-4 h-4" />
            <span>{downloadingPdf ? "Compiling..." : "Generate PDF"}</span>
          </button>
        </div>
      </div>

      {downloadMessage && (
        <div className="p-3 rounded-md bg-status-safe/10 border border-status-safe/30 text-caption text-status-safe flex items-center gap-2">
          <Check className="w-4 h-4" />
          <span>{downloadMessage}</span>
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Total Telemetry Windows"
          value="1,420"
          subtext="analyzed on edge"
        />
        <KPICard
          label="Risk Mitigation Rate"
          value="88.4%"
          delta="+4.2%"
          subtext="resolved warnings"
        />
        <KPICard
          label="OSHA Ergo Compliance"
          value="96.2%"
          delta="Optimal"
          subtext="workplace audit grade"
        />
        <KPICard
          label="Audit Records"
          value="100%"
          subtext="zero video stored"
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
            onClick={handleExportCsv}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md bg-bg-secondary hover:bg-bg-hover text-caption text-content-primary border border-subtle-border transition-colors font-medium"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download CSV Data</span>
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
            className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md bg-bg-secondary hover:bg-bg-hover text-caption text-content-primary border border-subtle-border transition-colors font-medium"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download Telemetry</span>
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
            onClick={handleExportPdf}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md bg-bg-secondary hover:bg-bg-hover text-caption text-content-primary border border-subtle-border transition-colors font-medium"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download Audit Certificate</span>
          </button>
        </Card>
      </div>
    </div>
  );
};
