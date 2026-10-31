import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'pp-navy':      '#001C64',
        'pp-blue-dark': '#003087',
        'pp-blue':      '#0070E0',
        'pp-sky':       '#009CDE',
        'pp-gold':      '#FFC439',
        'pp-gold-hover':'#F2BA36',
        ink:            '#2C2E2F',
        'ink-soft':     '#6C7378',
        line:           '#EAEDEF',
        surface:        '#F5F7FA',
        success:        '#1F8A4C',
        warning:        '#B26A00',
        danger:         '#D9360B',
        unknown:        '#5B6B8C',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        'xl':  '0.75rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
        'full':'9999px',
      },
      boxShadow: {
        card:   '0 1px 2px rgba(0,28,100,.06), 0 8px 24px rgba(0,28,100,.08)',
        mobile: '0 0 60px rgba(0,0,0,0.25)',
        float:  '0 8px 32px rgba(0,112,224,0.18)',
      },
      maxWidth: {
        mobile: '430px',
      },
    },
  },
  plugins: [],
} satisfies Config
