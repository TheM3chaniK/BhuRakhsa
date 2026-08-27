"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";
import RiskBadge from "@/components/ui/RiskBadge";
import { api } from "@/lib/api";
import { BackendCase, BackendRiskAssessment, RiskLevel } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

type ReasonTone = "verified" | "caution" | "risk" | "neutral";
type ReasonItem = { text: string; tone: ReasonTone };

const toneDot: Record<string, string> = {
  verified: "bg-verified",
  caution: "bg-caution",
  risk: "bg-risk",
  neutral: "bg-ink-soft",
};

function ResultContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user } = useAuth();
  const caseId = searchParams.get("caseId");

  useEffect(() => {
    if (user?.role === "AREA_OFFICER") {
      router.push("/queue");
      return;
    }
    if (user?.role === "SUPER_ADMIN") {
      router.push("/admin/officers");
      return;
    }
  }, [user, router]);

  const [caseData, setCaseData] = useState<BackendCase | null>(null);
  const [riskAssessment, setRiskAssessment] = useState<BackendRiskAssessment | null>(null);
  const [reasons, setReasons] = useState<ReasonItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (caseId) {
      setLoading(true);
      // 1. Fetch case metadata from backend
      api
        .getCase(caseId)
        .then((c) => {
          setCaseData(c);
        })
        .catch(() => {});

      // 2. Fetch risk assessment from backend
      api
        .getCaseRiskAssessment(caseId)
        .then((ra) => {
          if (ra) {
            setRiskAssessment(ra);
            if (ra.factors && ra.factors.length > 0) {
              const mappedReasons: ReasonItem[] = ra.factors.map((f) => ({
                text: f.description || f.factor_name,
                tone:
                  f.severity === "CRITICAL" || f.severity === "HIGH"
                    ? "risk"
                    : f.severity === "MEDIUM"
                    ? "caution"
                    : "verified",
              }));
              setReasons(mappedReasons);
            }
          }
        })
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [caseId]);

  const riskLevel: RiskLevel =
    riskAssessment?.risk_level || caseData?.risk_level || "UNKNOWN";

  const prevUrl = caseId ? `/validate?caseId=${caseId}` : "/validate";
  const caseUrl = caseId ? `/case/${caseId}` : "/queue";

  return (
    <div className="mx-auto max-w-3xl px-10 py-14">
      <PageHeader
        step="Step 04 · Risk Assessment"
        title="Evidence-based risk calculation for this property record."
        description="A deterministic rules engine combines discrepancy severities into an explainable composite risk level. Every score is backed by granular reasons — providing clear intelligence for human officer review."
      />

      <div className="flex items-center justify-between rounded border border-line bg-paper-dark/40 px-6 py-5">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-ink-soft">
            {caseData ? `Case ${caseData.case_number}` : "Property Case"}
          </p>
          <p className="mt-1 font-serif text-xl text-ink">
            {caseData?.title || (caseId ? `Case #${caseId.slice(0, 8)}` : "No Active Case")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {riskAssessment && (
            <span className="font-mono text-xs text-ink-soft">
              Score: <strong className="text-ink">{riskAssessment.risk_score}/100</strong>
            </span>
          )}
          <RiskBadge level={riskLevel} />
        </div>
      </div>

      <div className="mt-8">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-ink-soft">
          Risk Factors &amp; Discrepancies ({reasons.length})
        </p>

        {loading ? (
          <div className="rounded border border-line bg-paper-dark/20 p-8 text-center text-xs font-mono text-ink-soft">
            Computing risk factors from PostgreSQL engine...
          </div>
        ) : reasons.length === 0 ? (
          <div className="rounded border border-line bg-paper-dark/20 p-6 text-center text-xs text-ink-soft">
            <p className="font-medium text-ink">No risk discrepancies recorded</p>
            <p className="mt-1 text-[11px]">
              {caseId
                ? "This case passed validation without severe discrepancies."
                : "Select an active case from Step 01 or the Review Queue."}
            </p>
          </div>
        ) : (
          <ul className="space-y-3">
            {reasons.map((r, i) => (
              <li
                key={i}
                className="flex items-start gap-3 rounded border border-line bg-paper-dark/20 px-4 py-3 text-sm text-ink"
              >
                <span
                  className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                    toneDot[r.tone] || toneDot.neutral
                  }`}
                />
                {r.text}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-8 rounded border border-brass/40 bg-brass/10 px-5 py-4">
        <p className="text-xs font-medium uppercase tracking-wide text-brass">Recommended Next Action</p>
        <p className="mt-1 text-sm text-ink">
          Present the grounded evidence dossier, OCR bounding boxes, and PostGIS boundary overlay to the Area Officer for formal determination or supplementary proof request.
        </p>
      </div>

      <div className="mt-10 flex items-center justify-between">
        <Link href={prevUrl} className="text-xs text-ink-soft underline underline-offset-2 hover:text-ink">
          ← Back to validation
        </Link>
        <Link
          href={caseUrl}
          className="rounded bg-ink px-4 py-2 text-xs font-medium text-paper transition-colors hover:bg-ink/90"
        >
          Inspect full evidence dossier →
        </Link>
      </div>
    </div>
  );
}

export default function ResultPage() {
  return (
    <Suspense fallback={<div className="p-10 text-xs font-mono text-ink-soft">Calculating risk score...</div>}>
      <ResultContent />
    </Suspense>
  );
}