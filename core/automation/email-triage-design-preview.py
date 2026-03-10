#!/usr/bin/env python3
"""
Generate a local visual preview for inbox triage email styling.
No Gmail calls, no drafts, no side effects beyond writing preview files.
"""

from __future__ import annotations

import argparse
from pathlib import Path


HTML_TEMPLATE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Inbox Triage Preview</title>
</head>
<body style="margin:0;padding:24px;background:#ffffff;color:#1a1a1a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;line-height:1.45;">
  <div style="max-width:860px;margin:0 auto;">
    <p style="font-size:42px;font-weight:800;margin:0 0 10px 0;">Inbox Triage — Saturday February 28, 6:00 AM (47 new)</p>
    <p style="font-size:17px;color:#4b5563;margin:0 0 24px 0;">1 already addressed · 3 action needed · 1 monitoring · 10 FYI · 10 newsletters · 7 spam</p>

    <p style="display:block;width:100%;border-bottom:2px solid #111;padding-bottom:4px;margin-top:24px;margin-bottom:12px;font-size:31px;font-weight:800;color:#222;">Already Addressed (1)</p>
    <p style="font-size:18px;font-weight:700;margin:14px 0 6px 0;color:#4b5563;">Work</p>
    <p style="margin:0 0 14px 0;background:#eef3ee;border-left:4px solid #4b8a5a;padding:14px 16px;font-size:32px;">
      <b>Oberlin</b> RE: Visiting — Matt replied: "That would be great. Thank you so much!" —
      <a href="#" style="color:#2f6fa3;text-decoration:none;">View</a>
    </p>

    <p style="display:block;width:100%;border-bottom:2px solid #111;padding-bottom:4px;margin-top:24px;margin-bottom:12px;font-size:31px;font-weight:800;color:#111;">Action Needed (3)</p>
    <p style="font-size:18px;font-weight:700;margin:14px 0 6px 0;color:#4b5563;">Work</p>
    <p style="margin:0 0 12px 0;background:#f7f7f7;border-left:4px solid #5f6368;padding:14px 16px;font-size:32px;color:#111;">
      <b>Oberlin</b> RE: Visiting — Evan sent booking link for March 6, 7:30 PM.<br>
      Suggest: Open the Tock email and enter credit card info today.<br>
      <i>No draft — requires clicking Tock link and entering payment info.</i><br>
      <a href="#" style="color:#2f6fa3;text-decoration:none;">View thread</a>
    </p>
    <p style="margin:0 0 14px 0;background:#f7f7f7;border-left:4px solid #5f6368;padding:14px 16px;font-size:32px;color:#111;">
      <b>Caroline Chang</b> (Berkeley Carroll) — Permission slip due Monday.<br>
      Suggest: Sign and send today.<br>
      <i>No draft — physical signature required.</i><br>
      <a href="#" style="color:#2f6fa3;text-decoration:none;">View thread</a>
    </p>

    <p style="display:block;width:100%;border-bottom:2px solid #111;padding-bottom:4px;margin-top:24px;margin-bottom:12px;font-size:31px;font-weight:800;color:#bb5a00;">Monitoring (1)</p>
    <p style="font-size:18px;font-weight:700;margin:14px 0 6px 0;color:#4b5563;">Work</p>
    <p style="margin:0 0 14px 0;background:#f6f0de;border-left:4px solid #c78d2d;padding:14px 16px;font-size:32px;">
      <b>Darragh O'Sullivan</b> (OSD) — Ansul system install confirmed March 4 — <a href="#" style="color:#2f6fa3;text-decoration:none;">View</a>
    </p>

    <p style="display:block;width:100%;border-bottom:2px solid #111;padding-bottom:4px;margin-top:24px;margin-bottom:12px;font-size:31px;font-weight:800;color:#1f5fb8;">FYI (2)</p>
    <p style="font-size:18px;font-weight:700;margin:14px 0 6px 0;color:#4b5563;">Work</p>
    <p style="margin:0 0 8px 0;font-size:32px;"><b>Sarah Sanneh</b> — Press release thread update — <a href="#" style="color:#2f6fa3;text-decoration:none;">View</a></p>
    <p style="font-size:18px;font-weight:700;margin:14px 0 6px 0;color:#4b5563;">Personal</p>
    <p style="margin:0 0 8px 0;font-size:32px;"><b>Miranda</b> — Lesson payment confirmed — <a href="#" style="color:#2f6fa3;text-decoration:none;">View</a></p>

    <p style="display:block;width:100%;border-bottom:2px solid #111;padding-bottom:4px;margin-top:24px;margin-bottom:12px;font-size:31px;font-weight:800;color:#4b5563;">Newsletters (2)</p>
    <p style="font-size:18px;font-weight:700;margin:14px 0 6px 0;color:#4b5563;">Personal</p>
    <p style="margin:0 0 8px 0;font-size:30px;"><b>Figma</b> — New comments on PnT mockups — <a href="#" style="color:#2f6fa3;text-decoration:none;">View</a> · <a href="#" style="color:#2f6fa3;text-decoration:none;">Unsubscribe</a></p>

    <p style="display:block;width:100%;border-bottom:2px solid #111;padding-bottom:4px;margin-top:24px;margin-bottom:12px;font-size:31px;font-weight:800;color:#6b7280;">Spam / Marketing (1)</p>
    <p style="font-size:18px;font-weight:700;margin:14px 0 6px 0;color:#4b5563;">Personal</p>
    <p style="margin:0 0 8px 0;font-size:30px;"><b>SkiEssentials</b> — Weekend sale — <a href="#" style="color:#2f6fa3;text-decoration:none;">View</a> · <a href="#" style="color:#2f6fa3;text-decoration:none;">Unsubscribe</a></p>
  </div>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate triage email visual preview")
    parser.add_argument(
        "--output",
        default="/Users/matthewlieber/Obsidian/personal-os/logs/email-triage-design-preview.html",
        help="Output HTML file path",
    )
    args = parser.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(HTML_TEMPLATE, encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
