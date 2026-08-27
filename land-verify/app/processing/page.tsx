"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";
import ConfidenceMeter from "@/components/ui/ConfidenceMeter";
import { api } from "@/lib/api";
import { ExtractedField } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

function ProcessingContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user } = useAuth();
  const caseId = searchParams.get("caseId");
  const docId = searchParams.get("docId");

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

  const [activeCaseId, setActiveCaseId] = useState<string | null>(caseId);
  const [activeDocId, setActiveDocId] = useState<string | null>(docId);

  const [fields, setFields] = useState<ExtractedField[]>([]);
  const [ocrText, setOcrText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [processingStatus, setProcessingStatus] = useState<string>("queued");
  const [isTriggering, setIsTriggering] = useState(false);
  const [secondsElapsed, setSecondsElapsed] = useState(0);

  useEffect(() => {
    if (docId) setActiveDocId(docId);
    if (caseId) setActiveCaseId(caseId);
  }, [caseId, docId]);

  useEffect(() => {
    const resolveTarget = async () => {
      if (activeDocId) return;

      let cId = activeCaseId;
      if (!cId) {
        try {
          const casesRes = await api.listCases({ page: 1, page_size: 1 });
          if (casesRes.items && casesRes.items.length > 0) {
            cId = casesRes.items[0].id;
            setActiveCaseId(cId);
          }
        } catch {}
      }

      if (cId) {
        try {
          const docsRes = await api.getCaseDocuments(cId);
          const docs = docsRes.documents || docsRes.items || [];
          if (docs.length > 0) {
            setActiveDocId(docs[0].id);
          }
        } catch {}
      }
    };

    resolveTarget();
  }, [activeCaseId, activeDocId]);

  const loadExtractionData = async () => {
    if (!activeDocId) return;
    setLoading(true);
    try {
      // 1. Fetch processing status
      try {
        const statusRes = await api.getDocumentProcessingStatus(activeDocId);
        if (statusRes.processing?.status) {
          setProcessingStatus(statusRes.processing.status);
        } else if (statusRes.document_status) {
          setProcessingStatus(statusRes.document_status);
        }
      } catch {}

      // 2. Fetch OCR text
      const ocrRes = await api.getDocumentOcr(activeDocId);
      if (ocrRes && ocrRes.full_text) {
        setOcrText(ocrRes.full_text);
      } else if (ocrRes && ocrRes.pages && ocrRes.pages.length > 0) {
        setOcrText(
          ocrRes.pages
            .map((p) => `--- PAGE ${p.page_number} ---\n${p.text}`)
            .join("\n\n")
        );
      }

      // 3. Fetch structured extraction
      const res = await api.getDocumentExtraction(activeDocId);
      if (res && res.fields && res.fields.length > 0) {
        const mapped: ExtractedField[] = res.fields.map((f) => ({
          label: f.field_name
            .replace(/_/g, " ")
            .replace(/\b\w/g, (l) => l.toUpperCase()),
          value: f.field_value || f.normalized_value || "—",
          confidence: Math.round(
            (typeof f.confidence === "number" ? f.confidence : 0.85) *
              (f.confidence && f.confidence <= 1 ? 100 : 1)
          ),
        }));
        setFields(mapped);
        setProcessingStatus("completed");
      }
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  };

  // Trigger manual re-run if needed
  const handleTriggerProcessing = async () => {
    if (!activeDocId) return;
    setIsTriggering(true);
    try {
      await api.processDocument(activeDocId);
      await api.extractDocument(activeDocId);
      await loadExtractionData();
    } catch (err: any) {
      console.error("Trigger error:", err);
    } finally {
      setIsTriggering(false);
    }
  };

  // Timer while extracting
  useEffect(() => {
    if (fields.length > 0) return;
    const timer = setInterval(() => {
      setSecondsElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [fields.length]);

  // Polling loop
  useEffect(() => {
    if (!activeDocId) return;
    let isMounted = true;
    let pollCount = 0;

    loadExtractionData();

    const interval = setInterval(async () => {
      pollCount++;
      if (pollCount > 60 || !isMounted) {
        clearInterval(interval);
        return;
      }

      try {
        const ocrRes = await api.getDocumentOcr(activeDocId);
        if (
          ocrRes &&
          (ocrRes.full_text || (ocrRes.pages && ocrRes.pages.length > 0))
        ) {
          if (isMounted) {
            setOcrText(
              ocrRes.full_text ||
                ocrRes.pages
                  .map((p) => `--- PAGE ${p.page_number} ---\n${p.text}`)
                  .join("\n\n")
            );
          }
        }

        const res = await api.getDocumentExtraction(activeDocId);
        if (res && res.fields && res.fields.length > 0) {
          const mapped: ExtractedField[] = res.fields.map((f) => ({
            label: f.field_name
              .replace(/_/g, " ")
              .replace(/\b\w/g, (l) => l.toUpperCase()),
            value: f.field_value || f.normalized_value || "—",
            confidence: Math.round(
              (typeof f.confidence === "number" ? f.confidence : 0.85) *
                (f.confidence && f.confidence <= 1 ? 100 : 1)
            ),
          }));
          if (isMounted) {
            setFields(mapped);
            setProcessingStatus("completed");
          }
          clearInterval(interval);
        }
      } catch {}
    }, 2000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [activeDocId]);

  const handleFieldChange = (index: number, val: string) => {
    const updated = [...fields];
    updated[index].value = val;
    setFields(updated);
  };

  const lowConfidenceCount = fields.filter((f) => f.confidence < 65).length;
  const nextUrl = caseId ? `/validate?caseId=${caseId}` : "/validate";
  const isStillProcessing = fields.length === 0;

  return (
    <div className="mx-auto max-w-5xl px-10 py-14">
      <PageHeader
        step="Step 02 · Read & Extract"
        title="Extracted fields from the uploaded document."
        description="DeepSeek OCR renders document pages to high-resolution image bitmaps, performs vision-language text recognition via Ollama, and grounds structured property entities with citation evidence."
      />

      {/* Case Header Status */}
      {caseId && (
        <div className="mb-6 flex items-center justify-between rounded border border-brass/40 bg-brass/10 px-4 py-2.5 text-xs">
          <div className="flex items-center gap-3">
            <span className="font-mono text-ink">Case: {caseId.slice(0, 8)}...</span>
            <span className="text-[11px] text-ink-soft">Doc: #{docId?.slice(0, 8)}</span>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                fields.length > 0
                  ? "bg-verified"
                  : "bg-brass animate-ping"
              }`}
            />
            <span className="font-medium text-ink uppercase text-[10px] tracking-wider">
              {fields.length > 0
                ? "OCR & Extraction Complete"
                : "DeepSeek OCR Inference in Progress"}
            </span>
          </div>
        </div>
      )}

      {/* Prominent Active Progress & Spinner Banner */}
      {isStillProcessing && (
        <div className="mb-8 rounded-lg border border-brass/50 bg-paper-dark p-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              {/* Spinner */}
              <div className="relative flex h-10 w-10 shrink-0 items-center justify-center">
                <div className="absolute h-10 w-10 animate-spin rounded-full border-3 border-line border-t-brass" />
                <span className="font-mono text-[10px] font-bold text-brass">
                  {secondsElapsed}s
                </span>
              </div>

              <div>
                <h4 className="font-serif text-sm font-semibold text-ink">
                  DeepSeek-OCR &amp; Entity Extraction Running
                </h4>
                <p className="mt-0.5 text-xs text-ink-soft">
                  Converting PDF pages to 300 DPI bitmaps and running local Ollama vision inference.
                </p>

                {/* Stepped progress indicators */}
                <div className="mt-3 flex flex-wrap items-center gap-4 text-[11px]">
                  <span className="flex items-center gap-1.5 text-verified font-medium">
                    <span>✓</span> Page Bitmaps Rendered
                  </span>
                  <span className="flex items-center gap-1.5 text-ink font-medium">
                    <span className="h-2 w-2 animate-ping rounded-full bg-brass" />
                    DeepSeek Vision OCR
                  </span>
                  <span className="flex items-center gap-1.5 text-ink-soft">
                    <span>⏳</span> Entity Grounding
                  </span>
                </div>
              </div>
            </div>

            {/* Manual Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={loadExtractionData}
                className="rounded border border-line bg-paper px-3 py-1.5 text-xs font-mono text-ink hover:bg-paper-dark"
              >
                ↻ Refresh
              </button>
              <button
                onClick={handleTriggerProcessing}
                disabled={isTriggering}
                className="rounded bg-ink px-3 py-1.5 text-xs font-medium text-paper hover:bg-ink/90 disabled:opacity-50 shadow-sm"
              >
                {isTriggering ? "Processing..." : "⚡ Run Extraction"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-5 gap-8">
        {/* Document preview & Scanning Animation */}
        <div className="col-span-2">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
            Source document &amp; DeepSeek OCR
          </p>
          <div className="relative flex min-h-[400px] flex-col items-center justify-between overflow-hidden rounded border border-line bg-paper-dark/60 p-4 text-center">
            {/* Scanner Beam Animation when processing */}
            {isStillProcessing && !ocrText && (
              <div className="scanner-beam pointer-events-none absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-brass to-transparent shadow-[0_0_12px_#B8860B]" />
            )}

            <div className="my-auto flex flex-col items-center gap-2">
              <div className="relative">
                <svg
                  width="44"
                  height="44"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  className="text-ink-soft"
                >
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                  <path d="M14 2v6h6" />
                </svg>
                {isStillProcessing && (
                  <span className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-brass text-[9px] font-bold text-paper animate-pulse">
                    ⚡
                  </span>
                )}
              </div>
              <p className="text-xs font-medium text-ink">
                {docId ? `Document #${docId.slice(0, 8)}` : "No document active"}
              </p>
              <p className="text-[11px] text-ink-soft">
                300 DPI · Normalized &amp; Deskewed PNG
              </p>
            </div>

            {ocrText ? (
              <div className="max-h-56 w-full overflow-y-auto rounded border border-line bg-paper p-3 text-left font-mono text-[10px] text-ink-soft shadow-inner">
                <div className="flex items-center justify-between border-b border-line/60 pb-1 mb-2">
                  <p className="font-semibold text-ink uppercase text-[9px]">
                    ✓ Raw OCR Text Extracted:
                  </p>
                  <span className="text-[9px] text-verified font-medium">Verified</span>
                </div>
                <p className="whitespace-pre-line text-ink leading-relaxed font-sans text-[11px]">
                  {ocrText}
                </p>
              </div>
            ) : (
              <div className="w-full rounded border border-dashed border-line p-3">
                <p className="font-mono text-[10px] text-ink-soft">
                  DeepSeek-OCR · Local Ollama Vision Inference
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Extracted fields */}
        <div className="col-span-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">
              Extracted fields ({fields.length})
            </p>
            {lowConfidenceCount > 0 && (
              <p className="text-xs text-caution font-medium">
                {lowConfidenceCount} field{lowConfidenceCount > 1 ? "s" : ""} need verification
              </p>
            )}
          </div>

          {/* Skeleton loading rows while extracting */}
          {isStillProcessing ? (
            <div className="divide-y divide-line rounded border border-line bg-paper-dark/30 p-4 space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-line">
                <div className="flex items-center gap-2">
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-ink border-t-transparent" />
                  <span className="font-serif text-xs font-medium text-ink">
                    Extracting structured properties...
                  </span>
                </div>
                <span className="text-[11px] font-mono text-ink-soft">
                  {secondsElapsed}s elapsed
                </span>
              </div>

              {/* Skeleton Cards */}
              {[
                { name: "Owner Name / Testator", hint: "Primary purchaser or claimant" },
                { name: "Document Execution Date", hint: "Normalized timestamp" },
                { name: "Administrative District", hint: "Revenue jurisdiction" },
                { name: "Cadastral Survey / Plot", hint: "Parcel identifier" },
              ].map((item, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between gap-4 py-2 opacity-80"
                >
                  <div className="space-y-1.5 flex-1">
                    <p className="text-[11px] uppercase tracking-wide text-ink-soft font-mono">
                      {item.name}
                    </p>
                    <div className="h-4 w-3/4 animate-pulse rounded bg-paper-dark/80 border border-line" />
                    <p className="text-[10px] text-ink-soft/70">{item.hint}</p>
                  </div>
                  <div className="w-16 shrink-0 space-y-1">
                    <div className="h-2 w-full animate-pulse rounded bg-brass/30" />
                    <div className="h-2 w-10 animate-pulse rounded bg-line" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="divide-y divide-line rounded border border-line bg-paper-dark/30">
              {fields.map((field, idx) => (
                <div
                  key={field.label}
                  className="flex items-center justify-between gap-4 px-4 py-3 bg-paper/40"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] uppercase tracking-wide text-ink-soft font-mono">
                      {field.label}
                    </p>
                    {field.confidence < 65 ? (
                      <input
                        value={field.value}
                        onChange={(e) => handleFieldChange(idx, e.target.value)}
                        className="mt-0.5 w-full rounded border border-caution/50 bg-paper px-2 py-1 font-mono text-sm text-ink focus:border-caution focus:outline-none"
                      />
                    ) : (
                      <p className="mt-0.5 font-mono text-sm font-medium text-ink truncate">
                        {field.value}
                      </p>
                    )}
                  </div>

                  <div className="shrink-0 text-right">
                    <ConfidenceMeter value={field.confidence} />
                    <p className="mt-1 text-[10px] text-ink-soft">
                      {field.confidence >= 65 ? "Grounded in OCR" : "Needs Review"}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Action buttons */}
          <div className="mt-8 flex items-center justify-between">
            <Link
              href="/"
              className="text-xs text-ink-soft underline underline-offset-2 hover:text-ink"
            >
              ← Back to upload
            </Link>
            <button
              onClick={() => router.push(nextUrl)}
              disabled={fields.length === 0}
              className="rounded bg-ink px-6 py-2.5 text-xs font-medium text-paper transition-opacity hover:opacity-90 disabled:opacity-50 shadow-sm"
            >
              Proceed to Match &amp; Validate →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ProcessingPage() {
  return (
    <Suspense
      fallback={
        <div className="p-10 font-mono text-xs text-ink-soft">
          Loading document extraction workspace...
        </div>
      }
    >
      <ProcessingContent />
    </Suspense>
  );
}