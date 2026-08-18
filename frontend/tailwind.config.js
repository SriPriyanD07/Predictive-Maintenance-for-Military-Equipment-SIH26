/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Operations-center palette: dark neutral base + status accents.
        base: {
          950: "#0a0e14",
          900: "#0f151d",
          850: "#131a24",
          800: "#182130",
          700: "#243040",
          600: "#334154",
          500: "#4a5b72",
        },
        ink: {
          100: "#eef2f7",
          300: "#b7c2d0",
          500: "#8b98ab",
        },
        status: {
          healthy: "#22c55e",
          healthyBg: "rgba(34,197,94,0.12)",
          warning: "#f5a524",
          warningBg: "rgba(245,165,36,0.12)",
          critical: "#ef4444",
          criticalBg: "rgba(239,68,68,0.14)",
          info: "#38bdf8",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 0 rgba(255,255,255,0.03) inset, 0 8px 24px rgba(0,0,0,0.35)",
      },
      keyframes: {
        pulseRing: {
          "0%": { boxShadow: "0 0 0 0 rgba(239,68,68,0.45)" },
          "70%": { boxShadow: "0 0 0 8px rgba(239,68,68,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(239,68,68,0)" },
        },
      },
      animation: {
        "pulse-ring": "pulseRing 2s cubic-bezier(0.4,0,0.6,1) infinite",
      },
    },
  },
  plugins: [],
};
