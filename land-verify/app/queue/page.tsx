import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";
import RiskBadge from "@/components/ui/RiskBadge";
import { caseQueue } from "@/lib/mock";

const riskOrder = { HIGH: 0, MEDIUM: 1, LOW: 2 };

export default function QueuePage() {
  const sorted = [...caseQueue].sort((a, b) => riskOrder[a.risk] - riskOrder[b.risk]);
  const highCount = caseQueue.filter((c) => c.risk === "HIGH").length;

  return (
    <div className="mx-auto max-w-5xl px-10 py-14">
      <PageHeader
        step="Step 05 · Review Queue"
        title="Cases waiting on a human decision."
        description="Doubtful cases land here with the exact reasons attached. Clear cases never reach this queue — an officer only sees what actually needs judgement."
      />

      <div className="mb-4 flex items-center gap-4 text-xs text-ink-soft">
        <span>{caseQueue.length} open cases</span>
        <span className="text-risk">{highCount} high risk</span>
      </div>

      <div className="overflow-hidden rounded border border-line">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-line bg-paper-dark/60 text-[11px] uppercase tracking-wide text-ink-soft">
              <th className="px-4 py-2.5 font-medium">Case</th>
              <th className="px-4 py-2.5 font-medium">Village / Survey No.</th>
              <th className="px-4 py-2.5 font-medium">Owner</th>
              <th className="px-4 py-2.5 font-medium">Reason</th>
              <th className="px-4 py-2.5 font-medium">Risk</th>
              <th className="px-4 py-2.5 font-medium">Submitted</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {sorted.map((c) => (
              <tr key={c.id} className="bg-paper-dark/20 hover:bg-paper-dark/40">
                <td className="px-4 py-3">
                  <Link href={`/case/${c.id}`} className="font-mono text-xs text-brass underline underline-offset-2">
                    {c.id}
                  </Link>
                </td>
                <td className="px-4 py-3 text-ink">
                  {c.village} <span className="text-ink-soft">· {c.surveyNo}</span>
                </td>
                <td className="px-4 py-3 text-ink">{c.owner}</td>
                <td className="px-4 py-3 max-w-[220px] text-xs text-ink-soft">{c.reason}</td>
                <td className="px-4 py-3">
                  <RiskBadge level={c.risk} />
                </td>
                <td className="px-4 py-3 text-xs text-ink-soft">{c.submitted}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-8">
        <Link href="/result" className="text-xs text-ink-soft underline underline-offset-2 hover:text-ink">
          ← Back to risk result
        </Link>
      </div>
    </div>
  );
}