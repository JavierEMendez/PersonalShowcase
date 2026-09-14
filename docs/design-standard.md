# Design standard

Reference: the three approved mockups in `design/` (HTML with inline styles, and PNG renders at 1440px). When in doubt, open the HTML and lift the exact markup and values.

## Tone

Executive, bank style. The page should read like an institutional investment committee memo or a lender term sheet. Dense but ordered. One accent color. No decoration that does not carry information.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--bg` | `#FAFAF7` | page background |
| `--surface` | `#FFFFFF` | panels, top bar |
| `--ink` | `#16191D` | headings, primary text, total rules |
| `--ink-2` | `#3A4048` | body text, secondary labels |
| `--muted` | `#6C7078` | eyebrows, units, sources, footers |
| `--hairline` | `#E6E4DE` | table row dividers, section dividers |
| `--rule` | `#B8B5AC` | table header underline |
| `--border` | `#DCDAD3` | panel borders, secondary button borders |
| `--accent` | `#0F2A44` | primary buttons, links |
| `--pos` | `#1E6B48` | positive values, compliance, high confidence |
| `--neg` | `#9E3A2B` | negative values, breaches, low confidence |
| `--warn` | `#8A6A1A` | medium confidence |
| heat ramp | `#FBFCFC #F7F9FA #F2F5F8 #E9EEF3 #DCE4EC #C9D5E1 #B3C4D5 #9DB2C8 #7F9AB6` | sequential fill for sensitivity grids; text switches to `#FAFAF7` from `#9DB2C8` up |

No shadows. No gradients. Radii 2px on buttons and pills, 0 on panels and tables. Borders 1px.

## Type

- Headings and large figures: `'Source Serif 4', Georgia, 'Times New Roman', serif`, weight 500.
- Body and tables: `'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif`, weights 400/500/600.
- `font-variant-numeric: tabular-nums` on `body`.
- Google Fonts link: `https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&family=IBM+Plex+Sans:wght@400;500;600&display=swap`

| Role | Size / line height | Weight | Notes |
|---|---|---|---|
| Landing h1 | 56px / 1.08 | serif 500 | letter-spacing -.015em |
| Section h2 | 34px / 1.15 | serif 500 | letter-spacing -.01em |
| Tool deal title | 30px / 1.1 | serif 500 | |
| Summary figure | 26px / 1.1 | serif 500 | letter-spacing -.01em |
| Panel figure | 24px or 20px | serif 500 | |
| Landing body | 16–18px / 1.5–1.55 | sans 400 | color ink-2 |
| Table body | 14px / 1.45 | sans 400 | |
| Nav, buttons | 13px | sans 500 | |
| Eyebrow, table header | 11px | sans 500 | uppercase, letter-spacing .04em (headers) or .08em (eyebrows), color muted |
| Notes, units | 12px | sans 400 | color muted |

## Layout

- Design width 1440px. 12-column grid, `grid-template-columns: repeat(12, minmax(0, 1fr))`, 20px gap in tools, 40px on the landing page.
- Gutters: 32px in tool screens, 72px on the landing page.
- Tool screen skeleton, top to bottom:
  1. Top bar, 56px, surface background, 1px border-bottom. Left: wordmark, slash, product name, then tabs (underline 2px ink on active) or a 4-step stepper. Right: secondary buttons (1px border) and one primary button (accent fill).
  2. Deal header: eyebrow (deal type and status), serif title with an inline muted fact line, scenario or case pills on the right (active pill has 1px ink border, others 1px border color).
  3. Summary strip: 8 columns, 1px ink rule above, hairline below. Each cell: eyebrow, 26px serif figure, 12px muted note. Cells separated by hairline right borders.
  4. Panels on the 12-column grid. Panel: 1px border, surface background, 18px 20px padding. Header row: eyebrow left, 12px muted unit or context right, 10px below.
- Landing page anatomy: nav (wordmark, four links, outlined CTA), hero (7/5 split: eyebrow, h1, paragraph, primary CTA plus text link; sample-deal panel on the right), four-figure proof strip with a 1px ink rule above, two product sections (5/7 split, alternating), method section on a surface background, about section, footer line.

## Tables

- `border-collapse: collapse`, full width, 6px 10px cell padding.
- Header: 11px uppercase muted, 1px rule underline, `white-space: nowrap`.
- Body rows: hairline bottom border. Indented sub-lines use 24px left padding.
- Total rows: 1px ink top and bottom border, weight 600.
- Numbers right-aligned, negatives in parentheses, thousands separators, one decimal for $ millions, zero decimals for $ thousands, one decimal for percentages, two decimals for multiples with `×`.
- Units belong in the panel header, never repeated in every cell.

## Components seen in the mockups

- Summary strip cell (`kpi`): see `design/underwriting.html`, first grid after the deal header.
- Sensitivity grid: 5×5 shown (server supports up to 7×7), heat ramp fills, base case outlined with `outline: 1.5px solid ink; outline-offset: -1.5px` and weight 600.
- Net cash flow by year: table with a bar cell column (`min-width: 150px`) whose bar extends left (negative) or right (positive) from a center line; bar height 8px; positive `--pos`, negative `--neg`.
- Confidence indicator: 7px dot in pos / warn / neg followed by the word.
- Stepper: 20px numbered circles, done (ink fill, light text), active (1.5px ink border, label underlined), pending (1px border-color).

## Copy rules

- Sentence case everywhere except eyebrows and table headers.
- No em dashes. Use a period, a comma, or a middle dot (`·`) as a separator in fact lines.
- No "X, not Y" or "it's not X, it's Y" constructions. (lint-ignore)
- Banned words (lint-ignore): delve, leverage (as a verb), robust, seamless, unlock, empower, cutting-edge, game-changing.
- No exclamation points, no rhetorical questions.
- State the number, then what it means: "18.4% unlevered IRR. Breakeven in year 8."

## Starter site.css

```css
:root {
  --bg: #FAFAF7; --surface: #FFFFFF; --ink: #16191D; --ink-2: #3A4048; --muted: #6C7078;
  --hairline: #E6E4DE; --rule: #B8B5AC; --border: #DCDAD3; --accent: #0F2A44;
  --pos: #1E6B48; --neg: #9E3A2B; --warn: #8A6A1A;
  --serif: 'Source Serif 4', Georgia, 'Times New Roman', serif;
  --sans: 'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif;
}
html { background: var(--bg); }
body { margin: 0; color: var(--ink); font-family: var(--sans); font-size: 14px; line-height: 1.45; font-variant-numeric: tabular-nums; -webkit-font-smoothing: antialiased; }
a { color: var(--accent); text-decoration: none; } a:hover { color: var(--pos); text-decoration: underline; }
h1, h2, h3, .figure { font-family: var(--serif); font-weight: 500; margin: 0; }
.eyebrow { font-size: 11px; font-weight: 500; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.note { font-size: 12px; color: var(--muted); }
.panel { border: 1px solid var(--border); background: var(--surface); padding: 18px 20px; }
.panel-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
.grid-12 { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 20px; }
.topbar { display: flex; align-items: center; justify-content: space-between; height: 56px; padding: 0 32px; background: var(--surface); border-bottom: 1px solid var(--border); }
.btn { display: inline-block; padding: 7px 12px; border: 1px solid var(--border); border-radius: 2px; font-size: 13px; font-weight: 500; color: var(--ink); }
.btn-primary { background: var(--accent); border-color: var(--accent); color: var(--bg); }
.pill { padding: 6px 12px; border: 1px solid var(--border); border-radius: 2px; font-size: 13px; color: var(--ink-2); }
.pill.active { border-color: var(--ink); color: var(--ink); font-weight: 500; }
.kpis { display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); gap: 0 18px; border-top: 1px solid var(--ink); border-bottom: 1px solid var(--hairline); }
.kpi { display: flex; flex-direction: column; gap: 2px; padding: 14px 18px 14px 0; border-right: 1px solid var(--hairline); }
.kpi .figure { font-size: 26px; line-height: 1.1; letter-spacing: -.01em; }
table { border-collapse: collapse; width: 100%; }
th, td { padding: 6px 10px; text-align: left; vertical-align: baseline; }
th.r, td.r { text-align: right; }
thead th { white-space: nowrap; font-size: 11px; font-weight: 500; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--rule); }
tbody td { border-bottom: 1px solid var(--hairline); }
tr.total td { border-top: 1px solid var(--ink); border-bottom: 1px solid var(--ink); font-weight: 600; }
td.indent { padding-left: 24px; }
.pos { color: var(--pos); } .neg { color: var(--neg); }
```
