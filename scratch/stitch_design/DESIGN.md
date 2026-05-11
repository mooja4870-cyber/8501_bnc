---
name: Cyber-Trade Aesthetic
colors:
  surface: '#111318'
  surface-dim: '#111318'
  surface-bright: '#37393e'
  surface-container-lowest: '#0c0e12'
  surface-container-low: '#1a1c20'
  surface-container: '#1e2024'
  surface-container-high: '#282a2e'
  surface-container-highest: '#333539'
  on-surface: '#e2e2e8'
  on-surface-variant: '#b9ccb2'
  inverse-surface: '#e2e2e8'
  inverse-on-surface: '#2f3035'
  outline: '#84967e'
  outline-variant: '#3b4b37'
  surface-tint: '#00e639'
  primary: '#ebffe2'
  on-primary: '#003907'
  primary-container: '#00ff41'
  on-primary-container: '#007117'
  inverse-primary: '#006e16'
  secondary: '#bdf4ff'
  on-secondary: '#00363d'
  secondary-container: '#00e3fd'
  on-secondary-container: '#00616d'
  tertiary: '#fff7f6'
  on-tertiary: '#690003'
  tertiary-container: '#ffd2cc'
  on-tertiary-container: '#c4010b'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#72ff70'
  primary-fixed-dim: '#00e639'
  on-primary-fixed: '#002203'
  on-primary-fixed-variant: '#00530e'
  secondary-fixed: '#9cf0ff'
  secondary-fixed-dim: '#00daf3'
  on-secondary-fixed: '#001f24'
  on-secondary-fixed-variant: '#004f58'
  tertiary-fixed: '#ffdad5'
  tertiary-fixed-dim: '#ffb4aa'
  on-tertiary-fixed: '#410001'
  on-tertiary-fixed-variant: '#930005'
  background: '#111318'
  on-background: '#e2e2e8'
  surface-variant: '#333539'
typography:
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.03em
  headline-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 36px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 20px
  margin-mobile: 16px
  margin-desktop: 32px
  container-max: 1440px
---

## Brand & Style

This design system is engineered for the high-stakes world of automated trading and fintech. It projects a brand personality that is **precise, authoritative, and hyper-modern**. The target audience consists of data-driven traders who require immediate visual feedback and a sense of "live" connectivity.

The visual style is a fusion of **Glassmorphism** and **High-Contrast Dark Mode**. It leverages deep obsidian surfaces to make vibrant data points pop, simulating the sophisticated environment of a terminal or a command center. The emotional response should be one of confidence and technical superiority, utilizing subtle glows to indicate activity and "breathable" glass layers to manage complex data density without overwhelming the user.

## Colors

The palette is anchored by a "Terminal Black" foundation to ensure maximum contrast for critical trading signals.

- **Primary (Live Green):** `#00FF41`. Used exclusively for positive growth, "live" status indicators, and primary action triggers. It carries a subtle outer glow (0 0 8px).
- **Secondary (Active Blue):** `#00E5FF`. Used for "refresh" states, interactive accents, and secondary data visualizations. It represents movement and systemic activity.
- **Tertiary (Alert Red):** `#FF3B30`. Reserved for high-priority risk alerts, stop-losses, and destructive actions.
- **Neutral/Background:** The core background is `#0A0C10`. Surface layers utilize `#161B22` with varying opacities to create depth.

## Typography

This design system employs a tiered typographic approach to balance editorial impact with technical utility.

1. **Space Grotesk** is used for headlines to provide a geometric, futuristic edge.
2. **Inter** handles the bulk of the UI text, chosen for its exceptional legibility and neutral tone in complex data grids.
3. **JetBrains Mono** is utilized for all "Live" data points, prices, and timestamps. The monospaced nature ensures that fluctuating numbers do not cause layout shifts and maintain a technical, "code-like" aesthetic.

All labels should be set in Uppercase when used for navigation or category headers to reinforce the structured, institutional feel.

## Layout & Spacing

The layout utilizes a **12-column Fluid Grid** for desktop and a **4-column grid** for mobile. A strict 4px base-unit scale governs all padding and margins to maintain mathematical harmony.

- **Data Density:** In trading views, use a "compact" spacing model (8px between elements). In marketing or dashboard overviews, use "spacious" (24px+).
- **Safe Zones:** Always maintain a 20px gutter between cards to allow the background glow effects to remain visible and distinct.
- **Reflow:** On mobile, sidebars collapse into a bottom navigation bar, and complex data tables transition into expandable list cards.

## Elevation & Depth

Depth is achieved through **Glassmorphism** rather than traditional drop shadows.

- **Surface 1 (Base):** `#0A0C10` (Solid).
- **Surface 2 (Cards):** `#161B22` with 80% opacity and a 12px Backdrop Blur. A 1px border of `#FFFFFF10` is required to define edges.
- **Surface 3 (Modals/Popovers):** `#1C2128` with 90% opacity, 20px Backdrop Blur, and a subtle outer glow matching the primary color (opacity 10%).
- **Interactive States:** When hovering over an element, the border-opacity should increase from 10% to 30%, creating a "light-up" effect.

## Shapes

The shape language balances technical "sharpness" with modern accessibility.

- **Standard Radius:** 0.5rem (8px) for cards, buttons, and input fields.
- **Large Radius:** 1.5rem (24px) for parent containers and major dashboard modules.
- **Micro Radius:** 0.25rem (4px) for status tags and small data badges.

The use of "Pill" shapes is restricted to "Live" indicators and toggle switches to differentiate them from actionable buttons.

## Components

- **Buttons:** Primary buttons use a solid `#00FF41` fill with black text. On hover, apply a `box-shadow: 0 0 15px rgba(0, 255, 65, 0.4)`. Secondary buttons are transparent with a 1px `#00E5FF` border.
- **Input Fields:** Use a dark fill (`#00000030`) with a 1px border. On focus, the border transitions to `#00E5FF` with a subtle inner glow.
- **Cards:** Must feature the 1px stroke and backdrop blur defined in the Elevation section. Headers within cards should have a thin `#FFFFFF05` separator.
- **Trading List:** Rows should have a hover state that highlights the background with `#FFFFFF05` and changes the "Price" font color to the Primary color.
- **Glow Accents:** Use "Glow Orbs" (radial gradients) behind key metrics to draw the eye. For example, a faint green glow behind a "Profit" percentage.
- **Chips/Badges:** Small, monospaced text with a 10% opacity background of the color it represents (e.g., a green badge has a green text and a 10% green background).