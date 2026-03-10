#!/usr/bin/env python3
"""
Sync tasks FROM Things 3 TO Obsidian markdown files.
Things is the source of truth - this script pulls tasks and updates markdown.

Usage:
    python sync_from_things.py                    # Sync all lists
    python sync_from_things.py --list today       # Sync only Today list
    python sync_from_things.py --list inbox       # Sync only Inbox
    python sync_from_things.py --list projects    # Sync only Projects
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Base paths
SCRIPT_DIR = Path(__file__).parent
APPLESCRIPT_DIR = SCRIPT_DIR / "applescript"
VAULT_ROOT = SCRIPT_DIR.parent.parent.parent  # Goes up to personal-os
SYNC_DIR = VAULT_ROOT / "things-sync"

# Track tasks globally for smarter change detection
OLD_TASKS = {}  # {things_id: {'name': str, 'lists': set(), ...}}
NEW_TASKS = {}  # {things_id: {'name': str, 'lists': set(), ...}}


def run_applescript(script_name: str) -> str:
    """Run an AppleScript file and return its output."""
    script_path = APPLESCRIPT_DIR / script_name
    result = subprocess.run(
        ["osascript", str(script_path)],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"AppleScript error: {result.stderr}", file=sys.stderr)
        return "{}"
    return result.stdout.strip()


def read_existing_tasks(file_path: Path) -> dict:
    """Read existing tasks from a markdown file and return a dict keyed by Things ID.

    Returns dict: {things_id: {'name': str, 'completed': bool, 'when_date': str}}
    """
    tasks = {}
    if not file_path.exists():
        return tasks

    with open(file_path, 'r') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        # Match task lines: - [ ] or - [x] followed by name and [things:ID]
        match = re.match(r'^- \[([ x])\] (.+?)\s*`\[things:([^\]]+)\]`', line.strip())
        if match:
            completed = match.group(1) == 'x'
            name = match.group(2).strip()
            things_id = match.group(3)

            when_date = ''
            # Check next lines for metadata
            j = i + 1
            while j < len(lines) and lines[j].startswith('  - '):
                if lines[j].strip().startswith('- When:'):
                    when_date = lines[j].strip()[8:].strip()
                j += 1

            tasks[things_id] = {
                'name': name,
                'completed': completed,
                'when_date': when_date
            }
        i += 1

    return tasks


def collect_old_tasks(old_tasks: dict, context: str):
    """Collect existing tasks into the global OLD_TASKS dict."""
    for tid, task in old_tasks.items():
        if tid == 'new':
            continue
        if tid not in OLD_TASKS:
            OLD_TASKS[tid] = {
                'name': task['name'],
                'lists': set(),
                'when_date': task.get('when_date', ''),
                'completed': task.get('completed', False)
            }
        OLD_TASKS[tid]['lists'].add(context)


def collect_new_tasks(new_tasks: list, context: str):
    """Collect incoming tasks into the global NEW_TASKS dict."""
    for task in new_tasks:
        tid = task['id']
        if tid not in NEW_TASKS:
            NEW_TASKS[tid] = {
                'name': task['name'],
                'lists': set(),
                'when_date': task.get('when_date', ''),
                'notes': task.get('notes', ''),
                'completed': task.get('completed', False)
            }
        NEW_TASKS[tid]['lists'].add(context)


def sanitize_filename(name: str) -> str:
    """Convert a name to a safe filename."""
    # Remove or replace unsafe characters
    safe = re.sub(r'[<>:"/\\|?*]', '', name)
    safe = safe.strip()
    # Replace spaces with hyphens for cleaner filenames
    safe = re.sub(r'\s+', '-', safe)
    return safe[:100]  # Limit length


def format_task_markdown(task: dict) -> str:
    """Convert a Things task dict to markdown format."""
    checkbox = "[x]" if task.get("completed") else "[ ]"
    name = task["name"]
    things_id = task["id"]

    lines = [f"- {checkbox} {name} `[things:{things_id}]`\n"]

    # Add due date if present
    if task.get("when_date"):
        lines.append(f"  - When: {task['when_date']}\n")

    # Add notes if present
    if task.get("notes"):
        notes = task["notes"].strip()
        if notes:
            # For multi-line notes, truncate for readability
            notes_oneline = notes.replace('\n', ' ').strip()
            if len(notes_oneline) > 200:
                notes_oneline = notes_oneline[:200] + "..."
            lines.append(f"  - Notes: {notes_oneline}\n")

    # Add tags if present
    if task.get("tags"):
        tag_str = task["tags"]
        if tag_str:
            tags = [f"#{t.strip().replace(' ', '-')}" for t in tag_str.split(',')]
            lines.append(f"  - Tags: {' '.join(tags)}\n")

    # Add project/area context if present (skip for project-specific files)
    if task.get("project"):
        lines.append(f"  - Project: {task['project']}\n")
    elif task.get("area"):
        lines.append(f"  - Area: {task['area']}\n")

    return ''.join(lines)


def write_list_file(list_name: str, tasks: list, output_file: Path, include_context: bool = True):
    """Write a list of tasks to a markdown file.

    Args:
        list_name: Name of the Things list (for header)
        tasks: List of task dicts from Things
        output_file: Path to output markdown file
        include_context: Whether to include project/area in task output
    """
    # Read existing tasks before overwriting
    old_tasks = read_existing_tasks(output_file)
    collect_old_tasks(old_tasks, context=list_name)
    collect_new_tasks(tasks, context=list_name)

    # Skip write if task IDs haven't changed
    old_ids = set(old_tasks.keys())
    new_ids = {t['id'] for t in tasks}
    if old_ids == new_ids:
        return  # No changes, skip writing

    lines = [f"# {list_name}\n\n"]
    lines.append(f"*Last synced: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")

    if not tasks:
        lines.append("*No tasks*\n")
    else:
        for task in tasks:
            task_md = format_task_markdown(task)
            lines.append(task_md)
            lines.append("\n")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        f.writelines(lines)


def write_project_file(project: dict, output_dir: Path):
    """Write a project's tasks to a markdown file."""
    name = project["name"]
    tasks = project.get("tasks", [])
    area = project.get("area", "")

    filename = sanitize_filename(name) + ".md"
    output_file = output_dir / filename

    # Read existing tasks before overwriting
    old_tasks = read_existing_tasks(output_file)
    collect_old_tasks(old_tasks, context=f"Project: {name}")
    collect_new_tasks(tasks, context=f"Project: {name}")

    # Skip write if task IDs haven't changed
    old_ids = set(old_tasks.keys())
    new_ids = {t['id'] for t in tasks}
    if old_ids == new_ids:
        return len(tasks)

    lines = [f"# {name}\n\n"]
    if area:
        lines.append(f"*Area: {area}*\n\n")
    lines.append(f"*Last synced: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")

    if not tasks:
        lines.append("*No tasks*\n")
    else:
        for task in tasks:
            checkbox = "[x]" if task.get("completed") else "[ ]"
            task_lines = [f"- {checkbox} {task['name']} `[things:{task['id']}]`\n"]

            if task.get("when_date"):
                task_lines.append(f"  - When: {task['when_date']}\n")
            if task.get("notes"):
                notes = task["notes"].strip().replace('\n', ' ')
                if len(notes) > 200:
                    notes = notes[:200] + "..."
                if notes:
                    task_lines.append(f"  - Notes: {notes}\n")
            if task.get("tags"):
                tags = [f"#{t.strip().replace(' ', '-')}" for t in task["tags"].split(',')]
                task_lines.append(f"  - Tags: {' '.join(tags)}\n")

            lines.extend(task_lines)
            lines.append("\n")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        f.writelines(lines)

    return len(tasks)


def write_area_file(area: dict, output_dir: Path):
    """Write an area's tasks to a markdown file."""
    name = area["name"]
    tasks = area.get("tasks", [])

    filename = sanitize_filename(name) + ".md"
    output_file = output_dir / filename

    # Read existing tasks before overwriting
    old_tasks = read_existing_tasks(output_file)
    collect_old_tasks(old_tasks, context=f"Area: {name}")
    collect_new_tasks(tasks, context=f"Area: {name}")

    # Skip write if task IDs haven't changed
    old_ids = set(old_tasks.keys())
    new_ids = {t['id'] for t in tasks}
    if old_ids == new_ids:
        return len(tasks)

    lines = [f"# {name}\n\n"]
    lines.append(f"*Last synced: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")

    if not tasks:
        lines.append("*No tasks directly in this area (check projects)*\n")
    else:
        for task in tasks:
            checkbox = "[x]" if task.get("completed") else "[ ]"
            task_lines = [f"- {checkbox} {task['name']} `[things:{task['id']}]`\n"]

            if task.get("when_date"):
                task_lines.append(f"  - When: {task['when_date']}\n")
            if task.get("notes"):
                notes = task["notes"].strip().replace('\n', ' ')
                if len(notes) > 200:
                    notes = notes[:200] + "..."
                if notes:
                    task_lines.append(f"  - Notes: {notes}\n")
            if task.get("tags"):
                tags = [f"#{t.strip().replace(' ', '-')}" for t in task["tags"].split(',')]
                task_lines.append(f"  - Tags: {' '.join(tags)}\n")
            if task.get("project"):
                task_lines.append(f"  - Project: {task['project']}\n")

            lines.extend(task_lines)
            lines.append("\n")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        f.writelines(lines)

    return len(tasks)


def format_task_summary(task: dict) -> str:
    """Format a task for the change summary with date and notes."""
    parts = [f'"{task["name"]}"']

    if task.get('when_date'):
        parts.append(f"(due {task['when_date']})")

    result = ' '.join(parts)

    if task.get('notes'):
        notes = task['notes'].strip().replace('\n', ' ')
        if len(notes) > 80:
            notes = notes[:80] + "..."
        result += f" — {notes}"

    return result


def print_change_summary():
    """Print a compact summary of completed and new tasks."""
    completed = []
    new_tasks = []

    for tid, new_task in NEW_TASKS.items():
        in_new_logbook = 'Logbook' in new_task['lists']
        was_in_old_logbook = tid in OLD_TASKS and 'Logbook' in OLD_TASKS[tid]['lists']

        if in_new_logbook and not was_in_old_logbook:
            completed.append(new_task)
        elif tid not in OLD_TASKS and not in_new_logbook:
            new_tasks.append(new_task)

    if not completed and not new_tasks:
        print("\n📋 No changes")
        return

    print("\n" + "=" * 40)
    if completed:
        print("✅ COMPLETED:")
        for task in completed:
            print(f"  - {format_task_summary(task)}")
    if new_tasks:
        print("🆕 NEW:")
        for task in new_tasks:
            print(f"  - {format_task_summary(task)}")
    print("=" * 40)


def sync_all():
    """Sync all lists from Things."""
    # Clear global tracking dicts
    OLD_TASKS.clear()
    NEW_TASKS.clear()

    print("Syncing from Things...", end=" ", flush=True)
    json_output = run_applescript("read_all.applescript")

    try:
        data = json.loads(json_output)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}", file=sys.stderr)
        return

    # Ensure sync directory exists
    SYNC_DIR.mkdir(parents=True, exist_ok=True)

    # Sync standard lists
    write_list_file("Today", data.get("today", []), SYNC_DIR / "today.md")
    write_list_file("Inbox", data.get("inbox", []), SYNC_DIR / "inbox.md")
    write_list_file("Anytime", data.get("anytime", []), SYNC_DIR / "anytime.md")
    write_list_file("Someday", data.get("someday", []), SYNC_DIR / "someday.md")
    write_list_file("Upcoming", data.get("upcoming", []), SYNC_DIR / "upcoming.md")
    write_list_file("Logbook", data.get("logbook", []), SYNC_DIR / "logbook.md")

    # Sync projects
    projects = data.get("projects", [])
    projects_dir = SYNC_DIR / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    for proj in projects:
        write_project_file(proj, projects_dir)

    # Sync areas
    areas = data.get("areas", [])
    areas_dir = SYNC_DIR / "areas"
    areas_dir.mkdir(parents=True, exist_ok=True)
    for area in areas:
        write_area_file(area, areas_dir)

    print("done.")
    print_change_summary()


def sync_single_list(list_name: str):
    """Sync a single list (uses read_today.applescript for now)."""
    # Clear global tracking dicts
    OLD_TASKS.clear()
    NEW_TASKS.clear()

    if list_name == "today":
        json_output = run_applescript("read_today.applescript")
        try:
            tasks = json.loads(json_output)
        except json.JSONDecodeError:
            tasks = []
        write_list_file("Today", tasks, SYNC_DIR / "today.md")
        print_change_summary()
    else:
        # For other lists, use the full sync but only write the requested list
        sync_all()


def main():
    """Main entry point."""
    # Ensure sync directory exists
    SYNC_DIR.mkdir(parents=True, exist_ok=True)

    # Parse arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list" and len(sys.argv) > 2:
            list_name = sys.argv[2].lower()
            sync_single_list(list_name)
        elif sys.argv[1] in ["-h", "--help"]:
            print(__doc__)
            return
        else:
            print(__doc__)
            return
    else:
        # Sync everything
        sync_all()

    print("\nSync complete!")


if __name__ == "__main__":
    main()
