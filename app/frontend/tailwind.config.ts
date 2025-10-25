import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#F4B740",
          glow: "#FFCE73",
          contrast: "#211C1C"
        },
        accent: {
          jade: "#4AD991",
          lilac: "#B99CFF"
        },
        background: "#211C1C",
        surface: "#2A2222",
        "surface-elevated": "#322826",
        "surface-muted": "#372D2B",
        border: "rgba(255, 240, 224, 0.12)",
        control: "#3D322F",
        text: {
          primary: "#F9F5F0",
          muted: "#CBBFBA",
          subtle: "#9F8D86"
        }
      },
      boxShadow: {
        panel: "0 40px 120px rgba(12, 6, 4, 0.45)",
        card: "0 28px 80px rgba(19, 11, 8, 0.55)"
      }
    }
  },
  plugins: []
};

export default config;
