type StampTone = "verified" | "caution" | "risk" | "neutral";

const toneStyles: Record<StampTone, string> = {
  verified: "border-verified text-verified",
  caution: "border-caution text-caution",
  risk: "border-risk text-risk",
  neutral: "border-ink-soft text-ink-soft",
};

export default function Stamp({
  children,
  tone = "neutral",
  className = "",
}: {
  children: React.ReactNode;
  tone?: StampTone;
  className?: string;
}) {
  return (
    <span
      className={`inline-block -rotate-2 select-none border-2 border-dashed px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-widest ${toneStyles[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
