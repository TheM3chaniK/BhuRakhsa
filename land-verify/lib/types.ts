// =============================================================================
// Domain & Enums
// =============================================================================

export type UserRole =
  | "CIVILIAN"
  | "AREA_OFFICER"
  | "SUPER_ADMIN"
  | "civilian"
  | "area_officer"
  | "super_admin";

export function isOfficerRole(role?: string): boolean {
  if (!role) return false;
  const r = role.toUpperCase();
  return r === "AREA_OFFICER" || r === "OFFICER";
}

export function isAdminRole(role?: string): boolean {
  if (!role) return false;
  const r = role.toUpperCase();
  return r === "SUPER_ADMIN" || r === "ADMIN";
}

export function isCivilianRole(role?: string): boolean {
  if (!role) return false;
  const r = role.toUpperCase();
  return r === "CIVILIAN" || r === "USER";
}

export type CaseStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "PROCESSING"
  | "REVIEW_READY"
  | "UNDER_REVIEW"
  | "PROOF_REQUIRED"
  | "APPROVED"
  | "REJECTED";

export type ReviewStatus =
  | "NOT_STARTED"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "CANCELLED";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "UNKNOWN";

export type MatchStatus = "MATCHED" | "MISMATCH" | "MISSING" | "CANNOT_CHECK";

export type OfficerDecision = "APPROVE" | "REJECT" | "REQUEST_PROOF";

// =============================================================================
// UI Compatibility Types
// =============================================================================

export type ExtractedField = {
  label: string;
  value: string;
  confidence: number; // 0-100
  normalizedValue?: string;
  status?: string;
  evidenceText?: string;
  pageNumber?: number;
  bbox?: number[];
};

export type ValidationRow = {
  field: string;
  document: string;
  record: string;
  status: MatchStatus;
  notes?: string;
};

export type CaseSummary = {
  id: string;
  caseNumber?: string;
  village: string;
  surveyNo: string;
  owner: string;
  risk: RiskLevel;
  riskScore?: number;
  status?: CaseStatus;
  reviewStatus?: ReviewStatus;
  submitted: string;
  reason: string;
};

export type TimelineEvent = {
  label: string;
  detail: string;
  who: string;
  timestamp?: string;
};

// =============================================================================
// Backend API Schemas
// =============================================================================

export type UserProfile = {
  id: string;
  email: string;
  full_name: string;
  phone?: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  assigned_areas?: AreaResponse[];
};

export type AuthResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type AreaResponse = {
  id: string;
  name: string;
  code: string;
  description?: string;
  is_active: boolean;
  created_at: string;
};

export type BackendCase = {
  id: string;
  case_number: string;
  created_by: string;
  area_id: string;
  status: CaseStatus;
  risk_level: RiskLevel;
  title?: string;
  description?: string;
  created_at: string;
  updated_at: string;
  submitted_at?: string;
  reviewed_at?: string;
  reviewed_by?: string;
};

export type BackendDocument = {
  id: string;
  case_id: string;
  filename: string;
  file_size_bytes: number;
  mime_type: string;
  document_type: string;
  status: string;
  page_count: number;
  created_at: string;
};

export type BackendOCRPage = {
  id: string;
  document_id: string;
  page_number: number;
  text: string;
  model_name: string;
  processing_time_ms: number;
  created_at: string;
};

export type BackendExtractedField = {
  id: string;
  document_id: string;
  field_name: string;
  field_value?: string;
  normalized_value?: string;
  confidence: number;
  status: string;
  evidence_text?: string;
  page_number?: number;
  bbox?: number[];
};

export type BackendValidationRun = {
  id: string;
  property_profile_id: string;
  validation_type: "DATABASE" | "GIS";
  status: "PENDING" | "RUNNING" | "PASSED" | "PASSED_WITH_LIMITATIONS" | "FAILED";
  overall_score: number;
  executed_rules: string[];
  created_at: string;
  results?: Array<{
    id: string;
    field_name: string;
    submitted_value?: string;
    reference_value?: string;
    match_status: string;
    match_score: number;
    notes?: string;
  }>;
};

export type BackendMapData = {
  case_id: string;
  declared_polygon?: {
    type: string;
    coordinates: number[][][];
  };
  gis_parcel_polygon?: {
    type: string;
    coordinates: number[][][];
  };
  discrepancy_details?: {
    declared_area_acres?: number;
    mapped_area_acres?: number;
    area_difference_percentage?: number;
    is_contained?: boolean;
    overlap_percentage?: number;
  };
};

export type BackendRiskAssessment = {
  id: string;
  case_id: string;
  risk_score: number;
  risk_level: RiskLevel;
  mismatches_count: number;
  factors: Array<{
    factor_name: string;
    description: string;
    severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
    score_contribution: number;
  }>;
};

export type BackendAuditEvent = {
  id: string;
  case_id?: string;
  action: string;
  actor_id?: string;
  actor_type: string;
  entity_type: string;
  old_state?: string;
  new_state?: string;
  metadata_json?: Record<string, any>;
  created_at: string;
};

export type BackendProofSubmission = {
  id: string;
  proof_request_id: string;
  submitted_by: string;
  document_id: string;
  comment?: string;
  created_at: string;
  document?: BackendDocument;
};

export type BackendProofRequest = {
  id: string;
  case_id: string;
  requested_by: string;
  requested_from: string;
  title: string;
  description: string;
  proof_type: string;
  status: "open" | "submitted" | "accepted" | "rejected" | "cancelled";
  created_at: string;
  submissions?: BackendProofSubmission[];
};

export type CaseReviewResponse = {
  id: string;
  case_id: string;
  reviewer_id?: string;
  reviewer_area_id?: string;
  status: ReviewStatus;
  started_at?: string;
  completed_at?: string;
  decision?: OfficerDecision;
  decision_reason?: string;
  risk_score_at_decision?: number;
  risk_level_at_decision?: RiskLevel;
  created_at: string;
  updated_at: string;
};

export type ReviewQueueItem = {
  case_id: string;
  case_number: string;
  title?: string;
  area_id: string;
  risk_score: number;
  risk_level: RiskLevel;
  case_status: CaseStatus;
  review_status: ReviewStatus;
  reviewer_id?: string;
  created_at: string;
};

export type ReviewDetailResponse = {
  case: BackendCase;
  review?: CaseReviewResponse;
  property_profile?: {
    id: string;
    survey_number?: string;
    plot_number?: string;
    village?: string;
    district?: string;
    declared_area?: number;
    area_unit?: string;
    owners?: Array<{
      owner_name: string;
      owner_type?: string;
      share_percentage?: number;
    }>;
  };
  documents: BackendDocument[];
  database_validation?: BackendValidationRun;
  gis_validation?: BackendValidationRun;
  mismatches: Array<{
    id: string;
    mismatch_type: string;
    severity: string;
    field_name?: string;
    submitted_value?: string;
    reference_value?: string;
    reason_code: string;
    description: string;
  }>;
  risk_assessment?: BackendRiskAssessment;
  history: Array<{
    id: string;
    case_id: string;
    actor_id: string;
    action: string;
    old_status?: string;
    new_status: string;
    old_decision?: string;
    new_decision?: string;
    reason?: string;
    created_at: string;
  }>;
};

export type OfficerDetailResponse = {
  id: string;
  email: string;
  full_name: string;
  phone?: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  assigned_areas: AreaResponse[];
};
