/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./index.html",
        "./srccc/**/*.{js,jsx,ts,tsx}",
        "./srccc/index.css",
    ],
    theme: {
        extend: {
            colors: {
                edms: {
                    dark: "#111827",
                    darker: "#030712",
                    primary: "#3b82f6",
                    accent: "#10b981",
                },
            },
            animation: {
                'fade-in-up': 'fadeInUp 0.5s cubic-bezier(0.22, 1, 0.36, 1) forwards',
            },
            keyframes: {
                fadeInUp: {
                    '0%': {opacity: '0', transform: 'translateY(10px) scale(0.95)'},
                    '100%': {opacity: '1', transform: 'translateY(0) scale(1)'},
                },
            },
        },
    },
    plugins: [],
    corePlugins: {
        backdropFilter: true,
    },
};