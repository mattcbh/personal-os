#!/usr/bin/env python3
"""
Things 3 ↔ Obsidian Sync

Syncs tasks between Things 3 (via SQLite database) and Obsidian markdown files.
Things is the source of truth - this script reads from Things and writes to markdown.

Usage:
    python3 things_sync.py [--dry-run] [--list LIST_NAME]

Lists: today, inbox, anytime, upcoming, someday, logbook
"""

import sqlite3
import os
import re
import subprocess
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
import argparse

# Configuration
VAULT_PATH = Path.home() / "Obsidian" / "personal-os"
THINGS_SYNC_DIR = VAULT_PATH / "things-sync"
THINGS_DB_PATTERN = Path.home() / "Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-*/Things Database.thingsdatabase/main.sqlite"

# Things database constants
STATUS_OPEN = 0
STATUS_COMPLETED = 3
STATUS_CANCELLED = 2

START_INBOX = 0
START_TODAY = 1
START_ANYTIME = 2
START_SOMEDAY = 3

# Map start values to list names
START_TO_LIST = {
    START_INBOX: "inbox",
    START_TODAY: "today",
    START_ANYTIME: "anytime",
    START_SOMEDAY: "someday",
}


def find_things_db():
    """Find the Things 3 database file."""
    import glob
    matches = glob.glob(str(THINGS_DB_PATTERN))
    if matches:
        return matches[0]
    raise FileNotFoundError("Things 3 database not found. Is Things installed?")


def get_connection():
    """Get a read-only connection to Things database."""
    db_path = find_things_db()
    # Use URI to open read-only
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def things_date_to_str(date_int):
    """Convert Things date integer to YYYY-MM-DD string.

    Things uses a packed format: year << 16 | month << 12 | day << 7
    """
    if not date_int:
        return None
    year = date_int >> 16
    month = (date_int >> 12) & 0xF
    day = (date_int >> 7) & 0x1F
    if year < 2000 or month < 1 or month > 12 or day < 1 or day > 31:
        return None  # Invalid date
    return f"{year}-{month:02d}-{day:02d}"


def get_tasks_for_list(conn, list_name):
    """Get all open tasks for a given list."""

    if list_name == "today":
        # Today: start=1 (Today) OR has a startDate that is today or earlier
        # Things date format: year << 16 | month << 12 | day << 7
        now = datetime.now()
        today_int = (now.year << 16) | (now.month << 12) | (now.day << 7)
        query = """
            SELECT uuid, title, notes, startDate, project, area
            FROM TMTask
            WHERE status = 0 AND trashed = 0 AND type = 0
            AND (start = 1 OR (startDate IS NOT NULL AND startDate <= ?))
            ORDER BY todayIndex
        """
        return conn.execute(query, (today_int,)).fetchall()

    elif list_name == "inbox":
        query = """
            SELECT uuid, title, notes, startDate, project, area
            FROM TMTask
            WHERE status = 0 AND trashed = 0 AND type = 0 AND start = 0
            ORDER BY creationDate DESC
        """
        return conn.execute(query).fetchall()

    elif list_name == "anytime":
        query = """
            SELECT uuid, title, notes, startDate, project, area
            FROM TMTask
            WHERE status = 0 AND trashed = 0 AND type = 0 AND start = 2
            ORDER BY "index"
        """
        return conn.execute(query).fetchall()

    elif list_name == "someday":
        query = """
            SELECT uuid, title, notes, startDate, project, area
            FROM TMTask
            WHERE status = 0 AND trashed = 0 AND type = 0 AND start = 3
            ORDER BY "index"
        """
        return conn.execute(query).fetchall()

    elif list_name == "upcoming":
        # Tasks with startDate in the future
        now = datetime.now()
        today_int = (now.year << 16) | (now.month << 12) | (now.day << 7)
        query = """
            SELECT uuid, title, notes, startDate, project, area
            FROM TMTask
            WHERE status = 0 AND trashed = 0 AND type = 0
            AND startDate IS NOT NULL AND startDate > ?
            ORDER BY startDate
        """
        return conn.execute(query, (today_int,)).fetchall()

    elif list_name == "logbook":
        # Completed tasks from last 7 days
        query = """
            SELECT uuid, title, notes, startDate, project, area, stopDate
            FROM TMTask
            WHERE status = 3 AND trashed = 0 AND type = 0
            AND stopDate > ?
            ORDER BY stopDate DESC
        """
        week_ago = (datetime.now() - timedelta(days=7)).timestamp()
        # stopDate is a Unix timestamp (seconds since 2001-01-01)
        base_timestamp = datetime(2001, 1, 1).timestamp()
        return conn.execute(query, (week_ago - base_timestamp,)).fetchall()

    else:
        raise ValueError(f"Unknown list: {list_name}")


def get_project_name(conn, project_uuid):
    """Get project name from UUID."""
    if not project_uuid:
        return None
    row = conn.execute(
        "SELECT title FROM TMTask WHERE uuid = ?",
        (project_uuid,)
    ).fetchone()
    return row["title"] if row else None


def format_task_markdown(task, project_name=None, completed=False):
    """Format a task as markdown."""
    checkbox = "[x]" if completed else "[ ]"
    lines = [f"- {checkbox} {task['title']} `[things:{task['uuid']}]`"]

    when_date = things_date_to_str(task["startDate"])
    if when_date:
        lines.append(f"  - When: {when_date}")

    if task["notes"]:
        # Truncate long notes and escape for markdown
        notes = task["notes"][:200].replace("\n", " ")
        if len(task["notes"]) > 200:
            notes += "..."
        lines.append(f"  - Notes: {notes}")

    if project_name:
        lines.append(f"  - Project: {project_name}")

    return "\n".join(lines)


def write_list_file(list_name, tasks, conn, dry_run=False):
    """Write tasks to a markdown file."""
    file_path = THINGS_SYNC_DIR / f"{list_name}.md"

    # Build content
    title = list_name.title()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    is_logbook = list_name == "logbook"

    lines = [f"# {title}", "", f"*Last synced: {timestamp}*", ""]

    for task in tasks:
        project_name = get_project_name(conn, task["project"])
        lines.append(format_task_markdown(task, project_name, completed=is_logbook))
        lines.append("")

    content = "\n".join(lines)

    if dry_run:
        print(f"\n--- {file_path} ---")
        print(content[:500] + "..." if len(content) > 500 else content)
        return

    # Ensure directory exists
    THINGS_SYNC_DIR.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    print(f"Wrote {len(tasks)} tasks to {file_path}")


def parse_markdown_for_new_tasks(file_path):
    """Parse markdown file for tasks marked [things:new], including When and Notes."""
    if not file_path.exists():
        return []

    content = file_path.read_text()
    new_tasks = []

    # Match: - [ ] Task name `[things:new]` followed by optional indented metadata
    # Capture the task line and any following indented lines
    pattern = r"- \[ \] (.+?) `\[things:new\]`((?:\n  - (?:When|Notes): .+)*)"

    for match in re.finditer(pattern, content):
        task_title = match.group(1).strip()
        metadata_block = match.group(2) if match.group(2) else ""

        # Parse When and Notes from metadata block
        when = None
        notes = None

        when_match = re.search(r"- When: (.+)", metadata_block)
        if when_match:
            when = when_match.group(1).strip()

        notes_match = re.search(r"- Notes: (.+)", metadata_block)
        if notes_match:
            notes = notes_match.group(1).strip()

        new_tasks.append({
            "title": task_title,
            "when": when,
            "notes": notes,
            "full_match": match.group(0)
        })

    return new_tasks


def parse_markdown_for_completed_tasks(file_path):
    """Parse markdown file for completed tasks with Things UUIDs."""
    if not file_path.exists():
        return []

    content = file_path.read_text()
    completed_tasks = []

    # Match: - [x] Task name `[things:UUID]` (where UUID is not "new")
    pattern = r"- \[x\] (.+?) `\[things:([A-Za-z0-9-]+)\]`"

    for match in re.finditer(pattern, content):
        task_title = match.group(1).strip()
        things_uuid = match.group(2)
        if things_uuid != "new":
            completed_tasks.append({
                "title": task_title,
                "uuid": things_uuid,
                "full_match": match.group(0)
            })

    return completed_tasks


def is_task_open_in_things(conn, uuid):
    """Check if a task is still open (not completed) in Things."""
    row = conn.execute(
        "SELECT status FROM TMTask WHERE uuid = ?",
        (uuid,)
    ).fetchone()
    if row:
        return row["status"] == STATUS_OPEN
    return False


def complete_task_in_things(uuid, dry_run=False):
    """Complete a task in Things using URL scheme."""
    if dry_run:
        return True

    url = f"things:///update?id={uuid}&completed=true"
    result = subprocess.run(["open", url], check=False)
    return result.returncode == 0


def create_task_in_things(title, notes=None, when=None, list_name=None):
    """Create a task in Things using URL scheme."""
    params = {"title": title}

    if notes:
        params["notes"] = notes
    if when:
        params["when"] = when
    if list_name:
        params["list"] = list_name

    # Use quote_via to encode spaces as %20 instead of + (Things doesn't decode + properly)
    url = "things:///add?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    subprocess.run(["open", url], check=True)
    print(f"Created task: {title}")


def sync_all(dry_run=False, list_filter=None):
    """Sync all lists from Things to markdown."""
    lists = ["today", "inbox", "anytime", "upcoming", "someday", "logbook"]

    if list_filter:
        lists = [list_filter]

    conn = get_connection()

    try:
        for list_name in lists:
            tasks = get_tasks_for_list(conn, list_name)
            write_list_file(list_name, tasks, conn, dry_run)
    finally:
        conn.close()


def push_new_tasks(dry_run=False):
    """Find [things:new] tasks in markdown and create them in Things."""
    files = list(THINGS_SYNC_DIR.glob("*.md"))
    # Also check projects and areas subdirectories
    files.extend(THINGS_SYNC_DIR.glob("projects/*.md"))
    files.extend(THINGS_SYNC_DIR.glob("areas/*.md"))

    for file_path in files:
        new_tasks = parse_markdown_for_new_tasks(file_path)

        for task in new_tasks:
            if dry_run:
                print(f"Would create: {task['title']} (when={task.get('when')}, notes={task.get('notes')})")
            else:
                create_task_in_things(
                    task["title"],
                    notes=task.get("notes"),
                    when=task.get("when")
                )


def push_completions(dry_run=False):
    """Find completed tasks in markdown and complete them in Things."""
    files = list(THINGS_SYNC_DIR.glob("*.md"))
    # Also check projects and areas subdirectories
    files.extend(THINGS_SYNC_DIR.glob("projects/*.md"))
    files.extend(THINGS_SYNC_DIR.glob("areas/*.md"))

    conn = get_connection()
    completed_count = 0

    try:
        for file_path in files:
            completed_tasks = parse_markdown_for_completed_tasks(file_path)

            for task in completed_tasks:
                # Only complete if task is still open in Things
                if is_task_open_in_things(conn, task["uuid"]):
                    if dry_run:
                        print(f"Would complete: {task['title']}")
                    else:
                        if complete_task_in_things(task["uuid"]):
                            print(f"Completed: {task['title']}")
                            completed_count += 1
    finally:
        conn.close()

    return completed_count


def main():
    parser = argparse.ArgumentParser(description="Sync Things 3 with Obsidian")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--list", dest="list_name", help="Sync only this list")
    parser.add_argument("--push", action="store_true", help="Push new tasks and completions to Things")

    args = parser.parse_args()

    if args.push:
        push_new_tasks(args.dry_run)
        push_completions(args.dry_run)
    else:
        sync_all(args.dry_run, args.list_name)


if __name__ == "__main__":
    main()
