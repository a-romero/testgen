/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f9f9",
          100: "#d6f0f0",
          200: "#ade0e0",
          300: "#7ac9c9",
          400: "#47b0b0",
          500: "#145c5c",
          600: "#115050",
          700: "#0e4343",
          800: "#0b3737",
          900: "#082a2a",
        },
      },
    },
  },
  plugins: [],
};
