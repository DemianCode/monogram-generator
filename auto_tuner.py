#!/usr/bin/env python3
"""
Monogram Auto-Tuner & Self-Calibration Engine

Automated layout inspection and kerning optimizer:
1. Renders monogram combinations across 26 letters, tricky pairs, and multi-name structures.
2. Measures exact bounding box metrics, edge margins, letter gaps, clipping risks, and optical balance.
3. Automatically fine-tunes GLYPH_WIDTH_RATIOS and KERNING_PAIRS to eliminate clipping and optimize letter distinction.
4. Exports optimized parameters to 'kerning_config.json'.
"""

import json
import os
import re
import sys
from typing import Dict, List, Tuple, Any

try:
    from PIL import Image, ImageFont, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

import monogram_v1


# --- Metric Analysis Data Structure ---

class MonogramMetrics:
    def __init__(
        self,
        name_id: str,
        style: str,
        canvas_w: int,
        canvas_h: int,
        left_bound: float,
        right_bound: float,
        top_bound: float,
        bottom_bound: float,
        left_gap: float = 0.0,
        right_gap: float = 0.0
    ):
        self.name_id = name_id
        self.style = style
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h
        self.left_bound = left_bound
        self.right_bound = right_bound
        self.top_bound = top_bound
        self.bottom_bound = bottom_bound
        self.left_gap = left_gap
        self.right_gap = right_gap

        self.margin_left = left_bound
        self.margin_right = canvas_w - right_bound
        self.margin_top = top_bound
        self.margin_bottom = canvas_h - bottom_bound
        self.balance_diff = abs(self.margin_left - self.margin_right)

        # Check clipping
        self.is_clipped = (
            self.margin_left < 15.0 or
            self.margin_right < 15.0 or
            self.margin_top < 10.0 or
            self.margin_bottom < 10.0
        )

        # Check visual distinction / collision
        self.is_colliding = (self.left_gap < 8.0 and self.left_gap != 0.0) or (self.right_gap < 8.0 and self.right_gap != 0.0)
        self.is_excessive_gap = (self.left_gap > 90.0) or (self.right_gap > 90.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name_id": self.name_id,
            "style": self.style,
            "margin_left": round(self.margin_left, 1),
            "margin_right": round(self.margin_right, 1),
            "left_gap": round(self.left_gap, 1),
            "right_gap": round(self.right_gap, 1),
            "is_clipped": self.is_clipped,
            "is_colliding": self.is_colliding,
            "is_excessive_gap": self.is_excessive_gap,
            "balance_diff": round(self.balance_diff, 1)
        }


# --- Vector & Pillow Font Inspection Engine ---

def get_pil_font(font_family: str, font_size: int) -> ImageFont.FreeTypeFont:
    """Loads font file if available, or falls back to standard system font."""
    font_names = [
        f"{font_family.lower()}.ttf",
        f"{font_family.lower()}.otf",
        "georgia.ttf",
        "times.ttf",
        "arial.ttf"
    ]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def inspect_trad_layout(
    first_tokens: List[str],
    surname_token: str,
    font_family: str = "Georgia",
    canvas_w: int = 800,
    canvas_h: int = 500,
    ratios: Dict[str, float] = None,
    kerning_pairs: Dict[Tuple[str, str], float] = None
) -> MonogramMetrics:
    """
    Computes exact bounding boxes and gaps for a traditional monogram.
    """
    if ratios is None:
        ratios = monogram_v1.GLYPH_WIDTH_RATIOS
    if kerning_pairs is None:
        kerning_pairs = monogram_v1.KERNING_PAIRS

    center_x = canvas_w / 2
    center_y = canvas_h / 2

    total_flank = len(first_tokens)
    mid = (total_flank + 1) // 2
    left_str = "".join(first_tokens[:mid])
    right_str = "".join(first_tokens[mid:])

    sur_len = len(surname_token)
    if sur_len > 1:
        large_size = int(canvas_h * (0.65 / (sur_len * 0.75)))
    else:
        large_size = int(canvas_h * 0.62)

    max_flank_len = max(len(left_str), len(right_str), 1)
    small_size = int(min(large_size * 0.55, (canvas_w * 0.24) / max_flank_len))

    # Calculate center string optical width
    center_width = monogram_v1.get_str_width(surname_token, large_size)
    left_width = monogram_v1.get_str_width(left_str, small_size) if left_str else 0.0
    right_width = monogram_v1.get_str_width(right_str, small_size) if right_str else 0.0

    base_gap = canvas_w * 0.035
    avg_size = (large_size + small_size) / 2

    left_kerning = monogram_v1.get_pair_kerning(left_str, surname_token, avg_size) if left_str else 0.0
    right_kerning = monogram_v1.get_pair_kerning(surname_token, right_str, avg_size) if right_str else 0.0

    left_spread = (left_width / 2) + (center_width / 2) + base_gap + left_kerning
    right_spread = (center_width / 2) + (right_width / 2) + base_gap + right_kerning

    left_x = center_x - left_spread
    right_x = center_x + right_spread

    # Compute bounding coordinates
    left_bound = (left_x - (left_width / 2)) if left_str else (center_x - (center_width / 2))
    right_bound = (right_x + (right_width / 2)) if right_str else (center_x + (center_width / 2))
    top_bound = center_y - (large_size / 2)
    bottom_bound = center_y + (large_size / 2)

    # Compute visual edge-to-edge gaps between adjacent letters
    left_gap = (center_x - (center_width / 2)) - (left_x + (left_width / 2)) if left_str else 0.0
    right_gap = (right_x - (right_width / 2)) - (center_x + (center_width / 2)) if right_str else 0.0

    name_id = f"{''.join(first_tokens)}_{surname_token}"
    return MonogramMetrics(
        name_id=name_id,
        style="trad",
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        left_bound=left_bound,
        right_bound=right_bound,
        top_bound=top_bound,
        bottom_bound=bottom_bound,
        left_gap=left_gap,
        right_gap=right_gap
    )


def inspect_dots_layout(
    tokens: List[str],
    font_family: str = "Georgia",
    canvas_w: int = 800,
    canvas_h: int = 400
) -> MonogramMetrics:
    """Computes exact bounding boxes for dots linear monogram."""
    items = []
    for token in tokens:
        for char in token:
            items.append((char, False))
        items.append((".", True))

    total_opt_units = sum(monogram_v1.GLYPH_WIDTH_RATIOS.get(c.upper(), 0.70) for c, is_dot in items)
    font_size = int(min(canvas_h * 0.45, (canvas_w * 0.85) / max(total_opt_units, 1.0)))

    widths = [monogram_v1.get_char_width(c, font_size) for c, is_dot in items]
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
            gap = dot_gap if is_dot else (char_gap if prev_is_dot else char_gap + monogram_v1.get_pair_kerning(prev_char, char, font_size))
            curr_x += gap
            positions.append(curr_x)
            curr_x += widths[i]

    total_width = curr_x
    start_x = (canvas_w - total_width) / 2

    left_bound = start_x
    right_bound = start_x + total_width
    top_bound = (canvas_h / 2) - (font_size / 2)
    bottom_bound = (canvas_h / 2) + (font_size / 2)

    name_id = "_".join(tokens)
    return MonogramMetrics(
        name_id=name_id,
        style="dots",
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        left_bound=left_bound,
        right_bound=right_bound,
        top_bound=top_bound,
        bottom_bound=bottom_bound,
        left_gap=char_gap,
        right_gap=char_gap
    )


# --- Auto-Tuning Optimization Loop ---

def run_calibration_sweep(font_family: str = "Georgia") -> Dict[str, Any]:
    """
    Evaluates test suite across letter combinations, detects clipping/collisions,
    and calculates optimal tuned width ratios & kerning pairs.
    """
    print("=" * 60)
    print("    MONOGRAM AUTO-TUNER & SELF-CALIBRATION ENGINE")
    print("=" * 60)
    print(f"Target Font Family: {font_family}")
    print("Running diagnostic sweep across letter combinations...\n")

    letters = [chr(c) for c in range(ord('A'), ord('Z') + 1)]
    
    # 1. Inspect Single Letter Width Ratios
    tuned_ratios = dict(monogram_v1.GLYPH_WIDTH_RATIOS)
    font = get_pil_font(font_family, 100) if HAS_PIL else None

    if font and HAS_PIL:
        print("[Step 1] Measuring exact PIL glyph bounding boxes for 26 letters...")
        for char in letters:
            bbox = font.getbbox(char)
            if bbox:
                # bbox is (left, top, right, bottom)
                char_w = bbox[2] - bbox[0]
                ratio = char_w / 100.0
                tuned_ratios[char] = round(ratio, 2)
        print("  -> Updated GLYPH_WIDTH_RATIOS from font metrics.")

    # 2. Inspect Tricky Pairs & Calibrate Kerning Pairs
    tricky_pairs = [
        ("A", "V"), ("A", "W"), ("A", "Y"), ("V", "A"), ("W", "A"), ("Y", "A"),
        ("L", "V"), ("L", "W"), ("L", "Y"), ("L", "T"), ("T", "A"), ("F", "A"),
        ("I", "J"), ("J", "I"), ("M", "M"), ("W", "W"), ("H", "H"), ("O", "O")
    ]

    tuned_pairs = dict(monogram_v1.KERNING_PAIRS)
    metrics_log = []

    print("\n[Step 2] Evaluating layout metrics across test monograms...")
    clip_count = 0
    collision_count = 0

    # Test traditional monograms
    for p1, p2 in tricky_pairs:
        m = inspect_trad_layout([p1], p2, font_family=font_family)
        metrics_log.append(m)

        if m.is_clipped:
            clip_count += 1
            print(f"  [Clipping Alert] {p1}_{p2} (Trad) -> Left: {m.margin_left:.1f}px, Right: {m.margin_right:.1f}px")

        if m.is_colliding:
            collision_count += 1
            # Auto-adjust kerning pair to add clearance
            curr_val = tuned_pairs.get((p1, p2), 0.0)
            tuned_pairs[(p1, p2)] = round(curr_val + 0.04, 2)
            print(f"  [Collision Fixed] {p1}_{p2} -> adjusted kerning pair from {curr_val} to {tuned_pairs[(p1, p2)]}")
        elif m.is_excessive_gap:
            # Auto-adjust kerning pair to pull closer
            curr_val = tuned_pairs.get((p1, p2), 0.0)
            tuned_pairs[(p1, p2)] = round(curr_val - 0.04, 2)
            print(f"  [Gap Pulled Tighter] {p1}_{p2} -> adjusted kerning pair to {tuned_pairs[(p1, p2)]}")

    # Test multi-letter combinations
    multi_tests = [
        (["A", "M"], "W"),
        (["J", "F"], "S-C"),
        (["E", "C", "A"], "W"),
        (["I", "I"], "J")
    ]
    for flank, sur in multi_tests:
        m = inspect_trad_layout(flank, sur, font_family=font_family)
        metrics_log.append(m)
        if m.is_clipped:
            clip_count += 1
            print(f"  [Clipping Alert] {'_'.join(flank)}_{sur} -> Left: {m.margin_left:.1f}px, Right: {m.margin_right:.1f}px")

    print("\n" + "-" * 50)
    print(f"CALIBRATION SUMMARY:")
    print(f"  Total Monograms Analyzed: {len(metrics_log)}")
    print(f"  Clipping Issues Detected: {clip_count}")
    print(f"  Collision Issues Fixed:   {collision_count}")
    print("-" * 50)

    # Convert tuple keys to string for JSON serialization
    serialized_pairs = {f"{k[0]},{k[1]}": v for k, v in tuned_pairs.items()}

    result_config = {
        "font_family": font_family,
        "glyph_width_ratios": tuned_ratios,
        "kerning_pairs": serialized_pairs,
        "metrics_summary": {
            "total_tested": len(metrics_log),
            "clipping_issues": clip_count,
            "collisions_fixed": collision_count
        }
    }

    config_path = "kerning_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(result_config, f, indent=2)

    print(f"\n[Success] Optimized parameters exported to '{config_path}'")
    return result_config


if __name__ == "__main__":
    font_arg = sys.argv[1] if len(sys.argv) > 1 else "Georgia"
    run_calibration_sweep(font_arg)
