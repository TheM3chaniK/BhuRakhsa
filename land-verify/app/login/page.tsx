"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const router = useRouter();
  const { login, register } = useAuth();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === "login") {
        if (!email.trim() || !password.trim()) {
          throw new Error("Please enter your email and password.");
        }
        await login(email.trim(), password);
      } else {
        if (!fullName.trim()) {
          throw new Error("Please enter your full name.");
        }
        if (!email.trim()) {
          throw new Error("Please enter a valid email address.");
        }
        if (password.length < 8) {
          throw new Error("Password must be at least 8 characters long.");
        }
        await register(
          email.trim(),
          password,
          fullName.trim(),
          phone.trim() || undefined
        );
      }
      router.push("/");
    } catch (err: any) {
      console.error("Auth error:", err);
      setError(err.message || "Authentication failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleInstantDemoLogin = async (demoEmail: string, demoPass: string) => {
    setMode("login");
    setEmail(demoEmail);
    setPassword(demoPass);
    setError(null);
    setLoading(true);

    try {
      await login(demoEmail, demoPass);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4 py-12">
      <div className="w-full max-w-md rounded-lg border border-line bg-paper-dark/30 p-8 shadow-sm">
        {/* Header */}
        <div className="mb-6 text-center">
          <h1 className="font-serif text-2xl text-ink">
            Bhu<span className="text-brass">Raksha</span>
          </h1>
          <p className="mt-1 text-[11px] uppercase tracking-widest text-ink-soft">
            Property Document Verification &amp; Registry Portal
          </p>
        </div>

        {/* Tab switch */}
        <div className="mb-6 flex rounded border border-line bg-paper-dark p-1 text-xs">
          <button
            type="button"
            onClick={() => {
              setMode("login");
              setError(null);
            }}
            className={`flex-1 rounded py-1.5 font-medium transition-colors ${
              mode === "login"
                ? "bg-paper text-ink shadow-sm"
                : "text-ink-soft hover:text-ink"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("register");
              setError(null);
            }}
            className={`flex-1 rounded py-1.5 font-medium transition-colors ${
              mode === "register"
                ? "bg-paper text-ink shadow-sm"
                : "text-ink-soft hover:text-ink"
            }`}
          >
            Sign Up (Citizen)
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-4 rounded border border-risk/40 bg-risk/10 px-3 py-2 text-xs text-risk">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {mode === "register" && (
            <div>
              <label className="block font-medium text-ink">Full Name</label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Ramesh Ghosh"
                className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink placeholder:text-ink-soft/60 focus:border-brass focus:outline-none"
              />
            </div>
          )}

          <div>
            <label className="block font-medium text-ink">Email Address</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink placeholder:text-ink-soft/60 focus:border-brass focus:outline-none"
            />
          </div>

          {mode === "register" && (
            <div>
              <label className="block font-medium text-ink">
                Phone Number <span className="text-ink-soft">(Optional)</span>
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+91 98765 43210"
                className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink placeholder:text-ink-soft/60 focus:border-brass focus:outline-none"
              />
            </div>
          )}

          <div>
            <label className="block font-medium text-ink">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink placeholder:text-ink-soft/60 focus:border-brass focus:outline-none"
            />
            {mode === "register" && (
              <p className="mt-1 text-[10px] text-ink-soft">
                Must be at least 8 characters.
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="mt-2 w-full rounded bg-ink py-2.5 font-medium text-paper transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {loading
              ? "Authenticating with live DB..."
              : mode === "login"
              ? "Sign In to Portal"
              : "Create Citizen Account"}
          </button>
        </form>

        {/* Quick Demo Credentials Helper */}
        <div className="mt-6 border-t border-line/60 pt-4">
          <p className="text-[10px] font-medium uppercase tracking-wider text-ink-soft mb-2 text-center">
            Instant Demo Sign-In (Live DB)
          </p>
          <div className="grid grid-cols-2 gap-1.5 text-[11px]">
            <button
              type="button"
              disabled={loading}
              onClick={() => handleInstantDemoLogin("officer@example.com", "Officer@12345678!")}
              className="rounded border border-line bg-paper px-2.5 py-1.5 text-left text-ink-soft hover:border-brass hover:text-ink transition-colors disabled:opacity-50"
              title="Officer Ramesh Ghosh (Area Officer)"
            >
              👮 <strong>Officer:</strong> Ramesh
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => handleInstantDemoLogin("anita@example.com", "Citizen@12345678!")}
              className="rounded border border-line bg-paper px-2.5 py-1.5 text-left text-ink-soft hover:border-brass hover:text-ink transition-colors disabled:opacity-50"
              title="Anita Mondal (Citizen)"
            >
              👤 <strong>Citizen:</strong> Anita
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => handleInstantDemoLogin("citizen@example.com", "Citizen@12345678!")}
              className="rounded border border-line bg-paper px-2.5 py-1.5 text-left text-ink-soft hover:border-brass hover:text-ink transition-colors disabled:opacity-50"
              title="Citizen User"
            >
              👤 <strong>Citizen:</strong> User
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => handleInstantDemoLogin("admin@example.com", "Admin@12345678!")}
              className="rounded border border-line bg-paper px-2.5 py-1.5 text-left text-ink-soft hover:border-brass hover:text-ink transition-colors disabled:opacity-50"
              title="System Administrator"
            >
              🛡️ <strong>Super Admin</strong>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
