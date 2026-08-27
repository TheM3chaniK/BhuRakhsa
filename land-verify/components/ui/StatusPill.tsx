import { MatchStatus } from "@/lib/types";
import Stamp from "./Stamp";

const toneFor: Record<MatchStatus, "verified" | "caution" | "risk" | "neutral"> = {
  MATCHED: "verified",
  MISMATCH: "risk",
  MISSING: "caution",
  CANNOT_CHECK: "neutral",
};

const labelFor: Record<MatchStatus, string> = {
  MATCHED: "Matched",
  MISMATCH: "Mismatch",
  MISSING: "Missing",
  CANNOT_CHECK: "Cannot check",
};

export default function StatusPill({ status }: { status: MatchStatus }) {
  return <Stamp tone={toneFor[status]}>{labelFor[status]}</Stamp>;
}