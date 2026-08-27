import Link from "next/link";
import Stamp from "@/components/ui/Stamp";
import PageHeader from "@/components/ui/PageHeader";

export default function UploadPage() {
  return (
    <div className="mx-auto max-w-3xl px-10 py-14">
      <PageHeader
        step="Step 01 · Upload"
        title="Turn an old land record into a checkable case."
        description="Upload a scan, photo, or PDF. The system reads it, checks it against available records and maps, and shows a plain-language risk result — no legal decision is made here."
      />

      {/* Drop zone */}
      <div className="mt-10 rounded border-2 border-dashed border-line bg-paper-dark/60 px-8 py-16 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border-2 border-brass/40 text-brass">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M12 16V4M12 4l-4 4M12 4l4 4" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <p className="text-sm font-medium text-ink">
          Drag a document here, or{" "}
          <span className="cursor-pointer text-brass underline underline-offset-2">
            browse files
          </span>
        </p>
        <p className="mt-1.5 text-xs text-ink-soft">
          Scanned PDF, JPG, or PNG · handwritten or multilingual is fine
        </p>
      </div>

      {/* What happens next, kept minimal */}
      <div className="mt-8 flex items-center justify-between rounded border border-line bg-paper-dark/40 px-5 py-4">
        <div className="flex items-center gap-3">
          <Stamp tone="neutral">Demo Record</Stamp>
          <p className="text-xs text-ink-soft">
            No file? Load a sample record to see the full pipeline.
          </p>
        </div>
        <Link
          href="/processing"
          className="whitespace-nowrap rounded bg-ink px-4 py-2 text-xs font-medium text-paper transition-colors hover:bg-ink/90"
        >
          Use sample &amp; continue →
        </Link>
      </div>

      <div className="mt-10 grid grid-cols-3 gap-4 border-t border-line pt-6 text-xs text-ink-soft">
        <p><span className="font-medium text-ink">Citizens</span> preparing applications</p>
        <p><span className="font-medium text-ink">Data-entry staff</span> doing first checks</p>
        <p><span className="font-medium text-ink">Officers</span> reviewing doubtful cases</p>
      </div>
    </div>
  );
}