# Monogram & Initials Generator with Optical Kerning & Self-Calibration Engine

A pure Python monogram generator and layout inspection suite that creates high-resolution SVG and PNG monograms. Features an **Optical Kerning Engine**, a **Visual SVG Inspection Studio**, and an **Automated Self-Correcting Auto-Tuner**.

---

## 📖 The Problem & Evolutionary Journey

### 1. The Challenge of Monogram Spacing
In standard typography, letter spacing (kerning) is designed for running body text at small point sizes. In monogram design, initials are displayed at massive scale (100pt–300pt+) as standalone 1-, 2-, 3-, or 4-letter combinations.

During early testing, standard uniform character spacing produced severe visual flaws:
* **Clipping & Canvas Overflows**: Extra-wide letters (`W`, `M`), hyphenated surnames (`S-C`), or 4-name initials clipped against canvas boundaries.
* **Letter Collisions**: Asymmetric diagonal letters (`A` + `V`, `W` + `A`, `L` + `Y`, `T` + `A`) overlapped or merged into unreadable shapes.
* **Awkward Floating Whitespace**: Narrow letters (`I`, `J`, `L`) left empty gaps around them when assigned fixed slot widths.
* **Multi-Scale Scaling Failures**: In traditional monograms, the center surname initial is **1.8x–2.5x larger** than flanking given-name initials. Fixed center-to-center distances caused wide center letters to crush side initials, while narrow center letters left side initials floating far away.

---

## 🛠️ The Three-Phase Solution

To solve these layout challenges, we designed a 3-part architecture:

```
  ┌─────────────────────────────────┐
  │  Phase 1: Optical Kerning       │
  │  Rule-based width weighting &   │
  │  pairwise kerning offsets       │
  └────────────────┬────────────────┘
                   │
                   ▼
  ┌─────────────────────────────────┐
  │  Phase 2: Visual Inspection     │
  │  'viewer.html' with DOM bounds  │
  │  & grid/carousel inspection     │
  └────────────────┬────────────────┘
                   │
                   ▼
  ┌─────────────────────────────────┐
  │  Phase 3: Self-Correcting Tuner │
  │  'auto_tuner.py' inspects bbox  │
  │  metrics & auto-tunes JSON      │
  └─────────────────────────────────┘
```

### Phase 1: Rule-Based Optical Kerning Engine
Each letter is assigned an optical width factor (`GLYPH_WIDTH_RATIOS`) and pair-specific offset (`KERNING_PAIRS`):
* **Slanted Diagonals**: Pairs like `A`+`V`, `W`+`A`, `L`+`Y`, `T`+`A` receive negative kerning offsets (`-0.10em` to `-0.15em`) so diagonal strokes nest together.
* **Narrow Initial Compensation**: `I` (0.32 EM) and `J` (0.44 EM) take less optical space, automatically bringing side letters inward.
* **Dynamic Monogram Center-Spread Math**:
  $$\text{left\_spread} = \frac{\text{width}(L_{\text{left}})}{2} + \frac{\text{width}(L_{\text{center}})}{2} + \text{base\_gap} + \text{kerning\_pair}(L_{\text{left}}, L_{\text{center}})$$

### Phase 2: Visual SVG Inspection Studio (`viewer.html`)
To visualize where every SVG sits within its DOM bounding container, we created a web inspection studio:
* **Grid & Carousel View Modes**: Toggle between viewing all monograms on a single page or stepping through one-by-one with keyboard arrow keys (`←`, `→`, `Esc`).
* **SVG DOM Bounds Overlay**: Displays bright cyan dashed border outlines around the SVG DOM bounding element and an `SVG DOM BOUNDS` badge to reveal margins and centering.
* **Drag-and-Drop & Folder Selection**: Load any monogram folder or drop `.svg` files directly into the browser.
* **Canvas Theme Switcher**: Toggle between Dark Slate, Light White, and Grid Checkerboard background modes.

### Phase 3: Automated Self-Correcting Auto-Tuner (`auto_tuner.py`)
To eliminate manual trial and error, we built a self-calibration engine:
1. **Font Bounding Box Extraction**: Uses Pillow (`ImageFont.getbbox()`) to measure true pixel bounding boxes for any font family (e.g. Georgia, Cinzel, Times, or custom `.ttf`/`.otf` files).
2. **Diagnostic Metric Sweep**: Analyzes left/right canvas margins, top/bottom margins, inter-letter gaps, clipping risks ($M < 15\text{px}$), and collisions ($G < 8\text{px}$).
3. **Automated Feedback Loop**: If a pair collides, the tuner increases the kerning clearance; if a pair floats too far, it pulls them closer.
4. **Config Export**: Exports optimized parameters to `kerning_config.json`, which `monogram_v1.py` automatically detects and loads on startup.

---

## 📂 Codebase File Guide

| File | Description |
| :--- | :--- |
| **[`monogram_v1.py`](monogram_v1.py)** | Main generator CLI/TUI script. Handles single tests, batch generation, font showcases, and auto-tuner integration. |
| **[`auto_tuner.py`](auto_tuner.py)** | Automated layout inspection and self-calibration tuner script. |
| **[`viewer.html`](viewer.html)** | Web-based SVG Inspection Studio with Grid/Carousel modes and SVG DOM bounds overlay. |
| **[`kerning_config.json`](kerning_config.json)** | Dynamically generated configuration containing auto-tuned character ratios and kerning pairs. |
| **[`monograms.py`](monograms.py)** | Standard library version with optical kerning. |

---

## 🚀 Quick Start & Workflow

### 1. Generate Test Monograms
Run the interactive menu in Python:
```powershell
python monogram_v1.py
```
Or run a batch font showcase:
```powershell
python -c "import monogram_v1; monogram_v1.run_font_showcase('Georgia', 'showcase_georgia', True, False)"
```

### 2. Run the Automated Self-Calibration Engine
To auto-tune kerning metrics for a specific font family:
```powershell
python auto_tuner.py Georgia
```
This runs a diagnostic sweep, fixes letter collisions, and updates `kerning_config.json`.

### 3. Inspect Results in `viewer.html`
Open [`viewer.html`](viewer.html) in your browser or copy it into any output folder to inspect visual DOM boundaries, test light/dark contrast, and step through monograms using Carousel mode.

---

## 🎨 Layout Styles Supported

1. **Traditional Monogram (`trad`)**:
   Enlarged center surname initial with smaller flanking given-name initials. Supports 2-name, 3-name, 4-name, and hyphenated names (`S-C`).
2. **Dots Initials (`dots`)**:
   Clean linear row of initials with periods (`A.M.S.`). Uses explicit `<tspan x="...">` coordinate positioning derived from glyph optical widths.
