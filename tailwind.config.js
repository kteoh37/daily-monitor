/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        slate: {
          850: '#172033',
        },
      },
      flex: {
        '2': '2 2 0%',
        '3': '3 3 0%',
      },
    },
  },
  plugins: [],
}
