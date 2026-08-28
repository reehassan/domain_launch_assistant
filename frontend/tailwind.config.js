/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#14171F",
        paper: "#F7F6F2",
        signal: "#FF5A36",
        live: "#1FAA59",
        wire: "#4C5FD5",
        hairline: "#E4E2DA",
        reject: "#DC2626",
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
