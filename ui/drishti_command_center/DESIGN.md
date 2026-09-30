---
name: Drishti Command Center
colors:
  surface: '#0f141b'
  surface-dim: '#0f141b'
  surface-bright: '#353941'
  surface-container-lowest: '#090e15'
  surface-container-low: '#171c23'
  surface-container: '#1b2027'
  surface-container-high: '#252a32'
  surface-container-highest: '#30353d'
  on-surface: '#dee2ed'
  on-surface-variant: '#c1c6d4'
  inverse-surface: '#dee2ed'
  inverse-on-surface: '#2c3138'
  outline: '#8b919e'
  outline-variant: '#414752'
  surface-tint: '#a6c8ff'
  primary: '#a6c8ff'
  on-primary: '#003060'
  primary-container: '#4792f0'
  on-primary-container: '#002a54'
  inverse-primary: '#005eb1'
  secondary: '#4ae176'
  on-secondary: '#003915'
  secondary-container: '#00b954'
  on-secondary-container: '#004119'
  tertiary: '#ffb95f'
  on-tertiary: '#472a00'
  tertiary-container: '#ca8100'
  on-tertiary-container: '#3e2400'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d5e3ff'
  primary-fixed-dim: '#a6c8ff'
  on-primary-fixed: '#001c3b'
  on-primary-fixed-variant: '#004787'
  secondary-fixed: '#6bff8f'
  secondary-fixed-dim: '#4ae176'
  on-secondary-fixed: '#002109'
  on-secondary-fixed-variant: '#005321'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#0f141b'
  on-background: '#dee2ed'
  surface-variant: '#30353d'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 1.75rem
    fontWeight: '600'
    lineHeight: 2.25rem
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 1.375rem
    fontWeight: '600'
    lineHeight: 1.75rem
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 1.125rem
    fontWeight: '600'
    lineHeight: 1.5rem
    letterSpacing: -0.01em
  title-md:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '600'
    lineHeight: 1.25rem
    letterSpacing: '0'
  body-md:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '400'
    lineHeight: 1.25rem
    letterSpacing: '0'
  body-sm:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: '400'
    lineHeight: 1rem
    letterSpacing: '0'
  data-mono-lg:
    fontFamily: JetBrains Mono
    fontSize: 1rem
    fontWeight: '600'
    lineHeight: 1.25rem
    letterSpacing: -0.02em
  data-mono-md:
    fontFamily: JetBrains Mono
    fontSize: 0.8125rem
    fontWeight: '500'
    lineHeight: 1rem
    letterSpacing: -0.01em
  data-mono-sm:
    fontFamily: JetBrains Mono
    fontSize: 0.6875rem
    fontWeight: '500'
    lineHeight: 0.875rem
    letterSpacing: 0.02em
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 0.625rem
    fontWeight: '600'
    lineHeight: 0.75rem
    letterSpacing: 0.08em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 0.5rem
  margin: 0.75rem
  space-xs: 0.25rem
  space-sm: 0.375rem
  space-md: 0.5rem
  space-lg: 0.75rem
  space-xl: 1rem
---

## Brand & Style

This design system targets mission-critical public-safety operations, real-time threat detection, and tactical command centers (SOCs). The user base consists of security operators, intelligence analysts, and dispatch incident commanders who monitor multi-feed video walls and high-frequency sensor telemetry for 8 to 12-hour shifts. 

The aesthetic is precision-engineered, high-density situational awareness: cold, hyper-focused, distraction-free, and immediate. The visual style merges modern tactical SOC utility with low-fatigue dark surfaces. Chrome, unnecessary decoration, and large playful radii are stripped away in favor of razor-thin structural framing, distinct visual hierarchy, and instant perceptual triage. Bright semantic colors are restricted exclusively to real-time status signals, anomalies, and active perimeter breaches.

## Colors

The chromatic structure adheres strictly to dark-mode operational ergonomics to minimize eye strain and screen glare in dimly lit control rooms.

### Surface Tiers & Neutral Geometry
- **Canvas Base (`#0d1117`)**: The global viewport canvas and deep negative space behind monitoring modules.
- **Surface Level 1 (`#11161d`)**: Primary docked panels, persistent header ribbons, left telemetry rails, and camera grids.
- **Surface Level 2 (`#161c25`)**: Raised cards, active stream overlays, inspector drawers, and floating toolbars.
- **Subtle Border (`#1e2631`)**: Internal structural dividers, grid gutters, and dormant container bounds.
- **Stronger Border (`#2a3442`)**: Hover boundaries, selected telemetry containers, active modal perimeters, and resizable splitters.

### Typography & Content
- **Primary Text (`#e6eaf0`)**: Direct tactical readout, alert titles, and critical system states. High contrast against dark surfaces.
- **Muted Text (`#8b95a5`)**: Structural labels, inactive entity IDs, column headers, and secondary telemetry data.
- **Faint Text (`#5d6878`)**: Grid indices, breadcrumbs, disabled actions, and de-emphasized metadata.

### System Accent
- **Tactical Blue (`#3987e5`)**: Interactive system selections, active camera viewports, focused input states, and primary operational triggers.

### Semantic Telemetry & Incident Severity
Signals are reserved for operational classification and must never be used decoratively:
- **Critical / Offline (`#ef4444`)**: Active breaches, camera signal drop, weapon detection, server disconnect.
- **High Severity (`#f97316`)**: Unattended objects, crowd convergence anomalies, perimeter tampering.
- **Medium / Warning (`#f59e0b`)**: System threshold warnings, latency spikes, loitering alerts.
- **Online / Normal (`#22c55e`)**: Healthy node telemetry, encrypted stream alive, face-match verified.
- **Low Severity / Inactive (`#6b7280`)**: Routine log traces, resolved tickets, archived footage.

## Typography

Typography enforces a strict bifurcated system:
1. **Inter** handles narrative comprehension, contextual headings, and system dialogs. Letterforms are neutral, functional, and clean.
2. **JetBrains Mono** handles dense operational data, feed timestamps, GPS coordinates, camera hex IDs, frame rates, bounding-box labels, and telemetry values. The monospaced tracking prevents visual drift during rapid number updates.

Headings remain compact (rarely exceeding `headline-xl` at 28px) to protect screen real estate for live viewport matrices. Micro-labels (`label-caps`) use uppercase styling with expanded letter-spacing to ensure absolute legibility on high-density monitor configurations at arm's length.

## Layout & Spacing

This design system uses a strict **fluid, high-density modular docking grid**. Space is treated as a finite resource; padding and margins are compressed compared to consumer software.

- **Screen Density**: Built primarily for multi-head desktop setups (1080p, 1440p, 4K video walls). The primary grid relies on a 4px modular baseline (`0.25rem`).
- **Gutter Strategy**: Video stream matrices and tactical panels use tight 8px (`0.5rem`) gutters to prevent lost visual continuity when tracking moving objects across split cameras.
- **Docking Structure**: Layouts use a fixed-width expandable collateral sidebar (320px default), a persistent 40px utility header ribbon, an edge-to-edge multi-tile stage, and a collapsible bottom situational timeline (160px height).
- **Responsive Handling**:
  - **Wall / Ultra-wide (>1920px)**: Fluid multi-column matrix up to 16 live stream panes with concurrent side-by-side incident feed and spatial map.
  - **Desktop (1280px - 1919px)**: 4 to 8 active stream tiles; secondary panels dock into tabs or collapsible accordions.
  - **Tablet/Field Commander (<1279px)**: Dynamic single/dual pane split with swipeable drawer overrides for alert dispatching.

## Elevation & Depth

Tactile drop shadows are excluded. Depth is communicated strictly via **tonal layering and crisp low-contrast borders**. This eliminates visual blur across high-framerate video canvases and keeps edge contrast sharp.

1. **Surface 0 (`#0d1117`)**: Base background, matrix gap color.
2. **Surface 1 (`#11161d`)**: Main panels bordered with `#1e2631`.
3. **Surface 2 (`#161c25`)**: Elevated cards, toolbars, popovers, and selected tile frames.
4. **Focused / Selected Elevation**: Instead of heavy shadows, selected states employ a 1px inner or outer outline of `#3987e5` paired with a background shift to `#161c25`.
5. **Critical Alert Overlay**: Flashing or persistent containment rings use a 1px solid stroke of `#ef4444` accompanied by a localized 5% `#ef4444` ambient back-glow (`box-shadow: 0 0 12px rgba(239, 68, 68, 0.2)`), restricted only to active perimeter breaches.

## Shapes

The design system employs a **Soft (Level 1)** geometric standard. 

- Base UI components, buttons, inputs, badge tags, and stream tiles use a subtle `0.25rem` (4px) corner radius.
- Structural panels, dialog frames, and map overlays use `0.375rem` (6px) or `0.5rem` (8px maximum).
- Sharp corners or near-sharp micro-radii reinforce an instrumented, tactical feel while eliminating the harshness of raw 90-degree aliased cuts on OLED and LED displays. Full pills are restricted strictly to micro status indicators and live record badges.

## Components

### Buttons
- **Primary / Action**: `#3987e5` background, `#ffffff` text, 4px radius, 32px height for standard control, 24px for micro-actions. No gradients. Hover shifts to `#4f98ec`.
- **Secondary / Ghost**: Transparent background with `#1e2631` border, `#e6eaf0` text. Hover changes border to `#2a3442` and surface to `#161c25`.
- **Destructive / Emergency Dispatch**: `#ef4444` background with white text, or outline variant with `#ef4444` border and text for unconfirmed trigger states.

### Status Indicators & Severity Chips
- **Telemetry Chips**: Height 20px, font `JetBrains Mono` (`data-mono-sm`), 3px radius. Rendered with 12% opacity colored fills and 100% solid colored typography (e.g., Critical uses background `rgba(239, 68, 68, 0.12)`, border `rgba(239, 68, 68, 0.3)`, text `#ef4444`).
- **Live Stream Status Dots**: 6px pulsing circles (Online `#22c55e`, Offline `#ef4444`, Buffering/Warning `#f59e0b`).

### Video Tile Containers
- Dark frame wrapped in `#1e2631`.
- Header bar (height 28px) embedded directly on the top edge with camera ID, FPS counter, and PTZ status rendered in `JetBrains Mono`.
- Active selected stream acquires a 1px `#3987e5` border with top-right corner coordinates indicator.

### Data Tables & Event Logs
- Row heights compressed to 28px - 32px.
- Subtle horizontal row separation using 1px `#1e2631`.
- Timestamps, MAC addresses, plate numbers, and confidence scores right-aligned in `JetBrains Mono`.
- Hover state triggers full-width `#161c25` background highlight.

### Inputs & Filters
- Compact height (28px - 32px), background `#0d1117`, border 1px `#1e2631`, text `#e6eaf0`.
- Focus shifts border to `#3987e5` with zero outline-offset glow.
- Monospace font applied automatically to coordinate, sensor range, and IP filter inputs.

### Incident Threat Cards
- Background `#161c25`, border `#1e2631`.
- Left-border accent indicator (3px width) colored dynamically by severity: Critical (`#ef4444`), High (`#f97316`), Medium (`#f59e0b`), Low (`#6b7280`).
- Direct tactical payload displaying snapshot thumbnail, detected object class, detection confidence score, and instantaneous dispatch button.