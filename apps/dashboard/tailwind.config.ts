import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          950: "#08090c",
          900: "#0d0f14",
          800: "#14171f",
          700: "#1c202b",
          600: "#2a2f3d",
        },
        ink: {
          100: "#e7e9ee",
          300: "#a8adba",
          500: "#6b7180",
        },
        signal: {
          green: "#3ddc84",
          yellow: "#e8b93f",
          orange: "#e08a3c",
          red: "#e0524c",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
