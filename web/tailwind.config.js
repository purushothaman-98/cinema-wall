/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Sora", "system-ui", "sans-serif"],
        body: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        ink: {
          950: "#0a0b0f",
          900: "#0f1115",
          800: "#161922",
          700: "#1f232f",
          600: "#2a2f3d",
          500: "#3c4257",
          400: "#5b6178",
          300: "#8b8fa3",
          200: "#c4c7d4",
          100: "#e7e8ee",
        },
        ember: {
          400: "#ff8a5c",
          500: "#ff5f2e",
          600: "#ea3f16",
        },
        bloom: {
          400: "#ff6fa8",
          500: "#ff2e88",
          600: "#e01072",
        },
        signal: {
          400: "#3fe6c4",
          500: "#1fd1ac",
          600: "#0fae8d",
        },
        violet: {
          400: "#a78bfa",
          500: "#8b5cf6",
          600: "#7c3aed",
        },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(255,95,46,0.15), 0 8px 30px -8px rgba(255,46,136,0.35)",
      },
      backgroundImage: {
        "grid-fade":
          "radial-gradient(circle at 20% -10%, rgba(255,95,46,0.16), transparent 45%), radial-gradient(circle at 90% 0%, rgba(139,92,246,0.14), transparent 40%)",
      },
    },
  },
  plugins: [],
};
