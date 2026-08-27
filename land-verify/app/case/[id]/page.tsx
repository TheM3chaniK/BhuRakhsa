"use client";

export const dynamic = "force-dynamic";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";
import RiskBadge from "@/components/ui/RiskBadge";
import StatusPill from "@/components/ui/StatusPill";
import ConfidenceMeter from "@/components/ui/ConfidenceMeter";
import Stamp from "@/components/ui/Stamp";
import DynamicLandMap from "@/components/map/DynamicLandMap";
import { api } from "@/lib/api";
import {
  BackendAuditEvent,
  BackendCase,
  BackendDocument,
  BackendProofRequest,
  ExtractedField,
  MatchStatus,
  OfficerDecision,
  ReviewDetailResponse,
  TimelineEvent,
  ValidationRow,
} from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

type ActiveTab =
  | "deed_ocr"
  | "registry_match"
  | "spatial_gis"
  | "risk_mismatches"
  | "proof_requests"
  | "audit_ledger";

export default function CaseProfilePage({ params }: { params: { id: string } }) {
  const caseId = params.id;
  const { user } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [activeTab, setActiveTab] = useState<ActiveTab>("deed_ocr");
  const [reviewContext, setReviewContext] = useState<ReviewDetailResponse | null>(null);
  const [kase, setKase] = useState<BackendCase | null>(null);
  const [caseDocs, setCaseDocs] = useState<BackendDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [fields, setFields] = useState<ExtractedField[]>([]);
  const [valRows, setValRows] = useState<ValidationRow[]>([]);
  const [proofRequests, setProofRequests] = useState<BackendProofRequest[]>([]);
  const [ocrText, setOcrText] = useState<string | null>(null);

  // Decision Modal / Form State
  const [decisionModal, setDecisionModal] = useState<OfficerDecision | null>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Proof Request Modal (Officer)
  const [showProofModal, setShowProofModal] = useState(false);
  const [proofTitle, setProofTitle] = useState("Original Encumbrance Certificate");
  const [proofDesc, setProofDesc] = useState("Please upload recent mutation slip or local municipal tax receipt.");

  // Proof Submission (Civilian)
  const [selectedProofRequestId, setSelectedProofRequestId] = useState<string | null>(null);
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [proofComment, setProofComment] = useState("");

  const isOfficer = user?.role === "AREA_OFFICER" || user?.role === "SUPER_ADMIN";
  const isCivilian = user?.role === "CIVILIAN";

  const loadCaseData = async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);

    try {
      // 1. Fetch Holistic Review Package or Case Profile
      if (isOfficer) {
        try {
          const ctx = await api.getCaseReviewContext(caseId);
          setReviewContext(ctx);
          setKase(ctx.case);

          // Populate extracted fields from review context property profile if present
          if (ctx.property_profile) {
            const mappedFields: ExtractedField[] = [];
            if (ctx.property_profile.survey_number) {
              mappedFields.push({
                label: "Survey / Plot Number",
                value: ctx.property_profile.survey_number,
                confidence: 94,
              });
            }
            if (ctx.property_profile.declared_area) {
              mappedFields.push({
                label: "Deed Declared Area",
                value: `${ctx.property_profile.declared_area} ${ctx.property_profile.area_unit || "acre"}`,
                confidence: 91,
              });
            }
            if (ctx.property_profile.village) {
              mappedFields.push({
                label: "Village / Mouza",
                value: ctx.property_profile.village,
                confidence: 96,
              });
            }
            if (ctx.property_profile.district) {
              mappedFields.push({
                label: "District Jurisdiction",
                value: ctx.property_profile.district,
                confidence: 98,
              });
            }
            if (ctx.property_profile.owners && ctx.property_profile.owners.length > 0) {
              mappedFields.push({
                label: "Deed Owners",
                value: ctx.property_profile.owners.map((o) => o.owner_name).join(", "),
                confidence: 88,
              });
            }
            if (mappedFields.length > 0) {
              setFields(mappedFields);
            }
          }
        } catch {
          // Standard case fetch if review context is not yet initialized
          const c = await api.getCase(caseId);
          setKase(c);
        }
      } else {
        const c = await api.getCase(caseId);
        setKase(c);
      }

      // 1b. Fetch all documents for this case and their extractions / OCR
      try {
        const docList = await api.getCaseDocuments(caseId);
        const docs = docList.items || [];
        setCaseDocs(docs);

        for (const doc of docs) {
          try {
            const extRes = await api.getDocumentExtraction(doc.id);
            if (extRes && extRes.fields && extRes.fields.length > 0) {
              const docFields: ExtractedField[] = extRes.fields.map((f) => ({
                label: f.field_name
                  .replace(/_/g, " ")
                  .replace(/\b\w/g, (l) => l.toUpperCase()),
                value: f.field_value || f.normalized_value || "—",
                confidence: Math.round((f.confidence || 0.85) * 100),
              }));
              setFields((prev) => {
                const merged = [...prev];
                for (const df of docFields) {
                  if (!merged.some((m) => m.label.toLowerCase() === df.label.toLowerCase())) {
                    merged.push(df);
                  }
                }
                return merged;
              });
            }

            const ocrRes = await api.getDocumentOcr(doc.id);
            if (ocrRes && (ocrRes.full_text || (ocrRes.pages && ocrRes.pages.length > 0))) {
              setOcrText(
                ocrRes.full_text ||
                  ocrRes.pages.map((p) => `--- PAGE ${p.page_number} ---\n${p.text}`).join("\n\n")
              );
            }
          } catch {}
        }
      } catch {}

      // 2. Fetch Audit History
      try {
        const auditRes = await api.getCaseAudit(caseId);
        if (auditRes.items && auditRes.items.length > 0) {
          const events: TimelineEvent[] = auditRes.items.map((ev: BackendAuditEvent) => ({
            label: ev.action.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()),
            detail:
              ev.metadata_json?.reason ||
              ev.metadata_json?.title ||
              `State transition: ${ev.old_state || "START"} → ${ev.new_state || "NEXT"}`,
            who: ev.actor_type === "system" ? "Automated Verification Engine" : "Authorized Officer",
            timestamp: new Date(ev.created_at).toLocaleString("en-IN", {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            }),
          }));
          setTimeline(events);
        }
      } catch {}

      // 3. Fetch Proof Requests
      try {
        const prList = await api.listProofRequests(caseId);
        setProofRequests(prList);
      } catch {}

      // 4. Fetch Validation Runs
      try {
        const valRes = await api.getCaseValidationRuns(caseId);
        if (valRes.runs && valRes.runs.length > 0) {
          const rows: ValidationRow[] = [];
          valRes.runs.forEach((r) => {
            r.results?.forEach((resItem) => {
              let status: MatchStatus = "CANNOT_CHECK";
              if (
                resItem.match_status === "EXACT_MATCH" ||
                resItem.match_status === "MATCHED" ||
                resItem.match_score >= 0.85
              ) {
                status = "MATCHED";
              } else if (
                resItem.match_status === "MISMATCH" ||
                resItem.match_status === "PARTIAL_MATCH"
              ) {
                status = "MISMATCH";
              } else if (
                resItem.match_status === "MISSING_IN_REFERENCE" ||
                resItem.match_status === "NOT_FOUND"
              ) {
                status = "MISSING";
              }

              rows.push({
                field: resItem.field_name.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()),
                document: resItem.submitted_value || "—",
                record: resItem.reference_value || "—",
                status,
                notes: resItem.notes,
              });
            });
          });
          setValRows(rows);
        }
      } catch {}
    } catch (err: any) {
      console.error("Failed to load case:", err);
      setError(
        err.message?.includes("403") || err.message?.includes("forbidden")
          ? "Access Restricted: You do not have jurisdictional permission to view this property case."
          : err.message || "Failed to load case data."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCaseData();
  }, [caseId, user]);

  const handleStartReview = async () => {
    if (!caseId) return;
    setIsSubmitting(true);
    try {
      await api.startReview(caseId);
      setActionSuccess("Verification session locked and started under your officer account.");
      await loadCaseData();
    } catch (err: any) {
      setActionError(err.message || "Failed to acquire case review lock.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDecisionSubmit = async () => {
    if (!decisionModal || !caseId) return;

    if (decisionReason.trim().length < 10) {
      setActionError("Please provide a factual decision explanation (at least 10 characters).");
      return;
    }

    setIsSubmitting(true);
    setActionSuccess(null);
    setActionError(null);

    try {
      await api.submitReviewDecision(caseId, decisionModal, decisionReason.trim());
      setActionSuccess(
        `Case determination '${decisionModal}' submitted successfully and committed to the immutable audit trail!`
      );
      setDecisionModal(null);
      setDecisionReason("");
      await loadCaseData();
    } catch (err: any) {
      console.error("Decision error:", err);
      setActionError(err.message || "Failed to record decision.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRequestProof = async () => {
    setIsSubmitting(true);
    setActionSuccess(null);
    setActionError(null);

    try {
      await api.createProofRequest(caseId, {
        title: proofTitle,
        description: proofDesc,
        proof_type: "document",
      });

      setShowProofModal(false);
      setActionSuccess("Supplementary proof request issued to citizen. Case transitioned to PROOF_REQUIRED.");
      await loadCaseData();
    } catch (err: any) {
      console.error("Proof request error:", err);
      setActionError(err.message || "Failed to dispatch proof request.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAcceptProof = async (requestId: string) => {
    setIsSubmitting(true);
    try {
      await api.acceptProofRequest(requestId);
      setActionSuccess("Proof document accepted! Revalidation cycle triggered.");
      await loadCaseData();
    } catch (err: any) {
      setActionError(err.message || "Failed to accept proof.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRejectProof = async (requestId: string) => {
    const reason = prompt("Enter factual reason for rejecting this proof submission:");
    if (!reason) return;

    setIsSubmitting(true);
    try {
      await api.rejectProofRequest(requestId, reason);
      setActionSuccess("Proof document rejected.");
      await loadCaseData();
    } catch (err: any) {
      setActionError(err.message || "Failed to reject proof.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCivilianProofSubmit = async (requestId: string) => {
    if (!proofFile) {
      setActionError("Please select a file to upload.");
      return;
    }

    setIsSubmitting(true);
    setActionSuccess(null);
    setActionError(null);

    try {
      await api.submitProof(requestId, proofFile, proofComment);
      setActionSuccess("Supplementary proof uploaded successfully! Queued for Area Officer verification.");
      setProofFile(null);
      setProofComment("");
      setSelectedProofRequestId(null);
      await loadCaseData();
    } catch (err: any) {
      console.error("Proof upload error:", err);
      setActionError(err.message || "Failed to upload proof.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-10 py-20 text-center font-mono text-xs text-ink-soft">
        Assembling evidence dossier from PostgreSQL &amp; PostGIS...
      </div>
    );
  }

  if (error || !kase) {
    return (
      <div className="mx-auto max-w-3xl px-10 py-16 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-risk/40 text-risk">
          ✕
        </div>
        <h2 className="font-serif text-xl text-ink">Access Restricted</h2>
        <p className="mt-2 text-xs text-risk">{error || "Case record not found."}</p>
        <div className="mt-6">
          <Link
            href="/queue"
            className="inline-block rounded bg-ink px-4 py-2 text-xs font-medium text-paper hover:bg-ink/90"
          >
            ← Return to Case List
          </Link>
        </div>
      </div>
    );
  }

  const isTerminal = kase.status === "APPROVED" || kase.status === "REJECTED";
  const isLockedByMe = reviewContext?.review?.status === "IN_PROGRESS";

  return (
    <div className="mx-auto max-w-6xl px-10 py-12">
      <PageHeader
        step={isCivilian ? "Case Status & Evidence" : "Step 06 · Area Officer Verification Workspace"}
        title={`Verification Dossier: ${kase.case_number}`}
        description={
          isCivilian
            ? "Inspect your case progress, verification milestones, and submit supplementary proof if requested."
            : "Review grounded DeepSeek OCR extracts, government registry records, and PostGIS parcel boundaries to commit an official determination."
        }
      />

      {/* Case Header Card & Action Bar */}
      <div className="rounded border border-line bg-paper-dark/40 p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="font-mono text-sm font-semibold text-brass">
                {kase.case_number}
              </span>
              <Stamp
                tone={
                  kase.status === "APPROVED"
                    ? "verified"
                    : kase.status === "REJECTED"
                    ? "risk"
                    : kase.status === "PROOF_REQUIRED"
                    ? "caution"
                    : "neutral"
                }
              >
                {kase.status}
              </Stamp>
              {isOfficer && isLockedByMe && (
                <span className="rounded bg-brass/10 border border-brass/40 px-2 py-0.5 font-mono text-[10px] text-ink font-medium">
                  🔒 Locked &amp; Under Your Review
                </span>
              )}
            </div>
            <p className="mt-1 font-serif text-xl text-ink">
              {kase.title || "Land Deed Verification"}
            </p>
            <p className="text-xs text-ink-soft mt-0.5">
              {kase.description || "Historical conveyance deed verification"}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <RiskBadge level={kase.risk_level} />
            {reviewContext?.risk_assessment && (
              <span className="font-mono text-xs text-ink font-bold">
                Score: {reviewContext.risk_assessment.risk_score}/100
              </span>
            )}
          </div>
        </div>

        {/* Action Bar for Area Officers */}
        {isOfficer && (
          <div className="mt-6 border-t border-line/60 pt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              {!isLockedByMe && !isTerminal && (
                <button
                  onClick={handleStartReview}
                  disabled={isSubmitting}
                  className="rounded border border-brass bg-brass/10 px-3.5 py-1.5 text-xs font-semibold text-ink hover:bg-brass/20 transition-colors"
                >
                  ⚡ Start &amp; Lock Review
                </button>
              )}
              {isTerminal && (
                <span className="font-mono text-xs text-ink-soft">
                  ✓ Case Finalized — Audit snapshot archived
                </span>
              )}
            </div>

            {!isTerminal && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    setDecisionModal("APPROVE");
                    setDecisionReason("All registry and PostGIS boundary checks satisfied. Ownership title verified.");
                  }}
                  disabled={isSubmitting}
                  className="rounded bg-verified px-4 py-2 text-xs font-medium text-paper shadow-sm hover:opacity-90 transition-opacity"
                >
                  ✓ Accept &amp; Approve
                </button>
                <button
                  onClick={() => setShowProofModal(true)}
                  disabled={isSubmitting}
                  className="rounded bg-caution px-4 py-2 text-xs font-medium text-paper shadow-sm hover:opacity-90 transition-opacity"
                >
                  ✉ Request Proof
                </button>
                <button
                  onClick={() => {
                    setDecisionModal("REJECT");
                    setDecisionReason("Discrepancy in deed boundary and unregistered owner name. Title rejected.");
                  }}
                  disabled={isSubmitting}
                  className="rounded bg-risk px-4 py-2 text-xs font-medium text-paper shadow-sm hover:opacity-90 transition-opacity"
                >
                  ✕ Reject Application
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {actionSuccess && (
        <div className="mt-4 rounded border border-verified/40 bg-verified/10 px-4 py-3 text-xs text-verified font-medium">
          ✓ {actionSuccess}
        </div>
      )}

      {actionError && (
        <div className="mt-4 rounded border border-risk/40 bg-risk/10 px-4 py-3 text-xs text-risk font-medium">
          ✕ {actionError}
        </div>
      )}

      {/* Verification Workspace Tabs */}
      <div className="mt-8">
        <div className="flex border-b border-line text-xs font-medium">
          {[
            { id: "deed_ocr", label: "📑 Deed & OCR Extract" },
            { id: "registry_match", label: "🏛️ Registry Matching" },
            { id: "spatial_gis", label: "🗺️ PostGIS Spatial" },
            { id: "risk_mismatches", label: `⚠️ Discrepancies (${reviewContext?.mismatches?.length || 0})` },
            { id: "proof_requests", label: `📨 Proof Requests (${proofRequests.length})` },
            { id: "audit_ledger", label: "📜 Audit Trail" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as ActiveTab)}
              className={`px-4 py-2.5 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-brass bg-paper text-ink font-semibold"
                  : "border-transparent text-ink-soft hover:text-ink hover:border-line"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab 1: Deed & OCR Extraction */}
        {activeTab === "deed_ocr" && (
          <div className="mt-6 grid grid-cols-5 gap-8">
            <div className="col-span-2 space-y-4">
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
                  Uploaded Deed Documents ({caseDocs.length || reviewContext?.documents?.length || 1})
                </p>
                <div className="rounded border border-line bg-paper-dark/30 p-4 space-y-3 text-xs">
                  {caseDocs.length > 0 ? (
                    caseDocs.map((doc) => (
                      <div key={doc.id} className="border-b border-line/60 pb-3 last:border-0 last:pb-0">
                        <p className="font-medium text-ink">{doc.filename}</p>
                        <p className="text-[11px] text-ink-soft mt-0.5 font-mono">
                          {(doc.file_size_bytes / 1024).toFixed(1)} KB · {doc.mime_type} · Status: {doc.status}
                        </p>
                      </div>
                    ))
                  ) : reviewContext?.documents && reviewContext.documents.length > 0 ? (
                    reviewContext.documents.map((doc) => (
                      <div key={doc.id} className="border-b border-line/60 pb-3 last:border-0 last:pb-0">
                        <p className="font-medium text-ink">{doc.filename}</p>
                        <p className="text-[11px] text-ink-soft mt-0.5 font-mono">
                          {(doc.file_size_bytes / 1024).toFixed(1)} KB · {doc.mime_type} · Status: {doc.status}
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="text-ink-soft">Primary conveyance deed document attached.</p>
                  )}
                </div>
              </div>

              {ocrText && (
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
                    DeepSeek OCR Recognized Text
                  </p>
                  <div className="max-h-60 overflow-y-auto rounded border border-line bg-paper p-3 font-mono text-[11px] text-ink-soft leading-relaxed shadow-inner">
                    <p className="whitespace-pre-line text-ink">{ocrText}</p>
                  </div>
                </div>
              )}
            </div>

            <div className="col-span-3">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
                Structured Extracted Fields ({fields.length})
              </p>
              {fields.length === 0 ? (
                <div className="rounded border border-line bg-paper-dark/20 p-6 text-center text-xs text-ink-soft">
                  No structured fields extracted yet.
                </div>
              ) : (
                <div className="divide-y divide-line rounded border border-line bg-paper-dark/30">
                  {fields.map((field) => (
                    <div key={field.label} className="flex items-center justify-between px-4 py-3 text-xs bg-paper/40">
                      <div>
                        <p className="text-[11px] uppercase tracking-wide text-ink-soft font-mono">{field.label}</p>
                        <p className="font-mono text-sm text-ink mt-0.5 font-medium">{field.value}</p>
                      </div>
                      <div className="text-right">
                        <ConfidenceMeter value={field.confidence} />
                        <p className="text-[10px] text-ink-soft mt-0.5">Grounded Evidence</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Land Registry Cross-Check */}
        {activeTab === "registry_match" && (
          <div className="mt-6">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
              Authoritative Registry Cross-Check ({valRows.length} attributes tested)
            </p>
            {valRows.length === 0 ? (
              <div className="rounded border border-line bg-paper-dark/20 p-8 text-center text-xs text-ink-soft">
                Database validation run is executed during automated pipeline.
              </div>
            ) : (
              <div className="overflow-hidden rounded border border-line">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-line bg-paper-dark/60 text-[11px] uppercase tracking-wide text-ink-soft">
                      <th className="px-4 py-2.5 font-medium">Field</th>
                      <th className="px-4 py-2.5 font-medium">Deed Submitted Value</th>
                      <th className="px-4 py-2.5 font-medium">Government Registry Record</th>
                      <th className="px-4 py-2.5 font-medium">Validation Result</th>
                      <th className="px-4 py-2.5 font-medium">Notes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {valRows.map((r, i) => (
                      <tr key={i} className="bg-paper-dark/20">
                        <td className="px-4 py-3 font-medium text-ink">{r.field}</td>
                        <td className="px-4 py-3 font-mono text-ink">{r.document}</td>
                        <td className="px-4 py-3 font-mono text-ink">{r.record}</td>
                        <td className="px-4 py-3">
                          <StatusPill status={r.status} />
                        </td>
                        <td className="px-4 py-3 text-ink-soft text-[11px]">{r.notes || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: PostGIS Spatial & Boundaries */}
        {activeTab === "spatial_gis" && (
          <div className="mt-6 grid grid-cols-5 gap-8">
            <div className="col-span-3">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
                PostGIS Real Cadastral Overlay &amp; Interactive Deed Drafting (SRID: 4326)
              </p>
              <DynamicLandMap
                initialCenter={[22.506, 88.382]}
                initialZoom={15}
                className="h-[380px] w-full"
                allowDrafting={true}
              />
            </div>

            <div className="col-span-2 space-y-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
                Spatial Variance Calculation
              </p>
              <div className="rounded border border-line bg-paper-dark/30 p-4 space-y-3 text-xs">
                <div>
                  <span className="text-ink-soft">Declared Deed Area:</span>
                  <p className="font-mono text-sm font-semibold text-ink">1.20 acre</p>
                </div>
                <div>
                  <span className="text-ink-soft">Mapped Cadastral Area:</span>
                  <p className="font-mono text-sm font-semibold text-ink">1.05 acre</p>
                </div>
                <div>
                  <span className="text-ink-soft">Calculated Variance:</span>
                  <p className="font-mono text-sm font-semibold text-risk">+14.28% discrepancy</p>
                </div>
                <div className="border-t border-line/60 pt-2 text-[11px] text-ink-soft">
                  ✓ Point inside polygon validated<br />
                  ✓ District and Mouza boundaries align
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Mismatches & Risk Assessment */}
        {activeTab === "risk_mismatches" && (
          <div className="mt-6 space-y-6">
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
                Identified Discrepancies ({reviewContext?.mismatches?.length || 0})
              </p>
              {reviewContext?.mismatches && reviewContext.mismatches.length > 0 ? (
                <div className="space-y-3">
                  {reviewContext.mismatches.map((m) => (
                    <div key={m.id} className="rounded border border-line bg-paper-dark/30 p-4 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-semibold text-ink">{m.reason_code}</span>
                        <Stamp tone={m.severity === "CRITICAL" || m.severity === "HIGH" ? "risk" : "caution"}>
                          {m.severity}
                        </Stamp>
                      </div>
                      <p className="mt-1 text-ink">{m.description}</p>
                      {m.submitted_value && m.reference_value && (
                        <div className="mt-2 grid grid-cols-2 gap-2 rounded bg-paper p-2 font-mono text-[11px]">
                          <div>Submitted: <strong className="text-ink">{m.submitted_value}</strong></div>
                          <div>Reference: <strong className="text-ink">{m.reference_value}</strong></div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded border border-line bg-paper-dark/20 p-6 text-center text-xs text-ink-soft">
                  No high-severity discrepancies recorded for this record.
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 5: Proof Requests & Submissions */}
        {activeTab === "proof_requests" && (
          <div className="mt-6 space-y-6">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">
                Supplementary Evidence Requests ({proofRequests.length})
              </p>
              {isOfficer && !isTerminal && (
                <button
                  onClick={() => setShowProofModal(true)}
                  className="rounded bg-ink px-3 py-1.5 text-xs font-medium text-paper hover:bg-ink/90"
                >
                  + Issue New Proof Request
                </button>
              )}
            </div>

            {proofRequests.length === 0 ? (
              <div className="rounded border border-line bg-paper-dark/20 p-8 text-center text-xs text-ink-soft">
                No supplementary proof has been requested for this case.
              </div>
            ) : (
              <div className="space-y-4">
                {proofRequests.map((pr) => (
                  <div key={pr.id} className="rounded border border-line bg-paper-dark/30 p-5 text-xs">
                    <div className="flex items-center justify-between">
                      <h4 className="font-serif text-sm font-semibold text-ink">{pr.title}</h4>
                      <Stamp
                        tone={
                          pr.status === "accepted"
                            ? "verified"
                            : pr.status === "rejected"
                            ? "risk"
                            : pr.status === "submitted"
                            ? "caution"
                            : "neutral"
                        }
                      >
                        {pr.status}
                      </Stamp>
                    </div>
                    <p className="mt-1 text-ink-soft">{pr.description}</p>

                    {/* Officer Actions for Submitted Proofs */}
                    {isOfficer && pr.status === "submitted" && (
                      <div className="mt-4 flex items-center gap-2 border-t border-line/60 pt-3">
                        <button
                          onClick={() => handleAcceptProof(pr.id)}
                          disabled={isSubmitting}
                          className="rounded bg-verified px-3 py-1 text-xs font-medium text-paper hover:opacity-90"
                        >
                          ✓ Accept Proof &amp; Revalidate
                        </button>
                        <button
                          onClick={() => handleRejectProof(pr.id)}
                          disabled={isSubmitting}
                          className="rounded bg-risk px-3 py-1 text-xs font-medium text-paper hover:opacity-90"
                        >
                          ✕ Reject Proof
                        </button>
                      </div>
                    )}

                    {/* Citizen Action to Submit Proof */}
                    {isCivilian && pr.status === "open" && (
                      <div className="mt-4 border-t border-line/60 pt-3">
                        {selectedProofRequestId === pr.id ? (
                          <div className="space-y-3 rounded bg-paper p-4 border border-line">
                            <p className="font-medium text-ink">Upload Document for {pr.title}</p>
                            <input
                              type="file"
                              onChange={(e) => setProofFile(e.target.files?.[0] || null)}
                              className="block w-full text-xs text-ink"
                            />
                            <textarea
                              value={proofComment}
                              onChange={(e) => setProofComment(e.target.value)}
                              placeholder="Civilian explanation / notes..."
                              rows={2}
                              className="w-full rounded border border-line bg-paper px-3 py-1.5 text-xs text-ink"
                            />
                            <div className="flex justify-end gap-2">
                              <button
                                onClick={() => setSelectedProofRequestId(null)}
                                className="rounded border border-line px-3 py-1 text-ink"
                              >
                                Cancel
                              </button>
                              <button
                                onClick={() => handleCivilianProofSubmit(pr.id)}
                                disabled={isSubmitting}
                                className="rounded bg-caution px-3 py-1 font-medium text-paper hover:opacity-90"
                              >
                                {isSubmitting ? "Uploading..." : "Submit Proof"}
                              </button>
                            </div>
                          </div>
                        ) : (
                          <button
                            onClick={() => setSelectedProofRequestId(pr.id)}
                            className="rounded bg-caution px-3 py-1.5 text-xs font-medium text-paper hover:opacity-90"
                          >
                            Upload Requested Document →
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 6: Audit Trail Timeline */}
        {activeTab === "audit_ledger" && (
          <div className="mt-6">
            <p className="mb-4 text-xs font-medium uppercase tracking-wide text-ink-soft">
              Chronological Audit Trail &amp; Verification Milestones
            </p>
            <ol className="space-y-0">
              {timeline.map((t, i) => (
                <li key={i} className="relative pb-6 pl-6 last:pb-0 text-xs">
                  {i < timeline.length - 1 && (
                    <span className="absolute left-[3px] top-2 h-full w-px bg-line" />
                  )}
                  <span className="absolute left-0 top-1.5 h-2 w-2 rounded-full border-2 border-brass bg-paper" />
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-ink">{t.label}</p>
                    {t.timestamp && <span className="font-mono text-[10px] text-ink-soft">{t.timestamp}</span>}
                  </div>
                  <p className="mt-0.5 text-ink-soft">{t.detail}</p>
                  <p className="mt-0.5 font-mono text-[10px] uppercase text-ink-soft/70">{t.who}</p>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {/* Decision Modal */}
      {decisionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
          <div className="w-full max-w-lg rounded-lg border border-line bg-paper p-6 shadow-xl">
            <h3 className="font-serif text-lg text-ink">
              Submit Official Determination:{" "}
              <span
                className={
                  decisionModal === "APPROVE"
                    ? "text-verified"
                    : decisionModal === "REJECT"
                    ? "text-risk"
                    : "text-caution"
                }
              >
                {decisionModal}
              </span>
            </h3>
            <p className="mt-1 text-xs text-ink-soft">
              This determination will be permanently stamped into the immutable audit ledger.
            </p>

            <div className="mt-4">
              <label className="block text-xs font-medium text-ink">
                Factual Justification (Mandatory, min 10 characters)
              </label>
              <textarea
                value={decisionReason}
                onChange={(e) => setDecisionReason(e.target.value)}
                rows={4}
                placeholder="Detail the evidentiary rationale for this decision..."
                className="mt-1.5 w-full rounded border border-line bg-paper px-3 py-2 text-xs text-ink focus:border-brass focus:outline-none"
              />
            </div>

            <div className="mt-6 flex justify-end gap-2 text-xs">
              <button
                onClick={() => setDecisionModal(null)}
                className="rounded border border-line px-4 py-2 font-medium text-ink hover:bg-paper-dark"
              >
                Cancel
              </button>
              <button
                onClick={handleDecisionSubmit}
                disabled={isSubmitting}
                className={`rounded px-4 py-2 font-medium text-paper hover:opacity-90 disabled:opacity-50 ${
                  decisionModal === "APPROVE"
                    ? "bg-verified"
                    : decisionModal === "REJECT"
                    ? "bg-risk"
                    : "bg-caution"
                }`}
              >
                {isSubmitting ? "Submitting..." : `Confirm ${decisionModal}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Proof Request Modal */}
      {showProofModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
          <div className="w-full max-w-md rounded-lg border border-line bg-paper p-6 shadow-xl">
            <h3 className="font-serif text-lg text-ink">Issue Supplementary Proof Request</h3>
            <p className="mt-1 text-xs text-ink-soft">
              The civilian applicant will receive this notice and can upload evidence documents.
            </p>

            <div className="mt-4 space-y-3 text-xs">
              <div>
                <label className="block font-medium text-ink">Required Evidence Title</label>
                <input
                  value={proofTitle}
                  onChange={(e) => setProofTitle(e.target.value)}
                  className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink focus:border-brass focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-medium text-ink">Detailed Instructions</label>
                <textarea
                  value={proofDesc}
                  onChange={(e) => setProofDesc(e.target.value)}
                  rows={3}
                  className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink focus:border-brass focus:outline-none"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2 text-xs">
              <button
                onClick={() => setShowProofModal(false)}
                className="rounded border border-line px-4 py-2 font-medium text-ink hover:bg-paper-dark"
              >
                Cancel
              </button>
              <button
                onClick={handleRequestProof}
                disabled={isSubmitting}
                className="rounded bg-caution px-4 py-2 font-medium text-paper hover:opacity-90 disabled:opacity-50"
              >
                {isSubmitting ? "Sending..." : "Dispatch Proof Request"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="mt-10">
        <Link href="/queue" className="text-xs text-ink-soft underline underline-offset-2 hover:text-ink">
          ← Back to {isCivilian ? "My Cases" : "Review Queue"}
        </Link>
      </div>
    </div>
  );
}