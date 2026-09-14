# Brand mark and favicon

Design option B from the monogram artboard: the initials JM set in Source Serif 4 Medium, page ground `#FAFAF7` on a navy `#0F2A44` square. The letterforms are stored as vector paths, so no font has to load for the mark to render.

## Files (`app/static/brand/`)

| File | Use |
|---|---|
| `mark.svg` | Master mark, 64×64 viewBox, scales to any size. Use for the favicon (`rel="icon" type="image/svg+xml"`) and in templates. |
| `mark-cream.svg` | Same letters in navy on the page ground, for use on navy surfaces or print. |
| `favicon.ico` | 16, 32, 48 px for browsers that ignore SVG favicons. |
| `icon-16.png`, `icon-32.png`, `icon-48.png` | Raster fallbacks. |
| `apple-touch-icon.png` | 180×180 for iOS home screen. |
| `icon-192.png`, `icon-512.png` | Android and PWA, referenced from the manifest. |
| `site.webmanifest` | Name, icons, theme color `#0F2A44`, background `#FAFAF7`. |
| `lockup.svg` | Mark plus wordmark "Javier Mendez" at 24 px, for the top bar and README. |

## Head snippet (base template)

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&display=swap">
<link rel="icon" href="/static/brand/mark.svg" type="image/svg+xml">
<link rel="icon" href="/static/brand/favicon.ico" sizes="16x16 32x32 48x48">
<link rel="apple-touch-icon" href="/static/brand/apple-touch-icon.png">
<link rel="manifest" href="/static/brand/site.webmanifest">
<meta name="theme-color" content="#0F2A44">
```

Page titles follow `Javier Mendez · <Product>`: `Javier Mendez`, `Javier Mendez · MPC Underwriting`, `Javier Mendez · Deal-to-Portfolio Copilot`.

## Top bar lockup

```html
<a class="lockup" href="/">
  <img src="/static/brand/mark.svg" alt="" width="24" height="24">
  <span class="wordmark">Javier Mendez</span>
  <span class="lockup-sep">/</span>
  <span class="lockup-product">{{ product }}</span>
</a>
```

```css
.lockup { display: flex; align-items: center; gap: 10px; color: #16191D; text-decoration: none; }
.lockup img { display: block; }
.wordmark { font-family: 'Source Serif 4', Georgia, 'Times New Roman', serif; font-size: 17px; font-weight: 600; letter-spacing: .02em; }
.lockup-sep { color: #6C7078; font-size: 13px; }
.lockup-product { font-size: 13px; font-weight: 500; }
```

On the landing page the top bar shows the mark and wordmark without a product segment.

## Rules

- The mark is always the navy square with cream letters, or the cream version on navy. No other colors, no outlines, no drop shadows, no rounded corners.
- Minimum size 16 px. Below 24 px use the mark alone, never the lockup.
- Clear space around the mark equals one quarter of its width.
- Do not set the initials in any other typeface or recreate them as live text; use the SVG.
- README header: `lockup.svg` at 24 px height, left aligned, above the title.

## Regenerating

The marks were produced from font outlines with fontTools. If the mark ever needs to change, regenerate from the outlines rather than editing paths by hand: draw the initials in Source Serif 4 Medium at 56% of the tile height, tracking -0.03 em, optically centered at 46% of the tile height, then export at each size.
