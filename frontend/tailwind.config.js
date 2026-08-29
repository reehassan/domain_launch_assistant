/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // ---- Light theme, greenish/black/white (name.com-inspired) ----
        // Same semantic token names as before — every component that
        // referenced bg-paper / text-ink / border-hairline / bg-signal
        // etc. re-themes automatically just from these values changing.
        paper: "#F6F8F5",     // page background — warm off-white, faint green tint
        surface: "#FFFFFF",   // card background
        elevated: "#EEF5F0",  // highlighted box (AI pick, selected state) — pale mint
        ink: "#11151A",       // near-black text
        hairline: "#E2E6E1",  // borders/dividers
        signal: "#0E7A50",    // primary action green — the one confident accent
        live: "#1D9A6C",      // success/"done" green — distinct from signal
        wire: "#0F6E7A",      // secondary/AI accent — deep teal, stays in the green family
        hold: "#A16207",      // amber — now a real token instead of stock amber-500
        reject: "#C23434",    // error red
      },
      fontFamily: {
        display: ["Space Grotesk", "sans-serif"],
        sans: ["Inter", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
      keyframes: {
        "stamp-drop": {
          "0%": { opacity: "0", transform: "translateY(-10px) rotate(-14deg) scale(1.3)" },
          "60%": { opacity: "1", transform: "translateY(2px) rotate(-8deg) scale(0.95)" },
          "100%": { opacity: "1", transform: "translateY(0) rotate(-6deg) scale(1)" },
        },
        "stamp-hover": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-4px)" },
        },
      },
      animation: {
        "stamp-drop": "stamp-drop 240ms ease-out",
        "stamp-hover": "stamp-hover 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};