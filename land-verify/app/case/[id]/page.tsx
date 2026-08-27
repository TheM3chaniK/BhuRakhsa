import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";
import RiskBadge from "@/components/ui/RiskBadge";
import StatusPill from "@/components/ui/StatusPill";
import ConfidenceMeter from "@/components/ui/ConfidenceMeter";
import { caseQueue, extractedFields, validationRows } from "@/lib/mock";

const timeline = [
  { label: "Uploaded", detail: "land_record_scan_142.pdf received", who: "Citizen portal" },
  { label: "Prepared", detail: "Deskewed, denoised, contrast-enhanced", who: "System" },
  { label: "Read & extracted", detail: `${extractedFields.length} fields pulled, 2 flagged low-confidence`, who: "OCR pipeline" },
  { label: "Matched & validated", detail: "Checked against demo land database & GIS layer", who: "System" },
  { label: "Scored", detail: "MEDIUM risk — area mismatch, probable name match", who: "Rules engine" },
  { label: "Awaiting review", detail: "Queued for officer decision", who: "Review queue" },
];

export default function CaseProfilePage({ params }: { params: { id: string } }) {
  const kase = caseQueue.find((c) => c.id === params.id) ?? caseQueue[0];

  return (
    <div className="mx-auto max-w-5xl px-10 py-14">
      <PageHeader
        step="Step 06 · Evidence Profile"
        title={`Case ${kase.id}`}
        description="Every step leaves evidence behind — source page, extracted value, comparison, map result, and the reviewer's decision, kept in one timeline."
      />

      <div className="flex items-center justify-between rounded border border-line bg-paper-dark/40 px-6 py-5">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-ink-soft">
            {kase.village} · Survey No. {kase.surveyNo}
          </p>
          <p className="mt-1 font-serif text-xl text-ink">{kase.owner}</p>
        </div>
        <RiskBadge level={kase.risk} />
      </div>

      <div className="mt-10 grid grid-cols-5 gap-10">
        {/* Evidence timeline */}
        <div className="col-span-2">
          <p className="mb-3 text-xs font-medium uppercase tracking-wide text-ink-soft">
            Evidence timeline
          </p>
          <ol className="space-y-0">
            {timeline.map((t, i) => (
              <li key={t.label} className="relative pb-6 pl-6 last:pb-0">
                {i < timeline.length - 1 && (
                  <span className="absolute left-[3px] top-2 h-full w-px bg-line" />
                )}
                <span className="absolute left-0 top-1.5 h-2 w-2 rounded-full border-2 border-brass bg-paper" />
                <p className="text-sm font-medium text-ink">{t.label}</p>
                <p className="mt-0.5 text-xs text-ink-soft">{t.detail}</p>
                <p className="mt-0.5 font-mono text-[10px] uppercase tracking-wide text-ink-soft/70">
                  {t.who}
                </p>
              </li>
            ))}
          </ol>
        </div>

        {/* Fields + validation + decision */}
        <div className="col-span-3 space-y-8">
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
              Extracted fields
            </p>
            <div className="divide-y divide-line rounded border border-line bg-paper-dark/30">
              {extractedFields.map((f) => (
                <div key={f.label} className="flex items-center justify-between px-4 py-2.5">
                  <div>
                    <p className="text-[11px] uppercase tracking-wide text-ink-soft">{f.label}</p>
                    <p className="font-mono text-sm text-ink">{f.value}</p>
                  </div>
                  <ConfidenceMeter value={f.confidence} />
                </div>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
              Validation results
            </p>
            <div className="divide-y divide-line rounded border border-line bg-paper-dark/30">
              {validationRows.map((r) => (
                <div key={r.field} className="flex items-center justify-between px-4 py-2.5 text-sm">
                  <span className="text-ink-soft">{r.field}</span>
                  <StatusPill status={r.status} />
                </div>
              ))}
            </div>
          </div>

          {/* Reviewer decision */}
          <div className="rounded border border-line bg-paper-dark/40 px-5 py-5">
            <p className="mb-3 text-xs font-medium uppercase tracking-wide text-ink-soft">
              Reviewer decision
            </p>
            <div className="flex gap-2">
              <button className="flex-1 rounded bg-verified px-4 py-2 text-xs font-medium text-paper transition-opacity hover:opacity-90">
                Accept
              </button>
              <button className="flex-1 rounded bg-caution px-4 py-2 text-xs font-medium text-paper transition-opacity hover:opacity-90">
                Request proof
              </button>
              <button className="flex-1 rounded bg-risk px-4 py-2 text-xs font-medium text-paper transition-opacity hover:opacity-90">
                Reject
              </button>
            </div>
            <textarea
              placeholder="Reviewer comment (kept in the audit log)…"
              rows={3}
              className="mt-3 w-full resize-none rounded border border-line bg-paper px-3 py-2 text-xs text-ink placeholder:text-ink-soft focus:border-brass focus:outline-none"
            />
          </div>
        </div>
      </div>

      <div className="mt-10">
        <Link href="/queue" className="text-xs text-ink-soft underline underline-offset-2 hover:text-ink">
          ← Back to review queue
        </Link>
      </div>
    </div>
  );
}