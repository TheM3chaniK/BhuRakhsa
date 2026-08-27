"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useState, useEffect } from "react";
import Stamp from "../ui/Stamp";
import { api } from "@/lib/api";
import { AreaResponse, isOfficerRole, isAdminRole } from "@/lib/types";

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [officerAreas, setOfficerAreas] = useState<AreaResponse[]>([]);

  const isOfficer = isOfficerRole(user?.role);
  const isAdmin = isAdminRole(user?.role);
  const isCivilian = !isOfficer && !isAdmin;

  useEffect(() => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    fetch(`${baseUrl}/health`)
      .then((res) => setBackendOnline(res.ok))
      .catch(() => setBackendOnline(false));

    if (isOfficer) {
      api
        .getOfficerAreas()
        .then((res) => {
          if (res.areas) setOfficerAreas(res.areas);
        })
        .catch(() => {});
    }
  }, [user, isOfficer]);

  if (pathname === "/login") {
    return null;
  }

  // Navigation Links strictly tailored by Role
  const civilianSteps = [
    { n: "01", label: "Upload & Case", href: "/" },
    { n: "02", label: "Read & Extract", href: "/processing" },
    { n: "03", label: "Match & Validate", href: "/validate" },
    { n: "04", label: "Risk Result", href: "/result" },
    { n: "05", label: "My Applications", href: "/queue" },
  ];

  const officerSteps = [
    { n: "01", label: "Assigned Area Queue", href: "/queue" },
    { n: "02", label: "Review Ready Cases", href: "/queue?status=REVIEW_READY" },
    { n: "03", label: "In Progress Reviews", href: "/queue?status=UNDER_REVIEW" },
    { n: "04", label: "Awaiting Citizen Proof", href: "/queue?status=PROOF_REQUIRED" },
    { n: "05", label: "Solved & Approved", href: "/queue?status=APPROVED" },
  ];

  const adminSteps = [
    { n: "01", label: "👨‍💼 Area Officers", href: "/admin/officers" },
    { n: "02", label: "📋 Global Cases Queue", href: "/queue" },
  ];

  const steps = isAdmin ? adminSteps : isOfficer ? officerSteps : civilianSteps;

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col justify-between border-r border-line bg-paper-dark px-5 py-6">
      <div>
        {/* Brand Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <Link
              href={isAdmin ? "/admin/officers" : isOfficer ? "/queue" : "/"}
              className="font-serif text-lg leading-tight text-ink hover:opacity-90"
            >
              Bhu<span className="text-brass">Raksha</span>
            </Link>
            <div
              className="flex items-center gap-1.5"
              title={backendOnline ? "API Live" : "API Offline"}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  backendOnline ? "bg-verified" : "bg-caution"
                }`}
              />
              <span className="font-mono text-[9px] uppercase tracking-wider text-ink-soft">
                {backendOnline ? "Online" : "Offline"}
              </span>
            </div>
          </div>
          <p className="mt-0.5 text-[10px] uppercase tracking-widest text-ink-soft">
            {isOfficer
              ? "Area Officer Verification Portal"
              : isAdmin
              ? "Super Administrator Console"
              : "Citizen Land Record Verification"}
          </p>
        </div>

        {/* Assigned Area Badge for Officers */}
        {isOfficer && officerAreas.length > 0 && (
          <div className="mb-4 rounded border border-brass/40 bg-brass/10 p-2.5 text-xs">
            <p className="text-[9px] font-bold uppercase tracking-wider text-brass">
              📍 Dedicated Jurisdiction:
            </p>
            <p className="mt-0.5 font-medium text-ink text-[11px] truncate">
              {officerAreas.map((a) => `${a.name} (${a.code})`).join(", ")}
            </p>
          </div>
        )}

        {/* Admin Quick Callout */}
        {isAdmin && (
          <div className="mb-4 rounded border border-risk/40 bg-risk/10 p-2.5 text-xs">
            <p className="text-[9px] font-bold uppercase tracking-wider text-risk">
              🛡️ Super Administrator:
            </p>
            <p className="mt-0.5 font-medium text-ink text-[11px]">
              Provision &amp; manage dedicated Area Officers.
            </p>
          </div>
        )}

        {/* Navigation Menu */}
        <div className="mb-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-soft px-1 mb-1">
            {isAdmin ? "Admin Controls" : isOfficer ? "Officer Actions" : "Verification Pipeline"}
          </p>
          <nav className="flex flex-col space-y-0.5">
            {steps.map((step) => {
              const active =
                step.href === "/"
                  ? pathname === "/"
                  : step.href === "/queue"
                  ? pathname === "/queue"
                  : pathname.startsWith(step.href.split("?")[0]);

              return (
                <Link
                  key={step.label}
                  href={step.href}
                  className={`group flex items-baseline gap-3 border-l-2 py-2 pl-3 text-xs transition-colors ${
                    active
                      ? "border-brass bg-paper/60 text-ink font-medium"
                      : "border-transparent text-ink-soft hover:border-line hover:text-ink"
                  }`}
                >
                  <span className="font-mono text-[10px] text-ink-soft">{step.n}</span>
                  <span>{step.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      {/* User Footer Profile */}
      <div className="border-t border-line pt-4 space-y-3">
        {user ? (
          <div className="rounded border border-line bg-paper/60 p-3">
            <div className="flex items-center justify-between">
              <p className="font-medium text-xs text-ink truncate max-w-[130px]">
                {user.full_name}
              </p>
              <Stamp
                tone={
                  isOfficer
                    ? "caution"
                    : isAdmin
                    ? "risk"
                    : "neutral"
                }
              >
                {isOfficer
                  ? "Officer"
                  : isAdmin
                  ? "Admin"
                  : "Citizen"}
              </Stamp>
            </div>
            <p className="mt-1 font-mono text-[10px] text-ink-soft truncate">{user.email}</p>
            <div className="mt-2.5 pt-2 border-t border-line/60 flex items-center justify-between">
              <span className="text-[9px] uppercase tracking-wider text-ink-soft">
                {isOfficer
                  ? "Area Officer"
                  : isAdmin
                  ? "Administrator"
                  : "Citizen Account"}
              </span>
              <button
                onClick={() => logout()}
                className="text-[11px] font-medium text-risk hover:underline"
              >
                Log Out
              </button>
            </div>
          </div>
        ) : (
          <div className="rounded border border-line bg-paper/60 p-3 text-center">
            <p className="text-xs text-ink-soft mb-2">Not signed in</p>
            <Link
              href="/login"
              className="inline-block w-full rounded bg-ink py-1.5 text-xs font-medium text-paper hover:bg-ink/90"
            >
              Sign In / Register
            </Link>
          </div>
        )}

        <p className="text-[10px] leading-relaxed text-ink-soft">
          {isAdmin
            ? "Super Admin Console: Provision, edit, assign, and deactivate Area Officers."
            : isOfficer
            ? "Assigned Officer Console: Validating deeds & marking cases as solved within dedicated jurisdiction."
            : "Citizen Portal: Upload property deed and track verification milestones."}
        </p>
      </div>
    </aside>
  );
}
