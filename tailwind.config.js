/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/renderer/index.html', './src/renderer/src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        'cs-bg': {
          900: '#0a0a0f',
          800: '#0e0e16',
          700: '#12121a',
          600: '#1a1a2e',
          500: '#222240',
          400: '#2a2a4a'
        },
        'cs-accent': {
          blue: '#00d4ff',
          purple: '#7c3aed',
          pink: '#ec4899',
          green: '#22c55e',
          amber: '#f59e0b',
          red: '#ef4444'
        },
        'cs-text': {
          primary: '#f0f0f5',
          secondary: '#a0a0b8',
          muted: '#6b6b80'
        },
        'cs-glass': {
          border: 'rgba(255, 255, 255, 0.08)',
          bg: 'rgba(18, 18, 26, 0.7)',
          hover: 'rgba(255, 255, 255, 0.04)'
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace']
      },
      backdropBlur: {
        xs: '2px',
        glass: '12px',
        heavy: '24px'
      },
      animation: {
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
        'spin-slow': 'spin 3s linear infinite',
        'waveform': 'waveform 1.5s ease-in-out infinite',
        'glow-border': 'glowBorder 3s ease-in-out infinite'
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { opacity: 0.6, transform: 'scale(1)' },
          '50%': { opacity: 1, transform: 'scale(1.05)' }
        },
        slideUp: {
          '0%': { opacity: 0, transform: 'translateY(10px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' }
        },
        slideDown: {
          '0%': { opacity: 0, transform: 'translateY(-10px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' }
        },
        fadeIn: {
          '0%': { opacity: 0 },
          '100%': { opacity: 1 }
        },
        waveform: {
          '0%, 100%': { height: '4px' },
          '50%': { height: '20px' }
        },
        glowBorder: {
          '0%, 100%': { borderColor: 'rgba(0, 212, 255, 0.2)' },
          '50%': { borderColor: 'rgba(0, 212, 255, 0.6)' }
        }
      },
      boxShadow: {
        'glow-blue': '0 0 20px rgba(0, 212, 255, 0.15)',
        'glow-purple': '0 0 20px rgba(124, 58, 237, 0.15)',
        'glow-green': '0 0 20px rgba(34, 197, 94, 0.15)',
        'inner-glow': 'inset 0 1px 0 rgba(255, 255, 255, 0.05)'
      }
    }
  },
  plugins: []
}
