"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import PageHeader from "@/components/ui/PageHeader";
import RiskBadge from "@/components/ui/RiskBadge";
import Stamp from "@/components/ui/Stamp";
import { api } from "@/lib/api";
import {
  AreaResponse,
  BackendCase,
  CaseStatus,
  CaseSummary,
  ReviewQueueItem,
  ReviewStatus,
  RiskLevel,
} from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

const riskOrder: Record<RiskLevel, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
  UNKNOWN: 4,
};

function QueueContent() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialStatus = searchParams.get("status") || "ALL";

  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [officerAreas, setOfficerAreas] = useState<AreaResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterRisk, setFilterRisk] = useState<string>("ALL");
  const [filterStatus, setFilterStatus] = useState<string>(initialStatus);

  // Quick Solve Modal
  const [quickSolveCaseId, setQuickSolveCaseId] = useState<string | null>(null);
  const [quickSolveReason, setQuickSolveReason] = useState(
    "Verified against authoritative land registry and PostGIS boundary parcel. Title confirmed and marked as solved."
  );
  const [isSolving, setIsSolving] = useState(false);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);

  const isOfficer = user?.role === "AREA_OFFICER";
  const isAdmin = user?.role === "SUPER_ADMIN";
  const isCivilian = user?.role === "CIVILIAN";

  useEffect(() => {
    if (searchParams.get("status")) {
      setFilterStatus(searchParams.get("status")!);
    }
  }, [searchParams]);

  const fetchCases = async () => {
    setLoading(true);
    setError(null);

    try {
      if (isOfficer) {
        // Fetch dedicated assigned areas
        try {
          const areaRes = await api.getOfficerAreas();
          if (areaRes.areas) setOfficerAreas(areaRes.areas);
        } catch {}

        // Fetch officer review queue
        try {
          const queueRes = await api.getOfficerReviewQueue({
            risk_level: filterRisk !== "ALL" ? filterRisk : undefined,
          });

          if (queueRes.items && queueRes.items.length > 0) {
            const mapped: CaseSummary[] = queueRes.items.map((item: ReviewQueueItem) => {
              const statusNormalized = (item.case_status || "REVIEW_READY").toUpperCase() as CaseStatus;
              const riskNormalized = (item.risk_level || "UNKNOWN").toUpperCase() as RiskLevel;
              return {
                id: item.case_id,
                caseNumber: item.case_number || `CASE-${item.case_id.slice(0, 8).toUpperCase()}`,
                village: item.title || "Jurisdictional Property Record",
                surveyNo: item.case_number,
                owner: `Risk Score: ${item.risk_score}/100`,
                risk: riskNormalized,
                riskScore: item.risk_score,
                status: statusNormalized,
                reviewStatus: (item.review_status || "NOT_STARTED").toUpperCase() as ReviewStatus,
                submitted: new Date(item.created_at).toLocaleDateString("en-IN", {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                }),
                reason:
                  statusNormalized === "APPROVED"
                    ? "Marked as Solved · Verified Title"
                    : statusNormalized === "REJECTED"
                    ? "Rejected · Title Discrepancy"
                    : statusNormalized === "PROOF_REQUIRED"
                    ? "Awaiting Supplementary Citizen Proof"
                    : item.review_status?.toUpperCase() === "IN_PROGRESS"
                    ? "Under Active Officer Review"
                    : "Ready for Verification Determination",
              };
            });
            setCases(mapped);
            return;
          }
        } catch {}
      }

      // Standard listCases scoped to role
      const res = await api.listCases({ page: 1, page_size: 50 });
      if (res.items) {
        const mapped: CaseSummary[] = res.items.map((c: BackendCase) => {
          const statusNormalized = (c.status || "REVIEW_READY").toUpperCase() as CaseStatus;
          const riskNormalized = (c.risk_level || "UNKNOWN").toUpperCase() as RiskLevel;
          return {
            id: c.id,
            caseNumber: c.case_number || `CASE-${c.id.slice(0, 8).toUpperCase()}`,
            village: c.title || "Property Record",
            surveyNo: c.case_number,
            owner: c.description || "Deed Verification",
            risk: riskNormalized,
            status: statusNormalized,
            submitted: new Date(c.created_at).toLocaleDateString("en-IN", {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            }),
            reason:
              statusNormalized === "APPROVED"
                ? "Marked as Solved · Verified Title"
                : statusNormalized === "REJECTED"
                ? "Rejected · Discrepancy Recorded"
                : statusNormalized === "PROOF_REQUIRED"
                ? "Supplementary Proof Requested"
                : statusNormalized === "UNDER_REVIEW"
                ? "Under Review by Area Officer"
                : "Awaiting Verification",
          };
        });
        setCases(mapped);
      } else {
        setCases([]);
      }
    } catch (err: any) {
      console.error("Failed to load cases:", err);
      setError(err.message || "Could not fetch cases from database.");
      setCases([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, [user, filterRisk]);

  const handleStartReview = async (caseId: string) => {
    if (isOfficer) {
      try {
        await api.startReview(caseId);
      } catch {}
    }
    router.push(`/case/${caseId}`);
  };

  const handleQuickMarkSolved = async () => {
    if (!quickSolveCaseId) return;

    setIsSolving(true);
    try {
      // 1. Acquire lock if needed
      try {
        await api.startReview(quickSolveCaseId);
      } catch {}

      // 2. Submit APPROVE decision (Mark as Solved)
      await api.submitReviewDecision(
        quickSolveCaseId,
        "APPROVE",
        quickSolveReason.trim() || "Case verified and marked as solved."
      );

      setSuccessNotice("Case successfully validated and marked as Solved!");
      setQuickSolveCaseId(null);
      await fetchCases();
    } catch (err: any) {
      if (err.message?.includes("already finalized")) {
        setSuccessNotice("Case is already finalized and marked as Solved.");
        setQuickSolveCaseId(null);
        await fetchCases();
      } else {
        setError(err.message || "Failed to mark case as solved.");
      }
    } finally {
      setIsSolving(false);
    }
  };

  const filtered = cases.filter((c) => {
    const matchesRisk =
      filterRisk === "ALL" ? true : c.risk?.toUpperCase() === filterRisk.toUpperCase();
    const matchesStatus =
      filterStatus === "ALL" ? true : c.status?.toUpperCase() === filterStatus.toUpperCase();
    return matchesRisk && matchesStatus;
  });

  const sorted = [...filtered].sort(
    (a, b) => (riskOrder[a.risk] ?? 4) - (riskOrder[b.risk] ?? 4)
  );

  const highCount = cases.filter((c) => c.risk === "HIGH" || c.risk === "CRITICAL").length;
  const pendingCount = cases.filter(
    (c) => c.status === "REVIEW_READY" || c.status === "UNDER_REVIEW" || c.status === "PROCESSING"
  ).length;

  return (
    <div className="mx-auto max-w-6xl px-10 py-14">
      <PageHeader
        step={isCivilian ? "My Applications" : "Step 05 · Assigned Jurisdiction Queue"}
        title={
          isCivilian
            ? `My Property Cases (${user?.full_name || "Citizen"})`
            : `Area Officer Verification Console (${user?.full_name || "Officer"})`
        }
        description={
          isCivilian
            ? "Your submitted property verification records. Citizen access is strictly isolated — you cannot view or access records submitted by other users."
            : "Review cases in your assigned dedicated area. Inspect OCR extractions, registry matching, PostGIS overlays, and mark cases as Solved."
        }
      />

      {/* Scope Banner */}
      <div
        className={`mb-6 flex items-center justify-between rounded border px-5 py-3.5 text-xs ${
          isCivilian
            ? "border-verified/40 bg-verified/10 text-verified font-medium"
            : "border-brass/40 bg-brass/10 text-ink"
        }`}
      >
        {isCivilian ? (
          <p>
            🔒 <strong>Citizen Portal:</strong> Showing {cases.length} case
            {cases.length === 1 ? "" : "s"} owned by <strong>{user?.email}</strong>.
          </p>
        ) : (
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-ink">
                📍 Assigned Jurisdiction:
              </span>
              <span className="font-mono font-semibold text-brass">
                {officerAreas.length > 0
                  ? officerAreas.map((a) => `${a.name} (${a.code})`).join(", ")
                  : "Dedicated Area Assigned"}
              </span>
            </div>
            <p className="text-[11px] text-ink-soft mt-0.5">
              {pendingCount} cases pending review · {highCount} flagged with high/critical discrepancies.
            </p>
          </div>
        )}

        <button
          onClick={fetchCases}
          className="rounded border border-line bg-paper px-3 py-1 font-mono text-[11px] text-ink hover:bg-paper-dark"
        >
          ↻ Refresh List
        </button>
      </div>

      {successNotice && (
        <div className="mb-6 rounded border border-verified/40 bg-verified/10 px-4 py-2.5 text-xs text-verified font-medium">
          ✓ {successNotice}
        </div>
      )}

      {/* Filters Toolbar */}
      <div className="mb-6 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Status Filter */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-ink-soft text-[11px] uppercase tracking-wider font-medium">
              Status:
            </span>
            {[
              { id: "ALL", label: "All Cases" },
              { id: "REVIEW_READY", label: "Pending Review" },
              { id: "UNDER_REVIEW", label: "Under Review" },
              { id: "PROOF_REQUIRED", label: "Proof Required" },
              { id: "APPROVED", label: "✅ Solved & Approved" },
              { id: "REJECTED", label: "✕ Rejected" },
            ].map((st) => (
              <button
                key={st.id}
                onClick={() => setFilterStatus(st.id)}
                className={`rounded px-2.5 py-1 text-[11px] font-medium transition-colors ${
                  filterStatus === st.id
                    ? "bg-ink text-paper"
                    : "border border-line bg-paper-dark/60 text-ink hover:bg-paper-dark"
                }`}
              >
                {st.label}
              </button>
            ))}
          </div>

          {/* Risk Filter */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-ink-soft text-[11px] uppercase tracking-wider font-medium">
              Risk:
            </span>
            {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((lvl) => (
              <button
                key={lvl}
                onClick={() => setFilterRisk(lvl)}
                className={`rounded px-2 py-1 text-[11px] font-medium transition-colors ${
                  filterRisk === lvl
                    ? "bg-ink text-paper"
                    : "border border-line bg-paper-dark/60 text-ink hover:bg-paper-dark"
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="rounded border border-line bg-paper-dark/20 p-12 text-center text-xs font-mono text-ink-soft">
          Loading assigned area cases...
        </div>
      ) : error ? (
        <div className="rounded border border-risk/40 bg-risk/10 p-6 text-xs text-risk">
          {error}
        </div>
      ) : cases.length === 0 ? (
        <div className="rounded border border-line bg-paper-dark/20 p-12 text-center">
          <p className="font-serif text-lg text-ink">No cases in this jurisdiction</p>
          <p className="mt-1 text-xs text-ink-soft">
            {isCivilian
              ? "You have not submitted any property deeds yet."
              : "No cases match your assigned area."}
          </p>
          {isCivilian && (
            <div className="mt-4">
              <Link
                href="/"
                className="inline-block rounded bg-ink px-4 py-2 text-xs font-medium text-paper hover:bg-ink/90"
              >
                + Upload &amp; Submit Property Record
              </Link>
            </div>
          )}
        </div>
      ) : sorted.length === 0 ? (
        <div className="rounded border border-line bg-paper-dark/20 p-12 text-center">
          <p className="font-serif text-lg text-ink">
            No cases under {filterStatus === "APPROVED" ? "✅ Solved & Approved" : filterStatus}
          </p>
          <p className="mt-1 text-xs text-ink-soft">
            There are currently no cases matching the selected status filter.
          </p>
          <div className="mt-4">
            <button
              onClick={() => {
                setFilterStatus("ALL");
                setFilterRisk("ALL");
              }}
              className="inline-block rounded bg-ink px-4 py-2 text-xs font-medium text-paper hover:bg-ink/90"
            >
              Show All Cases ({cases.length})
            </button>
          </div>
        </div>
      ) : (
        <div className="overflow-hidden rounded border border-line">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line bg-paper-dark/60 text-[11px] uppercase tracking-wide text-ink-soft">
                <th className="px-4 py-2.5 font-medium">Case Number</th>
                <th className="px-4 py-2.5 font-medium">Property Record</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Risk Score</th>
                <th className="px-4 py-2.5 font-medium">Verification Status</th>
                <th className="px-4 py-2.5 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {sorted.map((c) => (
                <tr key={c.id} className="bg-paper-dark/20 hover:bg-paper-dark/40">
                  <td className="px-4 py-3.5 font-mono text-xs">
                    <button
                      onClick={() => handleStartReview(c.id)}
                      className="font-bold text-brass underline underline-offset-2 hover:opacity-80"
                    >
                      {c.caseNumber || c.id.slice(0, 8)}
                    </button>
                    <p className="text-[10px] text-ink-soft mt-0.5">{c.submitted}</p>
                  </td>
                  <td className="px-4 py-3.5 text-ink">
                    <p className="font-medium text-xs">{c.village}</p>
                    <p className="text-[11px] text-ink-soft">{c.owner}</p>
                  </td>
                  <td className="px-4 py-3.5">
                    <Stamp
                      tone={
                        c.status === "APPROVED"
                          ? "verified"
                          : c.status === "REJECTED"
                          ? "risk"
                          : c.status === "PROOF_REQUIRED"
                          ? "caution"
                          : "neutral"
                      }
                    >
                      {c.status === "APPROVED" ? "SOLVED" : c.status || "REVIEW_READY"}
                    </Stamp>
                  </td>
                  <td className="px-4 py-3.5">
                    <div className="flex items-center gap-2">
                      <RiskBadge level={c.risk} />
                      {c.riskScore !== undefined && (
                        <span className="font-mono text-[11px] text-ink-soft">
                          ({c.riskScore}/100)
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3.5 text-xs text-ink-soft max-w-[200px] truncate">
                    {c.reason}
                  </td>
                  <td className="px-4 py-3.5 text-right whitespace-nowrap">
                    {isOfficer ? (
                      <div className="flex items-center justify-end gap-1.5">
                        {c.status !== "APPROVED" && c.status !== "REJECTED" && (
                          <button
                            onClick={() => {
                              setQuickSolveCaseId(c.id);
                            }}
                            className="rounded bg-verified px-2.5 py-1 text-xs font-medium text-paper hover:opacity-90 transition-opacity"
                            title="Mark this case as verified and solved"
                          >
                            ✓ Mark as Solved
                          </button>
                        )}
                        <button
                          onClick={() => handleStartReview(c.id)}
                          className="rounded bg-ink px-2.5 py-1 text-xs font-medium text-paper transition-opacity hover:opacity-90"
                        >
                          Verify Details →
                        </button>
                      </div>
                    ) : (
                      <Link
                        href={`/case/${c.id}`}
                        className="rounded border border-line bg-paper px-3 py-1 text-xs font-medium text-ink hover:bg-paper-dark"
                      >
                        View Status →
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Quick Mark as Solved Modal */}
      {quickSolveCaseId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
          <div className="w-full max-w-md rounded-lg border border-line bg-paper p-6 shadow-xl">
            <h3 className="font-serif text-lg text-ink">
              Validate &amp; Mark Case as <span className="text-verified">Solved</span>
            </h3>
            <p className="mt-1 text-xs text-ink-soft">
              This will record an official APPROVAL determination and snapshot the verified record in your dedicated jurisdiction.
            </p>

            <div className="mt-4">
              <label className="block text-xs font-medium text-ink">
                Resolution Justification (Written to audit trail)
              </label>
              <textarea
                value={quickSolveReason}
                onChange={(e) => setQuickSolveReason(e.target.value)}
                rows={3}
                className="mt-1.5 w-full rounded border border-line bg-paper px-3 py-2 text-xs text-ink focus:border-brass focus:outline-none"
              />
            </div>

            <div className="mt-6 flex justify-end gap-2 text-xs">
              <button
                onClick={() => setQuickSolveCaseId(null)}
                className="rounded border border-line px-4 py-2 font-medium text-ink hover:bg-paper-dark"
              >
                Cancel
              </button>
              <button
                onClick={handleQuickMarkSolved}
                disabled={isSolving}
                className="rounded bg-verified px-4 py-2 font-medium text-paper hover:opacity-90 disabled:opacity-50"
              >
                {isSolving ? "Recording Resolution..." : "Confirm & Mark as Solved"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="mt-8 flex items-center justify-between">
        <span className="text-xs text-ink-soft">
          {isOfficer
            ? `Area Officer: ${user?.full_name} (${user?.email})`
            : "Citizen Application Tracking"}
        </span>
        {isCivilian && (
          <Link
            href="/"
            className="rounded bg-ink px-4 py-2 text-xs font-medium text-paper hover:bg-ink/90"
          >
            + Upload New Case
          </Link>
        )}
      </div>
    </div>
  );
}

export default function QueuePage() {
  return (
    <Suspense fallback={<div className="p-10 text-xs font-mono text-ink-soft">Loading queue...</div>}>
      <QueueContent />
    </Suspense>
  );
}