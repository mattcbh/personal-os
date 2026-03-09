#!/usr/bin/env python3
"""
fill_form_pdf.py - Fill known flat-PDF form fields with text, dates, and signatures.

This is intentionally template-driven. It does not try to infer arbitrary form layouts.
"""

import argparse
import json
import os
import sys
from datetime import date

import fitz  # PyMuPDF

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_PATH = os.path.join(SCRIPT_DIR, "form_templates.json")


def load_templates():
    with open(TEMPLATES_PATH) as handle:
        return json.load(handle)


def parse_fields(pairs):
    values = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ValueError(f"Invalid --field value: {pair!r}. Expected key=value.")
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid --field value: {pair!r}. Missing key.")
        values[key] = value
    return values


def identify_template(doc, templates, requested_template=None):
    if requested_template:
        if requested_template not in templates:
            available = ", ".join(sorted(templates))
            raise ValueError(
                f"Unknown template {requested_template!r}. Available: {available}"
            )
        return requested_template, templates[requested_template]

    text = "\n".join(page.get_text("text") for page in doc).lower()
    for template_id, template in templates.items():
        patterns = template.get("match_all", [])
        if all(pattern.lower() in text for pattern in patterns):
            return template_id, template

    available = ", ".join(sorted(templates))
    raise ValueError(
        "Could not identify a form template automatically. "
        f"Pass --template explicitly. Available: {available}"
    )


def resolve_value(field_name, field_spec, values):
    if field_name in values:
        return values[field_name]

    copy_from = field_spec.get("copy_from")
    if copy_from and copy_from in values:
        return values[copy_from]

    if "default" in field_spec:
        default = field_spec["default"]
        if default == "today":
            return date.today().strftime("%-m/%-d/%y")
        return str(default)

    return None


def insert_textbox_fit(page, rect, text, font_size, align):
    font_size = float(font_size)
    rect = fitz.Rect(rect)
    for size in range(int(font_size), 6, -1):
        remaining = page.insert_textbox(
            rect,
            text,
            fontsize=size,
            fontname="helv",
            color=(0, 0, 0),
            align=align,
        )
        if remaining >= 0:
            return size
    raise RuntimeError(f"Text did not fit in {tuple(rect)}: {text!r}")


def apply_field(page, field_spec, value):
    kind = field_spec["kind"]
    rect = field_spec["rect"]

    if kind == "text" or kind == "date":
        used_font_size = insert_textbox_fit(
            page,
            rect,
            value,
            field_spec.get("font_size", 11),
            field_spec.get("align", 0),
        )
        return {
            "kind": kind,
            "rect": [round(v, 1) for v in rect],
            "font_size": used_font_size,
            "value": value,
        }

    if kind == "signature":
        path = os.path.expanduser(value)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Signature image not found: {path}")
        page.insert_image(fitz.Rect(rect), filename=path)
        return {
            "kind": kind,
            "rect": [round(v, 1) for v in rect],
            "value": path,
        }

    raise ValueError(f"Unsupported field kind: {kind}")


def build_report(template_id, filled, missing, skipped):
    return {
        "template": template_id,
        "is_complete": not missing,
        "filled_fields": filled,
        "missing_required_fields": missing,
        "skipped_fields": skipped,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fill a known flat-PDF template with text, dates, and signatures."
    )
    parser.add_argument("input", nargs="?", help="Input PDF path")
    parser.add_argument("output", nargs="?", help="Output PDF path")
    parser.add_argument(
        "--template",
        default=None,
        help="Template ID from form_templates.json. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        help="Repeatable key=value form field input",
    )
    parser.add_argument(
        "--list-templates",
        action="store_true",
        help="Print available template IDs and exit",
    )

    args = parser.parse_args()

    templates = load_templates()
    if args.list_templates:
        print("\n".join(sorted(templates)))
        return

    if not args.input or not args.output:
        parser.error("input and output are required unless --list-templates is used")

    try:
        values = parse_fields(args.field)
        doc = fitz.open(args.input)
        template_id, template = identify_template(doc, templates, args.template)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    filled = {}
    missing = []
    skipped = []

    try:
        for field_name, field_spec in template["fields"].items():
            value = resolve_value(field_name, field_spec, values)
            if value in (None, ""):
                if field_spec.get("required", False):
                    missing.append(field_name)
                else:
                    skipped.append(field_name)
                continue

            page_index = field_spec["page"] - 1
            page = doc[page_index]
            filled[field_name] = apply_field(page, field_spec, value)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    doc.save(args.output)
    doc.close()

    print(json.dumps(build_report(template_id, filled, missing, skipped), indent=2))


if __name__ == "__main__":
    main()
