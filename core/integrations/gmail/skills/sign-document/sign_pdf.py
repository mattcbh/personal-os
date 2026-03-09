#!/usr/bin/env python3
"""
sign_pdf.py — Overlay a signature image onto a PDF.

Usage:
    # Auto-detect signature location (searches for "Signature", "Sign here", etc.)
    python3 sign_pdf.py input.pdf output.pdf

    # Place on specific page (1-indexed, default: last page)
    python3 sign_pdf.py input.pdf output.pdf --page 2

    # Explicit coordinates (x, y, width, height in points)
    python3 sign_pdf.py input.pdf output.pdf --coords 300,600,200,60

    # Search for specific text and place signature near it
    python3 sign_pdf.py input.pdf output.pdf --search "Authorized by"

    # Save placement as a template for reuse
    python3 sign_pdf.py input.pdf output.pdf --save-template "darragh-quote"

    # Reuse a saved template
    python3 sign_pdf.py input.pdf output.pdf --template "darragh-quote"
"""

import argparse
import json
import os
import sys
from datetime import date

import fitz  # PyMuPDF

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SIGNATURE_PATH = os.path.join(
    os.path.expanduser("~"),
    "Obsidian/personal-os/core/assets/signature.png",
)
TEMPLATES_PATH = os.path.join(SCRIPT_DIR, "templates.json")

# Common signature markers to search for
SIGNATURE_MARKERS = [
    "signature",
    "sign here",
    "authorized by",
    "authorized signature",
    "signed by",
    "approved by",
    "x___",
    "x ___",
    "____",
]

# Default signature dimensions (points). Aspect ratio preserved from the PNG.
DEFAULT_SIG_WIDTH = 180
DEFAULT_SIG_HEIGHT = 54  # ~3.3:1 ratio matching the 714x149 image


def load_templates():
    if os.path.exists(TEMPLATES_PATH):
        with open(TEMPLATES_PATH) as f:
            return json.load(f)
    return {}


def save_templates(templates):
    with open(TEMPLATES_PATH, "w") as f:
        json.dump(templates, f, indent=2)


def find_signature_marker(page):
    """Search a page for common signature markers. Returns (x, y) or None."""
    text_dict = page.get_text("dict")
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            line_spans = line.get("spans", [])
            for i, span in enumerate(line_spans):
                text_lower = span["text"].strip().lower()
                for marker in SIGNATURE_MARKERS:
                    if marker in text_lower:
                        bbox = span["bbox"]  # (x0, y0, x1, y1)

                        # Check if this span or the next contains underscores
                        # (signature line). If so, place on the underline.
                        has_underline = "___" in span["text"]
                        next_underline_bbox = None
                        if not has_underline and i + 1 < len(line_spans):
                            next_span = line_spans[i + 1]
                            if "___" in next_span["text"]:
                                has_underline = True
                                next_underline_bbox = next_span["bbox"]

                        if has_underline:
                            # Place centered on the underline portion
                            if next_underline_bbox:
                                ul_bbox = next_underline_bbox
                            else:
                                ul_bbox = bbox
                            center_x = (ul_bbox[0] + ul_bbox[2]) / 2
                            sig_x = center_x - DEFAULT_SIG_WIDTH / 2
                            sig_y = ul_bbox[1] - DEFAULT_SIG_HEIGHT + 10
                            return (max(sig_x, ul_bbox[0]), sig_y)

                        # No underline — place to the right or below
                        page_width = page.rect.width
                        marker_right = bbox[2]
                        marker_bottom = bbox[3]

                        if marker_right + DEFAULT_SIG_WIDTH + 20 < page_width:
                            return (marker_right + 10, bbox[1] - 5)
                        else:
                            return (bbox[0], marker_bottom + 5)
    return None


def find_underline_region(page):
    """Look for a long underline (______) which often marks a signature line."""
    text_dict = page.get_text("dict")
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span["text"].strip()
                if len(text) >= 10 and text.replace("_", "") == "":
                    bbox = span["bbox"]
                    # Center the signature on the underline
                    line_center_x = (bbox[0] + bbox[2]) / 2
                    sig_x = line_center_x - DEFAULT_SIG_WIDTH / 2
                    sig_y = bbox[1] - DEFAULT_SIG_HEIGHT + 10  # Sit on the line
                    return (max(sig_x, bbox[0]), sig_y)
    return None


def default_placement(page):
    """Fallback: bottom-right area of the page, above any footer."""
    pw = page.rect.width
    ph = page.rect.height
    x = pw - DEFAULT_SIG_WIDTH - 60
    y = ph - DEFAULT_SIG_HEIGHT - 80
    return (x, y)


def stamp_date(page, sig_x, sig_y, date_text=None, date_coords=None):
    """Add today's date near the signature on the same page.

    Auto-detection: finds the 'Date:' label closest to the signature's
    x-position and writes the date right after it on the underline.
    """
    if date_text is None:
        date_text = date.today().strftime("%-m/%-d/%y")

    if date_coords:
        x, y = date_coords
    else:
        # Find all "Date:" instances on this page
        instances = page.search_for("Date:")
        if not instances:
            print("Warning: No 'Date:' field found on page. Skipping date stamp.",
                  file=sys.stderr)
            return None

        # Pick the instance closest to the signature's x-position
        best = None
        best_dist = float("inf")
        for rect in instances:
            dist = abs(rect.x0 - sig_x)
            if dist < best_dist:
                best_dist = dist
                best = rect
        # Place date text just after the "Date:" label
        x = best.x1 + 4
        y = best.y1 - 2  # align baseline

    page.insert_text(
        (x, y),
        date_text,
        fontsize=11,
        fontname="helv",
        color=(0, 0, 0),
    )
    print(f"Date stamped: '{date_text}' at ({round(x,1)}, {round(y,1)})",
          file=sys.stderr)
    return {"date_text": date_text, "x": round(x, 1), "y": round(y, 1)}


def place_signature(input_path, output_path, page_num=None, coords=None,
                    search_text=None, template_name=None, save_template=None,
                    signature_path=None, add_date=False, date_coords=None):
    """
    Overlay signature onto a PDF.

    Returns a dict with placement info (page, x, y, width, height).
    """
    sig_path = signature_path or SIGNATURE_PATH
    if not os.path.exists(sig_path):
        print(f"Error: Signature image not found at {sig_path}", file=sys.stderr)
        sys.exit(1)

    doc = fitz.open(input_path)

    # Load template if requested
    if template_name:
        templates = load_templates()
        if template_name not in templates:
            print(f"Error: Template '{template_name}' not found. "
                  f"Available: {list(templates.keys())}", file=sys.stderr)
            sys.exit(1)
        t = templates[template_name]
        page_num = t["page"]
        coords = (t["x"], t["y"], t["width"], t["height"])

    # Determine which page (1-indexed input, 0-indexed internal)
    if page_num is not None:
        page_idx = page_num - 1
    else:
        page_idx = len(doc) - 1  # Default to last page

    if page_idx < 0 or page_idx >= len(doc):
        print(f"Error: Page {page_num} out of range (document has {len(doc)} pages)",
              file=sys.stderr)
        sys.exit(1)

    page = doc[page_idx]

    # Determine placement
    if coords:
        if len(coords) == 4:
            x, y, w, h = coords
        elif len(coords) == 2:
            x, y = coords
            w, h = DEFAULT_SIG_WIDTH, DEFAULT_SIG_HEIGHT
        else:
            print("Error: --coords must be x,y or x,y,width,height", file=sys.stderr)
            sys.exit(1)
    elif search_text:
        # Search for specific text
        text_instances = page.search_for(search_text)
        if text_instances:
            bbox = text_instances[0]
            page_width = page.rect.width
            if bbox.x1 + DEFAULT_SIG_WIDTH + 20 < page_width:
                x, y = bbox.x1 + 10, bbox.y0 - 5
            else:
                x, y = bbox.x0, bbox.y1 + 5
        else:
            print(f"Warning: Text '{search_text}' not found on page {page_idx + 1}. "
                  f"Using default placement.", file=sys.stderr)
            x, y = default_placement(page)
        w, h = DEFAULT_SIG_WIDTH, DEFAULT_SIG_HEIGHT
    else:
        # Auto-detect: try underlines first (best placement — on the line),
        # then text markers, then default bottom-right
        pos = find_underline_region(page)
        if pos:
            x, y = pos
            print(f"Found signature line on page {page_idx + 1}", file=sys.stderr)
        else:
            pos = find_signature_marker(page)
            if pos:
                x, y = pos
                print(f"Found signature marker on page {page_idx + 1}", file=sys.stderr)
            else:
                x, y = default_placement(page)
                print(f"No marker found. Using default placement (bottom-right of page "
                      f"{page_idx + 1})", file=sys.stderr)
        w, h = DEFAULT_SIG_WIDTH, DEFAULT_SIG_HEIGHT

    # Insert the signature image
    sig_rect = fitz.Rect(x, y, x + w, y + h)
    page.insert_image(sig_rect, filename=sig_path)

    # Stamp the date if requested
    date_info = None
    if add_date:
        date_info = stamp_date(page, x, y, date_coords=date_coords)

    # Save output
    doc.save(output_path)
    doc.close()

    placement = {
        "page": page_idx + 1,
        "x": round(x, 1),
        "y": round(y, 1),
        "width": round(w, 1),
        "height": round(h, 1),
    }
    if date_info:
        placement["date"] = date_info

    # Save template if requested
    if save_template:
        templates = load_templates()
        templates[save_template] = placement
        save_templates(templates)
        print(f"Saved template '{save_template}'", file=sys.stderr)

    print(json.dumps(placement))
    return placement


def _override_dimensions(width=None, height=None):
    global DEFAULT_SIG_WIDTH, DEFAULT_SIG_HEIGHT
    if width is not None:
        DEFAULT_SIG_WIDTH = width
    if height is not None:
        DEFAULT_SIG_HEIGHT = height


def main():
    parser = argparse.ArgumentParser(description="Overlay signature on a PDF")
    parser.add_argument("input", help="Input PDF path")
    parser.add_argument("output", help="Output PDF path")
    parser.add_argument("--page", type=int, default=None,
                        help="Page number (1-indexed). Default: last page")
    parser.add_argument("--coords", type=str, default=None,
                        help="Coordinates: x,y or x,y,width,height (in points)")
    parser.add_argument("--search", type=str, default=None,
                        help="Search for text and place signature near it")
    parser.add_argument("--template", type=str, default=None,
                        help="Use a saved placement template")
    parser.add_argument("--save-template", type=str, default=None,
                        help="Save this placement as a named template")
    parser.add_argument("--signature", type=str, default=None,
                        help="Path to signature image (default: core/assets/signature.png)")
    parser.add_argument("--width", type=float, default=None,
                        help=f"Signature width in points (default: {DEFAULT_SIG_WIDTH})")
    parser.add_argument("--height", type=float, default=None,
                        help=f"Signature height in points (default: {DEFAULT_SIG_HEIGHT})")
    parser.add_argument("--add-date", action="store_true",
                        help="Stamp today's date near the signature (auto-detects 'Date:' field)")
    parser.add_argument("--date-coords", type=str, default=None,
                        help="Explicit date coordinates: x,y (in points)")

    args = parser.parse_args()

    # Override default dimensions if specified
    if args.width:
        _override_dimensions(width=args.width)
    if args.height:
        _override_dimensions(height=args.height)

    coords = None
    if args.coords:
        coords = [float(c) for c in args.coords.split(",")]

    date_coords = None
    if args.date_coords:
        date_coords = [float(c) for c in args.date_coords.split(",")]

    place_signature(
        input_path=args.input,
        output_path=args.output,
        page_num=args.page,
        coords=coords,
        search_text=args.search,
        template_name=args.template,
        save_template=args.save_template,
        signature_path=args.signature,
        add_date=args.add_date,
        date_coords=date_coords,
    )


if __name__ == "__main__":
    main()
