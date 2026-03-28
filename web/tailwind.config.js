/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        chatBg: '#202123',
        panelBg: '#2A2B32',
        userBubble: '#343541',
        aiBubble: '#444654',
      }
    },
  },
  plugins: [],
}
