import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";
import StatusPill from "@/components/ui/StatusPill";
import { validationRows } from "@/lib/mock";

export default function ValidatePage() {
  return (
    <div className="mx-auto max-w-5xl px-10 py-14">
      <PageHeader
        step="Step 03 · Match & Validate"
        title="Comparing the document against records and the map."
        description="Every field is checked against the demo land database and the GIS parcel layer. Each result is labelled — matched, mismatch, missing, or cannot check — never a single hidden score."
      />

      <div className="grid grid-cols-5 gap-8">
        {/* Field comparison table */}
        <div className="col-span-3">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
            Database comparison
          </p>
          <div className="overflow-hidden rounded border border-line">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line bg-paper-dark/60 text-[11px] uppercase tracking-wide text-ink-soft">
                  <th className="px-4 py-2.5 font-medium">Field</th>
                  <th className="px-4 py-2.5 font-medium">Document</th>
                  <th className="px-4 py-2.5 font-medium">Record</th>
                  <th className="px-4 py-2.5 font-medium">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {validationRows.map((row) => (
                  <tr key={row.field} className="bg-paper-dark/20">
                    <td className="px-4 py-3 text-ink-soft">{row.field}</td>
                    <td className="px-4 py-3 font-mono text-xs text-ink">{row.document}</td>
                    <td className="px-4 py-3 font-mono text-xs text-ink">{row.record}</td>
                    <td className="px-4 py-3">
                      <StatusPill status={row.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Map check */}
        <div className="col-span-2">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
            Map check
          </p>
          <div className="relative aspect-square overflow-hidden rounded border border-line bg-paper-dark/60">
            <svg viewBox="0 0 200 200" className="h-full w-full">
              <rect width="200" height="200" fill="#EFE9DA" />
              {[...Array(6)].map((_, i) => (
                <line key={`v${i}`} x1={i * 34} y1="0" x2={i * 34} y2="200" stroke="#DDD5C0" strokeWidth="1" />
              ))}
              {[...Array(6)].map((_, i) => (
                <line key={`h${i}`} x1="0" y1={i * 34} x2="200" y2={i * 34} stroke="#DDD5C0" strokeWidth="1" />
              ))}
              {/* declared boundary (from doc) */}
              <polygon points="60,50 150,60 145,140 55,130" fill="none" stroke="#B08D3E" strokeWidth="2" strokeDasharray="4 3" />
              {/* actual parcel (from GIS) */}
              <polygon points="65,55 140,65 138,125 62,118" fill="#9B3327" fillOpacity="0.12" stroke="#9B3327" strokeWidth="2" />
            </svg>
            <p className="absolute bottom-2 left-2 rounded bg-paper/90 px-2 py-1 font-mono text-[10px] text-ink-soft">
              Demo GIS data — not official cadastral data
            </p>
          </div>
          <div className="mt-3 space-y-1.5 text-xs text-ink-soft">
            <p className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 border border-brass" /> Declared boundary (document)
            </p>
            <p className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 bg-risk/20 border border-risk" /> Parcel on map (GIS)
            </p>
          </div>
          <div className="mt-4 rounded border border-caution/40 bg-caution/10 px-3 py-2 text-xs text-ink">
            Declared area <span className="font-mono">1.20 acre</span> is larger than the
            mapped parcel area <span className="font-mono">1.05 acre</span> — a 14% gap.
          </div>
        </div>
      </div>

      <div className="mt-10 flex items-center justify-between">
        <Link href="/processing" className="text-xs text-ink-soft underline underline-offset-2 hover:text-ink">
          ← Back to extraction
        </Link>
        <Link
          href="/result"
          className="rounded bg-ink px-4 py-2 text-xs font-medium text-paper transition-colors hover:bg-ink/90"
        >
          Run risk scoring →
        </Link>
      </div>
    </div>
  );
}