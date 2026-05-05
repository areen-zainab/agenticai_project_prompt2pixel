/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#F5F2ED",
        surface: "#FFFFFF",
        surface2: "#FAF8F5",
        border: "#DDD9D2",
        border2: "#EBE7E1",
        ink: "#18150F",
        ink2: "#4A4540",
        muted: "#837D76",
        accent: "#B84A1E",
        "accent-lt": "#F7EAE4",
        blue: "#1E4476",
        "blue-lt": "#EBF0F9",
        green: "#245C3E",
        "green-lt": "#E2F0E9",
        red: "#8C1F1F",
        "red-lt": "#FAEAEA",
        gold: "#9B7D3A",
        "gold-lt": "#FBF4E4",
      },
      borderRadius: {
        r: "8px",
        "r-lg": "14px",
      },
      boxShadow: {
        "shadow-sm": "0 1px 4px rgba(24,21,15,.07)",
        shadow: "0 3px 16px rgba(24,21,15,.09)",
      },
      fontFamily: {
        display: ["'Cormorant Garamond'", "Georgia", "serif"],
        body: ["'Inter'", "system-ui", "sans-serif"],
      },
      transitionDuration: {
        DEFAULT: "180ms",
      },
      transitionTimingFunction: {
        DEFAULT: "cubic-bezier(.4,0,.2,1)",
      },
    },
  },
  plugins: [],
}
