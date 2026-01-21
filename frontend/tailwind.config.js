/** @type {import('tailwindcss').Config} */
export default {
    darkMode: 'class',
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // Using CSS variables for dynamic theme switching
                bg: {
                    primary: 'var(--bg-primary)',
                    surface: 'var(--bg-surface)',
                    hover: 'var(--bg-hover)',
                },
                text: {
                    primary: 'var(--text-primary)',
                    secondary: 'var(--text-secondary)',
                },
                border: {
                    DEFAULT: 'var(--border-color)',
                },
                accent: {
                    DEFAULT: 'var(--accent)',
                    hover: 'var(--accent-hover)',
                }
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
                arabic: ['Cairo', 'sans-serif'],
            },
            boxShadow: {
                'soft': '0 4px 20px -2px rgba(0, 0, 0, 0.1)',
                'glow': '0 0 20px rgba(34, 211, 238, 0.15)',
            },
            transitionProperty: {
                'theme': 'background-color, border-color, color, fill, stroke',
            }
        },
    },
    plugins: [],
}
