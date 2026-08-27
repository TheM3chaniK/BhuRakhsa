"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Stamp from "@/components/ui/Stamp";
import PageHeader from "@/components/ui/PageHeader";
import DynamicLandMap from "@/components/map/DynamicLandMap";
import { api } from "@/lib/api";
import { AreaResponse } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

export default function UploadPage() {
  const router = useRouter();
  const { user } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [areas, setAreas] = useState<AreaResponse[]>([]);
  const [selectedAreaId, setSelectedAreaId] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [caseTitle, setCaseTitle] = useState("Land Deed Verification");
  const [isUploading, setIsUploading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [draftVertices, setDraftVertices] = useState<[number, number][]>([]);
  const [draftAreaAcres, setDraftAreaAcres] = useState<number>(0);

  useEffect(() => {
    api.listAreas().then((res) => {
      if (res.items && res.items.length > 0) {
        setAreas(res.items);
        setSelectedAreaId(res.items[0].id);
      }
    }).catch(() => {});
  }, []);

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

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setErrorMessage(null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setErrorMessage(null);
    }
  };

  const handleUploadAndProcess = async () => {
    if (!file) {
      setErrorMessage("Please select a document to upload.");
      return;
    }

    if (!user) {
      router.push("/login");
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);

    try {
      // 1. Select valid area ID
      let areaId = selectedAreaId;
      if (!areaId && areas.length > 0) {
        areaId = areas[0].id;
      }

      if (!areaId) {
        const areaList = await api.listAreas();
        areaId = areaList.items[0]?.id;
      }

      if (!areaId) {
        throw new Error("No active administrative area found. Please ensure database is seeded.");
      }

      // 2. Create Case
      setStatusMessage("Creating verification case in registry...");
      const createdCase = await api.createCase({
        area_id: areaId,
        title: caseTitle || file.name,
        description: `Document uploaded: ${file.name}`,
      });

      // Save drafted vertices to localStorage if citizen plotted boundaries
      if (draftVertices.length > 0) {
        try {
          if (typeof window !== "undefined") {
            localStorage.setItem(`case_draft_vertices_${createdCase.id}`, JSON.stringify(draftVertices));
            localStorage.setItem(`case_draft_area_${createdCase.id}`, draftAreaAcres.toString());
            localStorage.setItem("last_draft_vertices", JSON.stringify(draftVertices));
          }
        } catch {}
      }

      // 3. Upload Document
      setStatusMessage("Uploading document to secure storage...");
      const doc = await api.uploadDocument(createdCase.id, file, "deed");

      // 4. Enqueue OCR Processing
      setStatusMessage("Enqueuing DeepSeek OCR processing...");
      try {
        await api.processDocument(doc.id);
      } catch {}

      // 5. Submit Case for Processing
      setStatusMessage("Submitting case to verification pipeline...");
      try {
        await api.submitCase(createdCase.id);
      } catch {}

      setStatusMessage("Ready! Navigating to extraction...");
      router.push(`/processing?caseId=${createdCase.id}&docId=${doc.id}`);
    } catch (err: any) {
      console.error("Upload flow error:", err);
      setErrorMessage(err.message || "Failed to process document.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-10 py-14">
      <PageHeader
        step="Step 01 · Upload & Ingestion"
        title="Turn a land record into an evidence-linked verification case."
        description="Upload a scan, photo, or PDF deed. The system reads it through DeepSeek OCR, extracts structured fields with bounding boxes, and cross-checks against government databases and PostGIS maps."
      />

      {/* Area & Case Setup */}
      <div className="mt-8 grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium uppercase tracking-wider text-ink-soft">
            Administrative Area / District
          </label>
          <select
            value={selectedAreaId}
            onChange={(e) => setSelectedAreaId(e.target.value)}
            className="mt-1.5 w-full rounded border border-line bg-paper-dark/60 px-3 py-2 text-xs text-ink focus:border-brass focus:outline-none"
          >
            {areas.length === 0 ? (
              <option value="">Loading areas from PostgreSQL...</option>
            ) : (
              areas.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.code})
                </option>
              ))
            )}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium uppercase tracking-wider text-ink-soft">
            Case Title / Reference
          </label>
          <input
            type="text"
            value={caseTitle}
            onChange={(e) => setCaseTitle(e.target.value)}
            placeholder="e.g. Hatgacha Plot 142 Deed"
            className="mt-1.5 w-full rounded border border-line bg-paper-dark/60 px-3 py-2 text-xs text-ink focus:border-brass focus:outline-none"
          />
        </div>
      </div>

      {/* Hidden File Input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        accept=".pdf,.png,.jpg,.jpeg"
        className="hidden"
      />

      {/* Drop zone */}
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`mt-6 cursor-pointer rounded border-2 border-dashed transition-colors ${
          file ? "border-verified bg-verified/5" : "border-line bg-paper-dark/60 hover:border-brass"
        } px-8 py-14 text-center`}
      >
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border-2 border-brass/40 text-brass">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M12 16V4M12 4l-4 4M12 4l4 4" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>

        {file ? (
          <div>
            <p className="text-sm font-medium text-ink">
              Selected: <span className="font-mono text-brass">{file.name}</span>
            </p>
            <p className="mt-1 text-xs text-ink-soft">
              {(file.size / 1024 / 1024).toFixed(2)} MB · Click to choose different file
            </p>
          </div>
        ) : (
          <div>
            <p className="text-sm font-medium text-ink">
              Drag &amp; drop a deed here, or{" "}
              <span className="text-brass underline underline-offset-2">browse files</span>
            </p>
            <p className="mt-1.5 text-xs text-ink-soft">
              PDF, JPG, or PNG (up to 25MB) · Scanned, handwritten, or multilingual deeds supported
            </p>
          </div>
        )}
      </div>

      {errorMessage && (
        <div className="mt-4 rounded border border-risk/40 bg-risk/10 px-4 py-2.5 text-xs text-risk">
          {errorMessage}
        </div>
      )}

      {statusMessage && (
        <div className="mt-4 flex items-center gap-2 rounded border border-brass/40 bg-brass/10 px-4 py-2.5 text-xs text-ink">
          <span className="h-2 w-2 animate-ping rounded-full bg-brass" />
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Real Map Land Drafting Section */}
      <div className="mt-8">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-medium uppercase tracking-wider text-ink-soft">
            📍 Real OpenStreetMap Land Drafter (Optional Deed Boundary)
          </p>
          <span className="font-mono text-[11px] text-brass">
            {draftVertices.length > 0
              ? `${draftVertices.length} vertices drafted (${draftAreaAcres} acres)`
              : "SRID: 4326 · Hatgacha Cadastral Grid"}
          </span>
        </div>
        <DynamicLandMap
          initialCenter={[22.506, 88.382]}
          initialZoom={15}
          className="h-[320px] w-full"
          allowDrafting={true}
          onDraftChange={(coords, acres) => {
            setDraftVertices(coords);
            setDraftAreaAcres(acres);
          }}
        />
        <p className="mt-1.5 text-[11px] text-ink-soft">
          💡 Click anywhere on the map or use <strong>"✏️ Draft Deed Boundary"</strong> to plot your land corner vertices.
        </p>
      </div>

      {/* Action button */}
      <div className="mt-8 flex items-center justify-between">
        <Link href="/queue" className="text-xs text-ink-soft underline underline-offset-2 hover:text-ink">
          {user?.role === "CIVILIAN" ? "← View my submitted applications" : "← View officer review queue"}
        </Link>
        <button
          onClick={handleUploadAndProcess}
          disabled={isUploading || !file}
          className="rounded bg-ink px-6 py-2.5 text-xs font-medium text-paper transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {isUploading ? "Uploading & Processing..." : "Upload & Run Extraction →"}
        </button>
      </div>

      <div className="mt-12 grid grid-cols-3 gap-4 border-t border-line pt-6 text-xs text-ink-soft">
        <p><span className="font-medium text-ink">Citizens</span> upload property records</p>
        <p><span className="font-medium text-ink">Automated Engine</span> verifies GIS &amp; registry</p>
        <p><span className="font-medium text-ink">Area Officers</span> make evidence-based decisions</p>
      </div>
    </div>
  );
}