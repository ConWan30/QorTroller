/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'vapi-bg':     '#020408',
        'gamer-cyan':  '#00d4ff',
        'gamer-green': '#00ff88',
        'dev-orange':  '#ff6b00',
        'dev-amber':   '#ffaa44',
        'mfr-blue':    '#4a9eff',
        'mfr-gold':    '#ffd700',
        'alert-red':   '#ff3b5c',
      },
      fontFamily: {
        display: ["'Rajdhani'", 'sans-serif'],
        mono:    ["'JetBrains Mono'", 'monospace'],
        body:    ["'Syne'", 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

