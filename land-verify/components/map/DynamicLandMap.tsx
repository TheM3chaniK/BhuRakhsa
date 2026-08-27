"use client";

import dynamic from "next/dynamic";
import type { ComponentProps } from "react";
import RealLandMap from "./RealLandMap";

// Export RealLandMap directly as client component with built-in dynamic leaflet resolution
export default function DynamicLandMap(props: ComponentProps<typeof RealLandMap>) {
  return <RealLandMap {...props} />;
}
