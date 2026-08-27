import {
  AreaResponse,
  AuthResponse,
  BackendAuditEvent,
  BackendCase,
  BackendDocument,
  BackendExtractedField,
  BackendMapData,
  BackendOCRPage,
  BackendProofRequest,
  BackendRiskAssessment,
  BackendValidationRun,
  CaseReviewResponse,
  CaseStatus,
  OfficerDecision,
  ReviewDetailResponse,
  ReviewQueueItem,
  RiskLevel,
  UserProfile,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

class ApiClient {
  private token: string | null = null;

  constructor() {
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("bhuraksha_token");
    }
  }

  setToken(token: string | null) {
    this.token = token;
    if (typeof window !== "undefined") {
      if (token) {
        localStorage.setItem("bhuraksha_token", token);
      } else {
        localStorage.removeItem("bhuraksha_token");
      }
    }
  }

  getToken(): string | null {
    if (!this.token && typeof window !== "undefined") {
      this.token = localStorage.getItem("bhuraksha_token");
    }
    return this.token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    const token = this.getToken();
    if (token && !headers["Authorization"]) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (response.status === 401) {
        this.setToken(null);
        if (
          typeof window !== "undefined" &&
          !window.location.pathname.startsWith("/login")
        ) {
          window.location.href = "/login";
        }
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Unauthorized. Please log in.");
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const message =
          errorData.detail ||
          errorData.error?.message ||
          `Request failed with status ${response.status}`;
        throw new Error(message);
      }

      return await response.json();
    } catch (err: any) {
      if (err.name === "AbortError" || err.message?.includes("aborted")) {
        // Silently resolve aborted requests from rapid client navigation
        return {} as T;
      }
      throw err;
    }
  }

  // ===========================================================================
  // Auth API
  // ===========================================================================

  async login(email: string, password: string): Promise<AuthResponse> {
    const data = await this.request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async register(
    email: string,
    password: string,
    fullName: string,
    phone?: string
  ): Promise<UserProfile> {
    return await this.request<UserProfile>("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        full_name: fullName,
        phone,
      }),
    });
  }

  async getMe(): Promise<UserProfile> {
    return await this.request<UserProfile>("/users/me");
  }

  async logout(): Promise<void> {
    try {
      await this.request("/auth/logout", { method: "POST" });
    } catch {
      // Ignore errors on logout
    }
    this.setToken(null);
  }

  // ===========================================================================
  // Areas API
  // ===========================================================================

  async listAreas(): Promise<{ items: AreaResponse[]; total: number }> {
    try {
      const res = await this.request<any>("/areas/active");
      if (Array.isArray(res)) {
        return { items: res, total: res.length };
      }
      if (res && res.items) {
        return res;
      }
    } catch {
      try {
        return await this.request<{ items: AreaResponse[]; total: number }>(
          "/areas?page=1&page_size=100&is_active=true"
        );
      } catch {
        return { items: [], total: 0 };
      }
    }
    return { items: [], total: 0 };
  }

  // ===========================================================================
  // Cases API
  // ===========================================================================

  async createCase(data: {
    area_id: string;
    title: string;
    description?: string;
  }): Promise<BackendCase> {
    return await this.request<BackendCase>("/cases", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async submitCase(caseId: string): Promise<BackendCase> {
    return await this.request<BackendCase>(`/cases/${caseId}/submit`, {
      method: "POST",
    });
  }

  async getCase(caseId: string): Promise<BackendCase> {
    return await this.request<BackendCase>(`/cases/${caseId}`);
  }

  async listCases(params?: {
    status?: CaseStatus;
    risk_level?: RiskLevel;
    page?: number;
    page_size?: number;
  }): Promise<{ items: BackendCase[]; total: number }> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.risk_level) searchParams.set("risk_level", params.risk_level);
    if (params?.page) searchParams.set("page", params.page.toString());
    if (params?.page_size)
      searchParams.set("page_size", params.page_size.toString());

    return await this.request<{ items: BackendCase[]; total: number }>(
      `/cases?${searchParams.toString()}`
    );
  }

  async getCaseAudit(caseId: string): Promise<{ items: BackendAuditEvent[] }> {
    try {
      const res = await this.request<any>(`/cases/${caseId}/audit`);
      const rawEvents = Array.isArray(res) ? res : res?.items || [];
      const items: BackendAuditEvent[] = rawEvents.map((e: any) => ({
        id: e.id,
        case_id: e.case_id,
        actor_id: e.actor_id,
        actor_type: e.actor_type || "system",
        action: e.action || "",
        old_state: e.old_state,
        new_state: e.new_state,
        metadata_json: e.metadata_json || {},
        created_at: e.created_at || new Date().toISOString(),
      }));
      return { items };
    } catch {
      return { items: [] };
    }
  }

  // ===========================================================================
  // Documents & OCR API
  // ===========================================================================

  async uploadDocument(
    caseId: string,
    file: File,
    documentType: string = "deed"
  ): Promise<BackendDocument> {
    const formData = new FormData();
    formData.append("file", file);

    const doc = await this.request<any>(`/cases/${caseId}/documents`, {
      method: "POST",
      body: formData,
    });
    return {
      id: doc.id,
      case_id: doc.case_id,
      filename: doc.original_filename || doc.filename || file.name,
      original_filename: doc.original_filename || doc.filename || file.name,
      file_size_bytes: doc.file_size || doc.file_size_bytes || file.size,
      file_size: doc.file_size || doc.file_size_bytes || file.size,
      file_extension: doc.file_extension,
      mime_type: doc.mime_type || file.type || "application/pdf",
      document_type: documentType,
      status: doc.status || "uploaded",
      page_count: doc.page_count || 1,
      uploaded_by: doc.uploaded_by,
      created_at: doc.created_at || new Date().toISOString(),
      updated_at: doc.updated_at,
      processed_at: doc.processed_at,
    };
  }

  async getCaseDocuments(
    caseId: string
  ): Promise<{ items: BackendDocument[]; documents: BackendDocument[]; total: number }> {
    try {
      const res = await this.request<any>(`/cases/${caseId}/documents`);
      const rawDocs =
        res?.documents || res?.items || (Array.isArray(res) ? res : []);
      const normalized: BackendDocument[] = rawDocs.map((d: any) => ({
        id: d.id,
        case_id: d.case_id,
        filename: d.original_filename || d.filename || "Document",
        original_filename: d.original_filename || d.filename || "Document",
        file_size_bytes: d.file_size || d.file_size_bytes || 0,
        file_size: d.file_size || d.file_size_bytes || 0,
        file_extension: d.file_extension,
        mime_type: d.mime_type || "application/pdf",
        document_type: d.document_type || "deed",
        status: d.status || "uploaded",
        page_count: d.page_count || 1,
        uploaded_by: d.uploaded_by,
        created_at: d.created_at || new Date().toISOString(),
        updated_at: d.updated_at,
        processed_at: d.processed_at,
      }));
      return {
        items: normalized,
        documents: normalized,
        total: normalized.length,
      };
    } catch {
      return { items: [], documents: [], total: 0 };
    }
  }

  async processDocument(
    docId: string
  ): Promise<{ document_id: string; job_id: string; processing_status: string }> {
    return await this.request<{
      document_id: string;
      job_id: string;
      processing_status: string;
    }>(`/documents/${docId}/process`, {
      method: "POST",
    });
  }

  async extractDocument(
    docId: string
  ): Promise<{ document_id: string; job_id: string; status: string }> {
    return await this.request<{
      document_id: string;
      job_id: string;
      status: string;
    }>(`/documents/${docId}/extract`, {
      method: "POST",
    });
  }

  async getDocumentOcr(
    docId: string
  ): Promise<{ pages: BackendOCRPage[]; full_text: string }> {
    try {
      const res = await this.request<any>(`/documents/${docId}/ocr`);
      const rawPages = res?.pages || (Array.isArray(res) ? res : []);
      const pages: BackendOCRPage[] = rawPages.map((p: any) => ({
        id: p.id || `page-${p.page_number}`,
        document_id: p.document_id || docId,
        page_number: p.page_number,
        text: p.text || "",
        model_name: p.model_name || "deepseek-ocr",
        processing_time_ms: p.processing_time_ms || 0,
        created_at: p.created_at || new Date().toISOString(),
      }));
      const full_text =
        res?.full_text ||
        pages.map((p) => `--- PAGE ${p.page_number} ---\n${p.text}`).join("\n\n");
      return { pages, full_text };
    } catch {
      return { pages: [], full_text: "" };
    }
  }

  async getDocumentProcessingStatus(
    docId: string
  ): Promise<{
    document_id: string;
    document_status: string;
    processing?: {
      job_id: string;
      status: string;
      attempts: number;
      error_code?: string;
      error_message?: string;
    };
  }> {
    return await this.request(`/documents/${docId}/processing`);
  }

  async getDocumentExtraction(
    docId: string
  ): Promise<{ fields: BackendExtractedField[]; document_id?: string; status?: string }> {
    try {
      const res = await this.request<any>(`/documents/${docId}/extraction`);
      const rawFields = res?.fields || (Array.isArray(res) ? res : []);
      const normalizedFields: BackendExtractedField[] = rawFields.map((f: any) => ({
        id: f.id,
        document_id: f.document_id || docId,
        field_name: f.field_name,
        field_value: f.field_value,
        normalized_value: f.normalized_value,
        confidence: typeof f.confidence === "number" ? f.confidence : 0.85,
        status: f.status || "extracted",
        evidence_text: f.evidence_text || (f.evidence && f.evidence[0]?.source_text),
        page_number: f.page_number || (f.evidence && f.evidence[0]?.page_number) || 1,
        bbox: f.bbox || (f.evidence && f.evidence[0]?.bounding_box),
      }));
      return {
        document_id: res?.document_id || docId,
        status: res?.status || "completed",
        fields: normalizedFields,
      };
    } catch {
      return { fields: [] };
    }
  }

  // ===========================================================================
  // Validation, Map & Risk API
  // ===========================================================================

  async getPropertyProfile(caseId: string): Promise<any> {
    try {
      return await this.request<any>(`/cases/${caseId}/property-profile`);
    } catch {
      return null;
    }
  }

  async getCaseValidationRuns(
    caseId: string
  ): Promise<{ runs: BackendValidationRun[] }> {
    try {
      let res: any;
      try {
        res = await this.request<any>(`/cases/${caseId}/property-profile/validation-runs`);
      } catch {
        res = await this.request<any>(`/cases/${caseId}/validation-runs`);
      }
      const rawRuns = Array.isArray(res) ? res : res?.runs || [];
      const runs: BackendValidationRun[] = await Promise.all(
        rawRuns.map(async (r: any) => {
          let results = r.results;
          if (!results && r.id) {
            try {
              const resList = await this.request<any[]>(`/validation-runs/${r.id}/results`);
              if (Array.isArray(resList)) {
                results = resList.map((item: any) => ({
                  id: item.id,
                  field_name: item.field_name,
                  submitted_value: item.document_value,
                  reference_value: item.reference_value,
                  match_status: item.match_status,
                  match_score: item.match_score,
                  notes: item.mismatch_reason,
                }));
              }
            } catch {}
          }
          return {
            id: r.id,
            property_profile_id: r.property_profile_id,
            validation_type: r.validation_type,
            status: r.status,
            overall_score: r.overall_score || 0,
            executed_rules: r.executed_rules || [],
            created_at: r.created_at,
            results: results || [],
          };
        })
      );
      return { runs };
    } catch {
      return { runs: [] };
    }
  }

  async getCaseMapData(caseId: string): Promise<BackendMapData | null> {
    try {
      try {
        return await this.request<BackendMapData>(`/cases/${caseId}/property-profile/map`);
      } catch {
        return await this.request<BackendMapData>(`/cases/${caseId}/map-data`);
      }
    } catch {
      return null;
    }
  }

  async getCaseRiskAssessment(
    caseId: string
  ): Promise<BackendRiskAssessment | null> {
    try {
      try {
        return await this.request<BackendRiskAssessment>(
          `/cases/${caseId}/risk-assessment/current`
        );
      } catch {
        return await this.request<BackendRiskAssessment>(
          `/cases/${caseId}/risk-assessment`
        );
      }
    } catch {
      return null;
    }
  }

  // ===========================================================================
  // Area Officer Dedicated Jurisdiction API
  // ===========================================================================

  async getOfficerAreas(): Promise<{ areas: AreaResponse[] }> {
    return await this.request<{ areas: AreaResponse[] }>("/officer/areas");
  }

  async getOfficerDashboard(): Promise<any> {
    return await this.request<any>("/officer/dashboard");
  }

  async getOfficerReviewQueue(params?: {
    risk_level?: string;
    case_status?: string;
    review_status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: ReviewQueueItem[]; total: number }> {
    const searchParams = new URLSearchParams();
    if (params?.risk_level && params.risk_level !== "ALL")
      searchParams.set("risk_level", params.risk_level.toLowerCase());
    if (params?.case_status) searchParams.set("case_status", params.case_status);
    if (params?.review_status)
      searchParams.set("review_status", params.review_status);
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.offset) searchParams.set("offset", params.offset.toString());

    return await this.request<{ items: ReviewQueueItem[]; total: number }>(
      `/officer/reviews/queue?${searchParams.toString()}`
    );
  }

  async getCaseReviewContext(caseId: string): Promise<ReviewDetailResponse> {
    return await this.request<ReviewDetailResponse>(`/cases/${caseId}/review`);
  }

  async startReview(
    caseId: string
  ): Promise<{ review: CaseReviewResponse; message: string }> {
    return await this.request<{ review: CaseReviewResponse; message: string }>(
      `/cases/${caseId}/review/start`,
      {
        method: "POST",
      }
    );
  }

  async submitReviewDecision(
    caseId: string,
    decision: OfficerDecision,
    reason: string
  ): Promise<{ review: CaseReviewResponse; case_status: string; message: string }> {
    return await this.request<{
      review: CaseReviewResponse;
      case_status: string;
      message: string;
    }>(`/cases/${caseId}/review/decision`, {
      method: "POST",
      body: JSON.stringify({
        decision: decision.toLowerCase(),
        reason,
      }),
    });
  }

  async getCaseReviewHistory(caseId: string): Promise<any[]> {
    try {
      return await this.request<any[]>(`/cases/${caseId}/review/history`);
    } catch {
      return [];
    }
  }

  // ===========================================================================
  // Proof Request & Civilian Response API
  // ===========================================================================

  async createProofRequest(
    caseId: string,
    data: {
      title: string;
      description: string;
      proof_type: string;
      requested_from?: string;
    }
  ): Promise<BackendProofRequest> {
    return await this.request<BackendProofRequest>(
      `/cases/${caseId}/proof-requests`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    );
  }

  async listProofRequests(
    caseId: string
  ): Promise<BackendProofRequest[]> {
    try {
      return await this.request<BackendProofRequest[]>(
        `/cases/${caseId}/proof-requests`
      );
    } catch {
      return [];
    }
  }

  async submitProof(
    requestId: string,
    file: File,
    comment?: string
  ): Promise<any> {
    const formData = new FormData();
    formData.append("file", file);
    if (comment) formData.append("comment", comment);

    return await this.request(`/proof-requests/${requestId}/submissions`, {
      method: "POST",
      body: formData,
    });
  }

  async acceptProofRequest(proofRequestId: string): Promise<BackendProofRequest> {
    return await this.request<BackendProofRequest>(
      `/proof-requests/${proofRequestId}/accept`,
      {
        method: "POST",
      }
    );
  }

  async rejectProofRequest(
    proofRequestId: string,
    reason: string
  ): Promise<BackendProofRequest> {
    return await this.request<BackendProofRequest>(
      `/proof-requests/${proofRequestId}/reject`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      }
    );
  }

  // ===========================================================================
  // Super Admin: Area Officer CRUD & Assignment API
  // ===========================================================================

  async listAdminOfficers(params?: {
    page?: number;
    page_size?: number;
    is_active?: boolean;
    search?: string;
  }): Promise<{ items: any[]; total: number }> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set("page", params.page.toString());
    if (params?.page_size)
      searchParams.set("page_size", params.page_size.toString());
    if (params?.is_active !== undefined)
      searchParams.set("is_active", params.is_active.toString());
    if (params?.search) searchParams.set("search", params.search);

    return await this.request<{ items: any[]; total: number }>(
      `/admin/officers?${searchParams.toString()}`
    );
  }

  async createAdminOfficer(data: {
    full_name: string;
    email: string;
    password: string;
    phone?: string;
  }): Promise<UserProfile> {
    return await this.request<UserProfile>("/admin/officers", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateAdminOfficer(
    officerId: string,
    data: {
      full_name?: string;
      phone?: string;
      is_active?: boolean;
    }
  ): Promise<UserProfile> {
    return await this.request<UserProfile>(`/admin/officers/${officerId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async assignOfficerArea(
    officerId: string,
    areaId: string
  ): Promise<any> {
    return await this.request(
      `/admin/officers/${officerId}/areas/${areaId}`,
      {
        method: "POST",
      }
    );
  }

  async removeOfficerArea(
    officerId: string,
    areaId: string
  ): Promise<any> {
    return await this.request(
      `/admin/officers/${officerId}/areas/${areaId}`,
      {
        method: "DELETE",
      }
    );
  }

  async demoteAdminOfficer(officerId: string): Promise<any> {
    return await this.request(`/admin/officers/${officerId}/demote`, {
      method: "POST",
    });
  }
}

export const api = new ApiClient();

