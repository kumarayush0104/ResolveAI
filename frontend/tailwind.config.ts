import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // PayPal-kit palette
        navy:           '#0A2A66',
        'navy-deep':    '#061B47',
        cyan:           '#0396D8',
        'cyan-soft':    '#E3F4FC',
        'cyan-deep':    '#0277B0',
        mist:           '#F1F8FD',
        canvas:         '#F3F7FB',
        muted:          '#6B7C93',
        // legacy tokens (still used by a few components)
        'pp-navy':      '#001C64',
        'pp-blue-dark': '#003087',
        'pp-blue':      '#0070E0',
        'pp-sky':       '#009CDE',
        'pp-gold':      '#FFC439',
        'pp-gold-hover':'#F2BA36',
        ink:            '#1E2A3B',
        'ink-soft':     '#6B7C93',
        line:           '#E4ECF4',
        surface:        '#F3F7FB',
        success:        '#1F8A4C',
        warning:        '#B26A00',
        danger:         '#D9360B',
        unknown:        '#5B6B8C',
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        // Unified radius scale
        control: '16px',  // inputs, chips, small buttons
        card:    '20px',  // standard cards
        hero:    '28px',  // hero sections, wallet cards
      },
      boxShadow: {
        // Layered, soft — not harsh
        card:       '0 1px 2px rgba(10,42,102,.04), 0 6px 20px rgba(10,42,102,.07)',
        'card-hover':'0 4px 12px rgba(10,42,102,.08), 0 12px 32px rgba(10,42,102,.12)',
        phone:      '0 48px 96px -16px rgba(10,42,102,.50), 0 16px 36px -8px rgba(0,0,0,.28), inset 0 1.5px 0 rgba(255,255,255,.15)',
        glass:      '0 8px 32px rgba(10,42,102,.10), inset 0 1px 0 rgba(255,255,255,.90)',
        glow:       '0 0 20px rgba(3,150,216,.35)',
        'glow-gold':'0 0 20px rgba(255,196,57,.40)',
      },
    },
  },
  plugins: [],
} satisfies Config
