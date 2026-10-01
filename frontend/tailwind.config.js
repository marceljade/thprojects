/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Segoe UI Variable Text"', '"Segoe UI"', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        canvas: 'rgb(var(--canvas) / <alpha-value>)',
        surface: 'rgb(var(--surface) / <alpha-value>)',
        raised: 'rgb(var(--raised) / <alpha-value>)',
        line: 'rgb(var(--line) / <alpha-value>)',
        ink: 'rgb(var(--ink) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        faint: 'rgb(var(--faint) / <alpha-value>)',
        accent: 'rgb(var(--accent) / <alpha-value>)',
        'accent-ink': 'rgb(var(--accent-ink) / <alpha-value>)',
        rot: 'rgb(var(--rot) / <alpha-value>)',
        orange: 'rgb(var(--orange) / <alpha-value>)',
        gelb: 'rgb(var(--gelb) / <alpha-value>)',
        gruen: 'rgb(var(--gruen) / <alpha-value>)',
        blau: 'rgb(var(--blau) / <alpha-value>)',
      },
      boxShadow: {
        pop: '0 8px 30px -8px rgb(0 0 0 / 0.25), 0 1px 2px rgb(0 0 0 / 0.08)',
      },
    },
  },
  plugins: [],
}
