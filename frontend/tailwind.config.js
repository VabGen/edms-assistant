/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'neon-glass': 'rgba(255, 255, 255, 0.75)',
        'neon-glass-hover': 'rgba(255, 255, 255, 0.85)',
        'neon-border': 'rgba(255, 255, 255, 0.2)',
        'neon-shadow': 'rgba(0, 0, 0, 0.05)',
        'neon-accent': '#6b7280',
        'neon-accent-hover': '#4b5563',
        'neon-accent-active': '#374151',
        'neon-red': '#ef4444',
        'neon-red-hover': '#dc2626',
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      spacing: {
        '0': '0px',
        '1': '0.25rem',
        '2': '0.5rem',
        '3': '0.75rem',
        '4': '1rem',
        '5': '1.25rem',
        '6': '1.5rem',
        '8': '2rem',
        '10': '2.5rem',
        '12': '3rem',
      },
    },
  },
  plugins: [],
}