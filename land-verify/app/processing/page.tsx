import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";
import ConfidenceMeter from "@/components/ui/ConfidenceMeter";
import { extractedFields } from "@/lib/mock";

export default function ProcessingPage() {
  const lowConfidenceCount = extractedFields.filter((f) => f.confidence < 65).length;

  return (
    <div className="mx-auto max-w-5xl px-10 py-14">
      <PageHeader
        step="Step 02 · Read & Extract"
        title="Extracted fields from the uploaded document."
        description="OCR reads the document and pulls out the fields that matter. Low-confidence fields are flagged for a quick manual check before matching."
      />

      <div className="grid grid-cols-5 gap-8">
        {/* Document preview */}
        <div className="col-span-2">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
            Source document
          </p>
          <div className="flex aspect-[3/4] flex-col items-center justify-center gap-3 rounded border border-line bg-paper-dark/60 px-6 text-center">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-ink-soft">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <path d="M14 2v6h6" />
            </svg>
            <p className="text-xs text-ink-soft">
              land_record_scan_142.pdf · page 1 of 1
            </p>
            <p className="rounded border border-dashed border-line px-2 py-1 font-mono text-[10px] text-ink-soft">
              deskewed · denoised · contrast-enhanced
            </p>
          </div>
        </div>

        {/* Extracted fields */}
        <div className="col-span-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">
              Extracted fields
            </p>
            {lowConfidenceCount > 0 && (
              <p className="text-xs text-caution">
                {lowConfidenceCount} field{lowConfidenceCount > 1 ? "s" : ""} need a quick check
              </p>
            )}
          </div>

          <div className="divide-y divide-line rounded border border-line bg-paper-dark/30">
            {extractedFields.map((field) => (
              <div key={field.label} className="flex items-center justify-between gap-4 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] uppercase tracking-wide text-ink-soft">
                    {field.label}
                  </p>
                  {field.confidence < 65 ? (
                    <input
                      defaultValue={field.value}
                      className="mt-0.5 w-full rounded border border-caution/50 bg-paper px-2 py-1 font-mono text-sm text-ink focus:border-caution focus:outline-none"
                    />
                  ) : (
                    <p className="mt-0.5 font-mono text-sm text-ink">{field.value}</p>
                  )}
                </div>
                <ConfidenceMeter value={field.confidence} />
              </div>
            ))}
          </div>

          <div className="mt-8 flex items-center justify-between">
            <Link href="/" className="text-xs text-ink-soft underline underline-offset-2 hover:text-ink">
              ← Back to upload
            </Link>
            <Link
              href="/validate"
              className="rounded bg-ink px-4 py-2 text-xs font-medium text-paper transition-colors hover:bg-ink/90"
            >
              Confirm fields & continue →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}