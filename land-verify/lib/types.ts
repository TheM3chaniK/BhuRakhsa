export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export type MatchStatus = "MATCHED" | "MISMATCH" | "MISSING" | "CANNOT_CHECK";

export type ExtractedField = {
  label: string;
  value: string;
  confidence: number; // 0-100
};

export type ValidationRow = {
  field: string;
  document: string;
  record: string;
  status: MatchStatus;
};

export type CaseSummary = {
  id: string;
  village: string;
  surveyNo: string;
  owner: string;
  risk: RiskLevel;
  submitted: string;
  reason: string;
};
