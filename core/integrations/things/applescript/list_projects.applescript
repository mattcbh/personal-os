-- List all project names in Things 3
-- Usage: osascript list_projects.applescript
-- Returns: newline-separated list of project names

tell application "Things3"
    set projectNames to {}
    repeat with p in projects
        set end of projectNames to name of p
    end repeat

    set AppleScript's text item delimiters to linefeed
    return projectNames as text
end tell
