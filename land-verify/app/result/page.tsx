import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";
import RiskBadge from "@/components/ui/RiskBadge";

const reasons = [
  { text: "Survey number matches exactly.", tone: "verified" as const },
  { text: "Declared area (1.20 acre) differs from mapped area (1.05 acre) by 14%.", tone: "caution" as const },
  { text: "Owner name is a probable match, not an exact match — \"Debasish Roy\" vs \"D. Roy\".", tone: "caution" as const },
  { text: "Boundary (East) could not be verified against any record.", tone: "neutral" as const },
];

const toneDot: Record<string, string> = {
  verified: "bg-verified",
  caution: "bg-caution",
  risk: "bg-risk",
  neutral: "bg-ink-soft",
};

export default function ResultPage() {
  return (
    <div className="mx-auto max-w-3xl px-10 py-14">
      <PageHeader
        step="Step 04 · Risk Result"
        title="Evidence-based risk result for this case."
        description="Simple rules combine mismatches and missing details into one risk level. Every level lists its exact reasons — this is a review signal, not proof of fraud or a legal verdict."
      />

      <div className="flex items-center justify-between rounded border border-line bg-paper-dark/40 px-6 py-5">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-ink-soft">Case SIH-0142</p>
          <p className="mt-1 font-serif text-xl text-ink">Hatgacha · Survey No. 142/3-B</p>
        </div>
        <RiskBadge level="MEDIUM" />
      </div>

      <div className="mt-8">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-ink-soft">Why</p>
        <ul className="space-y-3">
          {reasons.map((r) => (
            <li key={r.text} className="flex items-start gap-3 rounded border border-line bg-paper-dark/20 px-4 py-3 text-sm text-ink">
              <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${toneDot[r.tone]}`} />
              {r.text}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-8 rounded border border-brass/40 bg-brass/10 px-5 py-4">
        <p className="text-xs font-medium uppercase tracking-wide text-brass">Next action</p>
        <p className="mt-1 text-sm text-ink">
          Show the officer the marked document fields, matching records and parcel map.
          Ask for a manual area check.
        </p>
      </div>

      <div className="mt-10 flex items-center justify-between">
        <Link href="/validate" className="text-xs text-ink-soft underline underline-offset-2 hover:text-ink">
          ← Back to validation
        </Link>
        <Link
          href="/queue"
          className="rounded bg-ink px-4 py-2 text-xs font-medium text-paper transition-colors hover:bg-ink/90"
        >
          Send to review queue →
        </Link>
      </div>
    </div>
  );
}