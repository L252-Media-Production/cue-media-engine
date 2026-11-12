# UI scale audit and proposal

Step A of the scaling work. Nothing in `player.py` was changed for this document. Numbers come from the CSS in the embedded `UI` string
(about 42 KB, 546 rule blocks) and from computed sizes measured in a real browser (Playwright, Chromium) on the running page.
The "after" screenshots are mocks made by injecting a CSS override into the page; they are not in the code.

## 1. What is in use today

### Units
| Unit | Uses in CSS values | Where |
|---|---|---|
| `rem` | 360 | paddings, gaps, most widths and some heights |
| `px` | 205 | icon boxes, meter bars, many heights, border radii, `--fs`, `--btn`, `--ibs` |
| `em` | 82 | most `font-size` values (`.9em`, `.85em`...) |
| `vw` / `vh` / `dvh` | 9 / 5 / 1 | dialog widths, popover widths |

`html` has no `font-size`, so `1rem` is always the browser default (16 px). The body text size is a **pixel** token (`--fs`) set per skin,
and `em` values scale from that. So text follows the skin, but `rem` paddings and widths follow the browser, and the two do not move together.

### Skin tokens (the only existing "scale")
| Skin | `--fs` | `--btn` | `--ibs` (row icon button) | `--pad` | `--r` |
|---|---|---|---|---|---|
| console (default) | 13.5 px | 28 px | 24 px | .45rem | 4 px |
| studio | 14.5 px | 32 px | 28 px | .65rem | 12 px |
| stage | 16 px | 46 px | 40 px | .8rem | 14 px |

### Font sizes: 22 distinct declared values
`.9em` (12 rules), `.85em` (11), `.8em` (7), `.78em`, `.72em`, `.75em`, `.82em`, `.88em`, `.92em`, `.7em`, `.66em`, `.62em`, `1em`, `1.02em`, `1.05em`,
`1.1em`, `1.35em`, `2.2em`, plus `.8rem` (2), `1rem`, `1.1rem`, `1.15rem`. Because they stack (em inside em), the **rendered** sizes in the console skin
range from 9.7 px (dB badge) through 10.9 (selects), 11.1 (PVW / Go on rows), 11.5 (preview select), 12 (M / S), 12.2 (rows, Play), 12.8 (Xfade) to 13.5 (base), 29.7 (Go) and 80 (countdown).
Nine different sizes sit between 9.7 and 13.5 px.

### Control heights (rendered, console skin, 100 %)
| Control | h x w px | Source |
|---|---|---|
| Header STOP ALL / Settings | 28 | `--btn` |
| Live pause / fade / stop | 28 x 40 | `--btn`, `.ic` width 2.5rem |
| Live M / S | **26 x 26** | hard-coded 26 px |
| Live Output select | 28 | `--btn` |
| Cue A-B / Prev / Next | 28 | `--btn` |
| Cue Go | 80 x 109 | hard-coded 5rem x 6.8rem |
| Cue Cut / Crossfade toggle | **22 and 13** high (stage) | squeezed by the Go column |
| Cue Xfade box | 28 x 37 | `--btn` |
| Row PVW | **24** x 44 | `--ibs` |
| Row Go | **22** x 36 | `--ibs`, smaller text |
| Row end-action / info / trim / delete | **24 x 24-28** | `--ibs` |
| Playlist Play / edit / delete | 24 | `--btn` - 4 px |
| Playlist behavior / Level match selects | **24**, 10.9 px text | `--btn` - 4 px |
| Preview transport | 28 x 42 | `--btn` |
| Preview target select | **20**, 11.5 px text | `--btn` - 8 px |
| Library row buttons | 24 x 44 | `--ibs` |

Distinct `min-height` values in CSS: 16 (`var(--btn)`, `calc(var(--btn) - 4/6/8px)`, `var(--ibs)`, 26 px, 30 px, 1.3em, 1.5rem, 1.7em, 2.4em, 3rem...). Distinct `height`
values: 27. Distinct `width`: 45. Distinct `padding` shorthands: 48. Distinct `gap`: 27. Border radii: 14 (27 rules use `--r`).

### Icon sizes (inline SVG)
`16x16` (9 icons), `20x20` (3), `15x15` (3), `18x18` (2), `18x16` (2), `20x16`, `18x14`, `14x14`, `13x13`. Nine sizes for what are about four roles
(row icons, control icons, transport icons, inline marks). Row icons alone use 15, 16 and 18.

### Obvious unevenness (measured, console skin)
- A 24 px row button holds a 16 px icon, while the same row's info icon is 15 px in a 24 px box: icons do not line up optically.
- Row button text is 11.1-12.2 px next to 14.2 px row text; selects use 10.9 px.
- Live buttons are 28 px, M / S are 26 px, rows are 24 px, the preview select is 20 px: four heights within one screen.
- The Cut / Crossfade toggle (22 px tall in console, 13 px in stage) sits beside an 80 px Go.
- The stage skin already has comfortable sizes for rows (40 px) but its Cue toggle collapses to 13 px, so skins are not consistent with each other either.

## 2. How the UI responds today

| Condition | Behaviour |
|---|---|
| **Browser zoom 125 % / 150 %** | Everything scales uniformly (all CSS px). Measured: identical CSS sizes at 100/125/150 %. Because nothing changes in proportion, the small controls stay small relative to everything else. At 150 % a 1400 px window becomes about 933 CSS px and crosses the 1000 px / 850 px breakpoints, so the layout reflows (this works). |
| **Browser "default font size" setting** | Ignored by body text (px token), honoured by `rem` paddings and widths: spacing grows, text does not. |
| **Window width** | Five breakpoints (1250, 1000, 850, 700 px and 34rem) change the **layout** only. Control, icon and text sizes are identical at 420, 820 and 1400 px (measured). |
| **Large monitor (1920, 2560, 4K)** | `body{max-width:1320px}`, no fluid scaling: on a 4K screen at 100 % the whole UI is the same small CSS size, centred, with wide empty margins. |
| **Phone / tablet (touch)** | No `pointer:coarse` / `hover:none` rules. Row controls are 24 x 24 CSS px, selects 20-24 px: below the usual 40-44 px touch target. The stage skin (46 / 40 px) is the only comfortable option and must be chosen by hand. The viewport meta tag is present; `text-size-adjust` is not set. |
| **High-DPI / Retina** | Fine. Waveform and meter canvases use `devicePixelRatio`; icons are inline SVG; there are no raster images; borders are 1 CSS px. No change needed. |

## 3. Proposal: a small scale system

Principle: **sizes are chosen per role, not per component, and everything is in `rem`** so text, spacing, icons and controls move together with browser zoom, the browser's
font-size setting, the skin and the screen. A skin or a coarse pointer changes the root size and the control tokens, not individual rules.

### 3.1 Root and tokens
```css
html{font-size:100%}                              /* 1rem = the browser setting (16px) */
:root{
  /* text */  --t-xs:.75rem;  --t-sm:.8125rem;  --t-md:.875rem;  --t-lg:1rem;  --t-xl:1.25rem;   /* 12, 13, 14, 16, 20 px  (nothing below 12 px) */
  /* icons */ --i-sm:1rem;    --i-md:1.125rem;  --i-lg:1.375rem;                                  /* 16, 18, 22 px */
  /* controls */ --c-sm:1.75rem; --c-md:2.125rem; --c-lg:2.75rem;                                /* 28, 34, 44 px */
  --gap:.4rem;  --pad:.55rem;
}
@media (pointer:coarse){ :root{ --c-sm:2.5rem; --c-md:2.75rem; --c-lg:3rem; --i-sm:1.25rem; --i-md:1.375rem; --t-sm:.875rem } }   /* 40 / 44 / 48 px touch targets */
@media (min-width:1700px){ html{font-size:112.5%} }  @media (min-width:2300px){ html{font-size:131.25%} }   /* large monitors: 18 px, 21 px root */
body{max-width:82rem}                                 /* was 1320px: now grows with the root size */
```
Skins become **density** presets on the same tokens, instead of separate pixel tables: console keeps the `-sm` / `-md` values above (compact), studio adds about 10 %, stage uses the coarse-pointer values.
The skin's colours and radius are unaffected.

### 3.2 Roles (one size per role)
| Role | Text | Icon | Height |
|---|---|---|---|
| Primary action (Go, STOP ALL, transport: pause / fade out / stop) | `--t-lg` | `--i-lg` (22) | `--c-lg` (44) |
| Standard control (Cue buttons, selects, inputs, Output, Settings buttons, M / S, Play / Shuffle, header buttons) | `--t-md` (14, selects 13) | `--i-md` (18) | `--c-md` (34) |
| Row control (PVW, Go, end-action, trim, info, move, delete; library rows) | `--t-xs` (12) | `--i-sm` (16) | `--c-sm` (28) |
| Row text, names | `--t-md` | - | - |
| Secondary text (index `/0/1`, durations, badges, hints) | `--t-xs` | - | - |
| Countdown, track title | unchanged (large display sizes) | - | - |

Selects and number inputs use 13 px text, never below 12 px. The dB badge (now 9.7 px) becomes 12 px.

### 3.3 What changes and what does not
Changes (all by replacing hard-coded values with the tokens above): the Cue panel (toggle icons 18 to 22 px and the toggle no longer squeezed, Xfade box, buttons 28 to 34 px, Go slightly taller),
the Live card (transport 28 to 44 px, M / S 26 to 34 px, select 28 to 34 px), playlist rows (controls 24 to 28 px, icons 15-18 to 16 px, text 11 to 12 px, dB badge 9.7 to 12 px),
the playlist header (Play, edit, delete, selects 24 to 34 px), the Preview panel (target select 20 to 34 px), library rows, Settings and dialog controls (to `--c-md`), header buttons.
With `pointer:coarse` every row control becomes 40 px and every standard control 44 px.
Does not change: colours, layout breakpoints, the meters and waveforms (already `devicePixelRatio`-aware), the countdown and title display sizes, the stage page.

### 3.4 Cost
Measured with the mock below (console density, fine pointer, 1400 px): playlist panel 1334 to 1434 px for 35 rows (+7.5 %, still one line per row), Cue panel 156 to 162 px,
Live card 198 to 206 px. At 420 px the Cue panel grows 225 to 243 px. On touch devices rows are about 40 px tall (+60 % over today), which is the price of a real touch target;
a Settings option "Larger controls" can force or cancel that on any device.
Risk: rows must stay on one line at the 650 px playlist column. At 32 px row buttons they wrapped in a first mock (+38 % height), which is why row controls are **28 px** on a fine pointer. A 5-icon row
(info, PVW, Go, end-action, trim) plus the move / delete / crossfade controls is the width limit.

### 3.5 Implementation plan (small steps, each checked in 3 widths, 100 % / 125 % zoom, light and dark)
1. Add the token block and `html{font-size}` rules; keep every existing rule (no visible change). Convert `--fs`, `--btn`, `--ibs` to `rem` tokens derived from the new ones.
2. Row and library controls to `--c-sm` / `--i-sm` / `--t-xs` (the biggest visual change).
3. Standard controls to `--c-md` (selects, header, Cue, Preview, Live M / S); minimum text 12 px (dB badge, selects).
4. Primary controls to `--c-lg` / `--i-lg` (Go group and its toggle, Live transport, STOP ALL).
5. `pointer:coarse` and large-monitor rules, `text-size-adjust`, Settings option "Larger controls".
6. Settings and dialogs, then the Help text and the README.

## 4. Mock screenshots (in a scratch folder, not kept in the repository)
- `m-pair-cue-dark-1400.png`, `m-pair-cue-light-1400.png`, `m-pair-cue-dark-420.png`
- `m-pair-rows-dark-1400.png`, `m-pair-rows-light-1400.png`, `m-pair-rows-dark-420.png`
- `m-pair-live-dark-1400.png`, `m-pair-live-light-1400.png`, `m-pair-live-dark-420.png`
Each is BEFORE (left or top) and AFTER (mock). The mock CSS is `mock.css` in the same folder.
