/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  corePlugins: {
    preflight: false, // Avoid overriding Ant Design 5 CSS-in-JS styles
  },
  theme: {
    extend: {},
  },
  plugins: [],
};
