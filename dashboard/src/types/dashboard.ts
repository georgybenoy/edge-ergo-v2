export interface SummaryKPIs {
  workers_monitored: number;
  workers_monitored_delta: string;
  at_risk_workers: number;
  at_risk_workers_delta: string;
  posture_compliance_pct: number;
  posture_compliance_delta: string;
  active_alerts: number;
  active_alerts_delta: string;
}

export interface RiskDistribution {
  LOW: number;
  MODERATE: number;
  HIGH: number;
  VERY_HIGH: number;
}

export interface ExpressionDistribution {
  neutral_percentage: number;
  positive_percentage: number;
  negative_percentage: number;
  reduced_expression_percentage: number;
}

export interface AggregatedMetrics {
  total_windows: number;
  active_nodes: number;
  average_rula: number;
  maximum_rula: number;
  average_reba: number;
  maximum_reba: number;
  risk_distribution: RiskDistribution;
  high_risk_percentage: number;
  dominant_posture: string;
  expression_distribution: ExpressionDistribution;
  total_breaks_recommended: number;
  total_breaks_acknowledged: number;
  break_compliance_rate: number;
}

export interface DashboardSummaryResponse {
  kpis: SummaryKPIs;
  metrics: AggregatedMetrics;
  insight: string;
  privacy_guarantee: string;
}

export interface WorkstationSummary {
  device_id: string;
  device_name: string;
  total_windows: number;
  average_rula: number;
  average_reba: number;
  high_risk_percentage: number;
  dominant_posture: string;
  primary_expression: string;
  break_compliance_rate: number;
  health_status: "ONLINE" | "OFFLINE";
}

export interface BodySegments {
  neck: "Safe" | "Attention" | "High Risk" | "Critical";
  trunk: "Safe" | "Attention" | "High Risk" | "Critical";
  shoulders: "Safe" | "Attention" | "High Risk" | "Critical";
  wrists: "Safe" | "Attention" | "High Risk" | "Critical";
  legs: "Safe" | "Attention" | "High Risk" | "Critical";
}

export interface FatigueIndicators {
  screen_time_hours: number;
  movement_frequency_score: number;
  break_adherence_pct: number;
  posture_deterioration_trend: string;
}

export interface WorkstationDetail {
  device_id: string;
  device_name: string;
  status: string;
  software_version: string;
  last_seen: string;
  metrics: AggregatedMetrics;
  body_segments: BodySegments;
  fatigue_indicators: FatigueIndicators;
  recent_windows: any[];
}

export interface TrendPoint {
  time_bucket: string;
  window_count: number;
  average_rula: number;
  average_reba: number;
  dominant_risk_level: "LOW" | "MODERATE" | "HIGH" | "VERY_HIGH";
  dominant_posture: string;
}

export interface ObservedPattern {
  pattern_id: string;
  observed_pattern: string;
  quantitative_metrics: Record<string, any>;
}

export interface CorrelationsResponse {
  total_analyzed_windows: number;
  observed_patterns: ObservedPattern[];
  metadata?: Record<string, any>;
}

export type SeverityLevel = "All" | "Attention" | "High Risk" | "Critical" | "Resolved";

export interface AlertItem {
  alert_id: string;
  device_id: string;
  device_name: string;
  severity: "Attention" | "High Risk" | "Critical";
  condition: string;
  description: string;
  duration_sec: number;
  rula_score: number;
  timestamp: string;
  status: string;
}

export interface DeviceItem {
  device_id: string;
  device_name: string;
  software_version: string;
  registered_at: string;
  last_seen: string;
  health_status: "ONLINE" | "OFFLINE";
  camera_detected?: boolean;
}
