/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          app: "#000000",
          page: "#39383D",
          card: "#1D1D1D",
          secondary: "#222222",
          hover: "#2B2B2B",
        },
        content: {
          primary: "#F5F5F5",
          secondary: "#A7A7A7",
          muted: "#707070",
          disabled: "#505050",
        },
        brand: {
          primary: "#D98CB3",
          secondary: "#A878FF",
          accent: "#66C7FF",
        },
        status: {
          safe: "#39D98A",
          attention: "#F2C94C",
          highRisk: "#FF6B7A",
          critical: "#FF4D4D",
        },
        subtle: {
          border: "#303030",
        },
      },
      borderRadius: {
        sm: "6px",
        md: "10px",
        card: "14px",
        lg: "16px",
        pill: "9999px",
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
      },
      fontSize: {
        "display": ["32px", { lineHeight: "40px", fontWeight: "500" }],
        "page-title": ["26px", { lineHeight: "34px", fontWeight: "500" }],
        "section": ["18px", { lineHeight: "26px", fontWeight: "500" }],
        "card-title": ["14px", { lineHeight: "20px", fontWeight: "500" }],
        "body": ["13px", { lineHeight: "18px", fontWeight: "400" }],
        "caption": ["11px", { lineHeight: "16px", fontWeight: "400" }],
        "nav": ["13px", { lineHeight: "18px", fontWeight: "500" }],
      },
      maxWidth: {
        "content": "1440px",
      },
    },
  },
  plugins: [],
}
