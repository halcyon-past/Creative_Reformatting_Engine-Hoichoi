/** @type {import('tailwindcss').Config} */

/*
 * NEOBRUTALISM DESIGN SYSTEM
 * --------------------------
 * Hard black borders, offset shadows with zero blur, saturated flat colour,
 * chunky type, and elements that physically *move* when you touch them.
 *
 * The `ink` and `slate` scales keep their original names on purpose: the app
 * already uses them in ~250 places, so redefining the tokens re-skins the
 * whole thing without rewriting markup. Their meaning is inverted --
 * `ink-900` was the darkest surface and is now paper; `slate-*` was light text
 * on dark and is now dark text on paper. Anything that reads as a border
 * (`ink-600`, `slate-500..700`) resolves to black or near-black, because in
 * this language every edge is drawn.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#F5E9D0", // deepest paper — inset wells, code blocks
          900: "#FDF4E3", // page background (was near-black)
          800: "#FFFFFF", // card surface
          700: "#FFE4A0", // hover / secondary fill
          600: "#000000", // BORDERS. every edge is black.
        },
        slate: {
          100: "#000000",
          200: "#0A0A0A",
          300: "#171717",
          400: "#3F3A33", // secondary copy — dark enough to read on paper
          500: "#57534E", // tertiary copy, doubles as a visible rule
          600: "#78716C",
          700: "#000000",
        },
        accent: "#FF2E88", // hot pink

        // The pop palette. Flat, saturated, no gradients.
        pop: {
          yellow: "#FFD93D",
          pink: "#FF2E88",
          cyan: "#22D3EE",
          lime: "#A3E635",
          orange: "#FF7A2F",
          purple: "#A78BFA",
          blue: "#3B82F6",
          red: "#FF5252",
          mint: "#5EEAD4",
        },
      },

      fontFamily: {
        sans: ['"Space Grotesk"', "Inter", "system-ui", "sans-serif"],
        display: ['"Archivo Black"', '"Space Grotesk"', "Impact", "sans-serif"],
        mono: ['"Space Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },

      // Offset, zero-blur shadows. The whole look hangs off these.
      boxShadow: {
        brutal: "4px 4px 0 0 #000",
        "brutal-sm": "2px 2px 0 0 #000",
        "brutal-lg": "8px 8px 0 0 #000",
        "brutal-xl": "12px 12px 0 0 #000",
        "brutal-press": "1px 1px 0 0 #000",
        "brutal-pink": "4px 4px 0 0 #FF2E88",
        "brutal-cyan": "4px 4px 0 0 #22D3EE",
        "brutal-lime": "4px 4px 0 0 #A3E635",
        "brutal-inner": "inset 3px 3px 0 0 rgba(0,0,0,0.18)",
      },

      borderWidth: { 3: "3px", 5: "5px" },
      borderRadius: { brutal: "6px" },

      keyframes: {
        // A confident entrance, not a fade.
        "pop-in": {
          "0%": { transform: "scale(0.94) translateY(6px)", opacity: "0" },
          "70%": { transform: "scale(1.02) translateY(0)", opacity: "1" },
          "100%": { transform: "scale(1) translateY(0)", opacity: "1" },
        },
        "slide-up": {
          "0%": { transform: "translateY(14px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        wiggle: {
          "0%,100%": { transform: "rotate(-2deg)" },
          "50%": { transform: "rotate(2deg)" },
        },
        jitter: {
          "0%,100%": { transform: "translate(0,0) rotate(0deg)" },
          "25%": { transform: "translate(-1px,1px) rotate(-1deg)" },
          "75%": { transform: "translate(1px,-1px) rotate(1deg)" },
        },
        "marquee-x": {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
        "stripe-slide": {
          "0%": { backgroundPosition: "0 0" },
          "100%": { backgroundPosition: "28px 0" },
        },
        blink: { "0%,100%": { opacity: "1" }, "50%": { opacity: "0.15" } },
        "bounce-sm": {
          "0%,100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-4px)" },
        },
        "spin-slow": { to: { transform: "rotate(360deg)" } },
      },

      animation: {
        "pop-in": "pop-in 0.28s cubic-bezier(0.34,1.56,0.64,1) both",
        "slide-up": "slide-up 0.3s cubic-bezier(0.34,1.56,0.64,1) both",
        wiggle: "wiggle 0.4s ease-in-out",
        jitter: "jitter 0.35s ease-in-out infinite",
        marquee: "marquee-x 26s linear infinite",
        "marquee-fast": "marquee-x 14s linear infinite",
        stripes: "stripe-slide 0.7s linear infinite",
        blink: "blink 1.1s steps(1,end) infinite",
        "bounce-sm": "bounce-sm 1.2s ease-in-out infinite",
        "spin-slow": "spin-slow 7s linear infinite",
      },
    },
  },
  plugins: [],
};
