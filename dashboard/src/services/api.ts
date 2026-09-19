import {
  AlertItem,
  CorrelationsResponse,
  DashboardSummaryResponse,
  DeviceItem,
  TrendPoint,
  WorkstationDetail,
  WorkstationSummary,
} from "../types/dashboard";

const API_BASE = "/api/v1/dashboard";

class ApiError extends Error {
  isOffline: boolean;
  constructor(message: string, isOffline = false) {
    super(message);
    this.name = "ApiError";
    this.isOffline = isOffline;
  }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  try {
    const res = await fetch(url, options);
    if (!res.ok) {
      const errBody = await res.text().catch(() => "");
      throw new ApiError(`Request failed with status ${res.status}: ${errBody}`);
    }
    return (await res.json()) as T;
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    // Network / offline error
    throw new ApiError(
      "Central server unavailable, local monitoring continues. Telemetry will sync when connection restores.",
      true
    );
  }
}

export const DashboardApi = {
  getSummary: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request<DashboardSummaryResponse>(`${API_BASE}/summary${query}`);
  },

  getWorkstations: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request<WorkstationSummary[]>(`${API_BASE}/workstations${query}`);
  },

  getWorkstationDetail: (deviceId: string) => {
    return request<WorkstationDetail>(`${API_BASE}/workstations/${encodeURIComponent(deviceId)}`);
  },

  getTrends: (interval: "hourly" | "daily" = "hourly", deviceId?: string) => {
    const params = new URLSearchParams({ interval });
    if (deviceId) params.append("device_id", deviceId);
    return request<TrendPoint[]>(`${API_BASE}/trends?${params.toString()}`);
  },

  getCorrelations: () => {
    return request<CorrelationsResponse>(`${API_BASE}/correlations`);
  },

  getAlerts: (severity?: string) => {
    const params = new URLSearchParams();
    if (severity && severity !== "All") {
      params.append("severity", severity);
    }
    const query = params.toString() ? `?${params.toString()}` : "";
    return request<AlertItem[]>(`${API_BASE}/alerts${query}`);
  },

  getDevices: () => {
    return request<DeviceItem[]>(`${API_BASE}/devices`);
  },

  downloadCsv: async (startDate?: string, endDate?: string, deviceId?: string) => {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    if (deviceId) params.append("device_id", deviceId);
    const query = params.toString() ? `?${params.toString()}` : "";
    const res = await fetch(`/api/v1/export/csv${query}`);
    if (!res.ok) throw new Error("Failed to generate CSV export from central server.");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute(
      "download",
      `edgeergo_telemetry_${new Date().toISOString().slice(0, 10)}.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },

  getPeriodicReport: (reportType: "daily" | "weekly" | "monthly" = "weekly") => {
    return request<any>(`/api/v1/reports/${reportType}`);
  },

  openReportHtml: (reportType: "daily" | "weekly" | "monthly" = "weekly") => {
    window.open(`/api/v1/reports/${reportType}/html`, "_blank");
  },
};
