#!/usr/bin/env python3
"""
Sync tasks TO Things 3 FROM Obsidian markdown files.
Handles:
- Ensuring projects exist in Things (creates missing ones)
- Creating new tasks (marked with [things:new])
- Marking tasks complete (checked [x] in markdown)

Usage:
    python sync_to_things.py                    # Process all files
    python sync_to_things.py --dry-run          # Show what would be done
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
VAULT_ROOT = SCRIPT_DIR.parent.parent.parent
SYNC_DIR = VAULT_ROOT / "things-sync"


def run_applescript(script_name: str, *args) -> str:
    """Run an AppleScript file with arguments and return its output."""
    script_path = APPLESCRIPT_DIR / script_name
    cmd = ["osascript", str(script_path)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"AppleScript error: {result.stderr}", file=sys.stderr)
        return ""
    return result.stdout.strip()


def parse_task_line(line: str) -> dict | None:
    """Parse a task line and extract its components.

    Returns dict with: completed, name, things_id, or None if not a task line.
    """
    # Match: - [ ] or - [x] followed by task name and optional [things:ID]
    match = re.match(r'^- \[([ x])\] (.+)', line.strip())
    if not match:
        return None

    completed = match.group(1) == 'x'
    rest = match.group(2)

    # Extract Things ID if present
    id_match = re.search(r'`\[things:([^\]]+)\]`', rest)
    if id_match:
        things_id = id_match.group(1)
        name = re.sub(r'\s*`\[things:[^\]]+\]`', '', rest).strip()
    else:
        things_id = None
        name = rest.strip()

    return {
        'completed': completed,
        'name': name,
        'things_id': things_id,
        'original_line': line
    }


def parse_task_metadata(lines: list, start_idx: int) -> dict:
    """Parse metadata lines following a task (due date, notes, tags).

    Returns dict with: when_date, notes, tags
    """
    metadata = {'when_date': '', 'notes': '', 'tags': ''}
    i = start_idx

    while i < len(lines):
        line = lines[i]
        # Check if it's a sub-item (indented with 2 spaces)
        if not line.startswith('  - '):
            break

        content = line.strip()[2:].strip()  # Remove "- " prefix

        if content.startswith('When:'):
            metadata['when_date'] = content[5:].strip()
        elif content.startswith('Notes:'):
            metadata['notes'] = content[6:].strip()
        elif content.startswith('Tags:'):
            metadata['tags'] = content[5:].strip()

        i += 1

    return metadata


def determine_list_from_file(file_path: Path) -> str:
    """Determine which Things list a task should go to based on file path."""
    filename = file_path.stem.lower()
    if filename == 'today':
        return 'today'
    elif filename == 'inbox':
        return 'inbox'
    elif filename == 'anytime':
        return 'anytime'
    elif filename == 'upcoming':
        return 'anytime'  # Upcoming tasks go to Anytime, scheduled by date
    elif filename == 'someday':
        return 'someday'
    return 'inbox'  # Default


def determine_project_from_file(file_path: Path) -> str:
    """Determine project name from file path if in projects/ folder."""
    if 'projects' in file_path.parts:
        # Get the filename without extension, convert hyphens back to spaces
        return file_path.stem.replace('-', ' ')
    return ''


def ensure_project_exists(project_name: str, dry_run: bool = False) -> bool:
    """Ensure a project exists in Things, creating it if necessary.

    Returns True if project exists or was created successfully.
    """
    if dry_run:
        print(f"  [DRY RUN] Would ensure project exists: '{project_name}'")
        return True

    result = run_applescript("create_project.applescript", project_name)

    if result.startswith("exists:"):
        return True
    elif result.startswith("created:"):
        print(f"  Created project: '{project_name}'")
        return True
    else:
        print(f"  ERROR: Failed to ensure project '{project_name}': {result}")
        return False


def sync_projects(dry_run: bool = False):
    """Ensure all project files have corresponding projects in Things."""
    projects_dir = SYNC_DIR / 'projects'
    if not projects_dir.exists():
        return

    for file_path in projects_dir.glob('*.md'):
        project_name = file_path.stem.replace('-', ' ')
        ensure_project_exists(project_name, dry_run)


def create_task_in_things(name: str, notes: str, when_date: str, project: str, list_name: str, dry_run: bool = False) -> str:
    """Create a new task in Things and return its ID."""
    if dry_run:
        print(f"  [DRY RUN] Would create: '{name}' in {project or list_name}")
        return "DRY_RUN_ID"

    things_id = run_applescript(
        "create_todo.applescript",
        name,
        notes,
        when_date,
        project,
        list_name
    )

    if things_id:
        print(f"  Created: '{name}' -> {things_id}")
    else:
        print(f"  ERROR: Failed to create '{name}'")

    return things_id


def complete_task_in_things(things_id: str, name: str, dry_run: bool = False) -> bool:
    """Mark a task as completed in Things."""
    if dry_run:
        print(f"  [DRY RUN] Would complete: '{name}' ({things_id})")
        return True

    result = run_applescript("complete_todo.applescript", things_id)

    if result == "completed":
        print(f"  Completed: '{name}' ({things_id})")
        return True
    else:
        print(f"  ERROR completing '{name}': {result}")
        return False


def process_markdown_file(file_path: Path, dry_run: bool = False) -> list:
    """Process a markdown file for new tasks and completions.

    Returns list of line updates to apply: [(line_num, old_line, new_line), ...]
    """
    updates = []

    with open(file_path, 'r') as f:
        lines = f.readlines()

    list_name = determine_list_from_file(file_path)
    project_name = determine_project_from_file(file_path)

    i = 0
    while i < len(lines):
        line = lines[i]
        task = parse_task_line(line)

        if task:
            metadata = parse_task_metadata(lines, i + 1)

            # Case 1: New task to create
            if task['things_id'] == 'new':
                new_id = create_task_in_things(
                    task['name'],
                    metadata['notes'],
                    metadata['when_date'],
                    project_name,
                    list_name,
                    dry_run
                )

                if new_id and not dry_run:
                    # Update the line with real ID
                    new_line = line.replace('[things:new]', f'[things:{new_id}]')
                    updates.append((i, line, new_line))

            # Case 2: Completed task to sync
            elif task['completed'] and task['things_id'] and task['things_id'] != 'new':
                # Check if it's a real ID (not already completed)
                complete_task_in_things(task['things_id'], task['name'], dry_run)

        i += 1

    return updates


def apply_updates(file_path: Path, updates: list):
    """Apply line updates to a file."""
    if not updates:
        return

    with open(file_path, 'r') as f:
        lines = f.readlines()

    for line_num, old_line, new_line in updates:
        lines[line_num] = new_line

    with open(file_path, 'w') as f:
        f.writelines(lines)


def process_all_files(dry_run: bool = False):
    """Process all markdown files in the sync directory."""
    # First, ensure all projects exist in Things
    sync_projects(dry_run)

    # Process standard list files
    list_files = ['today.md', 'inbox.md', 'anytime.md', 'upcoming.md', 'someday.md']
    for filename in list_files:
        file_path = SYNC_DIR / filename
        if file_path.exists():
            updates = process_markdown_file(file_path, dry_run)
            if not dry_run:
                apply_updates(file_path, updates)

    # Process project files
    projects_dir = SYNC_DIR / 'projects'
    if projects_dir.exists():
        for file_path in projects_dir.glob('*.md'):
            updates = process_markdown_file(file_path, dry_run)
            if not dry_run:
                apply_updates(file_path, updates)

    # Process area files
    areas_dir = SYNC_DIR / 'areas'
    if areas_dir.exists():
        for file_path in areas_dir.glob('*.md'):
            updates = process_markdown_file(file_path, dry_run)
            if not dry_run:
                apply_updates(file_path, updates)


def main():
    """Main entry point."""
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv

    if dry_run:
        print("=== DRY RUN MODE ===\n")

    process_all_files(dry_run)

    if not dry_run:
        print("Push complete.")


if __name__ == "__main__":
    main()
