export default function ConfidenceMeter({ value }: { value: number }) {
  const tone =
    value >= 85 ? "bg-verified" : value >= 65 ? "bg-caution" : "bg-risk";

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-line">
        <div className={`h-full ${tone}`} style={{ width: `${value}%` }} />
      </div>
      <span className="font-mono text-[11px] text-ink-soft">{value}%</span>
    </div>
  );
}
