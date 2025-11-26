// tailwind.config.js
/** @type {import('tailwindcss').Config} */
import defaultTheme from 'tailwindcss/defaultTheme';

export default {
    content: ["./src/**/*.{js,jsx,ts,tsx}"],
    presets: [defaultTheme],
    theme: {
        extend: {
            animation: {
                fadeInScale: 'fadeInScale 0.35s cubic-bezier(0.22, 1, 0.36, 1) forwards',
                fadeOutScale: 'fadeOutScale 0.35s cubic-bezier(0.22, 1, 0.36, 1) forwards',
                eyeScan: 'eyeScan 8s cubic-bezier(0.3, 0, 0.7, 1) infinite',
                blink: 'blink 5s ease-in-out infinite',
                innerGlow: 'innerGlow 3s ease-in-out infinite alternate',
                pulseRing: 'pulseRing 4s ease-in-out infinite',
                outerRing: 'outerRing 6s linear infinite',
                particleExplode: 'particleExplode 0.7s ease-out forwards',
            },
            keyframes: {
                fadeInScale: {
                    '0%': {opacity: '0', transform: 'scale(0.92)'},
                    '100%': {opacity: '1', transform: 'scale(1)'}
                },
                fadeOutScale: {
                    '0%': {opacity: '1', transform: 'scale(1)'},
                    '100%': {opacity: '0', transform: 'scale(0.92)'}
                },
                eyeScan: {
                    '0%': {transform: 'translate(-1px, -4px)'},
                    '16%': {transform: 'translate(-1px, -6px)'},
                    '32%': {transform: 'translate(-1px, -2px)'},
                    '48%': {transform: 'translate(-3px, -4px)'},
                    '64%': {transform: 'translate(6px, -10px)'},
                    '80%': {transform: 'translate(-6px, -10px)'},
                    '100%': {transform: 'translate(-1px, -4px)'},
                },
                blink: {
                    '0%, 98%, 100%': {height: '12px'},
                    '99%': {height: '2px'},
                },
                innerGlow: {'0%': {opacity: '0.3', filter: 'blur(2px)'}, '100%': {opacity: '0.6', filter: 'blur(4px)'}},
                pulseRing: {
                    '0%': {transform: 'scale(1)', opacity: '0.8', filter: 'blur(2px)'},
                    '50%': {transform: 'scale(1.05)', opacity: '0.6', filter: 'blur(4px)'},
                    '100%': {transform: 'scale(1)', opacity: '0.8', filter: 'blur(2px)'},
                },
                outerRing: {
                    '0%': {transform: 'rotate(0deg)', filter: 'blur(3px)', opacity: '0.6'},
                    '50%': {filter: 'blur(4px)', opacity: '0.4'},
                    '100%': {transform: 'rotate(360deg)', filter: 'blur(3px)', opacity: '0.6'},
                },
                particleExplode: {
                    '0%': {opacity: '1', transform: 'scale(1) translate(0, 0)'},
                    '100%': {opacity: '0', transform: 'scale(0) translate(var(--dx), var(--dy))'},
                },
            },
            colors: {
                surface: {
                    DEFAULT: '#ffffff',
                    subtle: '#f8fafc',
                },
            },
        },
    },
    plugins: [],
}