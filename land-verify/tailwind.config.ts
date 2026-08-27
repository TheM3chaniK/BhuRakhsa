import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F6F2E8",
        "paper-dark": "#EFE9DA",
        ink: "#1D2733",
        "ink-soft": "#5B6675",
        brass: "#B08D3E",
        verified: "#3F6B4A",
        caution: "#B8853A",
        risk: "#9B3327",
        line: "#DDD5C0",
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "Helvetica", "Arial", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      borderRadius: {
        sm: "2px",
        DEFAULT: "3px",
      },
    },
  },
  plugins: [],
};
export default config;
