#!/usr/bin/env python3
"""
Monogram & Initials Generator with Interactive Menu (TUI)

Features:
- Pure Python standard library (Zero third-party dependencies for SVG & Menu).
- Decoupled PNG output via cairosvg (optional).
- Strict naming convention:
    {initials}_{name_structure}_{style}_{hyph|nohy}_{font_slug}.{ext}
- Comprehensive "Font Showcase" mode to preview all layout variations at once.
- Dual-style generation ("Both" traditional and dots) in batch runs.
"""

import itertools
import os
import re
import string
import sys
from typing import List, Tuple, Optional

# --- Filename & Text Sanitization ---

def sanitize_font_slug(font_name: str) -> str:
    """Sanitizes font names into clean, URL/POSIX-friendly slugs."""
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', font_name.strip().lower())
    return slug.strip('-')

def build_filename(
    initials_tokens: List[str],
    name_structure: str,
    style: str,
    has_hyphen: bool,
    font_slug: str,
    ext: str
) -> str:
    """Format: {initials}_{name_structure}_{style}_{hyph|nohy}_{font_slug}.{ext}"""
    initials_str = "_".join(initials_tokens)
    hyph_flag = "hyph" if has_hyphen else "nohy"
    return f"{initials_str}_{name_structure}_{style}_{hyph_flag}_{font_slug}.{ext}"


# --- Optical Kerning Engine ---

# Optical width ratio of uppercase letters relative to 1.0 EM height
GLYPH_WIDTH_RATIOS = {
    'A': 0.82, 'B': 0.68, 'C': 0.72, 'D': 0.75, 'E': 0.64, 'F': 0.60,
    'G': 0.76, 'H': 0.76, 'I': 0.32, 'J': 0.44, 'K': 0.74, 'L': 0.56,
    'M': 0.96, 'N': 0.76, 'O': 0.78, 'P': 0.64, 'Q': 0.78, 'R': 0.70,
    'S': 0.66, 'T': 0.62, 'U': 0.74, 'V': 0.80, 'W': 1.10, 'X': 0.78,
    'Y': 0.78, 'Z': 0.68, '-': 0.40, '.': 0.25
}

# Specific kerning pair offsets (as fraction of font size em)
# Negative values pull letters closer together, positive values push apart
KERNING_PAIRS = {
    # Slanted diagonals (A, V, W, Y, K)
    ('A', 'V'): -0.14, ('A', 'W'): -0.15, ('A', 'Y'): -0.13, ('A', 'T'): -0.10,
    ('V', 'A'): -0.14, ('W', 'A'): -0.15, ('Y', 'A'): -0.13, ('T', 'A'): -0.10,
    ('L', 'V'): -0.16, ('L', 'W'): -0.16, ('L', 'Y'): -0.16, ('L', 'T'): -0.12,
    ('L', 'A'): -0.06,
    ('F', 'A'): -0.10, ('P', 'A'): -0.08,
    
    # Round + Slanted
    ('A', 'C'): -0.06, ('A', 'O'): -0.05, ('A', 'G'): -0.05, ('A', 'Q'): -0.05,
    ('C', 'A'): -0.05, ('O', 'A'): -0.05, ('G', 'A'): -0.05,
    ('V', 'O'): -0.08, ('W', 'O'): -0.08, ('Y', 'O'): -0.08,
    ('O', 'V'): -0.08, ('O', 'W'): -0.08, ('O', 'Y'): -0.08,
    
    # Top bar (T, F) with round or straight
    ('T', 'O'): -0.08, ('T', 'C'): -0.08, ('F', 'O'): -0.06, ('F', 'C'): -0.06,

    # Straight wall pairs (H, M, N, U, I)
    ('M', 'M'): 0.03, ('H', 'H'): 0.03, ('N', 'N'): 0.02, ('U', 'U'): 0.02,
    ('I', 'I'): 0.06,
}

def get_char_width(char: str, font_size: float) -> float:
    """Calculates optical width of a single character in pixels."""
    ratio = GLYPH_WIDTH_RATIOS.get(char.upper(), 0.70)
    return font_size * ratio

def get_str_width(text: str, font_size: float) -> float:
    """Calculates total optical width of a string including internal kerning."""
    if not text:
        return 0.0
    total = sum(get_char_width(c, font_size) for c in text)
    for i in range(len(text) - 1):
        pair = (text[i].upper(), text[i+1].upper())
        k_offset = KERNING_PAIRS.get(pair, 0.0) * font_size
        total += k_offset
    return total

def get_pair_kerning(str1: str, str2: str, font_size: float) -> float:
    """Returns kerning adjustment between right edge of str1 and left edge of str2."""
    if not str1 or not str2:
        return 0.0
    c1 = str1[-1].upper()
    c2 = str2[0].upper()
    return KERNING_PAIRS.get((c1, c2), 0.0) * font_size


# --- Layout & SVG Builders ---

def render_dots_svg(
    tokens: List[str],
    font_family: str,
    canvas_w: int = 800,
    canvas_h: int = 400
) -> str:
    """
    Renders initials in a linear row with full stops.
    Uses optical glyph widths and pairwise kerning to precisely position every letter & period.
    """
    # Build list of (character, is_dot)
    items = []
    for token in tokens:
        for char in token:
            items.append((char, False))
        items.append((".", True))

    # Preliminary font size scaling based on total optical width
    total_opt_units = sum(GLYPH_WIDTH_RATIOS.get(c.upper(), 0.70) for c, is_dot in items)
    font_size = int(min(canvas_h * 0.45, (canvas_w * 0.85) / max(total_opt_units, 1.0)))
    center_y = canvas_h / 2

    # Calculate precise individual element widths and x-positions
    widths = [get_char_width(c, font_size) for c, is_dot in items]
    dot_gap = font_size * 0.06
    char_gap = font_size * 0.12

    positions = []
    curr_x = 0.0

    for i in range(len(items)):
        char, is_dot = items[i]
        if i == 0:
            positions.append(0.0)
            curr_x += widths[i]
        else:
            prev_char, prev_is_dot = items[i - 1]
            if is_dot:
                gap = dot_gap
            elif prev_is_dot:
                gap = char_gap
            else:
                pair_k = get_pair_kerning(prev_char, char, font_size)
                gap = char_gap + pair_k

            curr_x += gap
            positions.append(curr_x)
            curr_x += widths[i]

    total_width = curr_x
    start_x = (canvas_w - total_width) / 2

    tspans = []
    for i, (char, is_dot) in enumerate(items):
        pos_x = start_x + positions[i] + (widths[i] / 2)
        fill_attr = ' fill="#666666"' if is_dot else ''
        tspans.append(f'<tspan x="{pos_x:.1f}"{fill_attr}>{char}</tspan>')

    tspan_block = "\n    ".join(tspans)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {canvas_h}" width="{canvas_w}" height="{canvas_h}">
  <style>
    .mono-text {{
      font-family: "{font_family}", Georgia, serif;
      font-size: {font_size}px;
      font-weight: 500;
      fill: #111111;
      text-anchor: middle;
      dominant-baseline: central;
    }}
  </style>
  <rect width="100%" height="100%" fill="none"/>
  <text y="{center_y}" class="mono-text">
    {tspan_block}
  </text>
</svg>"""


def render_trad_svg(
    first_tokens: List[str],
    surname_token: str,
    font_family: str,
    canvas_w: int = 800,
    canvas_h: int = 500
) -> str:
    """
    Renders traditional monogram with center surname letter enlarged.
    Uses optical width math and pairwise kerning to dynamically compute left/right offsets.
    """
    center_x = canvas_w / 2
    center_y = canvas_h / 2

    total_flank = len(first_tokens)
    mid = (total_flank + 1) // 2
    left_tokens = first_tokens[:mid]
    right_tokens = first_tokens[mid:]

    left_str = "".join(left_tokens)
    right_str = "".join(right_tokens)

    sur_len = len(surname_token)
    if sur_len > 1:
        large_size = int(canvas_h * (0.65 / (sur_len * 0.75)))
    else:
        large_size = int(canvas_h * 0.62)

    max_flank_len = max(len(left_str), len(right_str), 1)
    small_size = int(min(large_size * 0.55, (canvas_w * 0.24) / max_flank_len))

    center_width = get_str_width(surname_token, large_size)
    left_width = get_str_width(left_str, small_size)
    right_width = get_str_width(right_str, small_size)

    base_gap = canvas_w * 0.035
    avg_size = (large_size + small_size) / 2

    left_kerning = get_pair_kerning(left_str, surname_token, avg_size) if left_str else 0.0
    right_kerning = get_pair_kerning(surname_token, right_str, avg_size) if right_str else 0.0

    left_spread = (left_width / 2) + (center_width / 2) + base_gap + left_kerning
    right_spread = (center_width / 2) + (right_width / 2) + base_gap + right_kerning

    left_x = center_x - left_spread
    right_x = center_x + right_spread

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {canvas_h}" width="{canvas_w}" height="{canvas_h}">
  <style>
    .trad-large {{
      font-family: "{font_family}", Georgia, serif;
      font-size: {large_size}px;
      font-weight: 600;
      fill: #111111;
      text-anchor: middle;
      dominant-baseline: central;
    }}
    .trad-small {{
      font-family: "{font_family}", Georgia, serif;
      font-size: {small_size}px;
      font-weight: 400;
      fill: #222222;
      text-anchor: middle;
      dominant-baseline: central;
    }}
  </style>
  <rect width="100%" height="100%" fill="none"/>
  {f'<text x="{left_x:.1f}" y="{center_y}" class="trad-small">{left_str}</text>' if left_str else ''}
  <text x="{center_x:.1f}" y="{center_y}" class="trad-large">{surname_token}</text>
  {f'<text x="{right_x:.1f}" y="{center_y}" class="trad-small">{right_str}</text>' if right_str else ''}
</svg>"""


# --- Decoupled PNG Exporter ---

def export_svg_to_png(svg_string: str, output_path: str) -> bool:
    """Renders SVG string to PNG using cairosvg if available."""
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg_string.encode('utf-8'), write_to=output_path)
        return True
    except ImportError:
        sys.stderr.write("\n[Notice] 'cairosvg' not installed. Skipped PNG generation.\n")
        return False
    except Exception as e:
        sys.stderr.write(f"\n[Error] Failed to render PNG {output_path}: {e}\n")
        return False


# --- Parsing & Core Generation ---

def parse_name_to_tokens(name: str, keep_hyphen: bool = True) -> Tuple[List[str], str, bool]:
    """Parses a full name into (given_tokens, surname_token, has_hyphen)."""
    parts = name.strip().split()
    if not parts:
        return ([], "", False)

    has_hyphen = any("-" in part for part in parts)
    tokens = []
    for part in parts:
        if "-" in part:
            subparts = [p[0].upper() for p in part.split("-") if p]
            tokens.append("-".join(subparts) if keep_hyphen else "".join(subparts))
        else:
            tokens.append(part[0].upper())

    if len(tokens) == 1:
        return ([], tokens[0], has_hyphen)
    return (tokens[:-1], tokens[-1], has_hyphen)


def generate_monogram_asset(
    tokens: List[str],
    name_structure: str,
    style: str,
    has_hyphen: bool,
    font_name: str,
    output_dir: str,
    generate_svg: bool = True,
    generate_png: bool = False
):
    os.makedirs(output_dir, exist_ok=True)
    font_slug = sanitize_font_slug(font_name)

    if style == "dots":
        svg_content = render_dots_svg(tokens, font_name)
    else:
        flank = tokens[:-1]
        surname = tokens[-1]
        svg_content = render_trad_svg(flank, surname, font_name)

    if generate_svg:
        svg_filename = build_filename(tokens, name_structure, style, has_hyphen, font_slug, "svg")
        with open(os.path.join(output_dir, svg_filename), "w", encoding="utf-8") as f:
            f.write(svg_content)

    if generate_png:
        png_filename = build_filename(tokens, name_structure, style, has_hyphen, font_slug, "png")
        export_svg_to_png(svg_content, os.path.join(output_dir, png_filename))


# --- Batch & Showcase Generators ---

def run_batch(
    names_count: int,
    surname_letter: Optional[str],
    hyphenated_surname: bool,
    keep_hyphen: bool,
    styles: List[str],
    font_name: str,
    output_dir: str,
    generate_svg: bool,
    generate_png: bool
):
    letters = list(string.ascii_uppercase)
    num_given = names_count - 1

    primary_surnames = [surname_letter.upper()] if surname_letter else letters

    if hyphenated_surname:
        surname_tokens = []
        for s1 in primary_surnames:
            for s2 in letters:
                token = f"{s1}-{s2}" if keep_hyphen else f"{s1}{s2}"
                surname_tokens.append(token)
        struct_tag = f"{names_count}name-hyph"
    else:
        surname_tokens = primary_surnames
        struct_tag = f"{names_count}name"

    given_combos = itertools.product(letters, repeat=num_given)

    print(f"\n[Processing] Output directory: {output_dir}")
    count = 0
    for given in given_combos:
        for sur in surname_tokens:
            tokens = list(given) + [sur]
            for style in styles:
                generate_monogram_asset(
                    tokens=tokens,
                    name_structure=struct_tag,
                    style=style,
                    has_hyphen=hyphenated_surname,
                    font_name=font_name,
                    output_dir=output_dir,
                    generate_svg=generate_svg,
                    generate_png=generate_png
                )
                count += 1
                if count % 500 == 0:
                    print(f"  Generated {count} items...", end="\r", flush=True)

    print(f"\n[Success] Done! Generated {count} monograms in '{output_dir}'.\n")


def run_font_showcase(
    font_name: str,
    output_dir: str,
    generate_svg: bool,
    generate_png: bool
):
    """
    Generates a full showcase suite covering:
    - 2-name, 3-name, 4-name
    - Hyphenated last (with & without hyphen)
    - Hyphenated first (with & without hyphen)
    - Both 'trad' and 'dots' styles
    """
    matrix = [
        # (tokens, name_structure, has_hyphen, description)
        (["A", "W"], "2name", False, "2-Name (First, Last)"),
        (["J", "F", "W"], "3name", False, "3-Name (First, Middle, Last)"),
        (["E", "C", "A", "W"], "4name", False, "4-Name (First, 2 Middles, Last)"),
        (["J", "F", "S-C"], "4name-hyph", True, "3-Name with Hyphenated Last (Hyphen On)"),
        (["J", "F", "SC"], "4name-hyph", False, "3-Name with Hyphenated Last (Hyphen Off)"),
        (["A-M", "C", "W"], "3name-hyph", True, "Hyphenated First Name (Hyphen On)"),
        (["AM", "C", "W"], "3name-hyph", False, "Hyphenated First Name (Hyphen Off)"),
    ]

    styles = ["trad", "dots"]
    total_renders = len(matrix) * len(styles)

    print(f"\n[Showcase] Generating {total_renders} test variations for font: '{font_name}'...")
    print(f"Directory: {output_dir}\n")

    for tokens, struct_tag, has_hyph, desc in matrix:
        for style in styles:
            generate_monogram_asset(
                tokens=tokens,
                name_structure=struct_tag,
                style=style,
                has_hyphen=has_hyph,
                font_name=font_name,
                output_dir=output_dir,
                generate_svg=generate_svg,
                generate_png=generate_png
            )
            print(f"  [+] Rendered: {desc:<45} [{style.upper()}]")

    print(f"\n[Success] Showcase complete! Inspect files in '{output_dir}'.\n")


# --- Interactive Menu Helpers ---

def prompt_choice(prompt: str, options: List[str], default: int = 1) -> int:
    """Presents a numbered list and returns 1-indexed selection."""
    print(f"\n{prompt}")
    for idx, opt in enumerate(options, 1):
        indicator = " (default)" if idx == default else ""
        print(f"  [{idx}] {opt}{indicator}")
    while True:
        choice = input(f"Select option [1-{len(options)}] (Enter for {default}): ").strip()
        if not choice:
            return default
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return int(choice)
        print("Invalid input. Please enter a valid number.")

def prompt_text(prompt: str, default: str) -> str:
    val = input(f"\n{prompt} [{default}]: ").strip()
    return val if val else default

def prompt_bool(prompt: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    val = input(f"{prompt} ({default_str}): ").strip().lower()
    if not val:
        return default
    return val in ["y", "yes", "true", "1"]


# --- Menu Orchestration ---

def interactive_single_test():
    print("\n" + "="*50)
    print("         SINGLE MONOGRAM TEST GENERATOR")
    print("="*50)

    name = input("\nEnter full name (e.g., 'Ann-Marie Jane Smith-Clark'): ").strip()
    if not name:
        print("[Aborted] No name entered.")
        return

    style_idx = prompt_choice("Select layout style:", [
        "Traditional (Enlarged center surname)",
        "Dots (Linear initials with periods)",
        "Both (Generate traditional and dots)"
    ], default=1)
    
    styles = ["trad"] if style_idx == 1 else (["dots"] if style_idx == 2 else ["trad", "dots"])

    keep_hyphen = prompt_bool("Retain visible hyphens if present?", default=True)
    font_name = prompt_text("Enter font family name", default="Cinzel")
    out_dir = prompt_text("Output directory", default="./monograms_test")

    fmt_idx = prompt_choice("Select output formats:", [
        "SVG only",
        "PNG only (requires cairosvg)",
        "Both SVG and PNG"
    ], default=1)
    gen_svg = fmt_idx in [1, 3]
    gen_png = fmt_idx in [2, 3]

    flank, surname, has_hyphen = parse_name_to_tokens(name, keep_hyphen=keep_hyphen)
    tokens = flank + [surname]
    struct_tag = f"{len(tokens)}name" + ("-hyph" if has_hyphen else "")

    print(f"\nParsed tokens: {tokens} | Flag: {'hyph' if has_hyphen else 'nohy'}")
    for style in styles:
        generate_monogram_asset(
            tokens=tokens,
            name_structure=struct_tag,
            style=style,
            has_hyphen=has_hyphen,
            font_name=font_name,
            output_dir=out_dir,
            generate_svg=gen_svg,
            generate_png=gen_png
        )
    print(f"[Success] Generated test monogram(s) in '{out_dir}'")


def interactive_font_showcase():
    print("\n" + "="*50)
    print("      FONT SHOWCASE & TEST SUITE GENERATOR")
    print("="*50)
    print("Generates a complete matrix of all configurations (2-4 names,")
    print("hyphenated, un-hyphenated, traditional, and dots) for a quick font check.")

    font_name = prompt_text("Enter font family name to test", default="Georgia")
    out_dir = prompt_text("Output directory", default=f"./showcase_{sanitize_font_slug(font_name)}")

    fmt_idx = prompt_choice("Select output formats:", [
        "SVG only",
        "PNG only (requires cairosvg)",
        "Both SVG and PNG"
    ], default=1)
    gen_svg = fmt_idx in [1, 3]
    gen_png = fmt_idx in [2, 3]

    run_font_showcase(
        font_name=font_name,
        output_dir=out_dir,
        generate_svg=gen_svg,
        generate_png=gen_png
    )


def interactive_batch():
    print("\n" + "="*50)
    print("           BATCH MONOGRAM GENERATOR")
    print("="*50)

    name_count_idx = prompt_choice("How many names in combination?", [
        "2 Names (First, Last)",
        "3 Names (First, Middle, Last)",
        "4 Names (First, Two Middles, Last)"
    ], default=2)
    names_count = name_count_idx + 1

    surname_filter = input("\nFilter to specific Surname initial? (A-Z, or leave empty for ALL): ").strip().upper()
    if surname_filter and (len(surname_filter) != 1 or surname_filter not in string.ascii_uppercase):
        print("[Warning] Invalid letter. Proceeding with ALL surnames.")
        surname_filter = None

    hyphen_surname = prompt_bool("Use hyphenated surnames (e.g. S-C)?", default=False)
    keep_hyphen = True
    if hyphen_surname:
        keep_hyphen = prompt_bool("Display visual hyphen character (S-C vs SC)?", default=True)

    style_idx = prompt_choice("Select layout style:", [
        "Traditional (Enlarged center surname)",
        "Dots (Linear initials with periods)",
        "Both (Generate traditional AND dots)"
    ], default=1)
    
    if style_idx == 1:
        styles = ["trad"]
    elif style_idx == 2:
        styles = ["dots"]
    else:
        styles = ["trad", "dots"]

    font_name = prompt_text("Enter font family name", default="Georgia")
    out_dir = prompt_text("Output directory", default="./monograms_batch")

    fmt_idx = prompt_choice("Select output formats:", [
        "SVG only",
        "PNG only (requires cairosvg)",
        "Both SVG and PNG"
    ], default=1)
    gen_svg = fmt_idx in [1, 3]
    gen_png = fmt_idx in [2, 3]

    # --- Batch Estimation Safety Check ---
    num_given_combos = 26 ** (names_count - 1)
    num_surname_combos = (1 if surname_filter else 26) * (26 if hyphen_surname else 1)
    total_monograms = num_given_combos * num_surname_combos * len(styles)
    
    print("\n" + "-"*40)
    print(f"ESTIMATED GENERATION COUNT: {total_monograms:,} monogram files")
    if gen_svg and gen_png:
        print(f"Total files written (SVG + PNG): {total_monograms * 2:,}")
    print("-"*40)

    if total_monograms > 5000:
        print("[Caution] This is a large batch that will take significant time and disk space.")

    proceed = prompt_bool("Do you want to proceed?", default=True)
    if not proceed:
        print("[Aborted] Batch canceled.")
        return

    run_batch(
        names_count=names_count,
        surname_letter=surname_filter,
        hyphenated_surname=hyphen_surname,
        keep_hyphen=keep_hyphen,
        styles=styles,
        font_name=font_name,
        output_dir=out_dir,
        generate_svg=gen_svg,
        generate_png=gen_png
    )


def load_tuned_kerning_config(config_path: str = "kerning_config.json"):
    """Loads dynamically auto-tuned kerning configuration if available."""
    global GLYPH_WIDTH_RATIOS, KERNING_PAIRS
    if os.path.exists(config_path):
        try:
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "glyph_width_ratios" in data:
                GLYPH_WIDTH_RATIOS.update(data["glyph_width_ratios"])
            if "kerning_pairs" in data:
                for k, v in data["kerning_pairs"].items():
                    parts = k.split(",")
                    if len(parts) == 2:
                        KERNING_PAIRS[(parts[0], parts[1])] = float(v)
            print(f"[Auto-Tuner] Loaded active kerning config: '{config_path}'")
        except Exception as e:
            sys.stderr.write(f"[Warning] Could not parse '{config_path}': {e}\n")

# Auto-load tuned configuration if present
load_tuned_kerning_config()


def interactive_auto_tuner():
    print("\n" + "="*50)
    print("      MONOGRAM AUTO-TUNER & CALIBRATION ENGINE")
    print("="*50)
    
    mode = prompt_choice("Select Calibration Scope:", [
        "Scan & Calibrate an Existing Monogram Batch Folder (Whole directory)",
        "Run Full 26x26 Alphabet Matrix Sweep (All 676 letter pairs)",
        "Run Quick Diagnostic Sweep (Sample tricky pairs)"
    ], default=1)

    font_name = prompt_text("Enter font family to auto-tune", default="Georgia")
    folder_path = None
    all_pairs = False

    if mode == 1:
        folder_path = prompt_text("Enter path to batch folder containing SVGs/PNGs", default="./monograms_batch")
    elif mode == 2:
        all_pairs = True

    try:
        import auto_tuner
        auto_tuner.run_calibration_sweep(font_family=font_name, folder_path=folder_path, all_pairs=all_pairs)
        load_tuned_kerning_config()
    except Exception as e:
        print(f"[Error] Auto-tuner failed: {e}")



def main():
    while True:
        print("\n" + "="*50)
        print("       MONOGRAM & INITIALS GENERATOR")
        print("="*50)
        choice = prompt_choice("What would you like to do?", [
            "Generate an individual test monogram",
            "Generate a batch of combinations",
            "Font Showcase / Test Suite (Generate all format variations)",
            "Run Auto-Tuner & Self-Calibration Engine",
            "Exit"
        ], default=3)

        if choice == 1:
            interactive_single_test()
        elif choice == 2:
            interactive_batch()
        elif choice == 3:
            interactive_font_showcase()
        elif choice == 4:
            interactive_auto_tuner()
        elif choice == 5:
            print("\nExiting. Happy engraving!")
            break

if __name__ == "__main__":
    main()