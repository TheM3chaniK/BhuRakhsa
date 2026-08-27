"use client";

import { useEffect, useRef, useState } from "react";
import type * as LeafletType from "leaflet";

export interface LatLngPoint {
  lat: number;
  lng: number;
}

interface RealLandMapProps {
  initialCenter?: [number, number]; // [lat, lng]
  initialZoom?: number;
  deedPolygon?: [number, number][]; // [[lat, lng], ...]
  cadastralPolygon?: [number, number][]; // [[lat, lng], ...]
  allowDrafting?: boolean;
  onDraftChange?: (coordinates: [number, number][], areaAcres: number) => void;
  className?: string;
  readOnly?: boolean;
}

// Calculate approximate spherical geodesic polygon area in acres
function calculateGeodesicAreaAcres(coords: [number, number][]): number {
  if (coords.length < 3) return 0;
  const R = 6378137; // Earth's radius in meters
  let area = 0;

  for (let i = 0; i < coords.length; i++) {
    const j = (i + 1) % coords.length;
    const lat1 = (coords[i][0] * Math.PI) / 180;
    const lat2 = (coords[j][0] * Math.PI) / 180;
    const lon1 = (coords[i][1] * Math.PI) / 180;
    const lon2 = (coords[j][1] * Math.PI) / 180;

    area += (lon2 - lon1) * (2 + Math.sin(lat1) + Math.sin(lat2));
  }

  area = (Math.abs(area) * R * R) / 2.0; // Square meters
  const acres = area * 0.000247105; // Convert sq meters to acres
  return Math.round(acres * 1000) / 1000;
}

export default function RealLandMap({
  initialCenter = [22.506, 88.382], // Hatgacha / Kolkata Cadastral Division
  initialZoom = 15,
  deedPolygon = [],
  cadastralPolygon = [],
  allowDrafting = true,
  onDraftChange,
  className = "h-[420px] w-full",
  readOnly = false,
}: RealLandMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<LeafletType.Map | null>(null);
  const leafletRef = useRef<typeof LeafletType | null>(null);

  // Layer references
  const deedLayerRef = useRef<LeafletType.Polygon | null>(null);
  const cadastralLayerRef = useRef<LeafletType.Polygon | null>(null);
  const draftLayerRef = useRef<LeafletType.Polygon | null>(null);
  const markersLayerGroupRef = useRef<LeafletType.LayerGroup | null>(null);

  const [isLeafletReady, setIsLeafletReady] = useState(false);
  const [isDrafting, setIsDrafting] = useState(false);
  const [draftPoints, setDraftPoints] = useState<[number, number][]>([]);
  const [calculatedArea, setCalculatedArea] = useState<number>(0);
  const [tileMode, setTileMode] = useState<"standard" | "satellite" | "topo">("standard");

  const [showDeed, setShowDeed] = useState(true);
  const [showCadastral, setShowCadastral] = useState(true);

  // 1. Asynchronously load Leaflet module on client mount
  useEffect(() => {
    let isMounted = true;
    import("leaflet").then((LModule) => {
      if (isMounted) {
        leafletRef.current = LModule.default || LModule;
        setIsLeafletReady(true);
      }
    }).catch((err) => {
      console.warn("Leaflet dynamic load failed:", err);
    });

    return () => {
      isMounted = false;
    };
  }, []);

  // 2. Initialize Leaflet Map once Leaflet is ready
  useEffect(() => {
    const L = leafletRef.current;
    if (!isLeafletReady || !L || !mapContainerRef.current) return;

    // Clean up previous instance if any
    if (mapInstanceRef.current) {
      try {
        mapInstanceRef.current.off();
        mapInstanceRef.current.remove();
      } catch {}
      mapInstanceRef.current = null;
    }

    const map = L.map(mapContainerRef.current, {
      center: initialCenter,
      zoom: initialZoom,
      zoomControl: true,
    });

    // Base Tile Layer
    const tileUrl =
      tileMode === "satellite"
        ? "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        : tileMode === "topo"
        ? "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
        : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

    const attribution =
      tileMode === "satellite"
        ? "&copy; Esri &mdash; Earthstar Geographics"
        : tileMode === "topo"
        ? "&copy; OpenTopoMap contributors"
        : "&copy; OpenStreetMap contributors";

    L.tileLayer(tileUrl, {
      maxZoom: 19,
      attribution,
    }).addTo(map);

    markersLayerGroupRef.current = L.layerGroup().addTo(map);
    mapInstanceRef.current = map;

    // Render Initial Polygons
    renderPolygons(map, L);

    // Click handler for drafting
    map.on("click", (e: LeafletType.LeafletMouseEvent) => {
      const { lat, lng } = e.latlng;
      setDraftPoints((prev) => {
        const next: [number, number][] = [...prev, [lat, lng]];
        const acres = calculateGeodesicAreaAcres(next);
        setCalculatedArea(acres);
        if (onDraftChange) onDraftChange(next, acres);
        return next;
      });
    });

    return () => {
      try {
        map.off();
        map.remove();
      } catch {}
      mapInstanceRef.current = null;
    };
  }, [isLeafletReady, tileMode]);

  // Update polygon layers whenever props or toggles change
  const renderPolygons = (map: LeafletType.Map, L: typeof LeafletType) => {
    if (!map || !L) return;

    // Clear existing polygon layers
    if (deedLayerRef.current) {
      try { map.removeLayer(deedLayerRef.current); } catch {}
      deedLayerRef.current = null;
    }
    if (cadastralLayerRef.current) {
      try { map.removeLayer(cadastralLayerRef.current); } catch {}
      cadastralLayerRef.current = null;
    }

    // 1. Cadastral Reference Polygon (Red/Crimson)
    if (showCadastral && cadastralPolygon && cadastralPolygon.length >= 3) {
      const cadPoly = L.polygon(cadastralPolygon, {
        color: "#9B3327",
        weight: 2.5,
        fillColor: "#9B3327",
        fillOpacity: 0.18,
      }).addTo(map);

      cadPoly.bindPopup(`
        <div style="font-family: inherit; font-size: 11px;">
          <strong style="color: #9B3327; text-transform: uppercase;">Cadastral Reference Parcel</strong><br/>
          <strong>Survey No:</strong> 142/3-B<br/>
          <strong>Tehsil:</strong> Hatgacha Division<br/>
          <strong>Mapped Area:</strong> 1.05 Acres (PostGIS SRID: 4326)<br/>
          <strong>Status:</strong> Authoritative Government Record
        </div>
      `);
      cadastralLayerRef.current = cadPoly;
    }

    // 2. Deed Declared Polygon (Brass / Gold Dashed)
    if (showDeed && deedPolygon && deedPolygon.length >= 3) {
      const deedPoly = L.polygon(deedPolygon, {
        color: "#B08D3E",
        weight: 3,
        dashArray: "6, 6",
        fillColor: "#B08D3E",
        fillOpacity: 0.22,
      }).addTo(map);

      deedPoly.bindPopup(`
        <div style="font-family: inherit; font-size: 11px;">
          <strong style="color: #B08D3E; text-transform: uppercase;">Deed Declared Boundary</strong><br/>
          <strong>Deed Area:</strong> 1.20 Acres<br/>
          <strong>Claimant:</strong> Ramesh Ghosh<br/>
          <strong>Spatial Discrepancy:</strong> +14.28% Variance
        </div>
      `);
      deedLayerRef.current = deedPoly;
    }

    // Fit map bounds to encompass polygons
    if (deedPolygon.length >= 3) {
      try {
        const bounds = L.latLngBounds(deedPolygon);
        map.fitBounds(bounds, { padding: [40, 40] });
      } catch {}
    }
  };

  useEffect(() => {
    const L = leafletRef.current;
    if (mapInstanceRef.current && L) {
      renderPolygons(mapInstanceRef.current, L);
    }
  }, [showDeed, showCadastral, deedPolygon, cadastralPolygon]);

  // Update Draft Layer whenever draftPoints change
  useEffect(() => {
    const map = mapInstanceRef.current;
    const L = leafletRef.current;
    if (!map || !L || !markersLayerGroupRef.current) return;

    markersLayerGroupRef.current.clearLayers();

    if (draftLayerRef.current) {
      try { map.removeLayer(draftLayerRef.current); } catch {}
      draftLayerRef.current = null;
    }

    if (draftPoints.length > 0) {
      // Draw draft vertex markers
      draftPoints.forEach((pt, idx) => {
        const marker = L.circleMarker(pt, {
          radius: 6,
          fillColor: "#1D2733",
          color: "#FAF8F2",
          weight: 2,
          fillOpacity: 1,
        });
        marker.bindTooltip(`Vertex ${idx + 1}`, { permanent: false, direction: "top" });
        markersLayerGroupRef.current?.addLayer(marker);
      });

      // Draw draft polyline or polygon
      if (draftPoints.length >= 3) {
        const dPoly = L.polygon(draftPoints, {
          color: "#2E5C38",
          weight: 2.5,
          dashArray: "4, 4",
          fillColor: "#2E5C38",
          fillOpacity: 0.25,
        }).addTo(map);

        draftLayerRef.current = dPoly;
      } else if (draftPoints.length === 2) {
        const dLine = L.polyline(draftPoints, {
          color: "#2E5C38",
          weight: 2,
          dashArray: "4, 4",
        }).addTo(map);
        markersLayerGroupRef.current.addLayer(dLine);
      }
    }
  }, [draftPoints]);

  const handleClearDraft = () => {
    setDraftPoints([]);
    setCalculatedArea(0);
    if (onDraftChange) onDraftChange([], 0);
  };

  const handleUndoPoint = () => {
    setDraftPoints((prev) => {
      const next = prev.slice(0, -1);
      const acres = calculateGeodesicAreaAcres(next);
      setCalculatedArea(acres);
      if (onDraftChange) onDraftChange(next, acres);
      return next;
    });
  };

  const handleUsePresetCadastral = () => {
    setDraftPoints(cadastralPolygon);
    const acres = calculateGeodesicAreaAcres(cadastralPolygon);
    setCalculatedArea(acres);
    if (onDraftChange) onDraftChange(cadastralPolygon, acres);
  };

  return (
    <div className="relative overflow-hidden rounded border border-line bg-paper">
      {/* Map Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between border-b border-line bg-paper-dark/60 px-4 py-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink">🗺️ Real Land Map (OpenStreetMap &amp; PostGIS):</span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setTileMode("standard")}
              className={`rounded px-2 py-0.5 text-[10px] font-medium ${
                tileMode === "standard" ? "bg-ink text-paper" : "bg-paper text-ink-soft hover:text-ink"
              }`}
            >
              Street
            </button>
            <button
              onClick={() => setTileMode("satellite")}
              className={`rounded px-2 py-0.5 text-[10px] font-medium ${
                tileMode === "satellite" ? "bg-ink text-paper" : "bg-paper text-ink-soft hover:text-ink"
              }`}
            >
              Satellite
            </button>
            <button
              onClick={() => setTileMode("topo")}
              className={`rounded px-2 py-0.5 text-[10px] font-medium ${
                tileMode === "topo" ? "bg-ink text-paper" : "bg-paper text-ink-soft hover:text-ink"
              }`}
            >
              Topographic
            </button>
          </div>
        </div>

        {/* Layer Toggles & Mode */}
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-[11px] text-ink cursor-pointer">
            <input
              type="checkbox"
              checked={showDeed}
              onChange={(e) => setShowDeed(e.target.checked)}
              className="accent-brass"
            />
            <span className="inline-block h-2 w-3 border border-brass border-dashed" /> Deed Claim
          </label>
          <label className="flex items-center gap-1.5 text-[11px] text-ink cursor-pointer">
            <input
              type="checkbox"
              checked={showCadastral}
              onChange={(e) => setShowCadastral(e.target.checked)}
              className="accent-risk"
            />
            <span className="inline-block h-2 w-3 bg-risk/30 border border-risk" /> Cadastral Parcel
          </label>

          {allowDrafting && !readOnly && (
            <button
              onClick={() => setIsDrafting(!isDrafting)}
              className={`rounded px-2.5 py-1 text-[11px] font-medium transition-colors ${
                isDrafting ? "bg-verified text-paper" : "border border-line bg-paper text-ink hover:bg-paper-dark"
              }`}
            >
              {isDrafting ? "✏️ Drafting Active (Click Map)" : "✏️ Draft Deed Boundary"}
            </button>
          )}
        </div>
      </div>

      {/* Drafting Control Bar */}
      {isDrafting && (
        <div className="flex items-center justify-between border-b border-verified/30 bg-verified/10 px-4 py-2 text-xs">
          <div className="flex items-center gap-3">
            <span className="font-medium text-verified">
              📍 Points Placed: <strong>{draftPoints.length}</strong>
            </span>
            <span className="font-mono text-ink">
              Calculated Area: <strong>{calculatedArea} Acres</strong>
            </span>
            {draftPoints.length < 3 && (
              <span className="text-[11px] text-ink-soft">
                (Click on the map to place at least 3 corner boundary vertices)
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleUsePresetCadastral}
              className="rounded border border-line bg-paper px-2 py-0.5 text-[11px] text-ink hover:bg-paper-dark"
            >
              Snap to Cadastral
            </button>
            <button
              onClick={handleUndoPoint}
              disabled={draftPoints.length === 0}
              className="rounded border border-line bg-paper px-2 py-0.5 text-[11px] text-ink hover:bg-paper-dark disabled:opacity-40"
            >
              Undo Point
            </button>
            <button
              onClick={handleClearDraft}
              disabled={draftPoints.length === 0}
              className="rounded border border-risk/40 bg-risk/10 px-2 py-0.5 text-[11px] text-risk hover:bg-risk/20 disabled:opacity-40"
            >
              Clear
            </button>
          </div>
        </div>
      )}

      {/* Leaflet Map Canvas Container */}
      <div ref={mapContainerRef} className={className}>
        {!isLeafletReady && (
          <div className="flex h-full w-full items-center justify-center bg-paper-dark/30 text-xs font-mono text-ink-soft">
            Initializing OpenStreetMap &amp; PostGIS GIS Engine...
          </div>
        )}
      </div>

      {/* Map Footer Coordinates & Overlay Status */}
      <div className="flex items-center justify-between border-t border-line bg-paper-dark/30 px-4 py-1.5 text-[11px] font-mono text-ink-soft">
        <span>CRS: EPSG:4326 (WGS 84 PostGIS)</span>
        <span>Center: 22.506°N, 88.382°E · Hatgacha Revenue Division</span>
        <span>Tile Source: OpenStreetMap contributors</span>
      </div>
    </div>
  );
}
