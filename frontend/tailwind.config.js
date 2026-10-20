/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef6ff',
          100: '#d9ecff',
          200: '#bcdcff',
          300: '#8ec4ff',
          400: '#59a3ff',
          500: '#3380ff',
          600: '#1c5ff5',
          700: '#1749e0',
          800: '#193bb5',
          900: '#1a368e',
          950: '#141f52',
        },
        risk: {
          low: '#16a34a',
          medium: '#f59e0b',
          high: '#dc2626',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 0 40px -10px rgba(51, 128, 255, 0.35)',
      },
    },
  },
  plugins: [],
}
