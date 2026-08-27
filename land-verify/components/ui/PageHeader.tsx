export default function PageHeader({
  step,
  title,
  description,
}: {
  step: string;
  title: string;
  description: string;
}) {
  return (
    <div className="mb-8">
      <p className="mb-2 font-mono text-[11px] uppercase tracking-widest text-ink-soft">
        {step}
      </p>
      <h1 className="font-serif text-2xl font-semibold leading-tight text-ink">
        {title}
      </h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft">
        {description}
      </p>
    </div>
  );
}