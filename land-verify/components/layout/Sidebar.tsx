"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const steps = [
  { n: "01", label: "Upload", href: "/" },
  { n: "02", label: "Read & Extract", href: "/processing" },
  { n: "03", label: "Match & Validate", href: "/validate" },
  { n: "04", label: "Risk Result", href: "/result" },
  { n: "05", label: "Review Queue", href: "/queue" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col justify-between border-r border-line bg-paper-dark px-5 py-6">
      <div>
        <div className="mb-8">
          <p className="font-serif text-lg leading-tight text-ink">
            BhuRakhsa<span className="text-brass"></span>
          </p>
          </div>

        <nav className="flex flex-col">
          {steps.map((step) => {
            const active =
              step.href === "/" ? pathname === "/" : pathname.startsWith(step.href);
            return (
              <Link
                key={step.href}
                href={step.href}
                className={`group flex items-baseline gap-3 border-l-2 py-2.5 pl-3 text-sm transition-colors ${
                  active
                    ? "border-brass text-ink"
                    : "border-transparent text-ink-soft hover:border-line hover:text-ink"
                }`}
              >
                <span className="font-mono text-[11px] text-ink-soft">{step.n}</span>
                <span className={active ? "font-medium" : ""}>{step.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="border-t border-line pt-4">
        <p className="text-[11px] leading-relaxed text-ink-soft">
          Screening only. A human officer makes the final decision on every
          doubtful record.
        </p>
      </div>
    </aside>
  );
}
