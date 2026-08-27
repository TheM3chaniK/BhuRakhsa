import { RiskLevel } from "@/lib/types";
import Stamp from "./Stamp";

const toneFor: Record<RiskLevel, "verified" | "caution" | "risk"> = {
  LOW: "verified",
  MEDIUM: "caution",
  HIGH: "risk",
};

export default function RiskBadge({ level }: { level: RiskLevel }) {
  return <Stamp tone={toneFor[level]}>{level} RISK</Stamp>;
}
