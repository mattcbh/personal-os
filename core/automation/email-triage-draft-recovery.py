#!/usr/bin/env python3
"""
Recover missing reply drafts for Action Needed triage records.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


REPLY_HINT_RE = re.compile(r"\b(reply|respond|confirmation|confirm|email|send)\b", re.IGNORECASE)


def normalize_bucket(raw: str) -> str:
    s = (raw or "").strip().lower().replace("_", " ")
    if s == "action needed":
        return "action needed"
    return s


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def extract_json_payload(text: str) -> Any:
    text = text.strip()
    if not text:
        return None

    # Try direct parse first.
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try fenced json blocks.
    for pattern in (r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```"):
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if m:
            block = m.group(1).strip()
            try:
                return json.loads(block)
            except Exception:
                continue

    # Fallback: parse first object/array span.
    start_obj = text.find("{")
    start_arr = text.find("[")
    starts = [p for p in (start_obj, start_arr) if p >= 0]
    if not starts:
        return None
    start = min(starts)
    for end in range(len(text), start, -1):
        chunk = text[start:end].strip()
        try:
            return json.loads(chunk)
        except Exception:
            continue
    return None


def fallback_draft_text(summary: str, suggested_action: str) -> str:
    summary = clean_text(summary)
    action = clean_text(suggested_action).rstrip(".")
    lower = action.lower()
    reply_payload = action
    if lower.startswith("reply with "):
        reply_payload = action[11:]
    elif lower.startswith("reply to ") and " with " in lower:
        reply_payload = action[lower.find(" with ") + 6 :]
    elif lower.startswith("respond with "):
        reply_payload = action[13:]
    elif lower.startswith("confirm "):
        reply_payload = action

    lines: list[str] = []
    lines.append("Thanks for the note.")
    if summary:
        lines.append("")
        lines.append(summary)
    if reply_payload:
        lines.append("")
        lines.append(reply_payload[:280].rstrip(".") + ".")
    lines.append("")
    lines.append("Best,")
    lines.append("Matt")
    return "\n".join(lines)


def account_email(account: str) -> str:
    if account.strip().lower() == "personal":
        return "lieber.matt@gmail.com"
    return "matt@cornerboothholdings.com"


def load_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"threads": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"threads": {}}
    if not isinstance(data, dict):
        return {"threads": {}}
    if not isinstance(data.get("threads"), dict):
        data["threads"] = {}
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover missing Action Needed drafts")
    parser.add_argument("--records", required=True, help="Path to records JSON")
    parser.add_argument("--claude", required=True, help="Path to claude CLI")
    parser.add_argument("--draft-script", required=True, help="Path to superhuman-draft.sh")
    parser.add_argument("--model", default="haiku", help="Model for draft text generation")
    parser.add_argument("--max-items", type=int, default=8, help="Max draft candidates to recover")
    parser.add_argument("--mode", choices=("direct", "queue"), default="direct", help="Draft execution mode")
    parser.add_argument(
        "--status-file",
        default="/Users/homeserver/Obsidian/personal-os/core/state/superhuman-draft-status.json",
        help="Path to superhuman draft status file",
    )
    args = parser.parse_args()

    records_path = Path(args.records)
    records = json.loads(records_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise SystemExit("records file must be a JSON array")

    candidates: list[dict[str, Any]] = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        bucket = normalize_bucket(str(rec.get("bucket") or ""))
        if bucket != "action needed":
            continue
        draft_status = clean_text(rec.get("draft_status")).lower() or "none"
        if draft_status in {"queued", "clipboard", "failed"}:
            continue
        thread_id = clean_text(rec.get("threadId"))
        if not thread_id:
            continue
        suggested_action = clean_text(rec.get("suggested_action"))
        if not suggested_action:
            continue
        if not REPLY_HINT_RE.search(suggested_action):
            continue
        summary = ""
        for field in ("summary_latest", "summary", "summary_brief", "body_preview", "snippet"):
            val = clean_text(rec.get(field))
            if val:
                summary = val
                break
        candidates.append(
            {
                "idx": i,
                "threadId": thread_id,
                "account": clean_text(rec.get("account") or "work").lower() or "work",
                "sender_email": clean_text(rec.get("sender_email")),
                "subject_latest": clean_text(rec.get("subject_latest")),
                "summary_latest": summary,
                "suggested_action": suggested_action,
            }
        )

    if not candidates:
        print("DRAFT_RECOVERY no eligible action-needed reply candidates")
        return 0

    candidates = candidates[: max(args.max_items, 0)]
    prompt_payload = [
        {
            "threadId": c["threadId"],
            "subject_latest": c["subject_latest"],
            "sender_email": c["sender_email"],
            "summary_latest": c["summary_latest"],
            "suggested_action": c["suggested_action"],
        }
        for c in candidates
    ]
    prompt = (
        "Generate concise email reply drafts.\n"
        "Return ONLY valid JSON object keyed by threadId.\n"
        "Each value must be plain text draft body, max 120 words, no markdown.\n"
        "Do not include subject lines.\n\n"
        f"INPUT:\n{json.dumps(prompt_payload, ensure_ascii=True, indent=2)}\n"
    )
    cmd = [
        args.claude,
        "-p",
        prompt,
        "--model",
        args.model,
        "--permission-mode",
        "bypassPermissions",
        "--system-prompt",
        "You write short practical business email replies. Output JSON only.",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--tools",
        "Read,Write,Edit,Bash,Glob,Grep",
    ]

    generated_map: dict[str, str] = {}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        raw = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        parsed = extract_json_payload(raw)
        if isinstance(parsed, dict):
            for key, val in parsed.items():
                k = clean_text(key)
                v = clean_text(val)
                if k and v:
                    generated_map[k] = v
    except Exception:
        generated_map = {}

    queued = 0
    clipboard = 0
    failed = 0

    for c in candidates:
        thread_id = c["threadId"]
        draft_text = clean_text(generated_map.get(thread_id))
        if not draft_text:
            draft_text = fallback_draft_text(c["summary_latest"], c["suggested_action"])
        account = account_email(c["account"])

        cmd = [args.draft_script]
        if args.mode == "queue":
            cmd.append("--queue")
        cmd.extend([thread_id, draft_text, account])
        run = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=140, check=False)

        status = "failed"
        if run.returncode == 0 and args.mode == "queue":
            status = "queued"
            queued += 1
        elif run.returncode == 0:
            state = load_status(Path(args.status_file))
            key = f"{account}:{thread_id}"
            state_status = clean_text(state.get("threads", {}).get(key, {}).get("status")).lower()
            if state_status in {"queued", "clipboard", "failed"}:
                status = state_status
            else:
                status = "queued"
            if status == "queued":
                queued += 1
            elif status == "clipboard":
                clipboard += 1
            else:
                failed += 1
        else:
            failed += 1

        records[c["idx"]]["draft_status"] = status

    records_path.write_text(json.dumps(records, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        f"DRAFT_RECOVERY mode={args.mode} candidates={len(candidates)} queued={queued} clipboard={clipboard} "
        f"failed={failed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
