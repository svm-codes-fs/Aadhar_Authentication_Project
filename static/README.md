# static/

`css/style.css` is the whole design system in one stylesheet, with no build step.

## Palette

| Role | Colour | Hex |
|---|---|---|
| Brand: header, headings, buttons, data bars | Deep Navy | `#0B3C5D` |
| Accent: active tab, accent lines, highlights | Saffron | `#F48020` |
| Success: pass, matched, service received | Green | `#2E7D32` |
| Alert: denial, fail, mismatch | Crimson | `#D32F2F` |
| Background | Off-white | `#F8F9FA` |
| Body text | Charcoal | `#212121` |

Colours are defined once as CSS variables in `:root`. Saffron is never used for small text (it is too light on white), and pass/fail always carry a word as well as a colour. The site stays light even when the operating system is in dark mode.

## Also in the stylesheet

- Layout: page width, split panels, stat tiles, cards
- Charts drawn in CSS: horizontal bars, columns, the stacked biometric/system bar, the heatmap
- Simulator meters and the attempt-by-attempt reveal animation (switched off for users who prefer reduced motion)
- Phone layout (no sideways scrolling) and a print stylesheet that hides navigation and filters
