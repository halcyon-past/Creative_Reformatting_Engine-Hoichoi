// Mirrors the backend response models in cre/api/schemas.py.

export type MediaKind = "image" | "video";
export type RuleOutcome = "pass" | "fail" | "warn" | "skip";
export type Severity = "error" | "warning" | "info";

export type VariantStatus =
  | "pending"
  | "rendering"
  | "validating"
  | "published"
  | "quarantined"
  | "failed";

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface RuleResult {
  rule_id: string;
  title: string;
  outcome: RuleOutcome;
  severity: Severity;
  message: string;
  expected: string | null;
  actual: string | null;
  evidence: Record<string, unknown>;
}

export interface ComplianceReport {
  report_id: string;
  variant_id: string;
  spec_id: string;
  spec_version: string;
  verdict: "pass" | "fail";
  generated_at: string;
  asset_sha256: string | null;
  results: RuleResult[];
}

export interface CropDecision {
  crop: { x1: number; y1: number; x2: number; y2: number };
  source_size: [number, number];
  output_size: [number, number];
  strategy: string;
  score: number;
  subject_coverage: number;
  faces_considered: number;
  faces_fully_inside: number;
  faces_clipped: number;
  rationale: string[];
}

export interface Variant {
  id: string;
  asset_id: string;
  profile_id: string;
  profile_label: string | null;
  ratio_label: string;
  kind: MediaKind;
  status: VariantStatus;
  in_library: boolean;
  url: string | null;
  thumbnail_url: string | null;
  width: number | null;
  height: number | null;
  duration_s: number | null;
  size_bytes: number | null;
  verdict: "pass" | "fail" | null;
  failure_count: number;
  warning_count: number;
  crop_decision: CropDecision | null;
  report: ComplianceReport | null;
  reframe_path_points: number;
  error: string | null;
}

export interface Asset {
  id: string;
  title: string;
  kind: MediaKind;
  status: "uploaded" | "analyzing" | "ready" | "failed";
  original_filename: string;
  url: string | null;
  thumbnail_url: string | null;
  width: number | null;
  height: number | null;
  duration_s: number | null;
  fps: number | null;
  size_bytes: number;
  has_audio: boolean;
  face_count: number;
  analysis_notes: string[];
  variant_count: number;
  published_count: number;
  error: string | null;
  created_at: string;
}

export interface Job {
  id: string;
  type: "analyze" | "reformat_all" | "reformat_one" | "revalidate";
  status: JobStatus;
  asset_id: string;
  progress: number;
  stage: string | null;
  error: string | null;
  result: Record<string, unknown>;
  created_at: string;
  finished_at: string | null;
}

export interface Profile {
  id: string;
  label: string;
  ratio: string;
  kind: MediaKind;
  width: number;
  height: number;
  source: string | null;
  safe_zones: { action: number[] | null; title: number[] | null };
  reserved_zones: { name: string; rect: number[] }[];
  composition: Record<string, unknown>;
}

export interface SpecSheet {
  spec_id: string;
  spec_version: string;
  description: string;
  updated: string | null;
  profiles: Profile[];
  render_sets: Record<string, string[]>;
  compliance_defaults: Record<string, unknown>;
}

export interface ReframePoint {
  t: number;
  cx: number;
  cy: number;
  width: number;
  height: number;
  active_track_id: number | null;
  shot_id: number;
}
