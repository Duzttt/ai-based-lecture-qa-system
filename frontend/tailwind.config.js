/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0b1326',
          dim: '#0b1326',
          lowest: '#060e20',
          low: '#131b2e',
          container: '#171f33',
          high: '#222a3d',
          highest: '#2d3449',
          bright: '#31394d',
        },
        primary: {
          DEFAULT: '#bdc2ff',
          container: '#818cf8',
          on: '#131e8c',
        },
        secondary: {
          DEFAULT: '#bcc7de',
          container: '#3e495d',
          on: '#aeb9d0',
        },
        tertiary: {
          DEFAULT: '#f7bd3e',
          container: '#c08d00',
        },
        on: {
          surface: '#dae2fd',
          'surface-variant': '#c6c5d5',
        },
        outline: {
          DEFAULT: '#908f9e',
          variant: '#454653',
        },
      },
      fontFamily: {
        headline: ['Manrope', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
      },
      borderRadius: {
        lg: '12px',
        md: '8px',
      },
    },
  },
  plugins: [],
}
